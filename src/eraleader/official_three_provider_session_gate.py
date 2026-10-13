"""Read-only KRX + DART + Kiwoom first-received same-session eligibility gate.

This does not certify an historical universe, issuer class, source publication
times, earnings features, or trading signals. Missing data means BLOCKED.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import stat

from .official_api_capture import _decoded, SCHEMA as RAW_SCHEMA
from .official_dart_daily import verify_dart_day
from .kiwoom_investor_flow import canonical, utc, verify_flow

SCHEMA="eraleader.kr_three_provider_same_session_gate.v1"
SOURCES=("krx-kospi","krx-kosdaq","dart-disclosures")
# Full DART claims must come from the strict original SHA/page verifier,
# never a caller-supplied summary dict passed directly into evaluate().
_DART_VERIFIED_TOKEN=object()

def normalized_day(value: str) -> str:
    if type(value) is not str:
        raise ValueError("Session date required")
    try:
        if re.fullmatch(r"[0-9]{8}",value):
            parsed=date(int(value[:4]),int(value[4:6]),int(value[6:8]))
        elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",value):
            parsed=date.fromisoformat(value)
        else:raise ValueError("Unrecognized session date")
    except ValueError:
        raise ValueError("Unrecognized session date") from None
    return parsed.strftime("%Y%m%d")

def evaluate(*, requested_day: str, security_id: str, originals: dict[str,dict],
             flow: dict, decision_at: datetime,
             complete_dart: dict | None = None,
             _verified_dart_token: object | None = None) -> dict:
    if (type(security_id) is not str or not re.fullmatch(r"[0-9]{6}",security_id)
            or set(originals)!=set(SOURCES) or type(flow) is not dict):
        raise ValueError("Exactly three provider first receipts and selected issue required")
    session=normalized_day(requested_day)
    if (decision_at.tzinfo is None or decision_at.utcoffset() is None or
            session > decision_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")):
        raise ValueError("Future or naive research decision")
    decision=decision_at.astimezone(timezone.utc)
    verify_flow(flow,decision_at=decision)
    if flow["security_id"]!=security_id or flow["environment_mode"]!="demo":
        raise ValueError("Kiwoom flow market/issuer mismatch")
    flow_session=normalized_day(flow["requested_day"])
    if flow_session!=session:
        raise ValueError("Different selected Kiwoom market session")
    sources={}
    payloads={}
    for source in SOURCES:
        received=originals[source]
        if (type(received) is not dict or
                received.get("source")!=source or
                normalized_day(received.get("request_value"))!=session or
                type(received.get("provider_row_count")) is not int or
                received["provider_row_count"]<0 or
                type(received.get("quality")) is not str or
                received.get("full_historic_universe_pit_certified") is not False):
            raise ValueError("Official provider first receipt is not admissible")
        if utc(received["first_local_received_at_utc"])>decision:
            raise ValueError("Official receipt not available at decision")
        sources[source]={
            "source":source,"market_day":session,
            "received_at_utc":received["first_local_received_at_utc"],
            "first_receipt_sha256":received["first_receipt_sha256"],
            "provider_row_count":received["provider_row_count"],
            "quality":received["quality"],
        }
        payloads[source]=received.get("body")
        if type(payloads[source]) is not dict:
            raise ValueError("Verified original response required")
    kospi=payloads["krx-kospi"].get("OutBlock_1")
    kosdaq=payloads["krx-kosdaq"].get("OutBlock_1")
    if type(kospi) is not list or type(kosdaq) is not list:
        raise ValueError("Unexpected KRX block")
    all_rows=kospi+kosdaq
    codes=[r.get("ISU_CD") for r in all_rows if type(r) is dict]
    if len(codes)!=len(set(codes)):
        raise ValueError("KRX issue appears in multiple venues")
    if any(type(r) is not dict or r.get("BAS_DD")!=session
           for r in all_rows):
        raise ValueError("KRX rows do not belong to expected day")
    issue=next((r for r in all_rows if r["ISU_CD"]==security_id),None)
    positive_close=False
    if issue is not None:
        close=issue.get("TDD_CLSPRC")
        if type(close) is str and re.fullmatch(r"[0-9,]+",close):
            positive_close=int(close.replace(",",""))>0
    krx_nonempty=(bool(kospi) and bool(kosdaq))
    dart=sources["dart-disclosures"]
    full_dart_verified=False
    dart_complete_counts=None
    if complete_dart is not None:
        if _verified_dart_token is not _DART_VERIFIED_TOKEN:
            raise ValueError("Unverified full DART summary cannot unlock research")
        if (type(complete_dart) is not dict or
                normalized_day(complete_dart.get("market_day"))!=session or
                type(complete_dart.get("total_rows")) is not int or
                complete_dart["total_rows"] < dart["provider_row_count"] or
                type(complete_dart.get("total_pages")) is not int or
                complete_dart["total_pages"] < 1 or
                type(complete_dart.get("rows")) is not list or
                len(complete_dart["rows"])!=complete_dart["total_rows"] or
                complete_dart.get("issuer_class_pit_verified") is not False or
                complete_dart.get("financial_pit_verified") is not False or
                type(complete_dart.get("manifest_sha256")) is not str or
                not re.fullmatch("[0-9a-f]{64}",complete_dart["manifest_sha256"]) or
                utc(complete_dart.get("last_received_at_utc")) > decision):
            raise ValueError("Complete DART first-received proof invalid")
        full_dart_verified=True
        dart_complete_counts={
            "total_count":complete_dart["total_rows"],
            "total_pages":complete_dart["total_pages"],
            "manifest_sha256":complete_dart["manifest_sha256"],
            "last_received_at_utc":complete_dart["last_received_at_utc"],
        }
    dart_day_covered=(full_dart_verified or
                      dart["quality"]=="ROWS_RECEIVED_NOT_PIT_CERTIFIED")
    flow_mature=(flow["latest_observed_day"]==session and
                 flow["flow_20_observed_sessions"]["combined_net_shares"] is not None)
    failures=[]
    if not krx_nonempty:failures.append("KRX_ONE_OR_BOTH_MARKETS_EMPTY")
    if issue is None:failures.append("SELECTED_ISSUE_NOT_IN_SAME_DAY_KRX")
    elif not positive_close:failures.append("SELECTED_ISSUE_CLOSE_UNAVAILABLE")
    if not dart_day_covered:failures.append("DART_DAY_NOT_COMPLETE_OR_PROVIDER_NO_DATA")
    if not flow_mature:failures.append("KIWOOM_DEMO_FLOW_WINDOW_INCOMPLETE")
    flags={
        "same_market_session":True,
        "provider_received_by_decision":True,
        "two_krx_markets_nonempty":krx_nonempty,
        "selected_issue_krx_ohlc_present":positive_close,
        "dart_first_page_complete_for_day":(
            dart["quality"]=="ROWS_RECEIVED_NOT_PIT_CERTIFIED"),
        "dart_full_listing_sha_verified":full_dart_verified,
        "dart_day_coverage_verified":dart_day_covered,
        "kiwoom_20_observation_window":flow_mature,
        "provider_demo_not_production":True,
    }
    result={
        "schema":SCHEMA,"market":"KR","security_id":security_id,
        "session":session,"decision_at_utc":decision.isoformat(),
        "source_receipts":sources,
        "dart_complete_daily_proof":dart_complete_counts,
        "kiwoom_demo_original_sha256":flow["content_sha256"],
        "kiwoom_first_received_utc":flow["source_first_locally_received_at_utc"],
        "flags":flags,
        "readiness":"SAME_DAY_RESEARCH_OBSERVABLE_NOT_CERTIFIED" if not failures
                    else "PAUSED_MISSING_OR_INCOMPLETE_OFFICIAL_EVIDENCE",
        "blockers":failures,
        "can_compare_same_session_research":not failures,
        "historical_source_publication_pit_certified":False,
        "issuer_share_class_independently_certified":False,
        "production_kiwoom_flow_certified":False,
        "investment_leader_score_available":False,
        "official_leaders":0,
        "trade_signal":None,"orders_enabled":False,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    return result

def _owner_only_file(path: Path, limit:int) -> bytes:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file() or
            path.stat().st_uid != os.geteuid() or
            path.stat().st_mode & 0o077 or
            path.stat().st_size > limit):
        raise ValueError("Official immutable first-received file is not owner-only")
    return path.read_bytes()

def verified_local_capture(folder:Path, source:str, pin:str,
                           decision:datetime) -> tuple[dict,dict]:
    """Verify the original SHA without changing its T5DATA mode-mapped files.

    ExFAT may map 0600 to 0700; both deny group/other access. All original
    fields/JSON/publisher-time checks stay strict. No data can be backdated.
    """
    folder=Path(folder)
    if (not folder.is_absolute() or folder.is_symlink() or not folder.is_dir() or
            folder.stat().st_uid != os.geteuid() or
            folder.stat().st_mode & 0o077 or folder.parent.is_symlink() or
            type(pin) is not str or not re.fullmatch(r"[0-9a-f]{64}",pin)):
        raise ValueError("Owner-only capture directory and independent SHA PIN required")
    first=_owner_only_file(folder/"first_receipt.json",8192)
    raw=_owner_only_file(folder/"raw_response.json",24*1024*1024)
    if sha256(first).hexdigest()!=pin:
        raise ValueError("Official first receipt SHA PIN mismatch")
    try:
        receipt=json.loads(first)
        body=json.loads(raw)
    except (UnicodeError,ValueError):
        raise ValueError("Malformed original official provider JSON") from None
    if (type(receipt) is not dict or
            receipt.get("schema")!=RAW_SCHEMA or receipt.get("source")!=source or
            receipt.get("raw_sha256")!=sha256(raw).hexdigest() or
            receipt.get("raw_length_bytes")!=len(raw) or
            receipt.get("official_leader_promotions")!=0 or
            receipt.get("full_historic_universe_pit_certified") is not False):
        raise ValueError("Official original receipt invariant violated")
    if utc(receipt["first_local_received_at_utc"])>decision.astimezone(timezone.utc):
        raise ValueError("Original official API data arrived after decision time")
    day=normalized_day(receipt.get("request_value"))
    count,quality=_decoded(raw,source,day=day[:4]+"-"+day[4:6]+"-"+day[6:],cik=None)
    if receipt.get("provider_row_count")!=count or receipt.get("quality")!=quality:
        raise ValueError("Original raw response does not match first receipt")
    return receipt,body


def verify_live_captures(*, krx_kospi:tuple[Path,str],
                         krx_kosdaq:tuple[Path,str],
                         dart_disclosures:tuple[Path,str],
                         market_day:str,security_id:str,
                         flow:dict,decision_at:datetime,
                         dart_complete:tuple[Path,str]|None=None) -> dict:
    originals={}
    for source,reference in zip(SOURCES,(krx_kospi,krx_kosdaq,dart_disclosures)):
        receipt,body=verified_local_capture(Path(reference[0]),source,reference[1],decision_at)
        originals[source]={**receipt,"first_receipt_sha256":reference[1],"body":body}
    complete=None
    if dart_complete is not None:
        folder,pin=dart_complete
        original_name=Path(dart_disclosures[0]).name
        mirror=Path(folder).parent/original_name
        # Strict 0600 verifier on the Mac copied original plus full-page
        # manifest SHA. Matching original first SHA is separately verified
        # from the SSD above; the original files remain untouched.
        complete=verify_dart_day(Path(folder),pin,first_folder=mirror,
                                 first_sha=dart_disclosures[1],
                                 decision_at=decision_at)
    return evaluate(requested_day=market_day,security_id=security_id,
                    originals=originals,flow=flow,decision_at=decision_at,
                    complete_dart=complete,
                    _verified_dart_token=(_DART_VERIFIED_TOKEN if complete is not None
                                          else None))

def render(report:dict) -> str:
    data=dict(report)
    saved=data.pop("content_sha256",None)
    if (saved!=sha256(canonical(data)).hexdigest() or
            data.get("schema")!=SCHEMA or
            data.get("orders_enabled") is not False or
            data.get("investment_leader_score_available") is not False):
        raise ValueError("Invalid research audit publication")
    x=lambda value:escape(str(value),quote=True)
    rows="".join(
        "<tr><td>"+x(src)+"</td><td>"+x(item["provider_row_count"])+
        "</td><td>"+x(item["quality"])+"</td><td>"+
        x(item["market_day"])+"</td></tr>"
        for src,item in sorted(report["source_receipts"].items())
    )
    issues=" · ".join(x(item) for item in report["blockers"]) or "없음"
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 공식 원천 동시점 감사</title>"
        "<style>body{font:15px system-ui;max-width:850px;margin:auto;padding:22px;"
        "background:#131a23;color:#f1f3f8}a{color:#9acaf8}table{width:100%;border-collapse:collapse}"
        "td,th{border-bottom:1px solid #5b6473;padding:12px;text-align:left}"
        "section{padding:15px;margin:14px 0;border:1px solid #4d5970;border-radius:9px}</style>"
        "</head><body><h1>KRX · DART · 키움 공식 원천 동시점 감사</h1>"
        "<p><a href='../index.html'>EraLeader 메인</a></p>"
        "<section><b>판정: "+x(report["readiness"])+"</b><br>시장 거래일 "
        +x(report["session"])+" · 종목 "+x(report["security_id"])+
        "<br>보류 사유: "+issues+"</section>"
        "<table><thead><tr><th>공급자</th><th>수신행</th><th>품질</th><th>거래일</th>"
        "</tr></thead><tbody>"+rows+"</tbody></table>"
        "<section>키움은 모의서버 연구용이며 생산시장 대표성·독립 최초 공표시각 인증이 없습니다."
        "<br>점수·공식 대장주 승격·실전 주문은 모두 비활성화됩니다.</section></body></html>"
    )
