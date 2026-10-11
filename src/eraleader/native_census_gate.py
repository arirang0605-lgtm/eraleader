"""5_3/5_5 native-score proof gate for a first-write prospective Top-K census.

Reuse the already-tested native maturity verifier. An ordinary ranked JSON,
even with a valid local SHA, must not qualify as a WATCH-derived native rank.
No market source or OS timestamp is independently attested by this local gate.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import re

from .prospective_census import (
    _basename, _read, _root, _sources, _validate_registry,
)
from .prospective_census_seal import (
    _inventory, indexed_register_census, indexed_audit_censuses,
)
from .ranked_discovery import _frozen, _now, _time, _save_new
from .ranked_maturity import audit_ranked_maturity

SCHEMA = "eraleader.native_census_proof_paths.v1"
KEYS = {"frozen_sha256", "score_ledger", "watch_ledger", "features_dir"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_PROOFS = 1000
NATIVE_MARKER = {
    "schema_version": "eraleader.native_census_gate_required.v1",
    "native_first_write_provenance_required": True,
    "source_pit_independently_attested": False,
}


def native_gate_marker(registry_dir: Path) -> Path:
    root = Path(registry_dir).absolute()
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("Unsafe linked native census registry")
    return root.parent / (root.name + "_native_required.json")


def _checked_native_marker(registry_dir: Path) -> str:
    path = native_gate_marker(registry_dir)
    expected = (json.dumps(NATIVE_MARKER, indent=2, ensure_ascii=False,
                           sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    # Check the exact O_EXCL first-write bytes, not merely JSON equivalence.
    # Reformatting and rehashing a marker must not silently weaken the gate.
    if _read(path) != NATIVE_MARKER or path.read_bytes() != expected:
        raise ValueError("Missing or altered first-write native census requirement marker")
    return sha256(expected).hexdigest()


def _config(file: Path) -> tuple[dict[str, dict], str]:
    """Read a strict non-published mapping from frozen SHA to local sources."""
    file = Path(file)
    raw = file.read_bytes() if (file.is_file() and not file.is_symlink()
                                and not file.parent.is_symlink()
                                and 0 < file.stat().st_size <= 1_000_000) else None
    if raw is None:
        raise ValueError("Native census source configuration missing or unsafe")
    document = _read(file)
    if (not isinstance(document, dict) or
        set(document) != {"schema_version", "cohorts"} or
        document["schema_version"] != SCHEMA or
        not isinstance(document["cohorts"], list) or
        not 1 <= len(document["cohorts"]) <= MAX_PROOFS):
        raise ValueError("Native census source configuration schema invalid")
    mapped = {}
    for row in document["cohorts"]:
        if not isinstance(row, dict) or set(row) != KEYS:
            raise ValueError("Native census source row has missing/extra paths")
        digest = row["frozen_sha256"]
        if not isinstance(digest, str) or not SHA.fullmatch(digest) or digest in mapped:
            raise ValueError("Duplicate or malformed frozen first-write SHA")
        for field in ("score_ledger", "watch_ledger", "features_dir"):
            value = row[field]
            if (type(value) is not str or not 0 < len(value) <= 4096 or
                    not Path(value).is_absolute() or ".." in Path(value).parts):
                raise ValueError("Native evidence path must be an absolute safe local path")
            path = Path(value)
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError("Linked native first-write evidence rejected")
            if field == "features_dir":
                if not path.is_dir():
                    raise ValueError("Missing native feature evidence directory")
            elif not path.is_file():
                raise ValueError("Missing native WATCH/score ledger")
        mapped[digest] = row
    if len(mapped) != len(document["cohorts"]):
        raise ValueError("Native source config duplicate entries")
    return mapped, sha256(raw).hexdigest()


def _preflight(
    sources: list[tuple[Path, Path, str]],
    config: Path, *, cutoff: datetime,
) -> dict:
    mapping, original_config_sha = _config(config)
    expected = {digest for _, _, digest in sources}
    if len(expected) != len(sources) or set(mapping) != expected:
        raise ValueError("Native first-write config must cover EXACTLY all declared cohorts")
    checked = []
    count = 0
    score_count = 0
    for frozen_file, definition_file, digest in sources:
        if sha256(frozen_file.read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen native first-write bytes revised during census")
        row = mapping[digest]
        report = audit_ranked_maturity(
            frozen_file, definition_file, Path(row["score_ledger"]),
            Path(row["watch_ledger"]), Path(row["features_dir"]),
            as_of=cutoff.isoformat(), clock=cutoff,
            sample_limit=1,
        )
        frozen = _frozen(frozen_file)
        if (report.get("local_native_provenance_rechecked") is not True or
            report.get("prospective_maturity_eligible") is not True or
            report.get("outcome_labels_read") is not False or
            report.get("actual_future_leader_skill_certified") is not False or
            report.get("selected_top_k_count") != min(
                frozen["requested_k"], len(frozen["ranked_candidates"])
            ) or report.get("frozen_first_score_count") != len(frozen["ranked_candidates"])
            or report.get("frozen_rank_sha256") != frozen["content_sha256"]):
            raise ValueError("Native positive WATCH / numeric first-score proof incomplete")
        count += report["selected_top_k_count"]
        score_count += report["frozen_first_score_count"]
        checked.append((digest, report["native_first_watch_score_binding_sha256"]))
    _, final_config_sha = _config(config)
    if final_config_sha != original_config_sha:
        raise ValueError("Native original source configuration changed during audit")
    return {
        "fully_native_bound_cohorts": len(checked),
        "native_frozen_selected_count": count,
        "complete_positive_watch_first_scores": score_count,
        "native_watch_score_witness_hashes_sha256": sha256(
            "|".join(item[0] + ":" + item[1] for item in sorted(checked)).encode("ascii")
        ).hexdigest(),
        "native_source_paths_manifest_sha256": original_config_sha,
    }


def _registered_sources(registry_dir: Path, assessed: datetime) -> list[tuple[Path, Path, str]]:
    root = _root(registry_dir)
    paths = []
    for receipt in sorted(_inventory(root).values()):
        _, source, rows = _validate_registry(receipt, assessed)
        for row in rows:
            freeze_path = source / _basename(row["frozen"])
            rule_path = source / _basename(row["definition"])
            digest = row["frozen_sha256"]
            if (not isinstance(digest, str) or not SHA.fullmatch(digest)):
                raise ValueError("Missing original frozen research bytes SHA")
            paths.append((freeze_path, rule_path, digest))
    return paths


def register_native_census(
    spec_file: Path, registry_dir: Path, name: str, *,
    native_config: Path, clock: datetime | None = None,
) -> dict:
    """Require actual native WATCH first-score/formula evidence BEFORE O_EXCL."""
    now = _now(clock)
    spec = _read(spec_file)
    if not isinstance(spec, list):
        raise ValueError("Native census needs explicitly declared frozen cohort array")
    source_dir = _root(Path(spec_file).parent)
    sources = []
    for item in spec:
        names, _ = _sources(source_dir, item, at=now)
        file = source_dir / names["frozen"]
        sources.append((file, source_dir / names["definition"],
                        sha256(file.read_bytes()).hexdigest()))
    verified_before = _preflight(sources, native_config, cutoff=now)
    marker = native_gate_marker(registry_dir)
    if not marker.exists() and not marker.is_symlink():
        if _inventory(Path(registry_dir).absolute()):
            raise ValueError("Existing unpinned census cannot be retroactively called native")
        # Pin strict-mode intent BEFORE any indexed O_EXCL writes. A crash
        # may strand this marker; fail-closed rather than silently downgrade.
        _save_new(marker, NATIVE_MARKER)
    marker_sha = _checked_native_marker(registry_dir)
    registered = indexed_register_census(spec_file, registry_dir, name, clock=now)
    verified_after = _preflight(sources, native_config, cutoff=now)
    if _checked_native_marker(registry_dir) != marker_sha:
        raise RuntimeError("Native census strict-mode marker revised after registration")
    if verified_after != verified_before:
        # Never delete the first-write entry if source changes after O_EXCL.
        # A surviving orphan is unsafe and will need evidence-backed repair.
        raise RuntimeError("Native first-write evidence changed after census registration")
    if verified_after["native_frozen_selected_count"] != registered["selected_denominator"]:
        raise ValueError("Native first-score selected denominator differs from census")
    return {
        **registered, **verified_after,
        "status": "LOCAL_NATIVE_FIRST_WRITE_CENSUS_REGISTERED_NOT_PIT_CERTIFIED",
        "native_first_write_required_marker_sha256": marker_sha,
        "local_native_score_provenance_complete": True,
        "issuer_source_pit_independently_verified": False,
        "real_future_leader_skill_certified": False,
    }


def audit_native_census(
    registry_dir: Path, *, native_config: Path, evaluated_at: str,
    clock: datetime | None = None,
) -> dict:
    """Audit ALL indexed cohorts plus complete original native score witnesses."""
    now = _now(clock)
    assessed = _time(evaluated_at)
    if assessed > now:
        raise ValueError("Future native cohort assessment not permitted")
    original_marker_sha = _checked_native_marker(registry_dir)
    indexed_before = indexed_audit_censuses(
        registry_dir, evaluated_at=assessed.isoformat(), clock=now)
    originals = _registered_sources(registry_dir, assessed)
    verified = _preflight(originals, native_config, cutoff=assessed)
    indexed_after = indexed_audit_censuses(
        registry_dir, evaluated_at=assessed.isoformat(), clock=now)
    if indexed_before != indexed_after:
        raise RuntimeError("Indexed first-write census changed during native audit")
    if (indexed_after["registered_cohort_count"] != verified["fully_native_bound_cohorts"]
            or indexed_after["frozen_selected_denominator"] !=
            verified["native_frozen_selected_count"]):
        raise ValueError("Native complete WATCH source count disagrees with indexed census")
    # Re-audit exact original source bytes after potentially lengthy label evaluation.
    if _preflight(originals, native_config, cutoff=assessed) != verified:
        raise RuntimeError("Native original sources changed during cohort evaluation")
    if _checked_native_marker(registry_dir) != original_marker_sha:
        raise RuntimeError("Native strict-mode requirement changed during cohort audit")
    return {
        **indexed_after, **verified,
        "native_first_write_required_marker_sha256": original_marker_sha,
        "status": "LOCAL_ALL_NATIVE_PROSPECTIVE_COHORTS_AUDITED_NOT_CERTIFIED",
        "local_native_score_provenance_complete": True,
        "issuer_source_pit_independently_verified": False,
        "real_future_leader_skill_certified": False,
        "real_precision_at_k": None,
        "recall_at_k": None,
        "official_leader_promotions": 0,
        "external_api_calls": 0,
    }
