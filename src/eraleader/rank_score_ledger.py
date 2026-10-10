"""Append-only, locally timed numeric rank-score research evidence.

Records submitted numeric scores and original feature-document hashes at
ACTUAL writing time. It cannot attest that scores were *computed* then, that
a publisher/time is authentic, or that a future era leader was discovered.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import re
import sqlite3

from .prospective import _SIGNAL_KIND, _STATUS, _canonical
from .ranked_discovery import _frozen, _time

MARKETS={"KR":ZoneInfo("Asia/Seoul"),"US":ZoneInfo("America/New_York")}
SCHEMA="eraleader.rank_score_observation.v1"
STATUS="LOCAL_NUMERIC_RANK_SCORE_REGISTERED_NOT_PIT_CERTIFIED"
SAFE_NAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.json\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
SCORE_COLS=("market","model_version","security_id","watch_signal_id",
            "watch_payload_sha256","watch_registered_at_utc","score",
            "feature_file","feature_sha256","feature_available_at_utc",
            "score_recorded_at_utc","evidence_hash")


def _now(clock):
    instant=clock if clock is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Score clock must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _data(path: Path, *, limit=1_000_000) -> bytes:
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise ValueError("Missing, linked or oversized rank evidence file")
    return path.read_bytes()


def _hash(record: dict) -> str:
    return sha256(_canonical(record).encode()).hexdigest()


def _watch_proof(db: sqlite3.Connection, market: str, model: str, sec: str,
                 at: datetime, max_lag_days: int) -> dict:
    try:
        rows=db.execute("""SELECT signal_id,kind,observed_as_of,recorded_at_utc,
            source_run_id,payload_hash,payload,status FROM prospective_signals
            WHERE market=? AND model_version=? AND security_id=?
            ORDER BY recorded_at_utc,signal_id""",(market,model,sec)).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Missing or broken original WATCH registry") from exc
    eligible=[]
    zone=MARKETS[market]
    for signal,kind,observed,registered,run_id,digest,payload,status in rows:
        seen=_time(observed)
        stored=_time(registered)
        if kind!=_SIGNAL_KIND or status!=_STATUS or not isinstance(payload,str):
            raise ValueError("Invalid original WATCH signal status")
        expected=sha256(f"{market}|{sec}|{kind}|{observed}|{model}".encode()).hexdigest()
        if signal!=expected or sha256(payload.encode()).hexdigest()!=digest:
            raise ValueError("Original WATCH signal checksum/ID mismatch")
        try:
            basis=json.loads(payload)
        except (ValueError,TypeError) as exc:
            raise ValueError("Original WATCH payload invalid") from exc
        company=basis.get("company") if isinstance(basis,dict) else None
        if (not isinstance(company,dict) or _canonical(basis)!=payload or
            basis.get("market")!=market or basis.get("model_version")!=model or
            basis.get("source_run_id")!=run_id or _time(basis.get("as_of"))!=seen or
            company.get("market")!=market or company.get("security_id")!=sec or
            _time(company.get("as_of"))!=seen or
            company.get("state")!="WATCH" or
            company.get("research_growth_screen_hit") is not True or
            company.get("research_screen_evaluated",True) is not True or
            company.get("full_score") is not None or
            company.get("verified_future_leader_candidate") is not False):
            raise ValueError("Original WATCH source event identity mismatch")
        lag=(stored.astimezone(zone).date()-seen.astimezone(zone).date()).days
        if seen>stored or lag<0:
            raise ValueError("Original WATCH source chronology mismatch")
        if stored<=at and lag<=max_lag_days:
            eligible.append({"watch_signal_id":signal,"watch_payload_sha256":digest,
                             "watch_registered_at_utc":stored.isoformat(),
                             "watch_registered_at":stored})
    if not eligible:
        raise ValueError("No eligible historically registered positive WATCH for scored security")
    return min(eligible,key=lambda row:row["watch_registered_at"])


def _open_watch(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("WATCH registry missing or symlinked")
    return sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)


def register_rank_scores(score_db: Path, watch_db: Path, feature_dir: Path,
                         scores_file: Path, *, market: str, model_version: str,
                         clock: datetime | None=None, max_watch_delay_minutes: int=60,
                         computation_provenance: dict | None=None) -> dict:
    """Save once per (market, model, issuer): reject changed re-submissions.

    Numeric scores arrive from an external scoring computation and are NOT
    generated by this ledger. No CLI option permits backdating OS wall clock.
    """
    if market not in MARKETS or not isinstance(model_version,str) or not model_version:
        raise ValueError("Pinned market and model required")
    if type(max_watch_delay_minutes) is not int or not 0<=max_watch_delay_minutes<=1440:
        raise ValueError("Invalid WATCH-to-score delay")
    if computation_provenance is not None:
        if (not isinstance(computation_provenance,dict) or
            set(computation_provenance)!={"kind","formula_version","formula_sha256"} or
            computation_provenance["kind"]!="LOCAL_FIXED_FOUR_FACTOR" or
            not isinstance(computation_provenance["formula_version"],str) or
            not computation_provenance["formula_version"].strip() or
            not isinstance(computation_provenance["formula_sha256"],str) or
            not SHA.fullmatch(computation_provenance["formula_sha256"])):
            raise ValueError("Invalid locally computed rank formula provenance")
    now=_now(clock)
    folder=Path(feature_dir)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Feature document directory missing or linked")
    source=json.loads(_data(Path(scores_file)))
    if not isinstance(source,list) or not 1<=len(source)<=1000:
        raise ValueError("Score input must contain 1..1000 candidates")
    watch=_open_watch(Path(watch_db))
    records=[]
    seen_ids=set()
    try:
        for row in source:
            if not isinstance(row,dict) or set(row)!={
                    "security_id","score","feature_file","feature_sha256","features_available_at"}:
                raise ValueError("Rank score input schema contains unexpected fields")
            sec=row["security_id"]
            value=row["score"]
            if not isinstance(sec,str) or not sec.strip() or sec in seen_ids:
                raise ValueError("Duplicate or missing scored security")
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:
                raise ValueError("Invalid rank score 0..100")
            seen_ids.add(sec)
            feature_name=row["feature_file"]
            feature_sha=row["feature_sha256"]
            if (not isinstance(feature_name,str) or
                    not SAFE_NAME.fullmatch(feature_name) or feature_name.startswith(".")):
                raise ValueError("Unsafe feature evidence filename")
            if not isinstance(feature_sha,str) or not SHA.fullmatch(feature_sha):
                raise ValueError("Invalid source feature SHA256")
            file=folder/feature_name
            if file.resolve().parent!=folder.resolve():
                raise ValueError("Feature source path escapes directory")
            blob=_data(file)
            if sha256(blob).hexdigest()!=feature_sha:
                raise ValueError("Feature source bytes SHA256 mismatch")
            feature=json.loads(blob)
            if (not isinstance(feature,dict) or
                set(feature)!={"schema","market","model_version","security_id",
                               "available_at","features"} or
                feature["schema"]!="eraleader.rank_feature_document.v1" or
                feature["market"]!=market or feature["model_version"]!=model_version or
                feature["security_id"]!=sec or
                feature["available_at"]!=row["features_available_at"] or
                not isinstance(feature["features"],dict) or not feature["features"]):
                raise ValueError("Feature evidence identity/schema mismatch")
            forbidden=("future","outcome","label","realized","leader_start")
            for key,metric in feature["features"].items():
                if (not isinstance(key,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,70}",key)
                    or any(s in key.lower() for s in forbidden)
                    or type(metric) not in (int,float) or not math.isfinite(metric)):
                    raise ValueError("Forbidden future/invalid feature data")
            available=_time(row["features_available_at"])
            if available>now:
                raise ValueError("Future feature availability forbidden")
            proof=_watch_proof(watch,market,model_version,sec,now,3)
            delay=(now-proof["watch_registered_at"]).total_seconds()
            if delay < 0 or delay>max_watch_delay_minutes*60:
                raise ValueError("Rank score registration too late for original WATCH")
            payload={
                "market":market,"model_version":model_version,"security_id":sec,
                "watch_signal_id":proof["watch_signal_id"],
                "watch_payload_sha256":proof["watch_payload_sha256"],
                "watch_registered_at_utc":proof["watch_registered_at_utc"],
                "score":float(value),"feature_file":feature_name,
                "feature_sha256":feature_sha,
                "feature_available_at_utc":available.isoformat(),
                "score_recorded_at_utc":now.isoformat(),
            }
            if computation_provenance is not None:
                payload["computation_provenance"]=dict(computation_provenance)
            records.append({**payload,"evidence_hash":_hash(payload)})
    finally:
        watch.close()
    target=Path(score_db)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("Symlink rank score ledger forbidden")
    target.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(target,timeout=30)
    inserted=0
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS rank_score_events (
            market TEXT NOT NULL, model_version TEXT NOT NULL, security_id TEXT NOT NULL,
            evidence_hash TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(market,model_version,security_id))""")
        conn.commit()
        with conn:
            for row in records:
                values=(market,model_version,row["security_id"])
                old=conn.execute("""SELECT evidence_hash,payload FROM rank_score_events
                    WHERE market=? AND model_version=? AND security_id=?""",values).fetchone()
                encoded=_canonical({k:v for k,v in row.items() if k!="evidence_hash"})
                if old is not None:
                    old_payload=json.loads(old[1])
                    if old[0]!=_hash(old_payload) or _canonical(old_payload)!=old[1]:
                        raise ValueError("Original rank score ledger corrupted")
                    # Identical score+feature+source event re-run remains idempotent,
                    # regardless of the current new OS clock.
                    if (old_payload["score"]!=row["score"] or
                        old_payload["feature_sha256"]!=row["feature_sha256"] or
                        old_payload["watch_signal_id"]!=row["watch_signal_id"] or
                        old_payload["watch_payload_sha256"]!=row["watch_payload_sha256"] or
                        old_payload["feature_available_at_utc"]!=row["feature_available_at_utc"] or
                        old_payload.get("computation_provenance")!=
                            row.get("computation_provenance")):
                        raise ValueError("Immutable first rank score event mutation rejected")
                    continue
                conn.execute("""INSERT INTO rank_score_events(
                    market,model_version,security_id,evidence_hash,payload)
                    VALUES (?,?,?,?,?)""",(*values,row["evidence_hash"],encoded))
                inserted+=1
    finally:
        conn.close()
    return {
        "status":STATUS,"market":market,"model_version":model_version,
        "supplied_scores":len(records),"new_score_records":inserted,
        "duplicate_score_records":len(records)-inserted,
        "score_recorded_at_utc":now.isoformat(),
        "score_computation_independently_verified":False,
        "original_feature_publication_independently_attested":False,
        "real_leader_prediction_certified":False,"official_leader_promotions":0,
    }


