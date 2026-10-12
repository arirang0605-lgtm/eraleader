"""ER-NC-01: fail-closed, read-only NewsCatalystOS event consumer.

No article fetching, AI inference, broker actions, schema migrations or
retrospective 'real' signals. Only independently produced licensed event exports.
NEWS_ENABLED=false is a strict no-op for the existing EraLeader research engine.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

SCHEMA_MAJOR = 1
REQUIRED = {
    "schema_version", "export_id", "event_id", "event_version", "event_type",
    "published_at", "first_seen_at", "available_at", "verification_status",
    "novelty", "catalyst_state", "evidence_ids", "source_refs",
    "related_issuer_ids", "beneficiary_candidates", "theme_hints",
    "model_version", "extractor_version", "data_cutoff",
    "license_profile", "quality_flags", "record_sha256",
}
ALLOWED_EXTRA = {"revised_at"}
VERIFICATIONS = {"VERIFIED", "OBSERVED_UNVERIFIED", "INVALIDATED"}
CATALYST_STATES = {"CONFIRMED", "WEAKENED", "INVALIDATED", "UNKNOWN"}
NOVELTIES = {"NEW", "REPEATED", "UNKNOWN"}
BENEFICIARY_RELATIONS = {"DIRECT_VERIFIED", "POTENTIAL", "UNVERIFIED_ASSOCIATION"}
MAX_FILE = 8 * 1024 * 1024
MAX_RECORDS = 10_000
ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _unique(items: list[tuple[str, Any]]) -> dict:
    answer = {}
    for key, value in items:
        if key in answer:
            raise ValueError("NEWS duplicate JSON key")
        answer[key] = value
    return answer


def _canonical(item: dict) -> bytes:
    return json.dumps(item, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def record_sha256(item: dict) -> str:
    """Stable SHA of the event without the record_sha256 self-field."""
    return sha256(_canonical({k: v for k, v in item.items()
                              if k != "record_sha256"})).hexdigest()


def _time(value: str, label: str) -> datetime:
    if type(value) is not str or len(value) > 48:
        raise ValueError("NEWS malformed timestamp " + label)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("NEWS invalid timestamp " + label) from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("NEWS timezone required for " + label)
    return dt.astimezone(timezone.utc)


def _ident(value: object, label: str) -> str:
    if type(value) is not str or not ID_PATTERN.fullmatch(value):
        raise ValueError("NEWS invalid " + label)
    return value


def _strings(value: object, label: str) -> list[str]:
    if type(value) is not list or len(value) > 100:
        raise ValueError("NEWS invalid " + label)
    seen = set()
    for text in value:
        if type(text) is not str or not 1 <= len(text) <= 256:
            raise ValueError("NEWS invalid string in " + label)
        if text in seen:
            raise ValueError("NEWS duplicate string in " + label)
        seen.add(text)
    return value


def _record(value: object) -> dict:
    if type(value) is not dict or not REQUIRED.issubset(value):
        raise ValueError("NEWS required event fields missing")
    if set(value) - (REQUIRED | ALLOWED_EXTRA):
        raise ValueError("NEWS unexpected raw article/unknown event fields")
    schema = value["schema_version"]
    if type(schema) is not str or not re.fullmatch(r"1\.[0-9]+(?:\.[0-9]+)?", schema):
        raise ValueError("NEWS unsupported schema major")
    for name in ("export_id", "event_id", "event_type", "model_version", "extractor_version"):
        _ident(value[name], name)
    revision = value["event_version"]
    if type(revision) is not int or not 1 <= revision <= 10000:
        raise ValueError("NEWS invalid event version")
    if value["verification_status"] not in VERIFICATIONS:
        raise ValueError("NEWS unknown verification status")
    if value["novelty"] not in NOVELTIES or value["catalyst_state"] not in CATALYST_STATES:
        raise ValueError("NEWS unknown novelty/catalyst state")
    published = _time(value["published_at"], "published_at")
    observed = _time(value["first_seen_at"], "first_seen_at")
    available = _time(value["available_at"], "available_at")
    cutoff = _time(value["data_cutoff"], "data_cutoff")
    if not (published <= observed <= available and cutoff <= available):
        raise ValueError("NEWS impossible first-seen/verified time order")
    if revision > 1 and "revised_at" not in value:
        raise ValueError("NEWS corrections require revised_at")
    if value.get("revised_at") is not None:
        revised = _time(value["revised_at"], "revised_at")
        if not published <= revised <= available:
            raise ValueError("NEWS correction outside publicly available interval")
    rights = value["license_profile"]
    if (type(rights) is not dict or
            rights.get("research_allowed") is not True or
            rights.get("derived_storage_allowed") is not True or
            type(rights.get("redistribution_allowed")) is not bool):
        raise ValueError("NEWS rights denied or undocumented")
    _strings(value["evidence_ids"], "evidence_ids")
    _strings(value["related_issuer_ids"], "related_issuer_ids")
    _strings(value["theme_hints"], "theme_hints")
    _strings(value["quality_flags"], "quality_flags")
    if (value["verification_status"] in {"VERIFIED", "INVALIDATED"}
            and not value["evidence_ids"]):
        raise ValueError("NEWS verified event without independent evidence IDs")
    if (value["verification_status"] == "OBSERVED_UNVERIFIED"
            and value["catalyst_state"] != "UNKNOWN"):
        raise ValueError("NEWS unverified material cannot be confirmed")
    if (value["verification_status"] == "INVALIDATED"
            and value["catalyst_state"] != "INVALIDATED"):
        raise ValueError("NEWS invalidated event cannot remain a positive catalyst")
    refs = value["source_refs"]
    if type(refs) is not list or not refs or len(refs) > 25:
        raise ValueError("NEWS missing licensed source references")
    for ref in refs:
        if (type(ref) is not dict or set(ref) != {"url", "source_id"} or
                type(ref["url"]) is not str or
                not ref["url"].startswith("https://") or
                len(ref["url"]) > 1500):
            raise ValueError("NEWS source must be authorized metadata, never article body")
        _ident(ref["source_id"], "source_id")
    benefits = value["beneficiary_candidates"]
    if type(benefits) is not list or len(benefits) > 100:
        raise ValueError("NEWS invalid beneficiary list")
    seen_benefit = set()
    for benefit in benefits:
        if (type(benefit) is not dict or
                set(benefit) != {"issuer_id", "relation", "first_known_at", "evidence_ids"}):
            raise ValueError("NEWS unverified beneficiary schema")
        issuer = _ident(benefit["issuer_id"], "beneficiary_issuer")
        if issuer in seen_benefit:
            raise ValueError("NEWS duplicate beneficiary issuer")
        seen_benefit.add(issuer)
        if benefit["relation"] not in BENEFICIARY_RELATIONS:
            raise ValueError("NEWS unverified beneficiary relationship")
        if not published <= _time(benefit["first_known_at"], "first_known_at") <= available:
            raise ValueError("NEWS late-confirmed beneficiary smuggled into early version")
        _strings(benefit["evidence_ids"], "beneficiary_evidence_ids")
        if benefit["relation"] == "DIRECT_VERIFIED" and not benefit["evidence_ids"]:
            raise ValueError("NEWS direct beneficiary claim without evidence")
    if (type(value["record_sha256"]) is not str or
            not SHA_PATTERN.fullmatch(value["record_sha256"]) or
            record_sha256(value) != value["record_sha256"]):
        raise ValueError("NEWS event record SHA256 mismatch")
    return value


class NewsCatalystEvents:
    """Read-only, single-export vintage; not a news aggregator or signal model."""

    def __init__(self, records: list[dict], *, source_sha256: str, source_name: str):
        if len(records) > MAX_RECORDS:
            raise ValueError("NEWS export exceeds record cap")
        versions: dict[str, dict[int, dict]] = {}
        export_id: str | None = None
        for item in records:
            checked = _record(item)
            if export_id is None:
                export_id = checked["export_id"]
            elif export_id != checked["export_id"]:
                raise ValueError("NEWS mixed export lineage IDs")
            history = versions.setdefault(checked["event_id"], {})
            previous = history.get(checked["event_version"])
            if previous is not None and previous["record_sha256"] != checked["record_sha256"]:
                raise ValueError("NEWS same event/version content SHA collision")
            history[checked["event_version"]] = checked
        self.versions: dict[str, tuple[dict, ...]] = {}
        for event_id, by_version in versions.items():
            ordered = tuple(sorted(by_version.values(), key=lambda x: x["event_version"]))
            for older, newer in zip(ordered, ordered[1:]):
                if (newer["event_version"] <= older["event_version"] or
                        _time(newer["first_seen_at"], "first_seen_at") <
                        _time(older["first_seen_at"], "first_seen_at") or
                        _time(newer["available_at"], "available_at") <
                        _time(older["available_at"], "available_at") or
                        newer["published_at"] != older["published_at"]):
                    raise ValueError("NEWS event revision ancestry/timing conflict")
            self.versions[event_id] = ordered
        self.source_sha256 = source_sha256
        self.source_name = source_name
        self.export_id = export_id
        self.unique_events = len(versions)

    @classmethod
    def load(cls, path: Path) -> "NewsCatalystEvents":
        path = Path(path)
        if (not path.is_absolute() or path.is_symlink() or
                any(parent.is_symlink() for parent in path.parents) or
                not path.is_file() or path.suffix not in {".json", ".jsonl"}):
            raise ValueError("NEWS absolute, ordinary nonlinked .json/.jsonl required")
        before = path.stat()
        if not 0 < before.st_size <= MAX_FILE:
            raise ValueError("NEWS export file size outside safety limit")
        raw = path.read_bytes()
        after = path.stat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError("NEWS input changed during read")
        try:
            if path.suffix == ".jsonl":
                docs = [json.loads(line, object_pairs_hook=_unique,
                                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NEWS nonfinite")))
                        for line in raw.decode("utf-8").splitlines() if line.strip()]
            else:
                document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
                docs = document["events"] if type(document) is dict else document
        except (UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("NEWS invalid complete JSON/JSONL export") from exc
        if type(docs) is not list:
            raise ValueError("NEWS expected JSON array of event versions")
        return cls(docs, source_sha256=sha256(raw).hexdigest(), source_name=path.name)

    def snapshot(self, as_of: str, mode: str = "LIVE_OBSERVED") -> dict:
        cutoff = _time(as_of, "as_of")
        if mode not in {"LIVE_OBSERVED", "HISTORICAL_PUBLIC_REPLAY"}:
            raise ValueError("NEWS unknown PIT snapshot mode")
        if mode == "HISTORICAL_PUBLIC_REPLAY":
            # Local export alone cannot independently attest a historic public
            # timestamp, rights and availability coverage. No hindsight credit.
            return {"schema":"ernc.news_snapshot.v1", "mode":mode, "as_of":cutoff.isoformat(),
                    "quality_status":"INDEPENDENT_PUBLICATION_WITNESS_REQUIRED",
                    "research_only":True, "events":[], "event_count":0,
                    "source_sha256":self.source_sha256, "export_id":self.export_id}
        visible = []
        pending_count = 0
        for event_id, records in sorted(self.versions.items()):
            observed = [r for r in records if
                        _time(r["first_seen_at"], "first_seen_at") <= cutoff]
            available = [r for r in observed if
                         _time(r["available_at"], "available_at") <= cutoff]
            if available:
                latest = available[-1]
                event = deepcopy(latest)
                event["evidence_status"] = ("VERIFIED_AS_OF" if
                    latest["verification_status"] == "VERIFIED" else
                    latest["verification_status"])
                # Later correction observed but not yet verified => do not
                # silently treat a historic claim as freshly re-confirmed.
                if len(observed) > len(available):
                    event["quality_flags"] = list(event["quality_flags"]) + ["REVISION_PENDING"]
                    pending_count += 1
                visible.append(event)
            elif observed:
                pending_count += 1
                visible.append({"event_id":event_id,
                                "verification_status":"OBSERVED_UNVERIFIED",
                                "catalyst_state":"UNKNOWN", "evidence_status":"NOT_YET_AVAILABLE",
                                "related_issuer_ids":[], "beneficiary_candidates":[],
                                "theme_hints":[], "source_refs":[], "evidence_ids":[]})
        return {"schema":"ernc.news_snapshot.v1", "mode":mode,
                "as_of":cutoff.isoformat(), "export_id":self.export_id,
                "source_sha256":self.source_sha256, "event_count":len(visible),
                "observed_unverified_count":pending_count,
                "quality_status":"OK" if visible else "NO_VISIBLE_EVENTS",
                "research_only":True, "events":visible}

    def related_events(self, entity_or_theme: str, as_of: str) -> list[dict]:
        _ident(entity_or_theme, "entity_or_theme")
        events = self.snapshot(as_of)["events"]
        return [item for item in events if
                item.get("evidence_status") == "VERIFIED_AS_OF" and
                (entity_or_theme in item.get("related_issuer_ids", []) or
                 entity_or_theme in item.get("theme_hints", []) or
                 entity_or_theme in [b["issuer_id"] for b in
                                      item.get("beneficiary_candidates", [])])]


def news_enabled(environ: dict | None = None) -> bool:
    setting = (environ if environ is not None else os.environ).get("NEWS_ENABLED", "false")
    return type(setting) is str and setting.casefold() in {"true", "1", "yes"}


def attach_news_evidence(existing_snapshot: dict, news_snapshot: dict | None,
                         *, enabled: bool = False) -> dict:
    """Opt-in sidecar only. NEWS_OFF preserves exact legacy object and HTML."""
    if not enabled:
        return existing_snapshot
    result = deepcopy(existing_snapshot)
    if not news_snapshot or news_snapshot.get("quality_status") not in {"OK", "NO_VISIBLE_EVENTS"}:
        result["news_quality_status"] = "DEGRADED_NEWS_UNAVAILABLE"
        return result
    for row in result.get("rows", []):
        security = row.get("security_id")
        row["news_evidence"] = [
            {"event_id":ev["event_id"],
             "event_version":ev["event_version"],
             "available_at":ev["available_at"],
             "catalyst_state":ev["catalyst_state"],
             "verification_status":ev["verification_status"],
             "record_sha256":ev["record_sha256"]}
            for ev in news_snapshot["events"]
            if ev.get("evidence_status") == "VERIFIED_AS_OF"
            and (security in ev.get("related_issuer_ids", []) or
                 security in [b["issuer_id"] for b in ev.get("beneficiary_candidates", [])])
        ]
    result["news_quality_status"] = news_snapshot["quality_status"]
    result["news_as_of"] = news_snapshot["as_of"]
    result["news_source_sha256"] = news_snapshot["source_sha256"]
    return result
