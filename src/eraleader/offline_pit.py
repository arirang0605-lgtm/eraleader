"""Strict offline input ledger for PIT membership, actions, fundamentals, sectors.

No API calls. No fixture or public input is automatically certified as complete.
Records are append-only; reuse of an ID with changed content is rejected.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import csv
import json
import math
import sqlite3

KINDS = ("membership", "actions", "fundamentals", "industry")
METRICS = ("revenue", "operating_income", "cashflow_operations", "capex",
           "net_income", "assets", "debt", "eps_estimate")
EVENTS = ("split", "dividend", "delist", "merger", "ticker_change")
PROVENANCES = ("synthetic_fixture", "external_public_file", "user_supplied")

def iso_day(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Date must be ISO string")
    return date.fromisoformat(value).isoformat()

def iso_time(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be ISO string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp missing timezone; fail closed")
    return dt.astimezone(timezone.utc).isoformat()

def numeric(value: Any) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("Missing/invalid numeric value")
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value {value!r}") from exc
    if not math.isfinite(f):
        raise ValueError("NaN/infinity must not enter finance data")
    return f

def normalize(kind: str, row: dict) -> dict:
    if kind not in KINDS:
        raise ValueError(f"Unknown offline record kind: {kind}")
    x = dict(row)
    for key in ("source_id", "revision"):
        if key not in x:
            raise ValueError(f"Missing {key} for {kind}")
    if not isinstance(x["source_id"], str) or not x["source_id"].strip():
        raise ValueError("Missing source_id provenance")
    revision = x["revision"]
    # CSV rows contain decimal integer strings. Refuse float/boolean
    # coercion: int(True) and int(1.9) silently create false PIT revisions.
    if type(revision) is int:
        pass
    elif isinstance(revision,str) and revision.isdecimal():
        revision = int(revision)
    else:
        raise ValueError("Revision must be a positive integer or decimal text")
    x["revision"] = revision
    if x["revision"] < 1:
        raise ValueError("Revision must be positive")
    if kind == "membership":
        for k in ("security_id", "market", "ticker", "industry_id", "valid_from", "known_at"):
            if not x.get(k):
                raise ValueError(f"Missing {k} for membership")
        if x["market"] not in ("KR", "US"):
            raise ValueError("Unknown market")
        x["valid_from"] = iso_day(x["valid_from"])
        x["valid_to"] = iso_day(x["valid_to"]) if x.get("valid_to") else None
        if x["valid_to"] and x["valid_to"] <= x["valid_from"]:
            raise ValueError("Invalid membership valid interval")
        x["known_at"] = iso_time(x["known_at"])
    elif kind == "actions":
        for k in ("security_id", "action_id", "action_type", "effective_on", "known_at"):
            if not x.get(k):
                raise ValueError(f"Missing {k} for corporate action")
        if x["action_type"] not in EVENTS:
            raise ValueError("Invalid action type")
        x["effective_on"] = iso_day(x["effective_on"])
        x["known_at"] = iso_time(x["known_at"])
        if x["action_type"] == "split":
            x["ratio"] = numeric(x.get("ratio"))
            if x["ratio"] <= 0:
                raise ValueError("Split ratio must be positive")
        elif x["action_type"] == "dividend":
            x["cash_amount"] = numeric(x.get("cash_amount"))
            if x["cash_amount"] < 0:
                raise ValueError("Dividend cannot be negative")
    else:
        for k in ("metric", "period_end", "available_at", "value", "unit"):
            if k not in x or x[k] in ("", None):
                raise ValueError(f"Missing {k} for {kind}")
        if kind == "fundamentals":
            if not x.get("security_id"):
                raise ValueError("Missing security_id for fundamental")
        else:
            if not x.get("industry_id"):
                raise ValueError("Missing industry_id for industry fact")
        if x["metric"] not in METRICS and kind == "fundamentals":
            raise ValueError("Unknown fundamental metric")
        if x["metric"] not in ("revenue", "capex", "production", "orders", "employment") and kind == "industry":
            raise ValueError("Unknown industry metric")
        x["period_end"] = iso_day(x["period_end"])
        x["available_at"] = iso_time(x["available_at"])
        # period_end may legitimately be later than a forward guidance publication, but
        # those are not realized accounting facts: separate EPS estimates explicitly.
        if x["metric"] != "eps_estimate" and x["period_end"] > x["available_at"][:10]:
            raise ValueError("Realized accounting observation available before period close")
        x["value"] = numeric(x["value"])
        if not isinstance(x["unit"], str) or not x["unit"].strip():
            raise ValueError("Missing unit")
    return x

def natural_key(kind: str, row: dict) -> str:
    base = [row["source_id"]]
    if kind == "membership":
        base += [row["security_id"], row["valid_from"]]
    elif kind == "actions":
        base += [row["security_id"], row["action_id"]]
    elif kind == "fundamentals":
        base += [row["security_id"], row["metric"], row["period_end"]]
    else:
        base += [row["industry_id"], row["metric"], row["period_end"]]
    return "|".join(base + [str(row["revision"])])

def _no_duplicate_keys(pairs: list[tuple[str,Any]]) -> dict:
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate stored PIT JSON key")
        result[key] = value
    return result


def verify_stored_pit_record(
    kind: str, record_key: str, available_at: str, source_id: str,
    provenance: str, payload: str, fingerprint: str,
) -> dict:
    """Prove *internal* first-import integrity before any source can affect PIT.

    It is not a proof that the supplied publisher or acquisition timestamp
    is real. Cross-check each persisted index column against the original
    immutable canonical payload instead of trusting rewritten SQLite cells.
    """
    if kind not in KINDS or provenance not in PROVENANCES:
        raise ValueError("Invalid stored PIT kind or provenance")
    if not isinstance(payload,str) or not isinstance(fingerprint,str):
        raise ValueError("PIT source fingerprint/payload type invalid")
    if sha256(payload.encode("utf-8")).hexdigest() != fingerprint:
        raise ValueError("PIT source fingerprint integrity mismatch")
    try:
        decoded = json.loads(payload,object_pairs_hook=_no_duplicate_keys)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid stored PIT source JSON") from exc
    if not isinstance(decoded,dict):
        raise ValueError("Stored PIT source is not an object")
    expected = json.dumps(decoded,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    if payload != expected:
        raise ValueError("Stored PIT source payload is not canonical")
    normalized=normalize(kind,decoded)
    if decoded != normalized:
        raise ValueError("Stored PIT source is not normalized")
    if not isinstance(source_id,str) or source_id != normalized["source_id"]:
        raise ValueError("Stored PIT source ID and payload identity mismatch")
    if not isinstance(record_key,str) or record_key != natural_key(kind,normalized):
        raise ValueError("Stored PIT natural record_key/identity mismatch")
    timestamp = normalized.get("available_at",normalized.get("known_at"))
    if not isinstance(available_at,str) or timestamp != available_at:
        raise ValueError("Stored PIT availability timestamp mismatch")
    decoded["provenance"]=provenance
    return decoded


class OfflineLedger:
    """Append-only PIT ledger. All operations local to the EraLeader SQLite file."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS offline_records(
            kind TEXT NOT NULL, record_key TEXT NOT NULL,
            available_at TEXT NOT NULL, source_id TEXT NOT NULL,
            provenance TEXT NOT NULL, payload TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY(kind,record_key))""")
        self.db.execute("CREATE INDEX IF NOT EXISTS offline_pit_idx ON offline_records(kind,available_at)")
        self.db.commit()

    @classmethod
    def open_readonly(cls, path: Path) -> "OfflineLedger":
        """Open an existing PIT source without creating tables or modifying bytes."""
        source = Path(path)
        if source.is_symlink() or not source.is_file():
            raise ValueError("Existing non-symlink PIT ledger required")
        instance = cls.__new__(cls)
        instance.path = source
        instance.db = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        instance.db.execute("PRAGMA query_only=ON")
        return instance

    def close(self):
        self.db.close()

    def _apply_rows(self, kind: str, rows: list[dict], provenance: str) -> dict:
        if kind not in KINDS:
            raise ValueError(f"Unknown offline record kind: {kind}")
        if provenance not in PROVENANCES:
            raise ValueError("Explicit provenance required")
        if not isinstance(rows, list):
            raise ValueError("rows must be a list")
        inserts = []
        for raw in rows:
            if not isinstance(raw, dict):
                raise ValueError("Row must be JSON object")
            row = normalize(kind, raw)
            key = natural_key(kind, row)
            when = row.get("available_at", row.get("known_at"))
            encoded = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            fingerprint = sha256(encoded.encode()).hexdigest()
            inserts.append((kind, key, when, row["source_id"], provenance, encoded, fingerprint))
        inserted = 0
        for item in inserts:
            existing = self.db.execute("""SELECT fingerprint FROM offline_records
                WHERE kind=? AND record_key=?""", item[:2]).fetchone()
            if existing:
                if existing[0] != item[-1]:
                    raise ValueError(f"Conflicting revision for {kind}:{item[1]}")
                continue
            self.db.execute("""INSERT INTO offline_records
              (kind,record_key,available_at,source_id,provenance,payload,fingerprint)
              VALUES(?,?,?,?,?,?,?)""", item)
            inserted += 1
        return {"kind": kind, "rows_received": len(rows), "inserted": inserted, "duplicates": len(rows)-inserted}

    def import_rows(self, kind: str, rows: list[dict], provenance: str) -> dict:
        with self.db:
            return self._apply_rows(kind, rows, provenance)

    def import_file(self, path: Path, *, kind: str | None = None, provenance: str | None = None) -> dict:
        path = Path(path)
        if path.suffix.lower() == ".json":
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("schema_version") != "eraleader.offline.v1":
                raise ValueError("Unsupported schema version")
            records = obj.get("records", {})
            if not isinstance(records, dict):
                raise ValueError("Expected records object")
            p = obj.get("provenance")
            if not p:
                raise ValueError("Top-level provenance is required")
            # Single transaction for all types: avoid partial imports when one kind invalid.
            with self.db:
                # Validate all records BEFORE first DB write.
                for ty, rows in records.items():
                    if not isinstance(rows, list):
                        raise ValueError("Each record set must be a list")
                    for row in rows:
                        normalize(ty, row)
                totals = {ty:self._apply_rows(ty, rows, p) for ty,rows in records.items()}
            return totals
        if path.suffix.lower() == ".csv":
            if not kind or not provenance:
                raise ValueError("CSV requires explicit kind and provenance")
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows=list(csv.DictReader(f))
            return {kind:self.import_rows(kind, rows, provenance)}
        raise ValueError("Only CSV/JSON offline imports are supported")

    def snapshot(self, as_of: str, *, market: str) -> dict:
        if market not in ("KR", "US"):
            raise ValueError("KR/US only")
        cutoff = iso_time(as_of)
        # Membership and corporate-action effective_on are exchange-local
        # calendar dates, regardless of the offset used by the caller.
        # Using the input's date leaks tomorrow's US listings for KST callers
        # (and can hide KR listings for New York callers). DST is zone-aware.
        market_zone = ZoneInfo("Asia/Seoul" if market == "KR" else "America/New_York")
        day = datetime.fromisoformat(cutoff).astimezone(market_zone).date().isoformat()
        rows = self.db.execute("""SELECT kind,record_key,available_at,source_id,
                     provenance,payload,fingerprint FROM offline_records
                 WHERE available_at<=? ORDER BY available_at,record_key""",(cutoff,)).fetchall()
        categories = {k:[] for k in KINDS}
        for stored in rows:
            kind=stored[0]
            # Verify persisted content hash AND every indexed source/identity
            # column BEFORE a record can enter a historical research snapshot.
            r=verify_stored_pit_record(*stored)
            categories[kind].append(r)
        # Membership: latest *then-known* historical record per company.
        membership_latest: dict[str,dict] = {}
        ever_known: set[str] = set()
        for row in categories["membership"]:
            if row["market"] != market or row["valid_from"] > day:
                continue
            sec = row["security_id"]
            ever_known.add(sec)
            previous = membership_latest.get(sec)
            # Select the latest then-known version of the latest membership
            # interval *before* applying its valid_to. An amendment that closes
            # an old listing must not resurrect the older open-ended version.
            if previous is None or (row["valid_from"],row["known_at"],row["revision"]) > (
                    previous["valid_from"],previous["known_at"],previous["revision"]):
                membership_latest[sec] = row
        active={sec:row for sec,row in membership_latest.items()
                if not row["valid_to"] or row["valid_to"] > day}
        # Duplicate tickers with concurrent different identities are ambiguous
        # and cannot be silently merged into a single historical price series.
        seen_tickers: dict[str,str] = {}
        for sec,row in active.items():
            tkr = row["ticker"]
            if tkr in seen_tickers and seen_tickers[tkr] != sec:
                raise ValueError(f"Ambiguous overlapping ticker {tkr} in {market}")
            seen_tickers[tkr] = sec
        def most_recent(seq: list[dict], identity: tuple[str,...]) -> list[dict]:
            values: dict[tuple,dict] = {}
            for row in seq:
                key = tuple(row[col] for col in identity)
                old = values.get(key)
                if old is None or (row["available_at"],row["revision"]) > (
                       old["available_at"],old["revision"]):
                    values[key] = row
            return list(values.values())
        latest_action: dict[tuple[str,str],dict] = {}
        for row in categories["actions"]:
            if row["security_id"] not in ever_known:
                continue
            key=(row["security_id"],row["action_id"])
            old=latest_action.get(key)
            if old is None or (row["known_at"],row["revision"]) > (
                    old["known_at"],old["revision"]):
                latest_action[key]=row
        announced_actions=list(latest_action.values())
        known_actions=[r for r in announced_actions if r["effective_on"]<=day]
        pending_actions=[r for r in announced_actions if r["effective_on"]>day]
        delisted={r["security_id"] for r in known_actions
                  if r["action_type"] in ("delist","merger")}
        members={sec:row for sec,row in active.items() if sec not in delisted}
        facts = most_recent(
            [r for r in categories["fundamentals"] if r["security_id"] in members],
            ("security_id","metric","period_end"))
        industries = {r["industry_id"] for r in members.values()}
        industry = most_recent(
            [r for r in categories["industry"] if r["industry_id"] in industries],
            ("industry_id","metric","period_end"))
        all_used = list(members.values()) + known_actions + pending_actions + facts + industry
        return {
            "market": market,"as_of":cutoff, "trading_day":day,"members":members,
            "actions":known_actions,"announced_future_actions":pending_actions,
            "exit_security_ids":sorted(delisted),
            "fundamentals":facts,"industry":industry,
            "quality":{
                "provenances":sorted({row["provenance"] for row in all_used}),
                "historic_membership_pit_verified":False,
                "corporate_actions_complete_verified":False,
                "financial_pit_complete_verified":False,
                "reason":"Input records are not proof of historic source completeness; certification pending",
            },
        }
