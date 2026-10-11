"""5_5: first-write prospective Top-K census and all-registered-cohort evaluation.

Never cherry-pick only evaluated/winning cohorts: every sealed registry entry
stays in the denominator, including missing, immature and censored outcomes.
Local clock and first-write hashes are NOT independent source attestations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import Counter
import json
import os
import re

from .ranked_discovery import _frozen, _time, _now, _label_protocol, ZONES
from .ranked_outcome_receipts import audit_ranked_outcome_receipts

SCHEMA = "eraleader.prospective_cohort_census.v1"
SPEC_KEYS = {"frozen", "definition", "outcomes", "receipts"}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
MAX_COHORTS = 200
MAX_REGISTRIES = 1000
MAX_BYTES = 1_000_000


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate cohort census JSON key")
        out[key] = value
    return out


def _read(path: Path):
    path = Path(path)
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= MAX_BYTES):
        raise ValueError("Missing, linked or oversized cohort census input")
    return json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _hash(body: dict) -> str:
    return sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _basename(value: object) -> str:
    if (type(value) is not str or not NAME.fullmatch(value)
            or value.startswith(".") or "/" in value or "\\" in value):
        raise ValueError("Cohort evidence must use safe declared JSON basename")
    return value


def _root(path: Path) -> Path:
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_dir() or path.parent.is_symlink():
        raise ValueError("Cohort evidence directory must be a real local directory")
    return path


def _due(frozen: dict) -> datetime:
    zone: ZoneInfo = ZONES[frozen["market"]]
    # Like the existing ranked evaluator, use exchange-local wall-clock
    # across US DST transitions, not a fixed UTC hours conversion.
    local = _time(frozen["snapshot_at_utc"]).astimezone(zone)
    return (local + timedelta(days=frozen["horizon_days"])).astimezone(timezone.utc)


def _sources(source: Path, item: dict, *, at: datetime | None = None) -> tuple[dict, dict]:
    if not isinstance(item, dict) or set(item) != SPEC_KEYS:
        raise ValueError("Expected frozen/definition/outcomes/receipts in cohort spec")
    names = {k: _basename(v) for k, v in item.items()}
    if len({names[k] for k in ("frozen", "outcomes", "receipts")}) != 3:
        raise ValueError("A cohort freeze and future outcomes need separate file names")
    frozen_path = source / names["frozen"]
    definition_path = source / names["definition"]
    frozen = _frozen(frozen_path)
    if (frozen.get("retrospective_freeze") is not False
            or frozen.get("label_rule_bytes_pinned") is not True
            or frozen.get("outcome_definition_pinned_before_labels") is not True
            or frozen.get("timestamp_independently_attested") is not False
            or frozen.get("source_pit_independently_authenticated") is not False):
        raise ValueError("Census requires prospective predeclared but not independently attested freeze")
    rule_sha = _label_protocol(definition_path, label_id=frozen["label_definition_id"],
                                market=frozen["market"], horizon=frozen["horizon_days"])
    if rule_sha != frozen["label_definition_sha256"]:
        raise ValueError("Changed frozen label definition")
    if at is not None:
        seal = _time(frozen["frozen_at_utc"])
        if not seal <= at <= seal + timedelta(minutes=60):
            raise ValueError("Late or future cohort census registration forbidden")
        for key in ("outcomes", "receipts"):
            p = source / names[key]
            if p.exists() or p.is_symlink():
                raise ValueError("Future outcome evidence must not exist when census is first sealed")
    return names, frozen


def register_census(spec_file: Path, registry_dir: Path, name: str, *,
                    clock: datetime | None = None) -> dict:
    """Seal a single snapshot's COMPLETE declared cohort list (O_EXCL)."""
    now = _now(clock)
    spec = _read(spec_file)
    if not isinstance(spec, list) or not 1 <= len(spec) <= MAX_COHORTS:
        raise ValueError("Predeclared census must contain 1..200 cohorts")
    source = _root(Path(spec_file).parent)
    registry_dir = Path(registry_dir).absolute()
    if (registry_dir.is_symlink() or registry_dir.parent.is_symlink()
            or (registry_dir.exists() and not registry_dir.is_dir())):
        raise ValueError("Unsafe local cohort census registry directory")
    cohort_id = _basename(name)
    if not cohort_id.startswith("census_"):
        raise ValueError("Registered census name must start with census_")
    cohort_rows = []
    used = set()
    for item in spec:
        names, frozen = _sources(source, item, at=now)
        identity = (frozen["market"], frozen["model_version"], frozen["snapshot_at_utc"])
        if identity in used:
            raise ValueError("Duplicate frozen cohort identity inside census")
        used.add(identity)
        cohort_rows.append({
            **names,
            "market": frozen["market"],
            "model_version": frozen["model_version"],
            "snapshot_at_utc": frozen["snapshot_at_utc"],
            "frozen_at_utc": frozen["frozen_at_utc"],
            "frozen_sha256": sha256((source/names["frozen"]).read_bytes()).hexdigest(),
            "label_definition_sha256": frozen["label_definition_sha256"],
            "top_k_selected_count": min(frozen["requested_k"], len(frozen["ranked_candidates"])),
            "horizon_due_utc": _due(frozen).isoformat(),
        })
    data = {"schema_version": SCHEMA, "registered_at_utc": now.isoformat(),
            "source_dir": str(source), "cohorts": cohort_rows,
            "claims_independent_source_pit": False, "actual_future_leader_skill_certified": False}
    data["content_sha256"] = _hash(data)
    registry_dir.mkdir(parents=True, exist_ok=True)
    file = registry_dir / cohort_id
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    return {"status": "PROSPECTIVE_CENSUS_FIRST_WRITE_RESEARCH_ONLY",
            "registered_cohorts": len(cohort_rows),
            "selected_denominator": sum(x["top_k_selected_count"] for x in cohort_rows),
            "registry_name": cohort_id, "official_leaders_confirmed": 0}


