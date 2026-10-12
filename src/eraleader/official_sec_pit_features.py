"""SEC CIK-first received companyfacts/submissions as-of research diagnostics.

SEC company facts are NOT a verified full US security universe, share-class
mapping, survivorship-free price series, nor a trading recommendation.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import re

from .official_api_pit_bridge import verified_capture
from .official_api_capture import _canonical

SCHEMA = "eraleader.sec_original_first_pit_financial_diagnostics.v1"
METRICS = {
    "revenue_usd": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet", "Revenues",
    ),
    "operating_income_usd": ("OperatingIncomeLoss",),
    "net_income_usd": ("NetIncomeLoss",),
    "diluted_eps_usd_per_share": ("EarningsPerShareDiluted",),
}
UNITS = {"revenue_usd":"USD", "operating_income_usd":"USD",
         "net_income_usd":"USD", "diluted_eps_usd_per_share":"USD/shares"}
ALLOWED_FORMS = {"10-K","10-Q","10-K/A","10-Q/A"}


def audit_sec_financial_asof(submissions: tuple[Path,str],
                            companyfacts: tuple[Path,str],
                            *, decision_at: str) -> dict:
    """Join SEC filings to company facts, using actual first-local receipt gate."""
    moment=datetime.fromisoformat(decision_at.replace("Z","+00:00"))
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("SEC as-of requires aware timestamp")
    decision=moment.astimezone(timezone.utc)
    sr, sub=verified_capture(submissions[0],"sec-submissions",submissions[1],decision)
    fr, facts=verified_capture(companyfacts[0],"sec-companyfacts",companyfacts[1],decision)
    if (sr["request_value"] != fr["request_value"] or
            int(sub["cik"]) != int(facts["cik"])):
        raise ValueError("SEC submission/companyfacts CIK mismatch")
    recent=sub["filings"]["recent"]
    required=("accessionNumber","acceptanceDateTime","form","filingDate")
    n=len(recent["accessionNumber"])
    if any(type(recent.get(k)) is not list or len(recent[k])!=n for k in required):
        raise ValueError("SEC recent parallel filing arrays incomplete")
    accepted={}
    for accn, stamp, form, filed in zip(*(recent[k] for k in required)):
        if (type(accn) is not str or
                not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}",accn) or
                accn in accepted):
            raise ValueError("SEC duplicate or invalid filing accession")
        try:
            when=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            day=date.fromisoformat(filed)
        except (TypeError,ValueError,AttributeError) as exc:
            raise ValueError("Invalid SEC accession timing") from exc
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("SEC acceptance timestamp must be timezone-aware")
        if when > decision or day > decision.date():
            # A future filing in a whole-document current API is not available
            # for a historical decision and cannot be silently accepted.
            continue
        accepted[accn]={"acceptance_at":when.astimezone(timezone.utc).isoformat(),
                        "form":form,"filed":filed}
    selected=[]
    seen=set()
    unmatched=0
    for name,tags in METRICS.items():
        valid=[]
        for priority,tag in enumerate(tags):
            unit=UNITS[name]
            records=facts.get("facts",{}).get("us-gaap",{}).get(tag,{}).get("units",{}).get(unit,[])
            if type(records) is not list:
                raise ValueError("Malformed SEC XBRL unit container")
            for record in records:
                if type(record) is not dict:
                    raise ValueError("SEC fact row must be object")
                accn=record.get("accn")
                filing=accepted.get(accn)
                if filing is None:
                    unmatched+=1
                    continue
                if record.get("form") != filing["form"] or record.get("filed") != filing["filed"]:
                    raise ValueError("SEC fact filing metadata disagrees with submission")
                if record.get("form") not in ALLOWED_FORMS or filing["form"] not in ALLOWED_FORMS:
                    continue
                try:
                    period_end=date.fromisoformat(record["end"])
                    start=date.fromisoformat(record["start"]) if "start" in record else None
                except (ValueError,TypeError,KeyError) as exc:
                    raise ValueError("SEC financial period invalid") from exc
                val=record.get("val")
                if (type(val) not in (int,float) or not math.isfinite(val) or
                        name=="revenue_usd" and val<0 or
                        period_end>date.fromisoformat(filing["filed"])):
                    raise ValueError("SEC metric numeric or period invalid")
                if start and start>period_end:
                    raise ValueError("SEC financial period starts after it ends")
                valid.append((period_end.isoformat(),
                              start.isoformat() if start else "",
                              filing["acceptance_at"],-priority,
                              {"metric":name,"value":val,"unit":unit,"start":str(start) if start else None,
                               "period_end":period_end.isoformat(), "accn":accn,
                               "form":filing["form"],"provider_acceptance_at_utc":filing["acceptance_at"],
                               "effective_available_at_utc":max(
                                  filing["acceptance_at"],
                                  sr["first_local_received_at_utc"],
                                  fr["first_local_received_at_utc"]),
                               "prospective_backtest_eligible":False,
                               "issuer_share_class_verified":False}))
        # Historic values can be restated in recent SEC filings. Pick an as-of
        # revision for identical period; never compare annual with quarterly.
        chosen={}
        for end,start,received,neg_priority,item in valid:
            key=(end,start)
            marker=(received,neg_priority)
            if key not in chosen or marker>chosen[key][0]:
                chosen[key]=(marker,item)
        selected += [row for _,row in chosen.values()]
    selected.sort(key=lambda x:(x["metric"],x["period_end"],x["start"] or ""))
    # No model scores are calculated with these observations: US price/company
    # class membership is not verified and SEC 'recent' is not full history.
    return {"schema":SCHEMA,"market":"US","cik":str(sub["cik"]),
            "decision_at":decision.isoformat(),
            "first_receipts":{"sec-submissions":submissions[1],"sec-companyfacts":companyfacts[1]},
            "first_received":{"sec-submissions":sr["first_local_received_at_utc"],
                              "sec-companyfacts":fr["first_local_received_at_utc"]},
            "recent_accessions_count":n,
            "fact_rows_unmatched_to_recent_submissions":unmatched,
            "derived_fact_rows":len(selected),"financial_rows":selected,
            "reporting_complete":False,"historic_universe_pit_verified":False,
            "issuer_share_class_verified":False,
            "financial_first_published_independently_certified":False,
            "us_price_pit_joined":False,
            "official_leaders":0,"pit_certified":False,
            "warning":"SEC recent submissions do not prove complete historic filings; "
                      "local first receipt forbids retrospective live signal credit"}


def save_sec_research(report: dict, folder: Path) -> dict:
    folder=Path(folder)
    if not folder.is_absolute() or folder.is_symlink() or folder.exists():
        raise ValueError("SEC first diagnostic requires a new absolute output folder")
    if (report.get("schema")!=SCHEMA or report.get("pit_certified") is not False or
            report.get("official_leaders")!=0):
        raise ValueError("Invalid SEC research certification gate")
    folder.mkdir(mode=0o700,parents=False)
    raw=_canonical(report)
    (folder/"research.json").write_bytes(raw)
    summary={k:v for k,v in report.items() if k not in ("financial_rows","warning")}
    lines=["<!doctype html><html lang='ko'><meta charset='utf-8'>",
           "<title>SEC 공인 재무자료 PIT 진단</title><body style='font:16px sans-serif'>",
           "<h1>SEC CIK 최초수신 기준 재무 연구</h1>",
           "<p>SEC 실제 공시와 최초 로컬 수신·접수시각 교차확인. 역사적 PIT 및 정식 대장주 판정 미인증.</p>",
           "<p>후보 편입/자동 매수/메시지 발송 없음</p>",
           f"<p>유효 연구용 시점 결합 재무 관측 {report['derived_fact_rows']}건</p>",
           "<table><tr><th>지표</th><th>시작</th><th>종료</th><th>단위</th><th>값</th></tr>"]
    for r in report["financial_rows"][-50:]:
        lines.append("<tr>"+"".join(f"<td>{escape(str(r.get(k) or 'N/A'))}</td>" for k in
                    ("metric","start","period_end","unit","value"))+"</tr>")
    lines.append("</table></body></html>")
    (folder/"index.html").write_text("".join(lines),encoding="utf-8")
    return {"status":"SEC_FIRST_RECEIVED_FINANCIAL_RESEARCH_ONLY",
            "metric_observations":report["derived_fact_rows"],
            "us_price_pit_joined":False,
            "pit_certified":False,
            "official_leaders":0,"messages_sent":0,
            "report_sha256":sha256(raw).hexdigest(),
            "research_json":str(folder/"research.json"),
            "dashboard":str(folder/"index.html")}
