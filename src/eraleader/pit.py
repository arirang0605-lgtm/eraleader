"""Point-in-time facts + state/event ledger. SQLite stays within EraLeader."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

def utc_iso(iso: str) -> str:
    t = datetime.fromisoformat(iso.replace("Z","+00:00"))
    if t.tzinfo is None:
        raise ValueError("PIT timestamps require timezone offsets")
    return t.astimezone(timezone.utc).isoformat()

class LocalStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS facts(
           security_id TEXT NOT NULL, metric TEXT NOT NULL, period_end TEXT NOT NULL,
           available_at TEXT NOT NULL, source_id TEXT NOT NULL, revision INTEGER NOT NULL,
           value REAL NOT NULL,
           PRIMARY KEY(security_id, metric, period_end, source_id, revision));
        CREATE TABLE IF NOT EXISTS snapshots(
           run_id TEXT PRIMARY KEY, market TEXT NOT NULL, as_of TEXT NOT NULL,
           body TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
           event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
           security_id TEXT NOT NULL, kind TEXT NOT NULL, as_of TEXT NOT NULL,
           body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(
           event_id TEXT PRIMARY KEY, dry_run_done INTEGER NOT NULL DEFAULT 0);
        """)
        self.db.commit()

    def insert_fact(self, security_id: str, metric: str, period_end: str,
                    available_at: str, source_id: str, revision: int, value: float) -> bool:
        before = self.db.total_changes
        self.db.execute("""INSERT OR IGNORE INTO facts
        (security_id,metric,period_end,available_at,source_id,revision,value)
        VALUES(?,?,?,?,?,?,?)""",
        (security_id,metric,period_end,utc_iso(available_at),source_id,revision,float(value)))
        self.db.commit()
        return self.db.total_changes > before

    def facts_asof(self, as_of: str) -> dict[tuple[str,str,str],float]:
        """Latest *available* revision only. Future edits cannot change past."""
        limit = utc_iso(as_of)
        rows=self.db.execute("""
        SELECT security_id,metric,period_end,value FROM (
          SELECT *,ROW_NUMBER() OVER(
            PARTITION BY security_id,metric,period_end
            ORDER BY available_at DESC, revision DESC) AS rank
          FROM facts WHERE available_at<=?
        ) WHERE rank=1""",(limit,)).fetchall()
        return {(s,m,p):v for s,m,p,v in rows}

    def save_snapshot(self, run_id: str, market: str, as_of: str,
                      body: dict, events: list[dict]) -> bool:
        before=self.db.total_changes
        with self.db:
            self.db.execute("""INSERT OR IGNORE INTO snapshots
                  (run_id,market,as_of,body,created_at) VALUES(?,?,?,?,?)""",
                  (run_id,market,as_of,json.dumps(body,ensure_ascii=False,sort_keys=True),
                   datetime.now(timezone.utc).isoformat()))
            for ev in events:
                self.db.execute("""INSERT OR IGNORE INTO events
                    (event_id,run_id,security_id,kind,as_of,body)
                    VALUES (?,?,?,?,?,?)""",
                    (ev["event_id"],run_id,ev["security_id"],ev["kind"],
                     ev.get("recorded_at_date",as_of),
                     json.dumps(ev,ensure_ascii=False,sort_keys=True)))
                self.db.execute("INSERT OR IGNORE INTO outbox(event_id) VALUES (?)",(ev["event_id"],))
        return self.db.total_changes > before

    def recent(self, market: str) -> dict | None:
        row=self.db.execute("SELECT body FROM snapshots WHERE market=? ORDER BY as_of DESC,created_at DESC LIMIT 1",(market,)).fetchone()
        return json.loads(row[0]) if row else None

    def events(self, *, pending_only: bool = False) -> list[dict]:
        q="""SELECT e.body FROM events e JOIN outbox o USING(event_id)"""
        if pending_only: q+=" WHERE o.dry_run_done=0"
        q+=" ORDER BY e.as_of,e.event_id"
        return [json.loads(r[0]) for r in self.db.execute(q)]

    def mark_dry_run(self, event_id: str) -> None:
        with self.db:self.db.execute("UPDATE outbox SET dry_run_done=1 WHERE event_id=?",(event_id,))

    def close(self) -> None:
        self.db.close()
