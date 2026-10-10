"""Append-only, forward-registered WATCH research signals.

This records when EraLeader actually saw a screen hit, distinct from the
historical observation date. It never certifies the synthetic/offline input,
nor retroactively credits a 2024 signal merely because a 2024 file is replayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sqlite3

_MARKET_TZ = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
_SIGNAL_KIND = "UNVERIFIED_GROWTH_SCREEN"
_STATUS = "PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED"

def _aware(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Timezone-aware date required")
    return stamp

def _canonical(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)

class ProspectiveRegistry:
    """Immutable local timestamp ledger; OS clock is not a trusted time authority."""

    def __init__(self, path: Path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(target, timeout=30)
        self.db.execute("""CREATE TABLE IF NOT EXISTS prospective_signals (
          signal_id TEXT PRIMARY KEY,
          market TEXT NOT NULL,
          security_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          observed_as_of TEXT NOT NULL,
          recorded_at_utc TEXT NOT NULL,
          source_run_id TEXT NOT NULL,
          model_version TEXT NOT NULL,
          payload_hash TEXT NOT NULL,
          payload TEXT NOT NULL,
          status TEXT NOT NULL,
          UNIQUE(market, security_id, kind, observed_as_of, model_version)
        )""")
        self.db.execute("""CREATE INDEX IF NOT EXISTS prospective_by_recorded
           ON prospective_signals(market, recorded_at_utc)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def record_integrated(self, result: dict, *, clock: datetime | None = None) -> dict:
        """Register each growth-screen WATCH hit at ACTUAL processing time.

        clock is injectable only for deterministic unit tests. It is not
        exposed on the user CLI or used to backdate imported history.
        """
        market = result.get("market")
        if market not in _MARKET_TZ:
            raise ValueError("Unsupported market")
        observation = _aware(result["as_of"])
        recorded = clock if clock is not None else datetime.now(timezone.utc)
        if recorded.tzinfo is None or recorded.utcoffset() is None:
            raise ValueError("Registration clock requires timezone")
        if observation > recorded:
            raise ValueError("Cannot prospectively register a future observation")
        if result.get("pit_certified") is not False:
            raise ValueError("Research registry rejects unvalidated PIT claim")
        source_run = result.get("run_id")
        version = result.get("version")
        if not isinstance(source_run, str) or not source_run or not isinstance(version, str) or not version:
            raise ValueError("Immutable source run and model version required")
        rows = result.get("company_rows")
        if not isinstance(rows, list):
            raise ValueError("Research company_rows list required")
        record_utc = recorded.astimezone(timezone.utc).isoformat()
        items = []
        seen = set()
        for row in rows:
            sec = row.get("security_id")
            if not isinstance(sec, str) or not sec:
                raise ValueError("Permanent security_id required")
            if sec in seen:
                raise ValueError("Duplicate security in same research run")
            seen.add(sec)
            if row.get("market") != market or row.get("as_of") != result["as_of"]:
                raise ValueError("Signal market/date differs from run header")
            if row.get("state") != "WATCH" or row.get("full_score") is not None or row.get("verified_future_leader_candidate") is not False:
                raise ValueError("Unverified signal must remain WATCH with no official score")
            if row.get("research_growth_screen_hit") is not True:
                continue
            basis = {"source_run_id": source_run, "market": market, "as_of": result["as_of"],
                     "model_version": version, "company": row,
                     "provenances": result.get("offline_provenance", [])}
            payload = _canonical(basis)
            digest = sha256(payload.encode("utf-8")).hexdigest()
            identity = f"{market}|{sec}|{_SIGNAL_KIND}|{observation.isoformat()}|{version}"
            signal_id = sha256(identity.encode("utf-8")).hexdigest()
            items.append((signal_id, market, sec, _SIGNAL_KIND, observation.isoformat(),
                          record_utc, source_run, version, digest, payload, _STATUS))
        inserted = 0
        self.db.execute("BEGIN IMMEDIATE")
        with self.db:
            for item in items:
                old = self.db.execute("""SELECT payload_hash,source_run_id
                         FROM prospective_signals WHERE signal_id=?""",
                         (item[0],)).fetchone()
                if old is not None:
                    if old != (item[8], item[6]):
                        raise ValueError("Prospective signal mutation/replacement rejected")
                    continue
                self.db.execute("""INSERT INTO prospective_signals (
                  signal_id,market,security_id,kind,observed_as_of,recorded_at_utc,
                  source_run_id,model_version,payload_hash,payload,status)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""", item)
                inserted += 1
        return {"status": _STATUS, "screen_hits": len(items),
                "new_records": inserted, "duplicates": len(items) - inserted,
                "recorded_at_utc": record_utc,
                "official_leader_signals": 0, "pit_certified": False}

    def first_signals(self, market: str) -> dict:
        """Export first real registration by identity, never first historical file date."""
        if market not in _MARKET_TZ:
            raise ValueError("Unsupported market")
        rows = self.db.execute("""SELECT security_id,observed_as_of,recorded_at_utc,
                  source_run_id,status,kind FROM prospective_signals
                  WHERE market=? ORDER BY recorded_at_utc, observed_as_of, signal_id""",
                  (market,)).fetchall()
        earliest = {}
        for sec, seen, registered, run_id, status, kind in rows:
            if sec in earliest:
                continue
            registered_day = _aware(registered).astimezone(_MARKET_TZ[market]).date()
            observation_day = _aware(seen).astimezone(_MARKET_TZ[market]).date()
            earliest[sec] = {
                "security_id": sec,
                "first_seen": observation_day.isoformat(),
                "recorded_at": registered_day.isoformat(),
                "recorded_at_utc": registered,
                "signal_kind": kind,
                "source_run_id": run_id,
                "status": status,
                "pit_certified": False,
                "historical_backfill": registered_day > observation_day,
            }
        return {
            "market": market,
            "status": _STATUS,
            "first_registration_signals": list(earliest.values()),
            "distinct_companies": len(earliest),
            "total_recorded_observations": len(rows),
            "official_leader_signals": 0,
            "certified_performance": False,
            "warning": "Local OS clock and research-only inputs are NOT independently trusted or PIT-certified.",
        }
