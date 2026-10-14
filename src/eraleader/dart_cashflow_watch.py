"""Verified annual CFS cash generation for archived WATCH research.

Uses existing private first receipts. Cash after PPE/intangible purchases is
a bounded observation, not an audited free-cash-flow or 20-point moat score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import shutil
import tempfile

from .official_dart_financials import parse_dart_financial, _parse_amount, _unique
from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search
from .early_watch_daily_brief import verified_watch

METHOD = "DART_CFS_ANNUAL_CFO_PPE_INTANGIBLE_OBSERVATION_V1"
SCHEMA = "eraleader.watch_annual_cashflow_research.v1"
FOLDER = "watch_annual_cashflow"
ACCOUNTS = {
    "dart_cfs_operating_cashflow_krw":
        "ifrs-full_CashFlowsFromUsedInOperatingActivities",
    "dart_cfs_ppe_purchase_raw_krw":
        "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    "dart_cfs_intangible_purchase_raw_krw":
        "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
}
CASH_FIELDS = (
    *ACCOUNTS, "dart_cfs_ppe_purchase_outflow_krw",
    "dart_cfs_intangible_purchase_outflow_krw",
    "dart_cfs_cash_after_ppe_intangibles_krw",
    "dart_cfs_operating_cash_to_revenue_pct",
    "dart_cfs_operating_cash_to_net_income_ratio",
    "dart_previous_cfs_operating_cashflow_krw",
    "dart_cfs_operating_cash_positive_two_years",
)


def parse_annual_cashflow(raw: bytes, *, corp_code: str, year: int) -> dict:
    """Keep exact observed account IDs; missing purchases never become zero."""
    financial = parse_dart_financial(raw, corp_code=corp_code, year=year,
                                     report="11011", statement="CFS")
    rows = json.loads(raw, object_pairs_hook=_unique).get("list", [])
    values = {name: set() for name in ACCOUNTS}
    for row in rows:
        if (row.get("sj_div") != "CF" or row.get("currency", "KRW") != "KRW"
                or row.get("account_detail") not in (None, "", "-")):
            continue
        for name, account in ACCOUNTS.items():
            if row.get("account_id") == account:
                amount = _parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    values[name].add(amount)
    result = {}
    for name, amounts in values.items():
        if len(amounts) > 1:
            raise ValueError("DART_CASHFLOW_AMBIGUOUS_ACCOUNT")
        result[name] = next(iter(amounts)) if amounts else None
    cfo = result["dart_cfs_operating_cashflow_krw"]
    ppe = result["dart_cfs_ppe_purchase_raw_krw"]
    intangible = result["dart_cfs_intangible_purchase_raw_krw"]
    ppe_out = abs(ppe) if ppe is not None else None
    int_out = abs(intangible) if intangible is not None else None
    revenue = financial["metrics"].get("revenue", {}).get("value")
    net = financial["metrics"].get("net_income", {}).get("value")
    result.update(
        dart_cfs_ppe_purchase_outflow_krw=ppe_out,
        dart_cfs_intangible_purchase_outflow_krw=int_out,
        dart_cfs_cash_after_ppe_intangibles_krw=(
            cfo-ppe_out-int_out if all(x is not None for x in (cfo, ppe_out, int_out))
            else None),
        dart_cfs_operating_cash_to_revenue_pct=(
            round(100*cfo/revenue, 4) if cfo is not None and revenue is not None
            and revenue > 0 else None),
        dart_cfs_operating_cash_to_net_income_ratio=(
            round(cfo/net, 6) if cfo is not None and net is not None and net > 0 else None))
    return result


def render_cashflow(doc: dict) -> bytes:
    def amount(value):
        return "N/A" if value is None else f"{value/100000000:,.2f}"
    rows = []
    for row in doc["entries"]:
        values = [row["name"], row["fiscal_year"],
                  amount(row["dart_cfs_operating_cashflow_krw"]),
                  amount(row["dart_cfs_ppe_purchase_outflow_krw"]),
                  amount(row["dart_cfs_intangible_purchase_outflow_krw"]),
                  amount(row["dart_cfs_cash_after_ppe_intangibles_krw"]),
                  row["dart_cfs_operating_cash_to_revenue_pct"],
                  row["dart_cfs_operating_cash_positive_two_years"],
                  row["first_received_at_utc"]]
        rows.append("<tr>"+"".join("<td>"+escape("N/A" if x is None else str(x))
                                  +"</td>" for x in values)+"</tr>")
    head = ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader WATCH 연간 현금창출 관찰</title>"
            "<style>body{font:14px system-ui;line-height:1.6;max-width:1400px;"
            "margin:20px auto;padding:0 15px}table{border-collapse:collapse}"
            "th,td{padding:8px;border-bottom:1px solid #ccc;text-align:left}</style>"
            "<h1>WATCH 연간 현금창출 관찰</h1><p>보관된 WATCH 시장일 "
            +escape(doc["source_market_session"])+" · 분석일 "
            +escape(doc["report_local_day"])+" · "+str(doc["watch_rows"])+"종목</p>"
            "<p>현재 시장일의 새 WATCH 선정이 아니라 기존 목록의 연간 연결재무 관측입니다. "
            "이전 관측자료를 오늘 시세나 오늘 대장주 상태로 바꾸지 않습니다.</p>"
            "<p>금액 단위: 억원. 취득 계정은 현금유출을 양수로 표시합니다. "
            "영업현금−유형·무형취득은 기업 인수·임차·기타 투자항목을 포함하지 않는 "
            "제한된 잔여현금 관측치입니다. 완전한 FCF·기업 경쟁력20점은 N/A입니다. "
            "누락된 취득액을 0으로 가정하지 않습니다. 정식 대장주·주문 0.</p>"
            "<table><thead><tr>"+ "".join("<th>"+x+"</th>" for x in (
                "종목", "회계연도", "영업현금", "유형취득", "무형취득",
                "영업현금−취득", "영업현금/매출(%)", "2년 연속 영업현금 양수",
                "원본 최초 수신 UTC"))+"</tr></thead><tbody>")
    return (head+"".join(rows)+"</tbody></table></html>").encode()


def read_cashflow(path: Path, *, clock: datetime | None = None) -> dict:
    now = clock or datetime.now(timezone.utc)
    if (not path.is_absolute() or path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not path.is_file() or path.stat().st_size > 500000):
        raise ValueError("DART_CASHFLOW_OUTPUT_UNSAFE")
    raw = path.read_bytes()
    doc = json.loads(raw, object_pairs_hook=_unique)
    unsigned = dict(doc)
    pin = unsigned.pop("content_sha256", None)
    first = datetime.fromisoformat(doc["first_report_generated_at_utc"])
    if (raw != canonical(doc)+b"\n" or sha256(canonical(unsigned)).hexdigest() != pin
            or first.tzinfo is None or first > now or doc.get("schema") != SCHEMA
            or doc.get("method") != METHOD or doc.get("orders_enabled") is not False
            or doc.get("selected_candidates") != [] or doc.get("receiver_project") is not None
            or doc.get("research_only") is not True or doc.get("official_leaders") != 0
            or not 1 <= len(doc.get("entries", [])) <= 100
            or len(doc["entries"]) != doc.get("watch_rows")
            or len({x["security_id"] for x in doc["entries"]}) != doc["watch_rows"]):
        raise ValueError("DART_CASHFLOW_OUTPUT_CONTRACT")
    return doc


def publish_watch_cashflow(*, project: Path, marketwide: Path, watch_manifest: Path,
                           capture_root: Path, clock: datetime | None = None) -> dict:
    """Publish separate immutable detail without rewriting a past WATCH edition."""
    from .dart_profitability_watch import dart_annual_margin_context
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DART_CASHFLOW_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    output = _owned_output(project)/FOLDER
    if output.is_symlink():
        raise ValueError("DART_CASHFLOW_ROOT_UNSAFE")
    output.mkdir(mode=0o700, exist_ok=True)
    watch = verified_watch(watch_manifest, clock=now)
    market, _ = _source(marketwide)
    viewed, _ = prepare_search(market,
        request_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(), clock=now)
    if watch["source_marketwide_sha256"] != market["content_sha256"]:
        raise ValueError("DART_CASHFLOW_WATCH_MARKET_MISMATCH")
    context = dart_annual_margin_context(market=market, capture_root=capture_root,
                                        now=now, include_cashflow=True)
    entries = []
    for row in watch["review_queue"]:
        firm = context.get(row["security_id"]) or {}
        entries.append({
            "security_id": row["security_id"], "name": row["name"],
            "fiscal_year": firm.get("dart_latest_cfs_business_year"),
            **{key: firm.get(key) for key in CASH_FIELDS},
            "first_receipt_sha256": firm.get("dart_cfs_first_receipt_sha256"),
            "first_received_at_utc": firm.get("dart_cfs_first_received_at_utc"),
            "previous_first_receipt_sha256": firm.get("dart_cfs_previous_first_receipt_sha256"),
            "previous_first_received_at_utc": firm.get("dart_cfs_previous_first_received_at_utc"),
            "competitive_advantage_score_20": None,
            "eligible_to_order": False})
    core = {
        "schema": SCHEMA, "method": METHOD, "market": "KR",
        "source_market_session": watch["source_market_session"],
        "source_watch_sha256": watch["content_sha256"],
        "source_marketwide_sha256": market["content_sha256"],
        "watch_rows": len(entries), "entries": entries,
        "cfo_available": sum(x["dart_cfs_operating_cashflow_krw"] is not None for x in entries),
        "cash_after_purchases_available": sum(
            x["dart_cfs_cash_after_ppe_intangibles_krw"] is not None for x in entries),
        "previous_watch_research_only": True, "research_only": True,
        "independent_historical_pit_certified": False, "receiver_project": None,
        "selected_candidates": [], "official_leaders": 0, "orders_enabled": False,
        "external_api_calls": 0}
    version = sha256(canonical(core)).hexdigest()[:16]
    dest = output/("KR_"+watch["source_market_session"].replace("-", "")+"_"+version)
    if dest.is_symlink():
        raise ValueError("DART_CASHFLOW_VERSION_LINKED")
    if dest.exists():
        doc = read_cashflow(dest/"cashflow.json", clock=now)
        previous = {k: v for k, v in doc.items() if k in core}
        if (previous != core or (dest/"index.html").is_symlink()
                or (dest/"index.html").read_bytes() != render_cashflow(doc)):
            raise ValueError("DART_CASHFLOW_EXISTING_CONFLICT")
        state = "ALREADY_PUBLISHED"
    else:
        doc = {**core, "report_local_day": now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),
               "first_report_generated_at_utc": now.isoformat(),
               "source_estimated_weekday_lag": viewed["estimated_weekday_lag"],
               "exchange_holiday_adjusted": False,
               "source_stale_warning": viewed["stale_warning"]}
        doc["content_sha256"] = sha256(canonical(doc)).hexdigest()
        stage = Path(tempfile.mkdtemp(prefix=".cashflow_", dir=output))
        try:
            for name, raw in (("cashflow.json", canonical(doc)+b"\n"),
                              ("index.html", render_cashflow(doc))):
                fd = os.open(stage/name, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            again = verified_watch(watch_manifest, clock=now)
            check, _ = _source(marketwide)
            if (again["content_sha256"] != watch["content_sha256"]
                    or check["content_sha256"] != market["content_sha256"]
                    or dest.exists() or dest.is_symlink()):
                raise ValueError("DART_CASHFLOW_SOURCE_CHANGED")
            os.rename(stage, dest)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        state = "PUBLISHED"
    return {"status": state, "manifest": str(dest/"cashflow.json"),
            "site": str(dest/"index.html"), "watch_rows": doc["watch_rows"],
            "cfo_available": doc["cfo_available"],
            "cash_after_purchases_available": doc["cash_after_purchases_available"],
            "source_market_session": doc["source_market_session"],
            "report_day": doc["report_local_day"], "external_api_calls": 0,
            "orders": 0}
