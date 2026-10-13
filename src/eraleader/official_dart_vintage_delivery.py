"""Read-only FY CFS first-seen/revision-status research dashboard sidecar.

Requires already-verified KRX/DART snapshot + independently recorded local
vintage ledger. Never rewrites WATCH ranking, alerts or original reports.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import os
import re

from .delivery import BASE_CSS
from .official_dart_vintage_registry import DartCFSVintageRegistry, _digest, _canonical, _aware

SCHEMA="eraleader.dart_cfs_vintage_dashboard.v1"
HASH=re.compile(r"[0-9a-f]{64}\Z")


def audit_dart_cfs_vintages(snapshot: dict, ledger: Path) -> dict:
    if not isinstance(snapshot,dict) or snapshot.get("source_market")!="KR":
        raise ValueError("DART vintage link only valid on KR research snapshot")
    evidence=snapshot.get("official_api_evidence")
    if (not isinstance(evidence,dict) or evidence.get("official_leaders")!=0
            or evidence.get("historic_universe_pit_verified") is not False
            or evidence.get("issuer_share_class_verified") is not False
            or snapshot.get("classification_quality")!="PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("Only unpromoted first-received KRX/DART research may be linked")
    asof=_aware(evidence["decision_at"])
    fiscal=snapshot.get("official_financial_research_observations",[])
    receipts=evidence.get("dart_financial_first_receipts",[])
    if type(fiscal) is not list or type(receipts) is not list:
        raise ValueError("Observed financial reports and SHA pins required")
    by_id={}
    for item in receipts:
        stock=item["stock_code"];year=item["report_year"]
        key=(stock,year)
        if (key in by_id or type(stock) is not str or type(year) is not int or
                not HASH.fullmatch(str(item.get("first_receipt_sha256","")))):
            raise ValueError("Duplicate or missing independently verified FY first SHA")
        if _aware(item["first_local_received_at_utc"])>asof:
            raise ValueError("Future financial FY first receipt forbidden")
        by_id[key]=item["first_receipt_sha256"]
    results=[]
    seen=set()
    with DartCFSVintageRegistry(Path(ledger),read_only=True) as db:
        before=db.checksum()
        for obs in sorted(fiscal,key=lambda x:x["security_id"]):
            stock=obs["security_id"]
            corp=obs.get("observed_dart_corp_code")
            if (stock in seen or type(corp) is not str or
                    not re.fullmatch(r"[0-9]{8}",corp)):
                raise ValueError("Financial issuer/corp mapping must be explicitly observed")
            seen.add(stock)
            years=obs.get("annual_receipt_years")
            if (type(years) is not list or
                    len(years) not in (2,3) or
                    years!=list(range(years[0],years[0]+len(years)))):
                raise ValueError("PIT annual vintage years must be consecutive")
            for year in years:
                required=by_id.get((stock,year))
                if required is None:
                    raise ValueError("Expected fiscal report missing from pinned DART input")
                review=db.review_as_of(
                    decision_at=asof.isoformat(),stock_code=stock,
                    corp_code=corp,fiscal_year=year)
                known=review["known_vintages"]
                if (known and required not in {v["source_first_receipt_sha256"] for v in known}):
                    raise ValueError("Stored research source PIN mismatches current DART receipt")
                results.append({
                    "stock_code":stock,"corp_code":corp,"fiscal_year":year,
                    "first_receipt_sha256":required,
                    "status":review["status"],
                    "registered_vintages_available":len(known),
                    "first_registered_at_utc":known[0]["registered_at_utc"] if known else None,
                    "revision_or_receipt_conflict":len(known)>1,
                    "historic_first_published_at":None,
                    "issuer_share_class_pit_certified":False,
                    "prospective_discovery_certified":False,
                })
        after=db.checksum()
    if before!=after:
        raise ValueError("Research ledger changed during snapshot audit")
    report={
        "schema":SCHEMA, "decision_at_utc":asof.isoformat(),
        "source_price_watch_run_id":snapshot.get("run_id"),
        "source_registry_chain_sha256":after["tail_chain_sha256"],
        "source_registered_vintages_total":after["records"],
        "annual_report_vintages_checked":len(results),
        "asof_available_vintages":sum(r["registered_vintages_available"]==1 for r in results),
        "needs_revision_reconciliation":sum(r["revision_or_receipt_conflict"] for r in results),
        "observations":results,
        "historical_first_publication_certified":False,
        "issuer_share_class_pit_certified":False,
        "official_leaders":0,"leader_score_100":None,
        "research_only":True,
        "note":"Actual registration != filing date. Older reports first downloaded later have no historic early-discovery credit.",
    }
    report["content_sha256"]=_digest(report)
    return report


def render_dart_cfs_vintages(report: dict) -> str:
    body=dict(report)
    expected=body.pop("content_sha256",None)
    if (body.get("schema")!=SCHEMA or body.get("official_leaders")!=0 or
            body.get("research_only") is not True or
            body.get("historical_first_publication_certified") is not False or
            body.get("leader_score_100") is not None or _digest(body)!=expected):
        raise ValueError("DART original vintage report was modified or promoted")
    def x(value):
        return escape("N/A" if value is None else str(value),quote=True)
    lines=[]
    for row in report["observations"]:
        lines.append("<tr>"+"".join("<td>"+x(v)+"</td>" for v in (
            row["stock_code"],row["fiscal_year"],row["status"],
            row["registered_vintages_available"],row["first_registered_at_utc"],
            "정정 검토 필요" if row["revision_or_receipt_conflict"] else "새로운 정정 없음/보증 아님",
        ))+"</tr>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader DART 최초 확보·정정 원본 연구</title><style>"+BASE_CSS+"</style>"
        "</head><body><header><h1>EraLeader · DART 원본 시점·정정 연구</h1>"
        "<nav><a href='index.html'>메인</a> <a href='kr.html'>가격 관찰</a> "
        "<a href='factor_readiness_kr.html'>실적 성장·데이터 확보</a></nav></header>"
        "<main><div class='note'>"
        "<strong>연구용 첫 로컬 수신 이력입니다. DART 실제 최초 공개시각 및 전체 정정 이력은 독립 인증 전입니다.</strong>"
        "<br>과거 수집 시점으로 사전 발굴을 소급하지 않으며 정정된 동일 사업연도 원본은 자동 선택하지 않습니다."
        "</div><div class='stats'>"
        "<div class='stat'>검증 원본 사업연도 수<br><strong>"+
        x(report["annual_report_vintages_checked"])+"</strong></div>"
        "<div class='stat'>실제 등록된 단일 원본 수<br><strong>"+
        x(report["asof_available_vintages"])+"</strong></div>"
        "<div class='stat'>정정·변조 검토 필요<br><strong>"+
        x(report["needs_revision_reconciliation"])+"</strong></div></div>"
        "<div class='wrap'><table><thead><tr>"
        "<th>종목</th><th>사업연도</th><th>이력 상태</th><th>등록 원본 수</th>"
        "<th>로컬 최초 등록시각(UTC)</th><th>주의</th>"
        "</tr></thead><tbody>"+"".join(lines)+"</tbody></table></div>"
        "<p><small>연구 판단시각 "+x(report["decision_at_utc"])+
        " · PIT 검증/대장주 공식순위 N/A · 주문/메시지 발송 0</small></p>"
        "</main><footer>EraLeader local-first · provenance research only</footer></body></html>"
    )


def write_dart_cfs_vintage_sidecar(report: dict, site: Path) -> tuple[Path,Path]:
    site=Path(site)
    if not site.is_dir() or site.is_symlink() or any(p.is_symlink() for p in site.parents):
        raise ValueError("DART source vintage sidecar requires ordinary existing site")
    html=render_dart_cfs_vintages(report).encode("utf-8")
    payload=(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
    paths=[site/"dart_cfs_vintages.html",site.parent/"dart_cfs_vintages.json"]
    written=[]
    try:
        for path,data in zip(paths,[html,payload]):
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            written.append(path)
            with os.fdopen(fd,"wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
    except BaseException:
        for created in written:
            created.unlink(missing_ok=True)
        raise
    return tuple(paths)
