"""5_3: immutable-at-write ranked research cohorts and censored precision@K.

Ranking inputs must precede the decision snapshot; future outcome labels are
read ONLY by evaluation. A local hash is integrity evidence, not external
timestamp notarization or proof of independently observed leader outcomes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from statistics import median
from zoneinfo import ZoneInfo

SCHEMA = "eraleader.ranked_snapshot.v1"
ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
INPUT_KEYS = {"security_id", "score", "features_available_at", "score_computed_at", "recorded_at"}
STATUS = "RESEARCH_RANKED_PRECISION_AT_K_NOT_CERTIFIED"


def _time(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("Timestamp must be an offset-aware ISO string")
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Timestamp must include a UTC offset")
    return ts.astimezone(timezone.utc)


def _now(clock: datetime | None) -> datetime:
    ts = clock if clock is not None else datetime.now(timezone.utc)
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("Audit clock needs an offset")
    return ts.astimezone(timezone.utc)


def _read(path: Path) -> object:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("Missing, linked or oversized research input")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed research JSON") from exc


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(obj: dict) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _save_new(path: Path, obj: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(obj, file, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        file.write("\n")


def _validate_ranked(records: object, snapshot: datetime) -> list[dict]:
    if not isinstance(records, list) or not records:
        raise ValueError("At least one ranked candidate is required")
    seen: set[str] = set()
    rows = []
    for row in records:
        if not isinstance(row, dict) or set(row) != INPUT_KEYS:
            raise ValueError("Ranking fields invalid: future outcomes and labels prohibited")
        sid = row["security_id"]
        score = row["score"]
        if not isinstance(sid, str) or not sid.strip() or sid in seen:
            raise ValueError("Missing or duplicated permanent security ID")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("Invalid finite 0..100 research score")
        seen.add(sid)
        available = _time(row["features_available_at"])
        calculated = _time(row["score_computed_at"])
        registered = _time(row["recorded_at"])
        if not available <= calculated <= registered <= snapshot:
            raise ValueError("Future feature, score, or registration leaked into ranked snapshot")
        rows.append({
            "security_id": sid, "score": float(score),
            "features_available_at_utc": available.isoformat(),
            "score_computed_at_utc": calculated.isoformat(),
            "recorded_at_utc": registered.isoformat(),
        })
    rows.sort(key=lambda row: (-row["score"], row["security_id"]))
    return [dict(row, rank=i) for i, row in enumerate(rows, 1)]


def freeze_ranked_snapshot(
    input_file: Path, output_file: Path, *, market: str, snapshot_at: str,
    model_version: str, horizon_days: int, k: int, clock: datetime | None = None,
) -> dict:
    """Seal rank ORDER before outcome labels exist; O_EXCL never overwrites it."""
    if market not in ZONES:
        raise ValueError("Only KR/US supported")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned model_version required")
    if type(k) is not int or k < 1 or k > 1000:
        raise ValueError("k must be within 1..1000")
    if type(horizon_days) is not int or not 1 <= horizon_days <= 1095:
        raise ValueError("Invalid prospective outcome horizon")
    snapshot = _time(snapshot_at)
    frozen = _now(clock)
    if snapshot > frozen:
        raise ValueError("Cannot seal a future snapshot")
    ranked = _validate_ranked(_read(input_file), snapshot)
    result = {
        "schema_version": SCHEMA, "market": market,
        "model_version": model_version, "horizon_days": horizon_days,
        "requested_k": k, "snapshot_at_utc": snapshot.isoformat(),
        "frozen_at_utc": frozen.isoformat(), "ranked_candidates": ranked,
        "retrospective_freeze": (frozen - snapshot) > timedelta(minutes=60),
        "source_pit_independently_authenticated": False,
        "timestamp_independently_attested": False,
        "real_leader_prediction_certified": False,
    }
    result["content_sha256"] = _digest(result)
    _save_new(output_file, result)
    return result


def _frozen(path: Path) -> dict:
    obj = _read(path)
    if not isinstance(obj, dict):
        raise ValueError("Frozen snapshot must be JSON object")
    digest = obj.get("content_sha256")
    if not isinstance(digest, str) or _digest({k: v for k, v in obj.items() if k != "content_sha256"}) != digest:
        raise ValueError("Frozen ranking SHA256 mismatch")
    if obj.get("schema_version") != SCHEMA or obj.get("market") not in ZONES:
        raise ValueError("Wrong ranked snapshot schema or market")
    if obj.get("source_pit_independently_authenticated") is not False or obj.get("real_leader_prediction_certified") is not False:
        raise ValueError("Ranked research claims independent certification")
    snapshot = _time(obj["snapshot_at_utc"])
    seal = _time(obj["frozen_at_utc"])
    if snapshot > seal:
        raise ValueError("Ranking sealed before the snapshot happened")
    if type(obj.get("requested_k")) is not int or not 1 <= obj["requested_k"] <= 1000:
        raise ValueError("Invalid pinned K")
    if type(obj.get("horizon_days")) is not int or not 1 <= obj["horizon_days"] <= 1095:
        raise ValueError("Invalid pinned horizon")
    candidates = obj["ranked_candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("No frozen rank candidates")
    inputs = []
    for idx, row in enumerate(candidates, 1):
        if not isinstance(row, dict) or row.get("rank") != idx:
            raise ValueError("Frozen rank changed")
        inputs.append({
            "security_id": row["security_id"], "score": row["score"],
            "features_available_at": row["features_available_at_utc"],
            "score_computed_at": row["score_computed_at_utc"],
            "recorded_at": row["recorded_at_utc"],
        })
    if _validate_ranked(inputs, snapshot) != candidates:
        raise ValueError("Frozen ranks or inputs inconsistent")
    return obj


def evaluate_ranked_precision_at_k(
    frozen_file: Path, outcome_file: Path | None, *,
    evaluated_at: str, clock: datetime | None = None,
) -> dict:
    """Read separate future labels after freezing; censor unknown and young negatives."""
    frozen = _frozen(frozen_file)
    assessed = _time(evaluated_at)
    if assessed > _now(clock) or assessed < _time(frozen["snapshot_at_utc"]):
        raise ValueError("Invalid evaluation cutoff relative to snapshot or clock")
    # Historical replay may evaluate as-of an earlier day than the file was
    # created. Explicitly disclose this; it is NEVER prospective proof.
    replay_postdated_seal = assessed < _time(frozen["frozen_at_utc"])
    zone = ZONES[frozen["market"]]
    signal_day = _time(frozen["snapshot_at_utc"]).astimezone(zone).date()
    horizon = frozen["horizon_days"]
    labels = _read(outcome_file) if outcome_file is not None else []
    if not isinstance(labels, list):
        raise ValueError("Outcomes must be a separate JSON array")
    by_id: dict[str, dict] = {}
    for label in labels:
        if not isinstance(label, dict) or not isinstance(label.get("security_id"), str):
            raise ValueError("Invalid outcome row")
        sec = label["security_id"]
        if not sec or sec in by_id:
            raise ValueError("Duplicate or invalid outcome ID")
        if type(label.get("is_future_leader")) is not bool:
            raise ValueError("Outcome labels must be boolean")
        mature = _time(label["mature_at"])
        available = _time(label["outcome_available_at"])
        if available < mature:
            raise ValueError("Outcome published before maturity")
        if label["is_future_leader"]:
            if "leader_start_at" not in label or _time(label["leader_start_at"]) > mature:
                raise ValueError("Positive label missing or invalid leader onset")
        elif "leader_start_at" in label:
            raise ValueError("Negative outcome cannot assert a leader onset")
        by_id[sec] = label
    all_ids = {row["security_id"] for row in frozen["ranked_candidates"]}
    chosen = frozen["ranked_candidates"][:frozen["requested_k"]]
    counts = {"early_hit": 0, "known_failure": 0, "censored": 0}
    breakdown = []
    lead_days: list[int] = []
    young_negative = 0
    for row in chosen:
        sec = row["security_id"]
        label = by_id.get(sec)
        state = "censored"
        lead = None
        if label is not None:
            mature = _time(label["mature_at"])
            available = _time(label["outcome_available_at"])
            if mature <= assessed and available <= assessed:
                if label["is_future_leader"]:
                    onset_day = _time(label["leader_start_at"]).astimezone(zone).date()
                    lead = (onset_day - signal_day).days
                    if 0 < lead <= horizon:
                        state = "early_hit"
                        lead_days.append(lead)
                    else:
                        state = "known_failure"
                elif mature.astimezone(zone).date() >= signal_day + timedelta(days=horizon):
                    state = "known_failure"
                else:
                    young_negative += 1
        counts[state] += 1
        breakdown.append({"rank": row["rank"], "security_id": sec,
                          "status": state, "early_lead_days": lead if state == "early_hit" else None})
    selected = len(chosen)
    known = counts["early_hit"] + counts["known_failure"]
    return {
        "status": STATUS, "market": frozen["market"],
        "model_version": frozen["model_version"], "horizon_days": horizon,
        "requested_k": frozen["requested_k"], "selected_count": selected,
        "frozen_content_sha256": frozen["content_sha256"],
        "snapshot_at_utc": frozen["snapshot_at_utc"],
        "evaluated_at_utc": assessed.isoformat(),
        "retrospective_freeze": frozen["retrospective_freeze"],
        "evaluation_as_of_precedes_actual_seal": replay_postdated_seal,
        "early_hits": counts["early_hit"], "known_failures": counts["known_failure"],
        "censored": counts["censored"], "premature_negative_censored": young_negative,
        "precision_at_k_on_known": round(counts["early_hit"]/known, 6) if known else None,
        "conservative_precision_at_k_floor": round(counts["early_hit"]/selected, 6),
        "median_early_lead_days": median(lead_days) if lead_days else None,
        "unmatched_label_ids": len(set(by_id) - all_ids),
        "recall_at_k": None, "real_leader_prediction_certified": False,
        "independent_pit_or_outcome_certified": False, "official_leader_promotions": 0,
        "ranked_results": breakdown,
        "warning": "Unverified research labels only. Censoring, issuer PIT, survival bias and source timing preclude certified precision/recall.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ranked early-leader precision@K research")
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--input", type=Path, required=True)
    freeze.add_argument("--out", type=Path, required=True)
    freeze.add_argument("--market", choices=("KR", "US"), required=True)
    freeze.add_argument("--snapshot-at", required=True)
    freeze.add_argument("--model-version", required=True)
    freeze.add_argument("--horizon-days", type=int, required=True)
    freeze.add_argument("--k", type=int, required=True)
    freeze.add_argument("--prospective-ledger",type=Path,
                        help="Optional fail-closed WATCH registration preflight before freeze file is created")
    freeze.add_argument("--score-ledger",type=Path,
                        help="Optional actually registered numeric score evidence; requires --prospective-ledger and --features-dir")
    freeze.add_argument("--features-dir",type=Path,
                        help="Read-only feature evidence directory, used only with --score-ledger")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--freeze", type=Path, required=True)
    evaluate.add_argument("--outcomes", type=Path)
    evaluate.add_argument("--evaluated-at", required=True)
    evaluate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        if (args.score_ledger is None)!=(args.features_dir is None):
            raise ValueError("--score-ledger and --features-dir must be supplied together")
        if args.score_ledger is not None and args.prospective_ledger is None:
            raise ValueError("--score-ledger also requires --prospective-ledger")
        if args.prospective_ledger is not None:
            # Preflight a disposable candidate BEFORE exclusively creating
            # the final sealed ranking. Missing/forged WATCH cannot leave
            # behind a published, unsupported rank artifact.
            from .ranked_registry import audit_ranked_watch_registry
            with TemporaryDirectory(prefix="era-ranked-preflight-") as scratch:
                prototype=Path(scratch)/"sealed-research.json"
                result=freeze_ranked_snapshot(
                    args.input,prototype,market=args.market,
                    snapshot_at=args.snapshot_at,model_version=args.model_version,
                    horizon_days=args.horizon_days,k=args.k)
                linkage=audit_ranked_watch_registry(prototype,args.prospective_ledger)
                if (linkage["blocker_count"] or
                        linkage["ranked_ids_and_first_timestamps_matched"] !=
                        linkage["ranked_candidate_count"]):
                    raise ValueError("Ranked WATCH registry preflight failed: "+
                                     ", ".join(linkage["blockers"][:10]))
                if args.score_ledger is not None:
                    from .rank_score_ledger import audit_frozen_rank_scores
                    score_link=audit_frozen_rank_scores(prototype,args.score_ledger,args.features_dir)
                    if (score_link["blocker_count"] or
                        score_link["local_numeric_score_records_matched"] !=
                        score_link["ranked_candidate_count"]):
                        raise ValueError("Numeric score ledger preflight failed: "+
                                         ", ".join(score_link["blockers"][:10]))
                _save_new(args.out,result)
        else:
            result = freeze_ranked_snapshot(args.input, args.out, market=args.market,
                                             snapshot_at=args.snapshot_at, model_version=args.model_version,
                                             horizon_days=args.horizon_days, k=args.k)
    else:
        result = evaluate_ranked_precision_at_k(args.freeze, args.outcomes,
                                                 evaluated_at=args.evaluated_at)
        _save_new(args.out, result)
    print(json.dumps({key: result.get(key) for key in (
        "status", "content_sha256", "early_hits", "known_failures", "censored",
        "precision_at_k_on_known", "real_leader_prediction_certified")},
        sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