def _validate_registry(file: Path, at: datetime):
    data = _read(file)
    if (not isinstance(data, dict) or
            set(data) != {"schema_version","registered_at_utc","source_dir",
                          "cohorts","claims_independent_source_pit",
                          "actual_future_leader_skill_certified","content_sha256"} or
            data["schema_version"] != SCHEMA or
            data["claims_independent_source_pit"] is not False or
            data["actual_future_leader_skill_certified"] is not False or
            not isinstance(data["content_sha256"], str) or
            not SHA.fullmatch(data["content_sha256"]) or
            _hash({k:v for k,v in data.items() if k!="content_sha256"}) != data["content_sha256"]):
        raise ValueError("Tampered/invalid prospective cohort census seal")
    registered = _time(data["registered_at_utc"])
    if registered > at:
        raise ValueError("Future census registration cannot be evaluated")
    path = data["source_dir"]
    if type(path) is not str or not Path(path).is_absolute():
        raise ValueError("Untrusted cohort source path")
    source = _root(Path(path))
    cohorts = data["cohorts"]
    if not isinstance(cohorts, list) or not 1 <= len(cohorts) <= MAX_COHORTS:
        raise ValueError("Invalid census cohort inventory")
    return registered, source, cohorts


def audit_all_registered_censuses(registry_dir: Path, *, evaluated_at: str,
                                  clock: datetime | None = None) -> dict:
    """Exhaustively evaluate *all on-disk registered* cohorts; omit none by score."""
    now = _now(clock)
    assessed = _time(evaluated_at)
    if assessed > now:
        raise ValueError("Future census evaluation clock forbidden")
    registry = _root(registry_dir)
    children = list(registry.iterdir())
    if any(p.is_symlink() or not p.is_file() or
           not p.name.startswith("census_") or not NAME.fullmatch(p.name)
           for p in children):
        raise ValueError("Unrecognized or hidden census registry evidence file")
    files = sorted(children)
    if not 1 <= len(files) <= MAX_REGISTRIES:
        raise ValueError("Census registry needs 1..1000 first-write manifests")
    counts = Counter()
    status_counts = Counter()
    identities = set()
    markets = Counter()
    for file in files:
        registered, source, cohorts = _validate_registry(file, assessed)
        for row in cohorts:
            if not isinstance(row, dict) or set(row) != SPEC_KEYS | {
                    "market","model_version","snapshot_at_utc","frozen_at_utc",
                    "frozen_sha256","label_definition_sha256",
                    "top_k_selected_count","horizon_due_utc"}:
                raise ValueError("Invalid cohort census pinned entry")
            names, frozen = _sources(source, {k:row[k] for k in SPEC_KEYS})
            identity = (frozen["market"],frozen["model_version"],frozen["snapshot_at_utc"])
            if identity in identities:
                raise ValueError("Duplicate cohort across registries would double-count outcomes")
            identities.add(identity)
            if (registered < _time(frozen["frozen_at_utc"]) or
                    registered > _time(frozen["frozen_at_utc"]) + timedelta(minutes=60) or
                    row["market"]!=frozen["market"] or
                    row["model_version"]!=frozen["model_version"] or
                    row["snapshot_at_utc"]!=frozen["snapshot_at_utc"] or
                    row["frozen_at_utc"]!=frozen["frozen_at_utc"] or
                    row["frozen_sha256"]!=sha256((source/names["frozen"]).read_bytes()).hexdigest() or
                    row["label_definition_sha256"]!=frozen["label_definition_sha256"] or
                    type(row["top_k_selected_count"]) is not int or
                    row["top_k_selected_count"]!=min(frozen["requested_k"],len(frozen["ranked_candidates"])) or
                    row["horizon_due_utc"]!=_due(frozen).isoformat()):
                raise ValueError("Census entry no longer matches first-sealed prospective frozen rank")
            k=row["top_k_selected_count"]
            counts["selected"] += k
            counts["cohorts"] += 1
            markets[frozen["market"]] += 1
            future = [source/names[x] for x in ("outcomes","receipts")]
            present = [p.exists() or p.is_symlink() for p in future]
            if not all(present):
                status = ("HORIZON_PENDING_SOURCE_UNKNOWN" if assessed < _due(frozen)
                          else ("PARTIAL_SOURCE_EVIDENCE" if any(present)
                                else "HORIZON_ELAPSED_SOURCE_UNKNOWN"))
                counts["unknown"] += k
            else:
                result=audit_ranked_outcome_receipts(
                    source/names["frozen"],future[0],future[1],
                    evaluated_at=assessed.isoformat(),
                    label_definition_file=source/names["definition"],clock=now)
                if (result["retrospective_freeze"] is not False or
                        result["top_k_selected_count"]!=k or
                        result["ranked_snapshot_sha256"]!=frozen["content_sha256"]):
                    raise ValueError("Cohort source evaluator changed original prospective K")
                counts["hits"]+=result["source_document_matched_early_hits"]
                counts["failures"]+=result["source_document_matched_known_failures"]
                counts["unknown"]+=result["unknown_or_source_censored_count"]
                status="CLAIMED_OUTCOME_SOURCES_AUDITED_UNCERTIFIED"
            status_counts[status]+=1
    if counts["hits"]+counts["failures"]+counts["unknown"] != counts["selected"]:
        raise ValueError("Registered frozen Top-K denominator was silently reduced")
    known=counts["hits"]+counts["failures"]
    return {
        "status":"ALL_REGISTERED_LOCAL_COHORTS_AUDITED_NOT_PIT_CERTIFIED",
        "evaluated_at_utc":assessed.isoformat(), "registry_manifest_count":len(files),
        "registered_cohort_count":counts["cohorts"],"registered_market_cohort_counts":dict(sorted(markets.items())),
        "frozen_selected_denominator":counts["selected"],
        "locally_documented_early_hits":counts["hits"],
        "locally_documented_known_failures":counts["failures"],
        "unknown_or_censored":counts["unknown"],
        "precision_on_documented_known":round(counts["hits"]/known,6) if known else None,
        "full_frozen_k_precision_floor":round(counts["hits"]/counts["selected"],6),
        "full_frozen_k_precision_ceiling":round((counts["hits"]+counts["unknown"])/counts["selected"],6),
        "cohort_status_counts":dict(sorted(status_counts.items())),
        "publisher_independently_authenticated":False,
        "census_exhaustiveness_independently_attested":False,
        "real_future_leader_accuracy_certified":False,
        "real_precision_at_k":None, "recall_at_k":None,
        "official_leader_promotions":0,"external_api_calls":0,
        "warning":"All discovered on-disk census entries are retained; a missing/deleted registry, publisher provenance and OS first-write clock are not independently verifiable.",
    }
