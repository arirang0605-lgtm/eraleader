"""Receipt-pinned DART CFS vintage registry: no retroactive financial revision.

Consumes the existing verify_dart_financial() contract. An original fiscal
report is first known no earlier than BOTH first local receipt and actual
registration time; a new FY receipt never overwrites an earlier vintage.
This local proof does not certify provider first publication or legal class.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import sqlite3
import stat

from .official_dart_financials import verify_dart_financial
from .official_api_pit_bridge import _private_file

SCHEMA = "eraleader.dart_cfs_vintage_registry.v1"
STATUS = "LOCAL_FIRST_RECEIPT_RESEARCH_ONLY_NOT_HISTORIC_PIT_CERTIFIED"
PIN = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"[0-9A-Za-z]{6}\Z")
CORP = re.compile(r"[0-9]{8}\Z")
ACC = re.compile(r"[0-9]{14}\Z")
METRICS = ("revenue", "operating_income", "net_income")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("Timezone-aware timestamp required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid aware timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Naive timestamp rejected")
    return dt.astimezone(timezone.utc)


def _now(clock: datetime | None) -> tuple[datetime, bool]:
    if clock is None:
        return datetime.now(timezone.utc), False
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("Injected clock must be timezone aware")
    return clock.astimezone(timezone.utc), True


def _identity(stock: str, corp: str, fy: int) -> str:
    if (type(stock) is not str or not CODE.fullmatch(stock) or
            type(corp) is not str or not CORP.fullmatch(corp) or
            type(fy) is not int or not 2015<=fy<=2100):
        raise ValueError("Unknown corporate share identifier/year")
    return f"KR|{stock}|{corp}|{fy}|11011|CFS"


class DartCFSVintageRegistry:
    """Append-only independent research log; caller stores first SHA pins."""

    def __init__(self, path: Path, *, read_only: bool = False):
        path = Path(path)
        if (not path.is_absolute() or path.suffix != ".sqlite" or
                path.is_symlink() or any(p.is_symlink() for p in path.parents) or
                not path.parent.is_dir()):
            raise ValueError("Registry requires absolute ordinary SQLite path")
        if path.exists() and not path.is_file():
            raise ValueError("Existing registry must be an ordinary file")
        if read_only and not path.is_file():
            raise ValueError("Cannot query a non-existent sealed local vintage database")
        self.path = path
        self.read_only=read_only
        self.db=(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=30,
                                 isolation_level=None) if read_only
                 else sqlite3.connect(str(path),timeout=30,isolation_level=None))
        if read_only:
            return
        if os.name == "posix":
            os.chmod(path,0o600)
        self.db.execute("""CREATE TABLE IF NOT EXISTS dart_cfs_vintages (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          vintage_sha TEXT UNIQUE NOT NULL,
          identity TEXT NOT NULL,
          first_received_at_utc TEXT NOT NULL,
          registered_at_utc TEXT NOT NULL,
          event_payload_sha TEXT NOT NULL,
          event_payload TEXT NOT NULL,
          preceding_chain_sha TEXT NOT NULL,
          chain_sha TEXT UNIQUE NOT NULL
        )""")
        self.db.execute("""CREATE INDEX IF NOT EXISTS dart_cfs_by_identity
          ON dart_cfs_vintages(identity,seq)""")
        self.db.execute("""CREATE TRIGGER IF NOT EXISTS dart_cfs_no_update
          BEFORE UPDATE ON dart_cfs_vintages BEGIN
          SELECT RAISE(ABORT,'DART CFS vintage ledger cannot update'); END""")
        self.db.execute("""CREATE TRIGGER IF NOT EXISTS dart_cfs_no_delete
          BEFORE DELETE ON dart_cfs_vintages BEGIN
          SELECT RAISE(ABORT,'DART CFS vintage ledger cannot delete'); END""")
        # Some external SSD filesystems temporarily expose a just-created
        # SQLite inode as read-only to the same connection after DDL/chmod.
        # Close the schema-creating handle and reopen before any append.
        self.db.close()
        self.db=sqlite3.connect(str(path),timeout=30,isolation_level=None)
        # Local SQLite integrity is NOT an independent clock or tamper-proof seal.

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _audit(self) -> list[dict]:
        rows=self.db.execute("""SELECT seq,vintage_sha,identity,first_received_at_utc,
            registered_at_utc,event_payload_sha,event_payload,preceding_chain_sha,
            chain_sha FROM dart_cfs_vintages ORDER BY seq""").fetchall()
        preceding="0"*64
        seen=set()
        decoded=[]
        last_registered=None
        for seq,vintage,identity,received,registered,payload_sha,payload,prior,chain in rows:
            if (type(seq) is not int or type(payload) is not str or
                    type(vintage) is not str or not PIN.fullmatch(vintage) or
                    vintage in seen or prior!=preceding or
                    sha256(payload.encode("utf-8")).hexdigest()!=payload_sha):
                raise ValueError("DART vintage registry SHA/chain/identity corrupted")
            body=json.loads(payload)
            if (type(body) is not dict or _canonical(body)!=payload or
                    body.get("schema") != SCHEMA or
                    body.get("vintage_sha") != vintage or
                    body.get("identity") != identity or
                    body.get("first_received_at_utc") != received or
                    body.get("registered_at_utc") != registered or
                    body.get("historical_first_publication_certified") is not False or
                    body.get("prospective_early_discovery_certified") is not False or
                    body.get("registered_clock_simulated") not in (True,False)):
                raise ValueError("DART vintage payload identity/status altered")
            stamp=_aware(registered)
            if (stamp < _aware(received) or
                    (last_registered is not None and stamp<last_registered)):
                raise ValueError("DART vintage retrospective registration detected")
            if _digest({"before":prior,"payload_sha":payload_sha,"seq":seq})!=chain:
                raise ValueError("DART vintage registry chain digest mismatch")
            preceding=chain
            last_registered=stamp
            seen.add(vintage)
            decoded.append(body)
        return decoded

    def register_verified(self, folder: Path, pin: str, *,
                          directory: tuple[Path,str],
                          clock: datetime | None = None) -> dict:
        """Only a genuine pre-existing, receipt-verified DART FY CFS input.

        No ability to pass unverified financial numbers, labels or synthetic
        publication timestamps via the public API.
        """
        if self.read_only:
            raise ValueError("Cannot register source receipts using a read-only registry")
        if type(pin) is not str or not PIN.fullmatch(pin):
            raise ValueError("Externally supplied first receipt SHA required")
        at, simulation=_now(clock)
        entry=verify_dart_financial(Path(folder),pin,decision_at=at,directory=directory)
        if (entry.get("statement")!="CFS" or entry.get("report_code")!="11011" or
                entry.get("pit_certified") is not False):
            raise ValueError("Only unpromoted pinned annual CFS reports accepted")
        identity=_identity(entry["stock_code"],entry["corp_code"],entry["year"])
        accessions=entry.get("report_accessions")
        if (type(accessions) is not list or len(accessions)!=1 or
                type(accessions[0]) is not str or not ACC.fullmatch(accessions[0])):
            raise ValueError("DART FY original requires one published filing accession")
        accession=accessions[0]
        try:
            accession_day=date.fromisoformat(accession[:4]+"-"+accession[4:6]+"-"+accession[6:8])
        except ValueError as exc:
            raise ValueError("Invalid DART filing accession calendar date") from exc
        registered=at.isoformat()
        received=_aware(entry["first_local_received_at_utc"])
        if accession_day > received.date():
            raise ValueError("Filing accession claims a day after first local receipt")
        metrics={}
        for metric in METRICS:
            item=entry["metrics"].get(metric)
            if item is None:
                metrics[metric]=None
            else:
                if (type(item) is not dict or type(item.get("value")) is not int or
                        item.get("unit")!="KRW" or
                        type(item.get("account_id")) is not str):
                    raise ValueError("Invalid audited financial amount/IFRS mapping")
                metrics[metric]={
                    "account_id":item["account_id"],"value":item["value"],
                    "unit":"KRW"
                }
        original_raw=_private_file(Path(folder)/"raw_response.json",0o600)
        vintage=sha256((pin+"|"+sha256(original_raw).hexdigest()).encode()).hexdigest()
        # Build immutable payload after obtaining original receipt-derived info.
        base={
            "schema":SCHEMA,"identity":identity,"vintage_sha":vintage,
            "source_first_receipt_sha256":pin,
            "source_raw_sha256":sha256(original_raw).hexdigest(),
            "stock_code":entry["stock_code"],"corp_code":entry["corp_code"],
            "fiscal_year":entry["year"],"report_code":"11011","statement":"CFS",
            "filing_accession":accession,
            "filing_calendar_date_only":accession_day.isoformat(),
            "first_received_at_utc":received.isoformat(),
            "registered_at_utc":registered,
            "registered_clock_simulated":simulation,
            "financial_metrics":metrics,
            "issuer_share_class_pit_certified":False,
            "historic_revision_history_certified":False,
            "historical_first_publication_certified":False,
            "prospective_early_discovery_certified":False,
            "leader_score_100":None,
        }
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous=self._audit()
            earlier=next((event for event in previous if event["vintage_sha"]==vintage),None)
            if earlier is not None:
                for key in base:
                    if key in ("registered_at_utc","registered_clock_simulated"):
                        continue
                    if base[key]!=earlier[key]:
                        raise ValueError("Original receipt replay differs from first registry payload")
                self.db.execute("COMMIT")
                return {"status":"ORIGINAL_ALREADY_REGISTERED",
                        "new_event":False,"vintage_sha":vintage,
                        "first_registered_at_utc":earlier["registered_at_utc"],
                        "simulated":earlier["registered_clock_simulated"],
                        "official_leaders":0}
            if previous and at<_aware(previous[-1]["registered_at_utc"]):
                raise ValueError("Cannot backdate newly seen DART vintage after later registration")
            if at<received:
                raise ValueError("DART receipt was not available before registry write")
            seq=len(previous)+1
            prior_row=self.db.execute("""SELECT chain_sha FROM dart_cfs_vintages
                                     ORDER BY seq DESC LIMIT 1""").fetchone()
            preceding=prior_row[0] if prior_row else "0"*64
            payload=_canonical(base)
            payload_sha=sha256(payload.encode("utf-8")).hexdigest()
            chain=_digest({"before":preceding,"payload_sha":payload_sha,"seq":seq})
            self.db.execute("""INSERT INTO dart_cfs_vintages(
                vintage_sha,identity,first_received_at_utc,registered_at_utc,
                event_payload_sha,event_payload,preceding_chain_sha,chain_sha)
                VALUES(?,?,?,?,?,?,?,?)""",
                (vintage,identity,base["first_received_at_utc"],registered,
                 payload_sha,payload,preceding,chain))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return {"status":"PROSPECTIVE_VINTAGE_RESEARCH_RECORDED",
                "new_event":True,"vintage_sha":vintage,
                "first_registered_at_utc":registered,"simulated":simulation,
                "official_leaders":0}

    def review_as_of(self, *, decision_at: str,
                     stock_code: str, corp_code: str,
                     fiscal_year: int) -> dict:
        """Never expose a later corrected CFS before its first receipt+registration."""
        cutoff=_aware(decision_at)
        identity=_identity(stock_code,corp_code,fiscal_year)
        all_items=self._audit()
        selected=[r for r in all_items if r["identity"]==identity and
                  _aware(r["registered_at_utc"])<=cutoff and
                  _aware(r["first_received_at_utc"])<=cutoff]
        accessions={r["filing_accession"] for r in selected}
        if not selected:
            outcome="NO_PIT_VINTAGE_AS_OF"
        elif len(selected)==1:
            outcome="SINGLE_LOCAL_VINTAGE_HISTORIC_PUBLICATION_UNKNOWN"
        elif len(accessions)==1:
            outcome="SAME_ACCESSION_CHANGED_UNVERIFIED"
        else:
            outcome="MULTIPLE_ACCESSIONS_REVISION_RECONCILIATION_REQUIRED"
        eligible=selected[0] if len(selected)==1 else None
        return {
            "schema":SCHEMA,"identity":identity,"as_of":cutoff.isoformat(),
            "status":outcome,"registered_vintages_available":len(selected),
            "known_vintages":[{
                "filing_accession":r["filing_accession"],
                "filing_calendar_date_only":r["filing_calendar_date_only"],
                "first_received_at_utc":r["first_received_at_utc"],
                "registered_at_utc":r["registered_at_utc"],
                "vintage_sha":r["vintage_sha"],
                "source_first_receipt_sha256":r["source_first_receipt_sha256"],
                "registered_clock_simulated":r["registered_clock_simulated"]
            } for r in selected],
            "research_metrics":eligible["financial_metrics"] if eligible else None,
            "historical_first_publication_certified":False,
            "issuer_share_class_pit_certified":False,
            "revision_history_complete":False,
            "official_leader":False,"leader_score_100":None,
            "prospective_early_discovery_certified":False,
            "registry_local_not_independently_sealed":True,
        }

    def checksum(self) -> dict:
        items=self._audit()
        last=self.db.execute("""SELECT chain_sha FROM dart_cfs_vintages
                    ORDER BY seq DESC LIMIT 1""").fetchone()
        return {"status":STATUS,"records":len(items),
                "tail_chain_sha256":last[0] if last else "0"*64,
                "historical_first_publication_certified":False,
                "publisher_independent_clock_certified":False}
