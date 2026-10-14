"""Browser-first searchable Korean market research, from immutable marketwide JSON.

This is an actual 2,765-stock *lookup*, not an invented investment ranking.
Only reuses previously captured data and the existing partially-scored research.
Source and generated HTML are local; no broker, network, state or orders.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import os
import re
import shutil
import tempfile

from .official_company_explorer import canonical

SCHEMA = "eraleader.official_kr_marketwide_factor_coverage.v1"
OUTPUT_SCHEMA = "eraleader.marketwide_local_search.v1"
TICKER = re.compile(r"[0-9A-Za-z]{6}\Z")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
FIELDS = (
    "security_id", "name", "venue", "market_session", "close",
    "market_cap", "turnover", "market_traded", "current_dart_directory_matched",
    "price_strength_25", "revenue_yoy", "operating_income_yoy",
    "revenue_growth_acceleration", "industry_code",
    "two_factor_research_50", "two_factor_research_rank",
    "price_top20_watch_rank", "institutional_flow", "foreign_flow",
)


def _instant(s: str) -> datetime:
    if type(s) is not str:
        raise ValueError("MARKETWIDE_SEARCH_TIME_MISSING")
    value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("MARKETWIDE_SEARCH_TIMEZONE_MISSING")
    return value.astimezone(timezone.utc)


def _number(value, *, min_value=None, max_value=None) -> None:
    if value is None:
        return
    if (type(value) not in (float, int) or not math.isfinite(value) or
            min_value is not None and value < min_value or
            max_value is not None and value > max_value):
        raise ValueError("MARKETWIDE_SEARCH_INVALID_NUMBER")


def _source(path: Path) -> tuple[dict, bytes]:
    if (not isinstance(path, Path) or not path.is_absolute()
            or path.is_symlink() or not path.is_file()
            or any(p.is_symlink() for p in path.parents)
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_size > 15_000_000):
        raise ValueError("MARKETWIDE_SEARCH_SOURCE_UNSAFE")
    data = path.read_bytes()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("MARKETWIDE_SEARCH_DUPLICATE_JSON")
            result[key] = value
        return result
    report = json.loads(
        data, object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(
            ValueError("MARKETWIDE_SEARCH_NONFINITE_JSON")))
    if type(report) is not dict or report.get("schema") != SCHEMA:
        raise ValueError("MARKETWIDE_SEARCH_UNSUPPORTED_SCHEMA")
    unsigned = dict(report)
    witness = unsigned.pop("content_sha256", None)
    if type(witness) is not str or sha256(canonical(unsigned)).hexdigest() != witness:
        raise ValueError("MARKETWIDE_SEARCH_SOURCE_HASH_MISMATCH")
    return report, data


def prepare_search(report: dict, *, request_day: str,
                   clock: datetime | None = None) -> tuple[dict, list[dict]]:
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("MARKETWIDE_SEARCH_CLOCK_NEEDS_ZONE")
    now = now.astimezone(timezone.utc)
    try:
        if type(request_day) is not str or not DAY.fullmatch(request_day):
            raise ValueError("INVALID")
        requested = date.fromisoformat(request_day)
        observed = date.fromisoformat(report["market_session"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("MARKETWIDE_SEARCH_MARKET_DATE_INVALID") from None
    if (report.get("schema") != SCHEMA or report.get("market") != "KR"
            or report.get("research_only") is not True
            or report.get("official_leaders") != 0
            or report.get("full_market_composite_rank_available") is not False
            or requested > now.astimezone(ZoneInfo("Asia/Seoul")).date()
            or observed > requested):
        raise ValueError("MARKETWIDE_SEARCH_INVALID_MARKET_OR_FUTURE_DATE")
    decided = _instant(report.get("source_decision_at_utc"))
    built = _instant(report.get("built_at_utc"))
    if built < decided or built > now:
        raise ValueError("MARKETWIDE_SEARCH_FUTURE_EVIDENCE")
    stocks = report.get("securities")
    if type(stocks) is not list or not 1 <= len(stocks) <= 5000:
        raise ValueError("MARKETWIDE_SEARCH_SECURITIES_MISSING")
    if report.get("official_krx_observed") != len(stocks):
        raise ValueError("MARKETWIDE_SEARCH_OBSERVED_COUNT_MISMATCH")
    out = []
    seen = set()
    ranks = set()
    top_price = set()
    finance = industry = price = flow = 0
    for item in stocks:
        if type(item) is not dict or any(k not in item for k in FIELDS):
            raise ValueError("MARKETWIDE_SEARCH_ROW_INCOMPLETE")
        code = item["security_id"]
        if (type(code) is not str or not TICKER.fullmatch(code) or
                code in seen or type(item["name"]) is not str or
                not item["name"].strip() or len(item["name"]) > 130 or
                item["venue"] not in ("KOSPI", "KOSDAQ") or
                item["market_session"] != observed.isoformat() or
                type(item["market_traded"]) is not bool or
                type(item["current_dart_directory_matched"]) is not bool):
            raise ValueError("MARKETWIDE_SEARCH_STOCK_IDENTITY_INVALID")
        seen.add(code)
        for field in ("close", "turnover", "market_cap"):
            _number(item[field], min_value=0)
        if item["close"] is None or item["close"] <= 0:
            raise ValueError("MARKETWIDE_SEARCH_PRICE_INVALID")
        _number(item["price_strength_25"], min_value=0, max_value=25)
        for field in ("revenue_yoy", "operating_income_yoy",
                      "revenue_growth_acceleration"):
            _number(item[field])
        if item["revenue_yoy"] is not None:
            finance += 1
        if item["industry_code"] is not None:
            if (type(item["industry_code"]) is not str or
                    not re.fullmatch(r"[0-9]{2,6}", item["industry_code"])):
                raise ValueError("MARKETWIDE_SEARCH_INDUSTRY_CODE_INVALID")
            industry += 1
        if item["price_strength_25"] is not None:
            price += 1
        rank = item["two_factor_research_rank"]
        score = item["two_factor_research_50"]
        _number(score, min_value=0, max_value=50)
        if (rank is None) != (score is None):
            raise ValueError("MARKETWIDE_SEARCH_RESEARCH_SCORE_MISMATCH")
        if score is not None:
            if (type(rank) is not int or rank in ranks or
                    item["price_strength_25"] is None or
                    item["revenue_yoy"] is None or
                    item["operating_income_yoy"] is None):
                raise ValueError("MARKETWIDE_SEARCH_INCOMPLETE_RESEARCH_RANK")
            ranks.add(rank)
        rank_price = item["price_top20_watch_rank"]
        if rank_price is not None:
            if type(rank_price) is not int or rank_price in top_price:
                raise ValueError("MARKETWIDE_SEARCH_PRICE_WATCH_DUPLICATE")
            top_price.add(rank_price)
        if (item.get("formal_leader_score_100") is not None or
                item.get("verified_leader_state") is not None):
            raise ValueError("MARKETWIDE_SEARCH_UNSUPPORTED_FORMAL_LEADERS")
        inst,foreign=item["institutional_flow"],item["foreign_flow"]
        if (inst is None)!=(foreign is None):
            raise ValueError("MARKETWIDE_SEARCH_PARTIAL_FLOW")
        if inst is not None:
            if (type(inst) is not int or type(foreign) is not int or
                    abs(inst)>10**12 or abs(foreign)>10**12):
                raise ValueError("MARKETWIDE_SEARCH_FLOW_INVALID")
            flow += 1
        out.append({key: item[key] for key in FIELDS if key != "market_session"})
    if (ranks != set(range(1, len(ranks) + 1))
            or top_price != set(range(1, len(top_price) + 1))
            or len(ranks) != report.get("two_factor_research_evaluable")
            or finance != report.get("financial_factors_observed")
            or industry != report.get("industry_factors_observed")
            or flow != report.get("flow_factors_observed",0)
            or (flow and (
                report.get("flow_matched_session_companies")!=flow or
                report.get("flow_certification")!="FIRST_LOCAL_RECEIPT_RESEARCH_ONLY_NOT_HISTORIC_PIT" or
                type(report.get("flow_source_manifest_sha256")) is not str or
                not re.fullmatch(r"[a-f0-9]{64}",report["flow_source_manifest_sha256"])))
            or (report.get("local_price_lookback_enabled") is True and
                price != report.get("local_price_lookback_evaluable"))):
        raise ValueError("MARKETWIDE_SEARCH_FACTOR_COVERAGE_INCONSISTENT")
    expected = sorted((s for s in out if s["two_factor_research_rank"] is not None),
                      key=lambda s: s["two_factor_research_rank"])[:20]
    listed = report.get("two_factor_research_top20")
    if (type(listed) is not list or len(listed) != len(expected) or
            any(src.get("security_id") != row["security_id"] or
                src.get("research_order") != row["two_factor_research_rank"] or
                src.get("observed_score_50") != row["two_factor_research_50"]
                for src, row in zip(listed, expected))):
        raise ValueError("MARKETWIDE_SEARCH_RESEARCH_TOP20_INCONSISTENT")
    days = (requested - observed).days
    weekdays = sum((observed + timedelta(days=i)).weekday() < 5
                   for i in range(1, days + 1))
    manifest = {
        "schema": OUTPUT_SCHEMA, "market": "KR",
        "source_market_session": observed.isoformat(),
        "requested_day": request_day,
        "published_at_utc": now.isoformat(),
        "source_built_at_utc": built.isoformat(),
        "source_decision_at_utc": decided.isoformat(),
        "source_marketwide_sha256": report["content_sha256"],
        "source_watch_run_id": report["source_watch_run_id"],
        "observed_stocks": len(out),
        "price_lookback_available": price, "financial_available": finance,
        "industry_available": industry, "flow_matched_session_companies":flow,
        "research_50_scored": len(ranks),
        "official_leaders": 0, "official_100_point_rank_available": False,
        "estimated_weekday_lag": weekdays, "exchange_holiday_adjusted": False,
        "stale_warning": weekdays >= 2,
        "research_only": True, "formal_selection": None,
    }
    manifest["content_sha256"] = sha256(canonical(manifest)).hexdigest()
    return manifest, out


_HTML = r"""
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader · 한국시장 2,765종목 검색</title>
<style>
:root{color-scheme:light dark}body{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;margin:0;line-height:1.55}
header{padding:20px clamp(16px,5vw,62px);background:#183251;color:#fff}
header h1{margin:0;font-size:24px}main{max-width:1260px;margin:auto;padding:20px 16px}
label{font-weight:600;font-size:14px}input,select,button{font:inherit;padding:8px;border-radius:6px;border:1px solid #adb6c1}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.field{display:flex;flex-direction:column;gap:4px;min-width:160px;flex:1}
.field input{min-width:120px}.stats{display:flex;gap:10px;flex-wrap:wrap}.stat{padding:10px;border:1px solid #aab2be;border-radius:8px;min-width:125px;flex:1}
.stat strong{display:block;font-size:22px}.note{padding:12px 16px;border-left:4px solid #b08038;background:rgba(128,128,128,.09);margin:12px 0}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px;text-align:right;border-bottom:1px solid #9996;white-space:nowrap}
td:nth-child(2),th:nth-child(2),td:nth-child(3),th:nth-child(3){text-align:left}
thead{background:rgba(128,128,128,.13)}tbody tr:hover{background:rgba(128,128,128,.08)}
.symbol{border:0;background:none;text-decoration:underline;cursor:pointer;text-align:left;color:inherit;padding:3px}
.pages{display:flex;align-items:center;gap:10px;margin-top:10px;justify-content:flex-end}
#detail{margin-top:20px;padding:14px;border:1px solid #9996;border-radius:8px}
#detail dl{display:grid;grid-template-columns:minmax(125px,220px) 1fr;gap:0 8px}
#detail dt,#detail dd{margin:0;padding:7px;border-bottom:1px solid #9993}
#detail dt{font-weight:600}footer{margin-top:25px;padding:18px;opacity:.7;font-size:12px}
@media(max-width:640px){.controls{display:grid}.field{min-width:0}header h1{font-size:20px}#detail dl{grid-template-columns:1fr}}
</style></head><body><header><h1>EraLeader · 한국 전체시장 종목 검색</h1>
<div>공식 KRX 가격 관측 &amp; DART 재무·업종 연구 자료</div></header><main>
<div class="note"><strong>가격 관측일: __OBS__ · 화면 요청일: __REQUEST__</strong>
<p>__WARNING__</p>모든 2,765개 관측 종목을 검색하지만 실적·산업 정보는 일부 기업만 확보됐습니다.
최대 50점은 가격·실적 2요소 <strong>연구용</strong> 점수입니다.
정식 대장주 100점·투자 우선순위·당일 실시간 시세가 아닙니다.</div>
<div class="stats" id="stats"></div>
<div class="controls">
<div class="field"><label for="search">종목명 / 코드 검색</label><input id="search" type="search" placeholder="삼성전자 / 005930"></div>
<div class="field"><label for="venue">시장</label><select id="venue"><option value="">코스피·코스닥</option><option value="KOSPI">코스피</option><option value="KOSDAQ">코스닥</option></select></div>
<div class="field"><label for="coverage">자료 충족</label><select id="coverage"><option value="">전체 종목</option><option value="price">과거 주가 강도 확인</option><option value="finance">재무 확보</option><option value="two">2요소 점수 계산 가능</option></select></div>
<div class="field"><label for="sort">정렬 (매수순위 아님)</label><select id="sort"><option value="score">연구 50점 높은순</option><option value="price">가격 강도 높은순</option><option value="turnover">관측 거래대금 높은순</option><option value="code">종목코드 순</option></select></div>
</div>
<p id="result-count" aria-live="polite">검색 준비 중</p>
<div class="scroll"><table><thead><tr><th>연구순서</th><th>종목</th><th>시장</th><th>가격 강도/25</th><th>매출 YoY</th><th>영업익 YoY</th><th>연구 50점</th><th>업종</th></tr></thead>
<tbody id="results"></tbody></table></div>
<div class="pages"><button type="button" id="previous">이전</button><span id="page-info"></span><button type="button" id="next">다음</button></div>
<section id="detail" aria-live="polite"><h2>종목 상세</h2><p>종목명을 선택하면 실제 보유 자료와 누락 항목을 확인할 수 있습니다.</p></section>
<footer>기준 공식 가격일 __OBS__ · 기존 시장자료 SHA __SHORTSHA__ · 연구용 / 공인 PIT·실제 대장주·매매신호 미인증</footer></main>
<script id="stock-data" type="application/json">__DATA__</script>
<script>
"use strict";
const stocks=JSON.parse(document.getElementById("stock-data").textContent);
const $=id=>document.getElementById(id);
const intfmt=new Intl.NumberFormat("ko-KR",{maximumFractionDigits:0});
const num=x=>x===null?"N/A":Number(x).toLocaleString("ko-KR",{maximumFractionDigits:2});
const percent=x=>x===null?"N/A":(100*x).toLocaleString("ko-KR",{maximumFractionDigits:1,signDisplay:"always"})+"%";
const score=x=>x===null?"N/A":Number(x).toFixed(2);
const PAGE=50;let page=0;
function stat(label,value){const b=document.createElement("div");b.className="stat";const t=document.createElement("span");t.textContent=label;const s=document.createElement("strong");s.textContent=intfmt.format(value);b.append(t,s);$("stats").append(b)}
const META=JSON.parse(document.getElementById("stock-meta").textContent);
for(const [label,key] of [["KRX 관측 종목","observed_stocks"],["가격 강도","price_lookback_available"],
["실적 연결","financial_available"],["업종 확인","industry_available"],["2요소 연구 점수","research_50_scored"],["동일 거래일 수급","flow_matched_session_companies"]])stat(label,META[key]);
function show(stock){const area=$("detail");area.replaceChildren();const h=document.createElement("h2");h.textContent=stock.name+" ("+stock.security_id+")";area.append(h);
const dl=document.createElement("dl");const pairs=[
["시장",stock.venue],["관측일",META.source_market_session],
["관측 종가 (원)",num(stock.close)],["시가총액 (원)",num(stock.market_cap)],
["관측 거래대금 (원)",num(stock.turnover)],
["매매 관측",stock.market_traded?"거래 관측":"거래 없음 / N/A"],
["과거 주가 강도 (25점)",num(stock.price_strength_25)],
["연구용 2요소 점수 (50점)",score(stock.two_factor_research_50)],
["연구용 2요소 표본 순서",stock.two_factor_research_rank??"N/A"],
["기존 가격 WATCH20 위치",stock.price_top20_watch_rank??"N/A"],
["기관 순매매 (주 · 연구 관측)",stock.institutional_flow===null?"N/A":num(stock.institutional_flow)],
["외국인 순매매 (주 · 연구 관측)",stock.foreign_flow===null?"N/A":num(stock.foreign_flow)],
["매출 YoY",percent(stock.revenue_yoy)],["영업이익 YoY",percent(stock.operating_income_yoy)],
["매출성장 가속도",percent(stock.revenue_growth_acceleration)],
["DART 현재 업종",stock.industry_code??"N/A"],
["기업코드 매칭",stock.current_dart_directory_matched?"확인":"미연결"],
["산업 전체 성장·경쟁력·기관외국인 수급","N/A (정식 100점 미산출)"],
["정식 대장주 상태","N/A (확정 없음)"]];
for(const [label,value] of pairs){const dt=document.createElement("dt");dt.textContent=label;const dd=document.createElement("dd");dd.textContent=String(value);dl.append(dt,dd)}area.append(dl);area.scrollIntoView({behavior:"smooth",block:"start"})}
function filtered(){const q=$("search").value.trim().toLocaleLowerCase();const v=$("venue").value;const c=$("coverage").value;
let a=stocks.filter(x=>(!q||x.name.toLocaleLowerCase().includes(q)||x.security_id.toLowerCase().includes(q))&&(!v||x.venue===v)&&
(!c||c==="price"&&x.price_strength_25!==null||c==="finance"&&x.revenue_yoy!==null||c==="two"&&x.two_factor_research_50!==null));
const field=$("sort").value, key={score:"two_factor_research_50",price:"price_strength_25",turnover:"turnover"}[field];
a.sort((x,y)=>{if(field==="code")return x.security_id.localeCompare(y.security_id);if(x[key]===null)return y[key]===null?x.security_id.localeCompare(y.security_id):1;if(y[key]===null)return -1;return y[key]-x[key]||x.security_id.localeCompare(y.security_id)});
return a}
function render(){const items=filtered();const pages=Math.max(1,Math.ceil(items.length/PAGE));page=Math.min(page,pages-1);const tbody=$("results");tbody.replaceChildren();
for(const r of items.slice(page*PAGE,(page+1)*PAGE)){const tr=document.createElement("tr");const cells=[r.two_factor_research_rank??"—",null,r.venue,num(r.price_strength_25),percent(r.revenue_yoy),percent(r.operating_income_yoy),score(r.two_factor_research_50),r.industry_code??"N/A"];
for(let i=0;i<cells.length;i++){const td=document.createElement("td");if(i===1){const b=document.createElement("button");b.type="button";b.className="symbol";b.textContent=r.name+" ("+r.security_id+")";b.addEventListener("click",()=>show(r));td.append(b)}else td.textContent=String(cells[i]);tr.append(td)}tbody.append(tr)}
$("result-count").textContent="검색 "+intfmt.format(items.length)+"개 / 전체 "+intfmt.format(stocks.length)+"개 · 공인 투자순위 아님";
$("page-info").textContent=(page+1)+"/"+pages+" 페이지";$("previous").disabled=page===0;$("next").disabled=page>=pages-1}
for(const id of ["search","venue","coverage","sort"])$(id).addEventListener(id==="search"?"input":"change",()=>{page=0;render()});
$("previous").addEventListener("click",()=>{page--;render()});$("next").addEventListener("click",()=>{page++;render()});render();
</script></body></html>"""


def render_html(manifest: dict, records: list[dict]) -> bytes:
    # Keep untrusted issuer names in JSON; they enter the DOM only via
    # textContent, not innerHTML. Script-ending tags must be escaped.
    rows = json.dumps(records, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    meta = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).replace("<", "\\u003c")
    message = ("자료 지연 경고: 오늘 시장 시세가 아닙니다. 관측 이후 평일 "
               + str(manifest["estimated_weekday_lag"])
               + "일 추정(휴장 미반영)."
               if manifest["stale_warning"] else
               "최근 보관된 검증 연구자료입니다. 당일 원시시세 인증은 별도입니다.")
    html = (_HTML.replace("__DATA__",rows)
            .replace("__OBS__",escape(manifest["source_market_session"],quote=True))
            .replace("__REQUEST__",escape(manifest["requested_day"],quote=True))
            .replace("__WARNING__",escape(message,quote=True))
            .replace("__SHORTSHA__",manifest["source_marketwide_sha256"][:16]))
    # Place metadata JSON before the behavior script so all UI controls work.
    html = html.replace('<script id="stock-data"',
                        '<script id="stock-meta" type="application/json">'
                        + meta + '</script><script id="stock-data"')
    return html.encode("utf-8")


def publish_search(*, input_report: Path, output: Path,
                   request_day: str, clock: datetime | None = None) -> dict:
    if (not isinstance(output, Path) or not output.is_absolute()
            or output.is_symlink() or output.exists()
            or any(p.is_symlink() for p in output.parents)
            or not output.parent.is_dir()
            or output.parent.stat().st_uid != os.geteuid()):
        raise ValueError("MARKETWIDE_SEARCH_NEW_OUTPUT_DIR_REQUIRED")
    if input_report == output or output in input_report.parents or input_report in output.parents:
        raise ValueError("MARKETWIDE_SEARCH_SOURCE_DEST_OVERLAP")
    source, raw = _source(input_report)
    manifest, rows = prepare_search(source,request_day=request_day,clock=clock)
    view = render_html(manifest,rows)
    staged = Path(tempfile.mkdtemp(prefix=".search_publish_",dir=output.parent))
    try:
        os.chmod(staged,0o700)
        for name, blob in (("index.html",view),("manifest.json",canonical(manifest)+b"\n")):
            fd = os.open(staged/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(blob)
                out.flush()
                os.fsync(out.fileno())
        if input_report.read_bytes() != raw:
            raise ValueError("MARKETWIDE_SEARCH_SOURCE_CHANGED")
        again, _ = _source(input_report)
        if again["content_sha256"] != manifest["source_marketwide_sha256"]:
            raise ValueError("MARKETWIDE_SEARCH_SOURCE_CHANGED")
        if output.exists() or output.is_symlink():
            raise ValueError("MARKETWIDE_SEARCH_OUTPUT_RACE")
        os.rename(staged,output)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return {
        "status": "KR_MARKETWIDE_SEARCH_PUBLISHED",
        "site": str(output/"index.html"),
        "manifest": str(output/"manifest.json"),
        "observed": manifest["observed_stocks"],
        "financial": manifest["financial_available"],
        "two_factor_evaluable": manifest["research_50_scored"],
        "stale_warning": manifest["stale_warning"],
        "formal_selected": 0,
    }
