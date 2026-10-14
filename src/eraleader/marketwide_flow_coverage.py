"""Verified, read-only cumulative Kiwoom demo selected-stock flow coverage.

Aggregates ONLY fully persisted shared-gateway research batches; never makes
provider requests, scores investment flow, or asserts historic availability.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import os
import shutil
import tempfile

from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source,prepare_search
from .marketwide_flow_batch import _checked_batch,FOLDER

SCHEMA="eraleader.marketwide_selected_flow_coverage.v1"


def summarize_flow_coverage(*, marketwide:Path,project:Path,
                            clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("FLOW_COVERAGE_AWARE_CLOCK")
    now=now.astimezone(timezone.utc)
    from zoneinfo import ZoneInfo
    day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    report,_=_source(marketwide)
    manifest,_=prepare_search(report,request_day=day,clock=now)
    root=_owned_output(project)/FOLDER
    prefix=("KR_"+report["market_session"].replace("-","")+"_"+report["content_sha256"][:16]+"_")
    batches=[]
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise ValueError("FLOW_COVERAGE_BATCH_FOLDER_UNSAFE")
        children=sorted(root.iterdir())
        if len(children)>500:
            raise ValueError("FLOW_COVERAGE_TOO_MANY_BATCHES")
        for folder in children:
            if folder.name.startswith(prefix):
                batches.append(_checked_batch(
                    folder,market=report["market_session"],
                    source_hash=report["content_sha256"],now=now))
    by_security={}
    pins=[]
    for batch in batches:
        pins.append(batch["content_sha256"])
        folder=root/("KR_"+batch["source_market_session"].replace("-","")+"_"
                     +batch["source_marketwide_sha256"][:16]+"_"
                     +sha256(canonical({
                         "day":batch["source_market_session"],
                         "source":batch["source_marketwide_sha256"],
                         "codes":batch["stock_codes"]
                     })).hexdigest()[:12])
        for item in batch["items"]:
            code=item["stock_code"]
            if code in by_security:
                raise ValueError("FLOW_COVERAGE_DUPLICATED_SECURITY")
            src=json.loads((folder/(code+".json")).read_bytes())
            by_security[code]={
                "security_id":code,
                "first_gateway_received_at_utc":src["first_gateway_received_at_utc"],
                "decision_at_utc":src["decision_at_utc"],
                "observed_sessions":src["observed_sessions"],
                "has_20_observed_sessions":item["has_20_observations"],
                "foreign_net_5_shares":src["foreign_net_5_sessions"],
                "institution_net_5_shares":src["institution_net_5_sessions"],
                "foreign_net_20_shares":src["foreign_net_20_sessions"],
                "institution_net_20_shares":src["institution_net_20_sessions"],
                "original_research_sha256":src["content_sha256"],
                "flow_score_10":None,
            }
    names={r["security_id"]:r["name"] for r in report["securities"]}
    if not set(by_security).issubset(names):
        raise ValueError("FLOW_COVERAGE_NOT_KRX_SECURITY")
    rows=[]
    for code,row in sorted(by_security.items()):
        rows.append({"name":names[code],**row})
    result={
        "schema":SCHEMA,
        "market":"KR","mode":"demo",
        "source_market_session":report["market_session"],
        "source_marketwide_sha256":report["content_sha256"],
        "source_built_at_utc":manifest["source_built_at_utc"],
        "market_price_stale_warning":manifest["stale_warning"],
        "batch_sha256":sorted(pins),
        "published_batches":len(pins),
        "collected_stocks":len(rows),
        "eligible_krx_stock_observations":manifest["observed_stocks"],
        "complete_20_observed_sessions":sum(r["has_20_observed_sessions"] for r in rows),
        "rows":rows,
        "selected_stocks_research_only":True,
        "units":"shares",
        "whole_market_investor_flow":False,
        "investment_flow_score_available":False,
        "formal_leaders":0,
        "independent_historical_pit_certified":False,
        "orders_enabled":False,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    return result


def _render(report:dict)->bytes:
    def val(v):
        return "N/A" if v is None else str(v)
    rows=[]
    for item in report["rows"]:
        cells=[
            item["security_id"],item["name"],
            item["observed_sessions"],item["has_20_observed_sessions"],
            item["foreign_net_5_shares"],item["institution_net_5_shares"],
            item["foreign_net_20_shares"],item["institution_net_20_shares"],
            item["first_gateway_received_at_utc"],
        ]
        rows.append("<tr>"+"".join(
            "<td>"+escape(val(x),quote=True)+"</td>" for x in cells)+"</tr>")
    html=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader · 시장전체 선택 종목 수급수집</title>'
        '<style>body{font:14px system-ui;margin:24px auto;max-width:1150px;padding:0 12px}'
        'table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #aaa}'
        '.scroll{overflow-x:auto}.note{padding:12px;background:#8881;border-left:4px solid #a86}</style>'
        '</head><body><h1>KR 선택종목 기관·외국인 수급 누적 관찰</h1>'
        '<p class="note">키움 모의계좌 읽기 전용, 순매매 주식 수(주). '
        '실제 자금/거래대금 비중이나 매수 신호가 아닙니다. '
        '5/20개는 관측된 행 수이며 독립 거래소 연속거래일 인증이 아닙니다. '
        '과거 시세일 이후 실제 로컬 수신시각으로 기록, PIT·100점 대장주 미인증.</p>'
        '<p>KRX 시장일 '+escape(report["source_market_session"])+
        ' · 수급 받은 종목 '+str(report["collected_stocks"])+
        ' · 최근 20행 충족 '+str(report["complete_20_observed_sessions"])+
        ' · 전체 KRX 관측 '+str(report["eligible_krx_stock_observations"])+
        ' · 주문0</p><div class="scroll"><table><thead><tr>'+
        ''.join("<th>"+x+"</th>" for x in [
            "종목코드","종목명","관측행","20행충족",
            "외국인5(주)","기관5(주)","외국인20(주)","기관20(주)","최초수신 UTC"])+
        '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
        '<footer>원천 KRX SHA '+report["source_marketwide_sha256"][:16]+
        ' · 정식 투자판정0 · 주문권한0</footer></body></html>'
    )
    return html.encode("utf-8")


def publish_flow_coverage(*,marketwide:Path,project:Path,
                          clock:datetime|None=None)->dict:
    output=_owned_output(project)
    data=summarize_flow_coverage(marketwide=marketwide,project=project,clock=clock)
    folder=output/"marketwide_flow_coverage"
    if folder.is_symlink():
        raise ValueError("FLOW_COVERAGE_OUTPUT_LINKED")
    folder.mkdir(mode=0o700,exist_ok=True)
    digest=sha256(canonical({
        "source":data["source_marketwide_sha256"],
        "batches":data["batch_sha256"],
    })).hexdigest()[:12]
    path=folder/("KR_"+data["source_market_session"].replace("-","")+"_"+data["source_marketwide_sha256"][:16]+"_"+digest)
    content=canonical(data)+b"\n"
    html=_render(data)
    if path.is_symlink():
        raise ValueError("FLOW_COVERAGE_VERSION_SYMLINK")
    if path.exists():
        if (not path.is_dir() or
                (path/"manifest.json").is_symlink() or
                (path/"index.html").is_symlink() or
                (path/"manifest.json").read_bytes()!=content or
                (path/"index.html").read_bytes()!=html):
            raise ValueError("FLOW_COVERAGE_EXISTING_VERSION_CONFLICT")
        status="ALREADY_PUBLISHED"
    else:
        stage=Path(tempfile.mkdtemp(prefix=".flowcoverage_",dir=folder))
        try:
            os.chmod(stage,0o700)
            for name,body in (("manifest.json",content),("index.html",html)):
                fd=os.open(stage/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"wb") as stream:
                    stream.write(body);stream.flush();os.fsync(stream.fileno())
            if path.exists() or path.is_symlink():
                raise ValueError("FLOW_COVERAGE_RACE")
            os.rename(stage,path)
        finally:
            if stage.exists():shutil.rmtree(stage)
        status="PUBLISHED"
    return {"status":status,
            "market_session":data["source_market_session"],
            "collected_stocks":data["collected_stocks"],
            "complete_20_observed_sessions":data["complete_20_observed_sessions"],
            "published_batches":data["published_batches"],
            "manifest":str(path/"manifest.json"),
            "site":str(path/"index.html"),
            "formal_leaders":0,"orders":0}
