"""Offline provider-neutral PIT bundle adapter: no API, no publisher certification.

Accept only locally staged JSONL source bytes with a sha256 manifest, then
reuse OfflineLedger's append-only normalized storage. Register the *actual
local first-ingestion time* atomically with imported records. Replaying a
historical vendor file today NEVER proves it was available back then.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3

from .frozen_holdout import _stamp
from .offline_pit import (
    KINDS, OfflineLedger, natural_key, normalize, verify_stored_pit_record
)

BUNDLE_SCHEMA="eraleader.provider_pit_bundle.v1"
INTAKE_STATUS="LOCAL_PROVIDER_PIT_BUNDLE_IMPORTED_NOT_CERTIFIED"
PREFLIGHT_STATUS="LOCAL_PROVIDER_PIT_BUNDLE_PREFLIGHT_NOT_CERTIFIED"
ASOF_STATUS="LOCAL_PROVIDER_PIT_FIRST_REGISTRATION_ASOF_NOT_CERTIFIED"
SHA=re.compile(r"[0-9a-f]{64}\Z")
BASENAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,90}\.jsonl\Z")
MANIFEST_KEYS={
    "schema_version","market","source_id","publisher_id_claimed",
    "vintage_id","retrieved_at_claimed","streams",
}
STREAM_KEYS={"kind","file","sha256","record_count"}
MAX_MANIFEST_BYTES=50_000
MAX_STREAM_BYTES=20_000_000
MAX_ROWS_PER_STREAM=100_000
FIELDS={
    "membership":{"source_id","revision","security_id","market","ticker",
                  "industry_id","valid_from","valid_to","known_at"},
    "actions":{"source_id","revision","security_id","action_id",
               "action_type","effective_on","known_at","ratio","cash_amount"},
    "fundamentals":{"source_id","revision","security_id","metric","period_end",
                    "available_at","value","unit"},
    "industry":{"source_id","revision","industry_id","metric","period_end",
                "available_at","value","unit"},
}
REQUIRED={
    "membership":{"source_id","revision","security_id","market","ticker",
                  "industry_id","valid_from","known_at"},
    "actions":{"source_id","revision","security_id","action_id","action_type",
               "effective_on","known_at"},
    "fundamentals":FIELDS["fundamentals"],
    "industry":FIELDS["industry"],
}


def _unique(pairs: list[tuple[str,object]]) -> dict:
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate provider bundle JSON key")
        result[key]=value
    return result


def _json(raw: bytes) -> object:
    try:
        return json.loads(raw,object_pairs_hook=_unique,
                          parse_constant=lambda x:(_ for _ in ()).throw(
                              ValueError("Nonfinite provider JSON numeric")))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid or duplicate provider bundle JSON source") from exc


def _now(clock: datetime | None) -> datetime:
    current=clock if clock is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Provider ingestion must use an aware OS UTC clock")
    return current.astimezone(timezone.utc)


def _text(item:dict,key:str) -> str:
    value=item.get(key)
    if not isinstance(value,str) or not value.strip() or len(value)>150:
        raise ValueError("Missing or malformed provider "+key)
    return value


def _read_bundle(manifest_file: Path, *, now: datetime) -> tuple[dict,dict[str,list],dict]:
    """Fully validate raw source bytes BEFORE any mutation of a target SQLite."""
    manifest=Path(manifest_file)
    if (manifest.is_symlink() or manifest.parent.is_symlink()
            or not manifest.is_file() or
            not 0 < manifest.stat().st_size <= MAX_MANIFEST_BYTES):
        raise ValueError("Missing or symlinked/oversized provider bundle manifest")
    raw=manifest.read_bytes()
    obj=_json(raw)
    if (not isinstance(obj,dict) or set(obj)!=MANIFEST_KEYS
            or obj.get("schema_version")!=BUNDLE_SCHEMA
            or obj.get("market") not in ("KR","US")):
        raise ValueError("Invalid provider manifest schema/market/fields")
    source=_text(obj,"source_id")
    _text(obj,"publisher_id_claimed")
    _text(obj,"vintage_id")
    retrieved=_stamp(obj["retrieved_at_claimed"])
    if retrieved > now:
        raise ValueError("Claimed provider retrieval is in the future of local ingest clock")
    streams=obj["streams"]
    if not isinstance(streams,list) or not 1<=len(streams)<=len(KINDS):
        raise ValueError("Provider bundle requires 1..4 distinct source kinds")
    rows:dict[str,list]={}
    seen_file=set()
    root=manifest.parent.resolve()
    total=0
    chrono:dict[tuple[str,str],list[tuple[int,datetime]]]=defaultdict(list)
    for stream in streams:
        if not isinstance(stream,dict) or set(stream)!=STREAM_KEYS:
            raise ValueError("Invalid provider stream schema")
        kind=stream.get("kind")
        if kind not in KINDS or kind in rows:
            raise ValueError("Duplicate or unsupported provider source kind")
        file=_text(stream,"file")
        if (not BASENAME.fullmatch(file) or file.startswith(".")
                or file in seen_file):
            raise ValueError("Unsafe or duplicate provider JSONL file basename")
        seen_file.add(file)
        expected=_text(stream,"sha256")
        if not SHA.fullmatch(expected):
            raise ValueError("Invalid provider source SHA256")
        expected_count=stream["record_count"]
        if type(expected_count) is not int or not 1<=expected_count<=MAX_ROWS_PER_STREAM:
            raise ValueError("Invalid provider source stream record_count")
        path=root/file
        if (path.is_symlink() or not path.is_file() or
                path.resolve().parent!=root or
                not 0<path.stat().st_size<=MAX_STREAM_BYTES):
            raise ValueError("Missing/symlink/oversized provider JSONL source")
        blob=path.read_bytes()
        if sha256(blob).hexdigest()!=expected:
            raise ValueError("Provider source bytes SHA256 mismatch")
        parts=blob.splitlines(keepends=True)
        if len(parts)!=expected_count:
            raise ValueError("Provider source JSONL row_count mismatch")
        batch=[]
        keys=set()
        for line in parts:
            if not line.strip() or len(line)>2_000_000:
                raise ValueError("Empty/oversized provider JSONL row")
            entry=_json(line)
            if (not isinstance(entry,dict) or
                    not REQUIRED[kind].issubset(entry) or
                    not set(entry).issubset(FIELDS[kind])):
                raise ValueError("Unsupported or missing provider source row fields")
            if entry.get("source_id")!=source:
                raise ValueError("Provider source_id disagrees with manifest")
            for idfield in ("source_id","security_id","industry_id",
                            "ticker","action_id","metric"):
                if idfield in entry:
                    identifier=entry[idfield]
                    if (type(identifier) is not str or
                            not identifier.strip() or
                            "|" in identifier or any(ord(c)<32 for c in identifier)):
                        raise ValueError("Invalid provider identity/key field delimiter or type")
            if kind=="membership" and entry.get("market")!=obj["market"]:
                raise ValueError("Provider membership market disagrees with manifest")
            # Disable an unrecognized action's optional cash/ratio fields,
            # preventing a synthetic delist payout from being silently trusted.
            if kind=="actions":
                event=entry.get("action_type")
                allowed_extra=(
                    {"ratio"} if event=="split" else
                    {"cash_amount"} if event=="dividend" else set()
                )
                if set(entry)-REQUIRED[kind]-allowed_extra:
                    raise ValueError("Invalid corporate action optional fields")
            if (kind=="membership" and
                    not isinstance(entry.get("security_id"),str)):
                raise ValueError("Invalid provider permanent security_id")
            record=normalize(kind,entry)
            pub=_stamp(record.get("known_at",record.get("available_at")))
            if pub > retrieved:
                raise ValueError("Provider row available later than claimed retrieval")
            identity=natural_key(kind,record)
            if identity in keys:
                raise ValueError("Duplicate immutable provider record revision")
            keys.add(identity)
            base=identity.rsplit("|",1)[0]
            chrono[(kind,base)].append((record["revision"],pub))
            batch.append(record)
            total+=1
        rows[kind]=batch
    if "membership" not in rows:
        raise ValueError("Provider bundle requires permanent membership identity stream")
    for key,historical in chrono.items():
        sequence=sorted(historical)
        if any(after[1]<before[1] for before,after in zip(sequence,sequence[1:])):
            raise ValueError("Provider revision chronology goes backwards")
    members={row["security_id"] for row in rows["membership"]}
    industry_ids={row["industry_id"] for row in rows["membership"]}
    for kind in ("actions","fundamentals"):
        for record in rows.get(kind,[]):
            if record["security_id"] not in members:
                raise ValueError("Provider action/fundamental issuer missing from membership batch")
    for record in rows.get("industry",[]):
        if record["industry_id"] not in industry_ids:
            raise ValueError("Provider industry fact not linked to any declared membership")
    # One locally claimed source must not reuse a ticker simultaneously for
    # different issuer IDs. Full historical intervals still need source PIT.
    membership=rows["membership"]
    for i,a in enumerate(membership):
        for b in membership[i+1:]:
            if (a["security_id"]!=b["security_id"] and
                    a["ticker"]==b["ticker"]):
                start_a,end_a=a["valid_from"],a.get("valid_to") or "9999-12-31"
                start_b,end_b=b["valid_from"],b.get("valid_to") or "9999-12-31"
                if start_a<end_b and start_b<end_a:
                    raise ValueError("Ambiguous overlapping provider ticker-to-issuer identity")
    digest=sha256(raw).hexdigest()
    assert total==sum(map(len,rows.values()))
    report={
        "status":PREFLIGHT_STATUS,
        "bundle_sha256":digest,
        "market":obj["market"],
        "source_id":source,
        "publisher_id_claimed":obj["publisher_id_claimed"],
        "vintage_id":obj["vintage_id"],
        "retrieved_at_claimed_utc":retrieved.isoformat(),
        "by_kind_received":{kind:len(rows.get(kind,[])) for kind in KINDS},
        "rows_received":total,
        "issuer_identity_independently_verified":False,
        "licensed_official_feed_verified":False,
        "ready_to_promote_leaders":False,
        "historic_pit_certified":False,
        "original_source_bytes_in_report":False,
        "warning":"Local SHA checks and claimed issuer/source dates are not independent PIT proof.",
    }
    return report,rows,obj


def inspect_provider_bundle(manifest_file:Path, *,
                            clock:datetime|None=None) -> dict:
    report,_,_=_read_bundle(manifest_file,now=_now(clock))
    return report


def _ensure_receipts(db:sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS provider_ingest_receipts (
        bundle_sha256 TEXT PRIMARY KEY,
        market TEXT NOT NULL,
        source_id TEXT NOT NULL,
        vintage_id TEXT NOT NULL,
        publisher_id_claimed TEXT NOT NULL,
        retrieved_at_claimed_utc TEXT NOT NULL,
        first_registered_at_utc TEXT NOT NULL,
        row_keys_sha256 TEXT NOT NULL,
        by_kind_json TEXT NOT NULL,
        UNIQUE(market,source_id,vintage_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS provider_ingest_rows (
        bundle_sha256 TEXT NOT NULL,
        kind TEXT NOT NULL,
        record_key TEXT NOT NULL,
        normalized_sha256 TEXT NOT NULL,
        PRIMARY KEY (bundle_sha256,kind,record_key)
    )""")


