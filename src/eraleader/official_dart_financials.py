"""Official single-company DART CFS as-of first receipt and conservative metrics.

This does NOT supply historic publication time, full issuer/share-class PIT,
all-company financial coverage, or official leader promotion.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlencode
import json
import os
import re
import shutil
import tempfile
import uuid
from zoneinfo import ZoneInfo

from .official_api_capture import _http_get, _root, _canonical, _write_new
from .official_api_pit_bridge import _private_file
from .official_dart_corp_directory import verify_dart_corp_directory

SCHEMA="eraleader.dart_financial_first_received.v1"
REPORTS={"11011","11012","11013","11014"}
METRIC_IDS={
    "revenue":("ifrs-full_Revenue","ifrs-full_RevenueFromContractsWithCustomers","ifrs_Revenue"),
    "operating_income":("dart_OperatingIncomeLoss",),
    "net_income":("ifrs-full_ProfitLoss","ifrs_ProfitLoss"),
}


def _unique(pairs):
    d={}
    for k,v in pairs:
        if k in d: raise ValueError("DART financial duplicate JSON key")
        d[k]=v
    return d


def _parse_amount(x):
    if x in (None,"","-"):return None
    if type(x) is not str:
        raise ValueError("DART amount must be decimal text")
    neg=x.startswith("(") and x.endswith(")")
    candidate=x[1:-1] if neg else x
    if not re.fullmatch(r"-?[0-9]{1,18}(,[0-9]{3})*",candidate):
        raise ValueError("DART malformed financial amount")
    return -int(candidate.replace(",","")) if neg else int(candidate.replace(",",""))


def parse_dart_financial(raw: bytes, *, corp_code: str, year: int,
                         report: str, statement: str="CFS") -> dict:
    if type(raw) is not bytes or not 0<len(raw)<=24*1024*1024:
        raise ValueError("DART financial response must be bounded")
    try:
        document=json.loads(raw,object_pairs_hook=_unique)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("DART financial response JSON invalid") from exc
    if type(document) is not dict:
        raise ValueError("DART financial response expected object")
    if document.get("status")=="013":
        if document.get("list") not in (None,[]):
            raise ValueError("DART no-data returned financial rows")
        return {"financial_rows":[],"metrics":{},"report_accessions":[],"status":"NO_DATA"}
    if document.get("status")!="000":
        raise ValueError("DART financial API reported non-success")
    rows=document.get("list")
    if not isinstance(rows,list) or not 0<len(rows)<=5000:
        raise ValueError("DART full statements empty or too many")
    candidates={metric:[] for metric in METRIC_IDS}
    receipts=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("DART financial row not a dict")
        acc=row.get("rcept_no")
        if (row.get("corp_code") != corp_code or
                str(row.get("bsns_year")) != str(year) or
                row.get("reprt_code") != report or
                not isinstance(acc,str) or not re.fullmatch(r"[0-9]{14}",acc)):
            raise ValueError("DART financial issuer, report or receipt mismatch")
        receipts.add(acc)
        if row.get("fs_div") not in (None,statement):
            raise ValueError("DART financial consolidated/standalone mixed")
        if row.get("sj_div") not in ("IS","CIS"):
            continue
        if row.get("currency","KRW")!="KRW":
            continue
        if row.get("account_detail") not in (None,"","-"):
            continue
        aid=row.get("account_id")
        for metric,ids in METRIC_IDS.items():
            if aid in ids:
                value=_parse_amount(row.get("thstrm_amount"))
                if value is not None:
                    candidates[metric].append((ids.index(aid),value,aid))
    if len(receipts)!=1:
        raise ValueError("DART financial multiple report revisions mixed")
    metrics={}
    for metric,items in candidates.items():
        if not items:continue
        priority=min(x[0] for x in items)
        winners={(value,aid) for order,value,aid in items if order==priority}
        if len(winners)!=1:
            raise ValueError("DART ambiguous duplicate financial accounts")
        value,account_id=next(iter(winners))
        metrics[metric]={"value":value,"unit":"KRW","account_id":account_id}
    return {"status":"FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY",
            "financial_rows":len(rows),"report_accessions":sorted(receipts),
            "metrics":metrics}


def capture_dart_financial(private_root: Path, *,
                           stock_code: str, directory: tuple[Path,str],
                           year: int, report: str, creds: dict,
                           statement: str="CFS", fetch=None, clock=None) -> dict:
    private_root=_root(private_root)
    observed_at=(clock or (lambda:datetime.now(timezone.utc)))()
    if observed_at.tzinfo is None:
        raise ValueError("DART financial API requires aware now")
    if type(stock_code) is not str or not re.fullmatch(r"[A-Za-z0-9]{6}",stock_code):
        raise ValueError("Invalid target stock code")
    if type(year) is not int or not 2015<=year<=observed_at.year or report not in REPORTS:
        raise ValueError("Invalid DART business year or report code")
    if statement not in ("CFS","OFS"):
        raise ValueError("Invalid financial statement variant")
    code_directory=verify_dart_corp_directory(*directory,decision_at=observed_at)
    if stock_code not in code_directory["mapping"]:
        raise ValueError("DART stock_code missing or ambiguous in first directory")
    corp_code=code_directory["mapping"][stock_code]
    key=creds.get("ERALEADER_DART_API_KEY")
    if type(key) is not str or not re.fullmatch(r"[A-Za-z0-9]{40}",key):
        raise ValueError("DART key unavailable")
    url="https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?"+urlencode({
        "crtfc_key":key,"corp_code":corp_code,
        "bsns_year":str(year),"reprt_code":report,"fs_div":statement})
    raw=(fetch or _http_get)(url,{"Accept":"application/json","User-Agent":"EraLeader/0.1"})
    audited=parse_dart_financial(raw,corp_code=corp_code,year=year,
                                 report=report,statement=statement)
    first=(clock or (lambda:datetime.now(timezone.utc)))()
    if first.tzinfo is None or first<observed_at:
        raise ValueError("DART financial receipt timestamp nonmonotonic")
    timestamp=first.astimezone(timezone.utc).isoformat()
    metadata={
        "schema":SCHEMA,"source":"dart-financial-cfs","stock_code":stock_code,
        "corp_code":corp_code,"source_directory_sha256":directory[1],
        "bsns_year":year,"reprt_code":report,"statement":statement,
        "raw_sha256":sha256(raw).hexdigest(),"raw_length":len(raw),
        "first_local_received_at_utc":timestamp,
        "financial_quality":audited["status"],
        "reported_row_count":audited["financial_rows"],
        "observed_account_count":len(audited["metrics"]),
        "report_accessions":audited["report_accessions"],
        "historic_publication_time_certified":False,
        "issuer_share_class_pit_certified":False,
        "official_leaders":0,
    }
    evidence=_canonical(metadata)
    stage=Path(tempfile.mkdtemp(prefix=".dart_finstage_",dir=private_root))
    target=private_root/("dart_fin_"+uuid.uuid4().hex)
    try:
        os.chmod(stage,0o700)
        _write_new(stage/"raw_response.json",raw)
        _write_new(stage/"first_receipt.json",evidence)
        os.replace(stage,target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {"status":audited["status"],"capture_id":target.name,
            "first_receipt_sha256":sha256(evidence).hexdigest(),
            "stock_code":stock_code,"year":year,"report_code":report,
            "observed_metrics":len(audited["metrics"]),
            "pit_certified":False}


def verify_dart_financial(folder: Path, pin: str, *, decision_at: datetime,
                          directory: tuple[Path,str]) -> dict:
    import stat
    folder=Path(folder)
    if (not folder.is_absolute() or folder.is_symlink() or
            stat.S_IMODE(folder.stat().st_mode)!=0o700 or
            not re.fullmatch(r"[0-9a-f]{64}",pin)):
        raise ValueError("DART financial owner-only first SHA required")
    evidence=_private_file(folder/"first_receipt.json",0o600)
    raw=_private_file(folder/"raw_response.json",0o600)
    if sha256(evidence).hexdigest()!=pin:
        raise ValueError("DART financial original first receipt tampered")
    metadata=json.loads(evidence)
    if (metadata.get("schema")!=SCHEMA or
            metadata.get("raw_sha256")!=sha256(raw).hexdigest() or
            metadata.get("raw_length")!=len(raw) or
            metadata.get("source_directory_sha256")!=directory[1] or
            metadata.get("official_leaders")!=0):
        raise ValueError("DART financial raw-source lineage corrupt")
    available=datetime.fromisoformat(metadata["first_local_received_at_utc"])
    if available.tzinfo is None or decision_at.tzinfo is None or available>decision_at:
        raise ValueError("DART financial not locally available at decision")
    d=verify_dart_corp_directory(*directory,decision_at=decision_at)
    if d["mapping"].get(metadata["stock_code"])!=metadata["corp_code"]:
        raise ValueError("DART financial original corporation identity diverged")
    result=parse_dart_financial(raw,corp_code=metadata["corp_code"],
                                year=metadata["bsns_year"],report=metadata["reprt_code"],
                                statement=metadata["statement"])
    if (result["status"]!=metadata["financial_quality"] or
            result["financial_rows"]!=metadata["reported_row_count"] or
            sorted(result["report_accessions"])!=metadata["report_accessions"] or
            len(result["metrics"])!=metadata["observed_account_count"]):
        raise ValueError("DART financial row count or metrics changed")
    if {p.name for p in folder.iterdir()}!={"raw_response.json","first_receipt.json"}:
        raise ValueError("DART financial unexpected original")
    return {**result, "stock_code":metadata["stock_code"],
            "corp_code":metadata["corp_code"],
            "year":metadata["bsns_year"],"report_code":metadata["reprt_code"],
            "statement":metadata["statement"],
            "first_local_received_at_utc":available.isoformat(),
            "pit_certified":False}


def annual_growth_diagnostic(previous: dict,current: dict) -> dict:
    if (previous["stock_code"]!=current["stock_code"] or
            previous["corp_code"]!=current["corp_code"] or
            previous["report_code"]!="11011" or current["report_code"]!="11011" or
            previous["year"]+1!=current["year"]):
        raise ValueError("DART annual growth needs consecutive audited CFS years")
    metrics={}
    for metric in ("revenue","operating_income","net_income"):
        old=previous["metrics"].get(metric,{}).get("value")
        new=current["metrics"].get(metric,{}).get("value")
        metrics[metric+"_yoy"]=(new/abs(old)-1 if old and new is not None and old>0
                                else None)
    return {"stock_code":current["stock_code"],"year":current["year"],
            "research_metrics":metrics,
            "issuer_share_class_pit_certified":False,
            "prospective_backtest_eligible":False}


def annual_acceleration_diagnostic(
        past: dict, middle: dict, current: dict, *,
        decision_at: datetime) -> dict:
    """3 consecutive verified CFS originals, strictly research only.

    The two annual growth rates are from different original fiscal reports,
    not a future retrospective 'thstrm_amount' copied from a later filing.
    Comparison is allowed only once all three original local receipts existed.
    Later DART corrections and historic market issuer/class completeness are
    NOT certified merely by this capture/receipt check.
    """
    if decision_at.tzinfo is None or decision_at.utcoffset() is None:
        raise ValueError("Annual acceleration needs a timezone-aware decision")
    three=(past,middle,current)
    identity={(r.get("stock_code"),r.get("corp_code"),
               r.get("report_code"),r.get("statement")) for r in three}
    if (len(identity)!=1 or
            any(r.get("report_code")!="11011" or r.get("statement")!="CFS"
                or r.get("pit_certified") is not False for r in three)):
        raise ValueError("Annual acceleration issuer/report/statement PIT conflict")
    years=[r.get("year") for r in three]
    if (any(type(year) is not int for year in years) or
            years[1]!=years[0]+1 or years[2]!=years[1]+1):
        raise ValueError("Annual acceleration needs three consecutive report years")
    seen_accessions=set()
    decision=decision_at.astimezone(timezone.utc)
    local_received=[]
    for item in three:
        stamp=datetime.fromisoformat(
            item["first_local_received_at_utc"].replace("Z","+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None or stamp>decision:
            raise ValueError("Future/naive annual CFS receipt cannot enter decision")
        local_received.append(stamp.isoformat())
        acc=item.get("report_accessions")
        if (type(acc) is not list or len(acc)!=1 or
                type(acc[0]) is not str or not re.fullmatch(r"[0-9]{14}",acc[0]) or
                acc[0] in seen_accessions):
            raise ValueError("Invalid or repeated annual CFS filing accession")
        seen_accessions.add(acc[0])
    # Existing 2-year function is the single authoritative value mapper.
    prior=annual_growth_diagnostic(past,middle)
    latest=annual_growth_diagnostic(middle,current)
    delta={}
    for metric in ("revenue","operating_income","net_income"):
        name=metric+"_yoy"
        before=prior["research_metrics"][name]
        now=latest["research_metrics"][name]
        delta[metric+"_yoy_acceleration"]=(
            round(now-before,10) if before is not None and now is not None
            else None)
    return {
        "stock_code":current["stock_code"], "corp_code":current["corp_code"],
        "year":current["year"], "annual_comparison_years":years,
        "previous_yoy":prior["research_metrics"],
        "research_metrics":latest["research_metrics"],
        "research_acceleration":delta,
        "first_local_received_at_utc":max(local_received),
        "read_only":True,
        "historic_publication_time_certified":False,
        "issuer_share_class_pit_certified":False,
        "original_report_revision_history_certified":False,
        "prospective_backtest_eligible":False,
        "official_leader":False,
        "interpretation":"THREE_YEAR_RESEARCH_ONLY_NOT_AUTHORITATIVE_PIT",
    }