def audit_frozen_rank_scores(frozen_file: Path, score_db: Path,
                             feature_dir: Path, *, sample_limit: int=100) -> dict:
    """Verify that each numeric frozen score was WRITTEN before rank snapshot."""
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Invalid sample limit")
    frozen=_frozen(Path(frozen_file))
    db=Path(score_db)
    if db.is_symlink() or not db.is_file():
        raise ValueError("Missing or linked score observation ledger")
    folder=Path(feature_dir)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Missing feature source directory")
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        try:
            rows=conn.execute("""SELECT security_id,evidence_hash,payload FROM rank_score_events
                WHERE market=? AND model_version=?""",
                (frozen["market"],frozen["model_version"])).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Rank score ledger unreadable") from exc
    finally:
        conn.close()
    indexed={}
    for sec,digest,encoded in rows:
        obj=json.loads(encoded)
        if (sec in indexed or not isinstance(obj,dict) or
            obj.get("security_id")!=sec or
            obj.get("market")!=frozen["market"] or
            obj.get("model_version")!=frozen["model_version"] or
            _canonical(obj)!=encoded or _hash(obj)!=digest):
            raise ValueError("Rank score observation evidence hash or identity corrupted")
        indexed[sec]=obj
    snapshot=_time(frozen["snapshot_at_utc"])
    blockers=[]
    matched=0
    sample=[]
    for row in frozen["ranked_candidates"]:
        sec=row["security_id"]
        original=indexed.get(sec)
        issues=[]
        if original is None:
            issues.append("MISSING_CONTEMPORANEOUS_NUMERIC_SCORE_OBSERVATION")
        else:
            registered=_time(original["score_recorded_at_utc"])
            watch_registered=_time(original["watch_registered_at_utc"])
            if registered>snapshot:
                issues.append("NUMERIC_SCORE_REGISTERED_AFTER_RANK_SNAPSHOT")
            if registered<watch_registered:
                issues.append("NUMERIC_SCORE_PREDATES_WATCH")
            if row["score"]!=original["score"]:
                issues.append("FROZEN_NUMERIC_SCORE_DIFFERS_FROM_LEDGER")
            name=original["feature_file"]
            if not isinstance(name,str) or not SAFE_NAME.fullmatch(name):
                raise ValueError("Invalid recorded feature source name")
            file=folder/name
            if file.is_symlink() or not file.is_file() or file.resolve().parent!=folder.resolve():
                issues.append("SOURCE_FEATURE_FILE_MISSING_OR_UNSAFE")
            elif sha256(_data(file)).hexdigest()!=original["feature_sha256"]:
                issues.append("SOURCE_FEATURE_BYTES_REVISED")
            if _time(original["feature_available_at_utc"])>registered:
                issues.append("FEATURE_AVAILABLE_AFTER_SCORE_RECORDING")
        blockers.extend(f"{sec}:{reason}" for reason in issues)
        if not issues:
            matched+=1
        if len(sample)<sample_limit:
            sample.append({"security_id":sec,"rank":row["rank"],
                           "local_score_event_present":original is not None,
                           "score_evidence_hash":_hash(original) if original else None,
                           "issues":issues})
    return {
        "status":"LOCAL_FROZEN_RANK_SCORE_EVIDENCE_NOT_CERTIFIED",
        "market":frozen["market"],"model_version":frozen["model_version"],
        "frozen_rank_sha256":frozen["content_sha256"],
        "ranked_candidate_count":len(frozen["ranked_candidates"]),
        "local_numeric_score_records_matched":matched,
        "blocker_count":len(set(blockers)),"blockers":sorted(set(blockers)),
        "candidate_sample":sample,
        "rank_score_preexisted_snapshot_locally":not blockers,
        "score_computation_independently_verified":False,
        "issuer_universe_pit_certified":False,
        "real_leader_prediction_certified":False,"official_leader_promotions":0,
        "warning":"Local timestamped score entry proves only local write, not actual computation or original source PIT.",
    }