def _receipt_rows_hash(rows:dict[str,list]) -> str:
    keys=sorted([kind+"|"+natural_key(kind,item)+"|"+
                 sha256(json.dumps(item,sort_keys=True,ensure_ascii=False,
                                   separators=(",",":")).encode()).hexdigest()
                 for kind,items in rows.items() for item in items])
    return sha256(json.dumps(keys,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def _verify_registered_bundle_rows(db:sqlite3.Connection,bundle_sha256:str,
                                   expected_digest:str,expected_count:int) -> None:
    recorded=db.execute(
        """SELECT kind,record_key,normalized_sha256 FROM provider_ingest_rows
           WHERE bundle_sha256=? ORDER BY kind,record_key""",
        (bundle_sha256,)
    ).fetchall()
    if len(recorded)!=expected_count:
        raise ValueError("Provider first-import receipt row count mismatch")
    descriptions=[]
    for kind,key,claimed_sha in recorded:
        if (kind not in KINDS or not isinstance(key,str)
                or not isinstance(claimed_sha,str) or not SHA.fullmatch(claimed_sha)):
            raise ValueError("Malformed provider first-import receipt row")
        stored=db.execute(
            """SELECT kind,record_key,available_at,source_id,
                      provenance,payload,fingerprint
               FROM offline_records WHERE kind=? AND record_key=?""",
            (kind,key)
        ).fetchone()
        if stored is None:
            raise ValueError("Provider first-import receipt references missing PIT row")
        verified=verify_stored_pit_record(*stored)
        if verified["provenance"]!="user_supplied" or stored[-1]!=claimed_sha:
            raise ValueError("Provider first-import receipt row digest/provenance mismatch")
        descriptions.append(kind+"|"+key+"|"+claimed_sha)
    digest=sha256(json.dumps(sorted(descriptions),sort_keys=True,
                             separators=(",",":")).encode()).hexdigest()
    if digest!=expected_digest:
        raise ValueError("Provider first-import receipt digest mismatch")


def import_provider_bundle(manifest_file: Path, target_ledger:Path, *,
                           clock: datetime|None=None) -> dict:
    """Atomic append of fully checked normalized files plus first-ingest receipt.

    All accepted provider rows are permanently tagged 'user_supplied',
    regardless of publisher_id_claimed: no self-attestation elevation.
    """
    now=_now(clock)
    pre,rows,_=_read_bundle(manifest_file,now=now)
    target=Path(target_ledger)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("symlink PIT import target not permitted")
    fingerprint=_receipt_rows_hash(rows)
    ledger=OfflineLedger(target)
    try:
        db=ledger.db
        db.execute("BEGIN IMMEDIATE")
        try:
            _ensure_receipts(db)
            previous=db.execute(
                """SELECT first_registered_at_utc,row_keys_sha256
                   FROM provider_ingest_receipts WHERE bundle_sha256=?""",
                (pre["bundle_sha256"],)
            ).fetchone()
            different_same_vintage=db.execute(
                """SELECT bundle_sha256 FROM provider_ingest_receipts
                   WHERE market=? AND source_id=? AND vintage_id=?""",
                (pre["market"],pre["source_id"],pre["vintage_id"])
            ).fetchone()
            if (different_same_vintage is not None and
                    different_same_vintage[0]!=pre["bundle_sha256"]):
                raise ValueError("Conflicting provider vintage manifest cannot be rewritten")
            if previous:
                _verify_registered_bundle_rows(
                    db,pre["bundle_sha256"],previous[1],pre["rows_received"],
                )
                if previous[1]!=fingerprint:
                    raise ValueError("Recorded provider bundle keys/source digest changed")
                # Check each original persisted normalized record before
                # claiming an idempotent replay.
                for kind,items in rows.items():
                    for row in items:
                        key=natural_key(kind,row)
                        stored=db.execute(
                            """SELECT kind,record_key,available_at,source_id,
                                      provenance,payload,fingerprint
                               FROM offline_records WHERE kind=? AND record_key=?""",
                            (kind,key)
                        ).fetchone()
                        if stored is None:
                            raise ValueError("Previously registered PIT source record missing")
                        restored=verify_stored_pit_record(*stored)
                        if restored["provenance"]!="user_supplied" or any(
                            restored.get(k)!=v for k,v in row.items()
                        ):
                            raise ValueError("Previously registered provider PIT payload changed")
                first_seen=previous[0]
                inserted=0
                status="ALREADY_RECORDED_IDENTICAL_PROVIDER_BUNDLE"
            else:
                inserted=0
                for kind,items in rows.items():
                    for item in items:
                        key=natural_key(kind,item)
                        # A legacy direct/offline import has NO trustworthy
                        # first-import receipt, even if its SHA is identical.
                        prior=db.execute(
                            """SELECT kind,record_key,available_at,source_id,
                                      provenance,payload,fingerprint FROM offline_records
                               WHERE kind=? AND record_key=?""",
                            (kind,key)
                        ).fetchone()
                        if prior:
                            old_receipt=db.execute(
                                """SELECT normalized_sha256 FROM provider_ingest_rows
                                   WHERE kind=? AND record_key=? LIMIT 1""",
                                (kind,key)
                            ).fetchone()
                            if old_receipt is None:
                                raise ValueError("preexisting PIT row lacks provider first-ingest receipt")
                            old_row=verify_stored_pit_record(*prior)
                            expected_sha=sha256(
                                json.dumps(item,sort_keys=True,ensure_ascii=False,
                                           separators=(",",":")).encode()
                            ).hexdigest()
                            if (old_row["provenance"]!="user_supplied" or
                                    prior[-1]!=old_receipt[0] or
                                    expected_sha!=old_receipt[0]):
                                raise ValueError("Conflicting immutable provider PIT record across vintages")
                    result=ledger._apply_rows(kind,items,"user_supplied")
                    inserted+=result["inserted"]
                    for item in items:
                        encoded=json.dumps(item,sort_keys=True,ensure_ascii=False,
                                           separators=(",",":"))
                        db.execute(
                            """INSERT INTO provider_ingest_rows
                               (bundle_sha256,kind,record_key,normalized_sha256)
                               VALUES(?,?,?,?)""",
                            (pre["bundle_sha256"],kind,natural_key(kind,item),
                             sha256(encoded.encode()).hexdigest())
                        )
                first_seen=now.isoformat()
                db.execute(
                    """INSERT INTO provider_ingest_receipts
                       (bundle_sha256,market,source_id,vintage_id,publisher_id_claimed,
                        retrieved_at_claimed_utc,first_registered_at_utc,
                        row_keys_sha256,by_kind_json)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (pre["bundle_sha256"],pre["market"],pre["source_id"],
                     pre["vintage_id"],pre["publisher_id_claimed"],
                     pre["retrieved_at_claimed_utc"],first_seen,
                     fingerprint,json.dumps(pre["by_kind_received"],sort_keys=True))
                )
                status=INTAKE_STATUS
            _verify_registered_bundle_rows(
                db,pre["bundle_sha256"],fingerprint,pre["rows_received"],
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    except sqlite3.IntegrityError as exc:
        raise ValueError("Conflicting provider vintage already registered") from exc
    finally:
        ledger.close()
    return {
        **pre,"status":status,
        "first_registered_at_utc":first_seen,
        "rows_inserted":inserted,
        "rows_duplicate_or_preexisting":pre["rows_received"]-inserted,
        "original_publisher_independently_authenticated":False,
        "source_retrieval_time_independently_attested":False,
        "official_leader_promotions":0,
        "past_retrieval_proven_by_local_hash":False,
    }


def audit_registered_provider_asof(
    target_ledger:Path,bundle_sha256:str, *,
    decision_at:str,clock:datetime|None=None,
) -> dict:
    """Conservative as-of receipt audit, separate from legacy research snapshot.

    Historical records imported only today must never be claimed as real
    pre-decision evidence, even if their self-declared known_at is years old.
    """
    now=_now(clock)
    cutoff=_stamp(decision_at)
    if cutoff>now:
        raise ValueError("Future provider receipt decision cutoff forbidden")
    if not isinstance(bundle_sha256,str) or not SHA.fullmatch(bundle_sha256):
        raise ValueError("Invalid provider bundle SHA256")
    ledger=OfflineLedger.open_readonly(target_ledger)
    try:
        try:
            ledger.db.execute("BEGIN")
            row=ledger.db.execute(
                """SELECT market,source_id,vintage_id,publisher_id_claimed,
                          retrieved_at_claimed_utc,first_registered_at_utc,
                          row_keys_sha256,by_kind_json FROM provider_ingest_receipts
                   WHERE bundle_sha256=?""",
                (bundle_sha256,)
            ).fetchone()
            if row is None:
                raise ValueError("Missing provider bundle first-ingestion receipt")
            registered_counts=_json(row[7].encode())
            if (not isinstance(registered_counts,dict) or
                    set(registered_counts)!=set(KINDS) or
                    any(type(x) is not int or x<0 for x in registered_counts.values())):
                raise ValueError("Corrupted provider first-import receipt count")
            _verify_registered_bundle_rows(
                ledger.db,bundle_sha256,row[6],sum(registered_counts.values())
            )
        except sqlite3.DatabaseError as exc:
            raise ValueError("No original provider first-ingest receipt ledger") from exc
    finally:
        ledger.close()
    market,source,vintage,publisher,claimed,registered,key_hash,counts_json=row
    if market not in ("KR","US") or not SHA.fullmatch(key_hash):
        raise ValueError("Corrupted provider receipt identity")
    claimed_at=_stamp(claimed)
    actual_first=_stamp(registered)
    if actual_first<claimed_at:
        raise ValueError("Provider receipt claimed retrieval after actual first import")
    if actual_first>now:
        raise ValueError("Provider registered first ingestion in the future")
    counts=_json(counts_json.encode())
    if not isinstance(counts,dict) or set(counts)!=set(KINDS):
        raise ValueError("Corrupted provider receipt count map")
    early=claimed_at<=cutoff and actual_first<=cutoff
    return {
        "status":ASOF_STATUS,
        "bundle_sha256":bundle_sha256,
        "market":market,"source_id":source,
        "publisher_id_claimed":publisher,
        "vintage_id":vintage,
        "decision_at_utc":cutoff.isoformat(),
        "retrieved_at_claimed_utc":claimed_at.isoformat(),
        "first_registered_at_utc":actual_first.isoformat(),
        "rows_first_imported_local":sum(counts.values()),
        "eligible_for_contemporaneous_research":early,
        "retrospective_provider_retrieval":claimed_at>cutoff,
        "retrospective_local_ingestion":actual_first>cutoff,
        "original_clock_independently_attested":False,
        "publisher_independently_authenticated":False,
        "historic_universe_pit_certified":False,
        "true_future_leader_precision":None,
        "official_leader_promotions":0,
        "warning":(
            "Local wall clock of first import is not trusted hardware time or "
            "an external source signature. Retrospectively imported history "
            "cannot prove contemporaneous source availability."
        )
    }
