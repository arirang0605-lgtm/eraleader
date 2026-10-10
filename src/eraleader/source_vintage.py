"""Fail-closed, local-only audit of declared source vintages (2_2/2_5).

A matching file hash proves integrity relative to a supplied manifest, NOT that
its claimed historical retrieval timestamp, publisher, or coverage is authentic.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

KINDS = {
    "membership": ("known_at", "valid_from"),
    "actions": ("known_at", "effective_on"),
    "fundamentals": ("available_at", "period_end"),
    "industry": ("available_at", "period_end"),
    "raw_prices": ("available_at", "session"),
    "total_return_index": ("available_at", "session"),
}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
FILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.jsonl\Z")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Source timestamp must be timezone-aware ISO text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid source timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Source timestamp must include timezone")
    return stamp.astimezone(timezone.utc)


def _nonempty(row: dict, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing source field: {name}")
    return value


def audit_source_vintages(manifest_file: Path, *, decision_at: str) -> dict:
    """Audit local JSONL files as declared, but NEVER certify provider PIT."""
    cutoff = _timestamp(decision_at)
    root = Path(manifest_file).resolve().parent
    manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "source_vintage_manifest_v1":
        raise ValueError("Unsupported source-vintage manifest schema")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 64:
        raise ValueError("Source manifest requires 1..64 sources")
    seen_sources = set()
    results = []
    for spec in sources:
        if not isinstance(spec, dict):
            raise ValueError("Source specification must be an object")
        source_id = _nonempty(spec, "source_id")
        vintage_id = _nonempty(spec, "vintage_id")
        publisher_id = _nonempty(spec, "publisher_id")
        kind = spec.get("kind")
        market = spec.get("market")
        if kind not in KINDS or market not in ("KR", "US"):
            raise ValueError("Invalid source kind/market")
        source_key = (source_id, vintage_id, kind, market)
        if source_key in seen_sources:
            raise ValueError("Duplicate source vintage declaration")
        seen_sources.add(source_key)
        filename = _nonempty(spec, "file")
        if not FILE_RE.fullmatch(filename) or filename.startswith("."):
            raise ValueError("Unsafe source filename (basename JSONL only)")
        path = root / filename
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise ValueError("Source file missing, symlinked or outside manifest directory")
        expected = _nonempty(spec, "sha256")
        if not SHA_RE.fullmatch(expected):
            raise ValueError("Invalid SHA256 manifest digest")
        retrieved = _timestamp(spec.get("retrieved_at"))
        digest = sha256()
        count = known = future = 0
        row_ids = set()
        visible_latest_revisions = {}
        timestamp_field, day_field = KINDS[kind]
        with path.open("rb") as fp:
            for line in fp:
                digest.update(line)
                if len(line) > 2 * 1024 * 1024:
                    raise ValueError("Oversized source JSONL row")
                if not line.strip():
                    raise ValueError("Blank source JSONL row")
                count += 1
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ValueError(f"Invalid source JSONL row {count}") from exc
                if not isinstance(row, dict) or row.get("source_id") != source_id:
                    raise ValueError("Source row ID differs from manifest")
                record_id = _nonempty(row, "record_id")
                identity_field = "industry_id" if kind == "industry" else "security_id"
                _nonempty(row, identity_field)
                revision = row.get("revision")
                if type(revision) is not int or revision < 1:
                    raise ValueError("Source record revision must be positive integer")
                key = (record_id, revision)
                if key in row_ids:
                    raise ValueError("Repeated source record revision")
                row_ids.add(key)
                try:
                    date.fromisoformat(_nonempty(row, day_field))
                except ValueError as exc:
                    raise ValueError("Invalid source observation date") from exc
                available = _timestamp(row.get(timestamp_field))
                if available > retrieved:
                    raise ValueError("Source row availability postdates claimed retrieval")
                if available <= cutoff:
                    known += 1
                    visible_latest_revisions[record_id] = max(
                        revision, visible_latest_revisions.get(record_id, 0))
                else:
                    future += 1
        if not count:
            raise ValueError("Empty source file cannot establish vintage coverage")
        if digest.hexdigest() != expected:
            raise ValueError("Source SHA256 does not match manifest")
        # Multiple known revisions of the same logical record do not
        # inflate snapshot row coverage; only its latest known revision does.
        latest_known = len(visible_latest_revisions)
        usable = latest_known if retrieved <= cutoff else 0
        results.append({
            "source_id": source_id, "publisher_id_claimed": publisher_id,
            "vintage_id": vintage_id, "market": market, "kind": kind,
            "sha256_verified": True, "rows_total": count,
            "rows_available_by_decision_claimed": known,
            "superseded_revisions_excluded": known - latest_known,
            "rows_after_decision_excluded": future,
            "rows_potentially_usable_asof": usable,
            "retrieved_by_decision_claimed": retrieved <= cutoff,
            "retrospective_backfill": retrieved > cutoff,
        })
    backfilled = sum(1 for row in results if row["retrospective_backfill"])
    return {
        "status": ("RESEARCH_RETROSPECTIVE_VINTAGE_NOT_PIT" if backfilled
                   else "RESEARCH_DECLARED_VINTAGE_NOT_CERTIFIED"),
        "decision_at": cutoff.isoformat(), "source_count": len(results),
        "retrospective_source_count": backfilled,
        "rows_potentially_usable_asof": sum(x["rows_potentially_usable_asof"] for x in results),
        "sources": results, "file_integrity_checked": True,
        "historical_pit_certified": False,
        "source_timestamp_independently_attested": False,
        "official_historic_universe_verified": False,
        "corporate_action_completeness_verified": False,
        "delisting_settlement_verified": False,
        "independent_provider_identity_verified": False,
        "warning": ("Local hashes prove only manifest-relative byte integrity. "
                    "Publisher identity, historical retrieval timestamps, revisions, "
                    "license, issuer universe and omitted events remain unverified."),
    }
