"""ER-NC-09: seal B0/B1/B2/B3 scenario membership BEFORE outcome labels.

Consumes an existing prospective frozen holdout; never selects winners from
future labels, never changes original score/WATCH, never executes trading.
B4/B5 remain NOT_READY until the original authors' rules are verified.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

from .frozen_holdout import (
    _canonical, _digest, _publish_once, _read_frozen, _stamp,
    evaluate_frozen_candidates,
)
from .market_regime_experiment import entry_permission
from .news_catalyst_adapter import _unique

SCHEMA = "eraleader.er_nc09_frozen_ablation.v1"
CONTEXT_SCHEMA = "eraleader.er_nc09_context.v1"
ARM_NAMES = ("B0", "B1", "B2", "B3")
BASELINE_NAME = "EraLeader_WATCH_ORIGINAL"
THEME_STATES = {"EMERGING", "RISING", "CONSOLIDATING", "WEAKENING", "DORMANT", "REACTIVATING", "UNKNOWN"}
THEME_ENTRY = {"RISING", "REACTIVATING"}
REGIME_STATES = {"RISING", "SIDEWAYS", "FALLING", "TRANSITION", "UNKNOWN"}
REQUIRED_REGIME_QUALITY = "RESEARCH_PIT_INPUTS_PRESENT_NOT_PERFORMANCE_VERIFIED"
MAX_SOURCE_BYTES = 2_000_000
MARKET_ZONES = {"KR": "Asia/Seoul", "US": "America/New_York"}


def _hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _bytes(path: Path) -> bytes:
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("An absolute non-symlink input is required")
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Missing or oversized research input")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError("Input was modified while reading")
    return raw


def _context(path: Path, sha_pin: str) -> tuple[dict, str]:
    if not _hex(sha_pin):
        raise ValueError("Independent 64-digit SHA pin required")
    raw = _bytes(path)
    digest = sha256(raw).hexdigest()
    if digest != sha_pin:
        raise ValueError("Context source does not match independently stored SHA pin")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NaN prohibited")))
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise ValueError("Invalid context JSON") from exc
    if type(obj) is not dict or set(obj) != {"schema", "market", "model_version", "source_mode", "items"}:
        raise ValueError("Invalid or outcome-leaking context fields")
    if obj["schema"] != CONTEXT_SCHEMA or obj["source_mode"] != "LIVE_OBSERVED":
        raise ValueError("Historical-public replay requires an independent proof; unavailable here")
    if type(obj["items"]) is not list or len(obj["items"]) > 5000:
        raise ValueError("Bounded context rows required")
    return obj, digest


def _timefields(item: dict, keys: tuple[str, ...], *, recorded: datetime) -> None:
    for name in keys:
        if _stamp(item[name]) > recorded:
            raise ValueError("Future or late PIT "+name+" relative to first registration")


def _session_before(raw: str, observation: datetime, zone: str) -> None:
    from datetime import date
    day = date.fromisoformat(raw)
    if day > observation.astimezone(ZoneInfo(zone)).date():
        raise ValueError("Future session embedded in PIT context")
    if (observation.astimezone(ZoneInfo(zone)).date() - day).days > 7:
        raise ValueError("Stale market session cannot justify a live PIT filter")


def _validate_row(row: dict, signal: dict, market: str) -> dict:
    if type(row) is not dict or set(row) - {"security_id", "theme", "regime", "news"}:
        raise ValueError("Unexpected context fields or future labels")
    if row.get("security_id") != signal["security_id"]:
        raise ValueError("Context security identity differs from frozen signal")
    recorded = _stamp(signal["recorded_at_utc"])
    observed = _stamp(signal["observed_as_of"])
    if recorded < observed:
        raise ValueError("Backfilled or future prospective signal")
    zone = MARKET_ZONES[market]
    theme = row.get("theme")
    regime = row.get("regime")
    news = row.get("news")
    eligible_theme = False
    allowed_rising_regime = False
    if theme is not None:
        fields = {"schema", "theme_id", "state", "episode_id", "as_of",
                  "available_at", "source_first_received_at", "member_first_known_at",
                  "market_session", "research_only", "official_leaders",
                  "source_sha256", "quality_status"}
        if (type(theme) is not dict or set(theme) != fields or
                theme["schema"] != "eraleader.er_nc_theme_lifecycle.v1" or
                theme["research_only"] is not True or theme["official_leaders"] != 0 or
                theme["state"] not in THEME_STATES or
                not isinstance(theme["theme_id"], str) or not theme["theme_id"] or
                not _hex(theme["source_sha256"]) or
                not isinstance(theme["episode_id"], str) or not theme["episode_id"] or
                theme["quality_status"] != "PRICE_RESEARCH_WITH_PARTIAL_ISSUER_CLASS_PROVENANCE"):
            raise ValueError("Invalid PIT theme research contract")
        _timefields(theme, ("as_of", "available_at",
                            "source_first_received_at", "member_first_known_at"), recorded=recorded)
        _session_before(theme["market_session"], observed, zone)
        if _stamp(theme["available_at"]) < _stamp(theme["as_of"]):
            raise ValueError("PIT theme source cannot precede analysis timestamp")
        eligible_theme = theme["state"] in THEME_ENTRY
    if regime is not None:
        fields = {"schema", "market", "state", "quality_status", "regime_as_of",
                  "input_cutoff", "source_first_received_at", "market_session", "research_only"}
        if (type(regime) is not dict or set(regime) != fields or
                regime["schema"] != "eraleader.er_nc_market_regime.v1" or
                regime["research_only"] is not True or regime["state"] not in REGIME_STATES or
                regime["market"] not in (("KR_KOSPI", "KR_KOSDAQ") if market == "KR"
                                         else ("US_SP500", "US_NASDAQ100"))):
            raise ValueError("Invalid experimental market regime contract")
        _timefields(regime, ("regime_as_of", "input_cutoff", "source_first_received_at"),
                    recorded=recorded)
        if _stamp(regime["input_cutoff"]) > _stamp(regime["regime_as_of"]):
            raise ValueError("Regime input cutoff after decision")
        _session_before(regime["market_session"], observed, zone)
        allowed_rising_regime = (
            entry_permission(regime, policy="GATE_STRICT_UPTREND_V1")["permission"]
            == "ALLOW_NEW_BUY_RESEARCH_ONLY"
        )
    if news is not None:
        fields = {"schema", "mode", "as_of", "source_first_received_at",
                  "source_sha256", "quality_status"}
        if (type(news) is not dict or set(news) != fields or
                news["schema"] != "ernc.news_snapshot.v1" or
                news["mode"] != "LIVE_OBSERVED" or not _hex(news["source_sha256"]) or
                news["quality_status"] not in {"OK", "NO_VISIBLE_EVENTS",
                                               "UNKNOWN", "STALE", "MISSING"}):
            raise ValueError("Invalid or hindsight news vintage")
        _timefields(news, ("as_of", "source_first_received_at"), recorded=recorded)
    return {"security_id": signal["security_id"],
            "has_theme": theme is not None, "has_regime": regime is not None,
            "has_news": news is not None,
            "b2_eligible": eligible_theme,
            "b3_eligible": eligible_theme and allowed_rising_regime,
            "theme_state": theme["state"] if theme else "UNKNOWN",
            "regime_state": regime["state"] if regime else "UNKNOWN"}


def _safe_target(target: Path) -> None:
    if (not target.is_absolute() or target.exists() or target.is_symlink()
            or not target.parent.is_dir() or
            any(p.is_symlink() for p in target.parents)):
        raise ValueError("Require a new output directory, not an existing or linked path")


def freeze_news_ablations(
    frozen_holdout: Path, context_json: Path, target_dir: Path, *,
    expected_context_sha256: str, clock: datetime | None = None,
) -> dict:
    """Freeze arm membership with no access to outcome labels or trading streams."""
    target = Path(target_dir)
    _safe_target(target)
    source_freeze = _read_frozen(Path(frozen_holdout))
    source = Path(frozen_holdout)
    if not source.is_file() or source.is_symlink():
        raise ValueError("Ordinary pre-existing frozen source required")
    ctx, ctx_digest = _context(Path(context_json), expected_context_sha256)
    market = source_freeze["market"]
    if (market not in MARKET_ZONES or ctx["market"] != market or
            ctx["model_version"] != source_freeze["model_version"]):
        raise ValueError("Market/model mismatch between PIT context and original freeze")
    if source_freeze.get("outcome_labels_included") is not False:
        raise ValueError("No future label is allowed at scenario freeze time")
    fixed_at = _stamp(source_freeze["frozen_at_utc"])
    actual_now = datetime.now(timezone.utc)
    at = clock if clock is not None else actual_now
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Freeze clock requires timezone")
    at = at.astimezone(timezone.utc)
    if at <= fixed_at or at > actual_now:
        raise ValueError("Ablation seal must occur after base freeze and never in the future")
    originals = source_freeze["signals"]
    if source_freeze["eligible_count"] != len(originals):
        raise ValueError("Original holdout candidate count mismatch")
    base = {}
    for signal in originals:
        sec = signal.get("security_id")
        if not isinstance(sec, str) or not sec or sec in base:
            raise ValueError("Duplicate or invalid frozen security")
        if _stamp(signal["recorded_at_utc"]) > fixed_at:
            raise ValueError("Future signal in original frozen cohort")
        base[sec] = signal
    context_by_security = {}
    for item in ctx["items"]:
        if type(item) is not dict:
            raise ValueError("Context item must be object")
        sec = item.get("security_id")
        if not isinstance(sec, str) or sec in context_by_security or sec not in base:
            raise ValueError("Unknown/duplicate context security")
        context_by_security[sec] = _validate_row(item, base[sec], market)

    sorted_signals = sorted(originals, key=lambda row: row["security_id"])
    selected = {
        "B0": sorted_signals, "B1": sorted_signals,
        "B2": [row for row in sorted_signals
               if context_by_security.get(row["security_id"], {}).get("b2_eligible")],
        "B3": [row for row in sorted_signals
               if context_by_security.get(row["security_id"], {}).get("b3_eligible")],
    }
    if selected["B0"] != selected["B1"]:
        raise ValueError("Information-only B1 must never change baseline candidates")
    policy = {
        "B0": "ORIGINAL_BASELINE_NO_NEWS",
        "B1": "NEWS_SIDECAR_ONLY_EXACT_BASELINE",
        "B2": "THEME_RISING_OR_REACTIVATING_PIT_FILTER_HYPOTHESIS",
        "B3": "B2_AND_STRICT_UPTREND_NEW_ENTRY_HYPOTHESIS",
    }
    report = {
        "schema": SCHEMA, "created_at_utc": at.isoformat(),
        "market": market, "model_version": source_freeze["model_version"],
        "label_definition_id": source_freeze["label_definition_id"],
        "horizon_days": source_freeze["horizon_days"],
        "base_frozen_manifest_sha256": source_freeze["content_sha256"],
        "base_frozen_file_sha256": sha256(source.read_bytes()).hexdigest(),
        "pinned_context_file_sha256": ctx_digest,
        "context_mode": "LIVE_OBSERVED",
        "cohorts": {},
        "source_pit_certified": False, "real_time_news_witness_attested": False,
        "actual_prospective_prediction_accuracy_certified": False,
        "outcome_labels_included": False,
        "simulation_clock_supplied": clock is not None,
        "blocked_strategies": {
            "B4": "RULE_REVIEW_REQUIRED_NO_AUTHOR_ORIGINAL_EXECUTABLE",
            "B5": "RULE_REVIEW_REQUIRED_NO_AUTHOR_NEWS_FILTER_EXECUTABLE",
        },
        "warning": (
            "Selection-only retrospective ablation; local timestamps/source "
            "completeness are not independently certified; no future outcomes read."
        ),
    }
    scratch = Path(tempfile.mkdtemp(prefix=".er_nc09_stage_", dir=target.parent))
    os.chmod(scratch, 0o700)
    try:
        for arm in ARM_NAMES:
            scenario = dict(source_freeze)
            scenario.pop("content_sha256", None)
            scenario["signals"] = selected[arm]
            scenario["eligible_count"] = len(selected[arm])
            scenario["frozen_at_utc"] = at.isoformat()
            scenario["ablation_arm"] = arm
            scenario["ablation_policy"] = policy[arm]
            scenario["historic_pit_certified"] = False
            scenario["outcome_labels_included"] = False
            scenario["content_sha256"] = _digest(scenario)
            rel = arm + "_frozen.json"
            _publish_once(scratch / rel, scenario)
            report["cohorts"][arm] = {
                "policy": policy[arm], "count": len(selected[arm]),
                "security_ids": [s["security_id"] for s in selected[arm]],
                "scenario_file": rel,
                "scenario_content_sha256": scenario["content_sha256"],
                "scenario_file_sha256": sha256((scratch / rel).read_bytes()).hexdigest(),
            }
        report["content_sha256"] = _digest(report)
        _publish_once(scratch / "ablation_manifest.json", report)
        _safe_target(target)
        os.rename(scratch, target)
    except BaseException:
        if scratch.exists():
            shutil.rmtree(scratch)
        raise
    return {
        "status": "FROZEN_ABLATION_RESEARCH_ONLY_NOT_CERTIFIED",
        "manifest_sha256": report["content_sha256"],
        "source_context_sha256": ctx_digest,
        "candidate_counts": {k: len(v) for k, v in selected.items()},
        "B0_equals_B1": True, "outcome_labels_seen": False,
        "simulation_clock_supplied": clock is not None,
        "B4_B5": "NOT_READY",
        "target": str(target),
    }


def evaluate_news_ablations(
    sealed_dir: Path, outcome_json: Path, *,
    expected_manifest_sha256: str, evaluated_at: str,
    clock: datetime | None = None,
) -> dict:
    """Evaluate post-freeze labels with the existing maturity engine.

    The independent manifest SHA PIN and each derived frozen hash prevent
    accidental revision after knowing the outcome. No baseline is re-ranked.
    """
    if not _hex(expected_manifest_sha256):
        raise ValueError("A separately stored frozen SHA anchor is required")
    root = Path(sealed_dir)
    if not root.is_absolute() or root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("Only an ordinary absolute sealed directory can be evaluated")
    raw = _bytes(root / "ablation_manifest.json")
    try:
        frozen = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NaN prohibited")))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("Malformed sealed ablation manifest") from exc
    anchor = frozen.pop("content_sha256", None)
    if (not isinstance(frozen, dict) or frozen.get("schema") != SCHEMA or
            anchor != expected_manifest_sha256 or _digest(frozen) != anchor):
        raise ValueError("Frozen ablation SHA witness mismatch")
    if (frozen.get("outcome_labels_included") is not False or
            frozen.get("source_pit_certified") is not False or
            set(frozen.get("cohorts", {})) != set(ARM_NAMES)):
        raise ValueError("Outcome-injected or incomplete frozen experiment")
    if _stamp(evaluated_at) <= _stamp(frozen["created_at_utc"]):
        raise ValueError("Outcome evaluation must occur strictly after cohort seal")
    if not _hex(frozen.get("base_frozen_manifest_sha256")):
        raise ValueError("Missing source original freeze pin")
    if not _hex(frozen.get("pinned_context_file_sha256")):
        raise ValueError("Missing pre-outcome PIT context pin")
    # All four arms must use exactly the same outcome bytes, even when a
    # different process updates a local label file during evaluation.
    outcome_digest = sha256(_bytes(Path(outcome_json))).hexdigest()
    arm_metrics = {}
    for arm in ARM_NAMES:
        meta = frozen["cohorts"][arm]
        if (type(meta) is not dict or meta.get("scenario_file") != arm+"_frozen.json"
                or not _hex(meta.get("scenario_file_sha256"))):
            raise ValueError("Missing or redirected frozen scenario")
        scenario_path = root / meta["scenario_file"]
        raw_scenario = _bytes(scenario_path)
        if sha256(raw_scenario).hexdigest() != meta["scenario_file_sha256"]:
            raise ValueError("Frozen arm file changed after seal")
        scenario = _read_frozen(scenario_path)
        ids = [row["security_id"] for row in scenario["signals"]]
        if (scenario.get("content_sha256") != meta.get("scenario_content_sha256") or
                scenario.get("ablation_arm") != arm or
                scenario.get("market") != frozen["market"] or
                scenario.get("model_version") != frozen["model_version"] or
                scenario.get("label_definition_id") != frozen["label_definition_id"] or
                scenario.get("horizon_days") != frozen["horizon_days"] or
                scenario.get("frozen_at_utc") != frozen["created_at_utc"] or
                scenario.get("eligible_count") != len(ids) or
                len(ids) != meta.get("count") or ids != meta.get("security_ids")):
            raise ValueError("Frozen arm identity/date/selection has been altered")
        if sha256(_bytes(Path(outcome_json))).hexdigest() != outcome_digest:
            raise ValueError("Outcome file changed during arm comparison")
        metric = evaluate_frozen_candidates(
            scenario_path, Path(outcome_json),
            evaluated_at=evaluated_at,
            horizon_days=frozen["horizon_days"], clock=clock,
        )
        if sha256(_bytes(Path(outcome_json))).hexdigest() != outcome_digest:
            raise ValueError("Outcome file changed during arm comparison")
        tp = metric["true_early_discoveries"]
        fp = metric["false_discoveries"]
        arm_metrics[arm] = {
            "policy": meta["policy"], "signal_count": metric["eligible_candidates"],
            "known_outcomes": metric["known_outcomes"],
            "censored_outcomes": metric["censored_outcomes"],
            "true_early_discoveries": tp,
            "false_discoveries": fp,
            "late_or_post_onset": metric["late_or_post_onset"],
            "precision_on_matured_known": metric["precision_known_including_late"],
            "false_discovery_rate_known_nonlate": round(fp/(tp+fp),6) if tp+fp else None,
            "conservative_precision_floor": metric["conservative_precision_floor"],
            "lead_days_median": metric["median_early_lead_days"],
            "coverage_fraction": metric["coverage_fraction"],
            "precision_at_k": None,  # Frozen original registration lacks a pinned top-K rank.
            "recall_full_universe": metric["recall_complete_universe"],
            "CAGR": None, "MDD": None, "trading_costs": None,
            "source_pit_certified": False, "research_only": True,
        }
    if arm_metrics["B0"] != {**arm_metrics["B1"], "policy": arm_metrics["B0"]["policy"]}:
        raise ValueError("NEWS sidecar-only B1 changed baseline results")
    if not (arm_metrics["B3"]["signal_count"] <= arm_metrics["B2"]["signal_count"]
            <= arm_metrics["B0"]["signal_count"]):
        raise ValueError("Candidate filter improperly added new securities")
    return {
        "status": "RESEARCH_NOT_CERTIFIED_OUTCOME_EVALUATION",
        "manifest_sha256": anchor, "outcome_input_sha256": outcome_digest,
        "market": frozen["market"],
        "model_version": frozen["model_version"],
        "label_definition_id": frozen["label_definition_id"],
        "horizon_days": frozen["horizon_days"], "evaluated_at": evaluated_at,
        "news_sidecar_baseline_identity_verified": True,
        "run_is_simulation": frozen.get("simulation_clock_supplied") is True,
        "evaluation_clock_injected": clock is not None,
        "arms": arm_metrics,
        "B4": {"status": "NOT_READY", "reason": frozen["blocked_strategies"]["B4"]},
        "B5": {"status": "NOT_READY", "reason": frozen["blocked_strategies"]["B5"]},
        "source_pit_certified": False,
        "real_prospective_accuracy_certified": False,
        "statistical_improvement_claimed": False,
        "warnings": [
            "Label maturity and separate evaluation controlled by original frozen_holdout.",
            "PIT receipts are locally asserted, not independently provider-certified.",
            "B2/B3 are selective subcohorts; do not compare their precision as proof of causality.",
            "Frozen source has no verified rank@K or executable original-author strategy.",
            "No investment performance, return, risk, cost or corporate action calculation.",
        ],
    }
