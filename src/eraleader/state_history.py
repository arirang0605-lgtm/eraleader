"""Deterministic state history; no retroactive rewriting or duplicate events.

Production inputs must be sourced from verified PIT evidence. Current offline
research JOIN supplies incomplete components, so state remains WATCH.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .states import evaluate_leader_state

class StateHistory:
    def __init__(self,path:Path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS state_history(
           market TEXT NOT NULL,security_id TEXT NOT NULL,as_of TEXT NOT NULL,
           input_hash TEXT NOT NULL,previous TEXT NOT NULL,current TEXT NOT NULL,
           confirmations INTEGER NOT NULL,first_candidate_at TEXT,
           body TEXT NOT NULL,PRIMARY KEY(market,security_id,as_of))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS state_events(
           event_id TEXT PRIMARY KEY,market TEXT NOT NULL,security_id TEXT NOT NULL,
           as_of TEXT NOT NULL,previous TEXT NOT NULL,current TEXT NOT NULL,
           reason TEXT NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def record(self,market:str,as_of:str,observations:list[dict]) -> dict:
        if market not in ("KR","US"):
            raise ValueError("Unsupported market")
        observed=[]
        seen=set()
        for row in observations:
            sec=row["security_id"]
            if sec in seen:raise ValueError("Duplicate security ID within snapshot")
            seen.add(sec)
            enc=json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))
            observed.append((sec,sha256(enc.encode()).hexdigest(),row))
        changes=[]
        with self.db:
            for sec,fingerprint,row in observed:
                existing=self.db.execute("""SELECT input_hash,current,first_candidate_at
                    FROM state_history WHERE market=? AND security_id=? AND as_of=?""",
                    (market,sec,as_of)).fetchone()
                if existing:
                    if existing[0]!=fingerprint:
                        raise ValueError(f"Historical input mutation rejected {sec}@{as_of}")
                    continue
                old=self.db.execute("""SELECT as_of,current,confirmations,first_candidate_at
                    FROM state_history WHERE market=? AND security_id=?
                    ORDER BY as_of DESC LIMIT 1""",(market,sec)).fetchone()
                if old and old[0]>=as_of:
                    raise ValueError(f"Out-of-order state history rejected {sec}@{as_of}")
                previous=old[1] if old else "WATCH"
                streak=(old[2]+1 if old and previous=="POTENTIAL" else 1)
                assessment=evaluate_leader_state(
                    row.get("components",{}),row.get("evidence",{}),
                    previous=previous,continuous_confirmations=streak)
                now=assessment["state"]
                first_seen=(old[3] if old else None)
                if first_seen is None and now in ("POTENTIAL","CONFIRMED"):
                    first_seen=as_of
                body={"market":market,"security_id":sec,"as_of":as_of,
                      "previous":previous,"state":now,"first_candidate_at":first_seen,
                      "reason":assessment["reason"],"score":assessment["total"],
                      "input_hash":fingerprint,"model":"stage4-pit-state-v0.1"}
                self.db.execute("""INSERT INTO state_history
                  (market,security_id,as_of,input_hash,previous,current,confirmations,
                   first_candidate_at,body) VALUES(?,?,?,?,?,?,?,?,?)""",
                   (market,sec,as_of,fingerprint,previous,now,
                    streak if now=="POTENTIAL" else 0,first_seen,
                    json.dumps(body,ensure_ascii=False,sort_keys=True)))
                if now!=previous:
                    event_id=sha256(f"{market}|{sec}|{as_of}|{previous}|{now}".encode()).hexdigest()[:24]
                    self.db.execute("""INSERT INTO state_events
                      (event_id,market,security_id,as_of,previous,current,reason)
                      VALUES(?,?,?,?,?,?,?)""",
                      (event_id,market,sec,as_of,previous,now,assessment["reason"]))
                    changes.append({"event_id":event_id,"security_id":sec,
                                    "previous":previous,"state":now,"as_of":as_of,
                                    "reason":assessment["reason"]})
        return {"market":market,"as_of":as_of,"total":len(observed),
                "new_state_events":changes,
                "status":"LOCAL_RESEARCH_STATE_HISTORY_NOT_CERTIFIED"}

    def history(self,market:str,security_id:str) -> list[dict]:
        rows=self.db.execute("""SELECT body FROM state_history WHERE market=? AND security_id=?
              ORDER BY as_of""",(market,security_id)).fetchall()
        return [json.loads(x[0]) for x in rows]
