"""6_2/6_5: conservative read-only local operations status for KR/US research.

No live market data, no original PIT audit, no authentication, no API calls,
no scheduled jobs and no claims about success/precision. Read only the three
*production* scheduler checkpoints; ignore demo/trial output directories.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import json

from .delivery import BASE_CSS
from .local_backup import DB_NAMES, verify_backup
from .watch_operating_reports import _atomic_text

SCHEMA="eraleader.local_operations_overview.v1"
GATE="HOLD_UNVERIFIED_RESEARCH"
MAX_CHECKPOINT_BYTES=65536
MAX_PRICE_AGE_DAYS=10
MAX_WATCH_RUN_AGE_DAYS=7
PERIODS=("daily","weekly","monthly")
SPEC={
    "price":("scheduled","scheduler_control","scheduler_backups",
             "last_verified_batch.json","RESEARCH_ONLY_VERIFIED_BACKUP","eraleader_"),
    "watch":("scheduled_watch","scheduler_watch_control","scheduler_watch_backups",
             "last_verified_watch_only.json","WATCH_ONLY_RESEARCH_VERIFIED_BACKUP","watch_only_"),
    "maturity":("scheduled_maturity","scheduler_maturity_control",
                "scheduler_maturity_backups","last_verified_ranked_maturity_only.json",
                "RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP","ranked_maturity_only_"),
}
MODES=tuple(SPEC)
STATES=frozenset({
    "NO_CHECKPOINT","CHECKPOINT_INVALID","ARCHIVE_PATH_REJECTED",
    "ARCHIVE_UNVERIFIED","INCOMPLETE_ARCHIVE","PUBLISHED_BYTES_MISMATCH",
    "STALE_PRICE_OBSERVATIONS","OUTDATED_RESEARCH_SNAPSHOT",
    "SOURCE_NOT_RECHECKED",
})
LABELS={
    "NO_CHECKPOINT":"예약 완료 기록 없음",
    "CHECKPOINT_INVALID":"완료 기록이 손상되었거나 안전 계약 위반",
    "ARCHIVE_PATH_REJECTED":"백업 경로가 승인된 로컬 폴더가 아님",
    "ARCHIVE_UNVERIFIED":"백업 ZIP/매니페스트 무결성 확인 실패",
    "INCOMPLETE_ARCHIVE":"필수 한국·미국 결과가 백업에서 누락됨",
    "PUBLISHED_BYTES_MISMATCH":"실제 화면·보고서가 검증된 백업과 다름",
    "STALE_PRICE_OBSERVATIONS":"과거 시장 관측일 · 가격 자료 갱신 필요",
    "OUTDATED_RESEARCH_SNAPSHOT":"이전 WATCH 연구 실행이 오래됨",
    "SOURCE_NOT_RECHECKED":"파일 SHA 일치 · 현재 원천 재감사 별도 필요",
}


def _unique(pairs:list[tuple[str,object]]) -> dict:
    obj={}
    for key,value in pairs:
        if key in obj:
            raise ValueError("Duplicated operations checkpoint key")
        obj[key]=value
    return obj


def _checkpoint(path:Path,mode:str,now:datetime) -> tuple[dict,dict]:
    if (path.is_symlink() or path.parent.is_symlink() or
        not path.is_file() or not 0<path.stat().st_size<=MAX_CHECKPOINT_BYTES):
        raise ValueError("Missing/unsafe scheduler checkpoint")
    try:
        record=json.loads(path.read_bytes(),object_pairs_hook=_unique)
    except (UnicodeError,ValueError,TypeError) as exc:
        raise ValueError("Invalid operations checkpoint JSON") from exc
    if not isinstance(record,dict) or record.get("status")!=SPEC[mode][4]:
        raise ValueError("Unexpected/unsafe completed research status")
    if (record.get("dry_run_only") is not True or
        type(record.get("messages_sent")) is not int or record["messages_sent"]!=0 or
        type(record.get("external_api_calls")) is not int or
        record["external_api_calls"]!=0):
        raise ValueError("A live delivery claim cannot be displayed as local research")
    raw_time=record.get("run_finished_utc")
    if not isinstance(raw_time,str):
        raise ValueError("Research checkpoint has no verified run clock")
    try:
        finished=datetime.fromisoformat(raw_time)
    except ValueError as exc:
        raise ValueError("Invalid research run clock") from exc
    if (finished.tzinfo is None or finished.utcoffset() is None or
        finished.astimezone(timezone.utc)>now+timedelta(minutes=5)):
        raise ValueError("Missing timezone or future scheduler checkpoint")
    finished=finished.astimezone(timezone.utc)
    details={
        "run_finished_utc":finished.isoformat(),
        "run_age_days":max(0,int((now-finished).total_seconds()//86400)),
    }
    if mode=="price":
        observations=record.get("observations")
        # The first local price scheduler checkpoint predated optional WATCH
        # integration; absence means price-only, not corrupt or PIT-certified.
        if (not isinstance(observations,dict) or set(observations)!={"KR","US"} or
            ("watch_research_enabled" in record and
             type(record["watch_research_enabled"]) is not bool)):
            raise ValueError("KR/US price claims are incomplete")
        parsed={}
        age={}
        for market in ("KR","US"):
            value=observations[market]
            if not isinstance(value,str) or len(value)!=10:
                raise ValueError("Invalid market observation date")
            try:
                observed=date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Invalid market session date") from exc
            days=(now.date()-observed).days
            if days < -1:
                raise ValueError("Future market session in research checkpoint")
            parsed[market]=observed.isoformat()
            age[market]=max(0,days)
        details["observations_as_claimed"]=parsed
        details["market_observation_age_days"]=age
        details["used_stale_override_at_run"]=record.get("used_stale_override") is True
    elif mode=="watch":
        if (record.get("watch_research_enabled") is not True or
            record.get("official_leaders_confirmed")!=0 or
            record.get("independent_market_pit_certified") is not False or
            record.get("real_leader_prediction_certified") is not False):
            raise ValueError("WATCH claimed success or independent PIT")
    else:
        if (record.get("ranked_maturity_research_enabled") is not True or
            record.get("official_leaders_confirmed")!=0 or
            record.get("actual_future_leader_skill_certified") is not False or
            record.get("outcome_labels_read") is not False or
            type(record.get("ranked_maturity_report_pages")) is not int or
            record["ranked_maturity_report_pages"]!=16):
            raise ValueError("Maturity outcome/official leader claims are unsupported")
        fingerprints=record.get("ranked_maturity_fingerprints")
        if not isinstance(fingerprints,dict) or set(fingerprints)!={"KR","US"}:
            raise ValueError("Both sealed native Top-K markets are required")
        counts={}
        for market in ("KR","US"):
            items=fingerprints[market]
            if not isinstance(items,dict):
                raise ValueError("Malformed market maturity inventory")
            values={}
            for name in ("horizon_pending","horizon_elapsed"):
                value=items.get(name)
                if type(value) is not int or not 0<=value<=100000:
                    raise ValueError("Unsafe Top-K maturity inventory count")
                values[name]=value
            counts[market]=values
        details["horizon_status_at_last_run_only"]=counts
    return record,details


def _expected(mode:str, details:dict) -> set[str]:
    if mode=="price":
        out={"kr_latest.json","us_latest.json","site/kr.html","site/us.html"}
        for market in ("KR","US"):
            observed=details["observations_as_claimed"][market]
            for period in PERIODS:
                out.add(f"reports/{market.lower()}_{period}_{observed}.md")
        return out
    head="watch" if mode=="watch" else "ranked_maturity"
    out={f"{'watch_operating' if mode=='watch' else 'ranked_maturity'}_{market}_research.json"
         for market in ("kr","us")}
    for market in ("kr","us"):
        if mode=="maturity":
            out.add(f"site/ranked_maturity_{market}.html")
        for period in PERIODS:
            out.add(f"site/{head}_{period}_{market}.html")
            out.add(f"reports/{head}_{period}_{market}.md")
    return out


def _compare_backup_and_live(archive:Path,derived:Path,mandatory:set[str]) -> tuple[str,int]:
    """Archive SHA first, then compare every published non-SQLite file byte."""
    try:
        verified=verify_backup(archive)
        if verified.get("status")!="LOCAL_BACKUP_VERIFIED":
            return "ARCHIVE_UNVERIFIED",0
    except (OSError,ValueError,KeyError,TypeError,BadZipFile,RuntimeError):
        return "ARCHIVE_UNVERIFIED",0
    try:
        with ZipFile(archive,"r") as reader:
            manifest=json.loads(reader.read("MANIFEST.json"))
            entries={item["path"]:item for item in manifest["files"]}
            if not mandatory.issubset(entries):
                return "INCOMPLETE_ARCHIVE",0
            tracked=[item for item in manifest["files"]
                     if Path(item["path"]).name not in DB_NAMES]
            if derived.is_symlink() or derived.parent.is_symlink():
                return "PUBLISHED_BYTES_MISMATCH",0
            for item in tracked:
                file=derived/item["path"]
                if (file.is_symlink() or file.parent.is_symlink() or
                    not file.is_file() or file.stat().st_size!=item["bytes"]):
                    return "PUBLISHED_BYTES_MISMATCH",0
                digest=sha256()
                with file.open("rb") as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b""):
                        digest.update(chunk)
                if digest.hexdigest()!=item["sha256"]:
                    return "PUBLISHED_BYTES_MISMATCH",0
    except (OSError,ValueError,KeyError,TypeError,BadZipFile,RuntimeError):
        return "PUBLISHED_BYTES_MISMATCH",0
    return "ARCHIVE_LIVE_MATCHED",len(tracked)


def _audit_mode(root:Path,mode:str,now:datetime) -> dict:
    result={
        "state":"NO_CHECKPOINT","source_reverified_now":False,
        "archive_live_bytes_matched":False,"matched_published_files":0,
        "run_finished_utc":None,"run_age_days":None,
    }
    output,control,backup_folder,marker,_,prefix=SPEC[mode]
    cp=root/control/marker
    if not cp.exists() and not cp.is_symlink():
        return result
    try:
        record,details=_checkpoint(cp,mode,now)
    except (ValueError,OSError):
        result["state"]="CHECKPOINT_INVALID"
        return result
    result.update(details)
    archive_name=record.get("archive")
    folder=root/backup_folder
    if not isinstance(archive_name,str):
        result["state"]="ARCHIVE_PATH_REJECTED"
        return result
    archive=Path(archive_name)
    if (not archive.is_absolute() or ".." in archive.parts or
        archive.parent!=folder or not archive.name.startswith(prefix) or
        archive.suffix!=".zip" or archive.is_symlink() or
        folder.is_symlink() or not archive.is_file()):
        result["state"]="ARCHIVE_PATH_REJECTED"
        return result
    integrity,count=_compare_backup_and_live(archive,root/output,_expected(mode,details))
    if integrity!="ARCHIVE_LIVE_MATCHED":
        result["state"]=integrity
        return result
    result["archive_live_bytes_matched"]=True
    result["matched_published_files"]=count
    if mode=="price" and max(details["market_observation_age_days"].values())>MAX_PRICE_AGE_DAYS:
        result["state"]="STALE_PRICE_OBSERVATIONS"
    elif mode=="watch" and details["run_age_days"]>MAX_WATCH_RUN_AGE_DAYS:
        result["state"]="OUTDATED_RESEARCH_SNAPSHOT"
    else:
        result["state"]="SOURCE_NOT_RECHECKED"
    return result


def audit_local_operations(project:Path, *,clock:datetime|None=None) -> dict:
    """Check checkpoint/ZIP/live bytes without touching the original market vault."""
    base=Path(project)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Operations dashboard needs a real project directory")
    now=(clock or datetime.now(timezone.utc))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Operations snapshot UTC clock must be timezone aware")
    now=now.astimezone(timezone.utc)
    root=base/"output"
    modes={mode:_audit_mode(root,mode,now) for mode in MODES}
    return {
        "schema_version":SCHEMA,
        "evaluated_at_utc":now.isoformat(),
        "overall_gate":GATE,
        "modes":modes,
        "archive_live_bytes_matched_modes":sum(
            m["archive_live_bytes_matched"] for m in modes.values()),
        "local_snapshot_integrity_only":True,
        "original_pit_sources_reverified_now":False,
        "actual_future_leader_skill_certified":False,
        "official_leader_promotions":0,
        "live_notifications_sent":0,
        "external_api_calls":0,
        "real_precision_at_k":None,
    }


def render_operations_overview(snapshot:dict) -> str:
    """Render a static local research status page, never a real trading signal."""
    if (not isinstance(snapshot,dict) or snapshot.get("schema_version")!=SCHEMA or
        snapshot.get("overall_gate")!=GATE or
        snapshot.get("actual_future_leader_skill_certified") is not False or
        snapshot.get("original_pit_sources_reverified_now") is not False or
        snapshot.get("official_leader_promotions")!=0 or
        snapshot.get("live_notifications_sent")!=0 or
        snapshot.get("external_api_calls")!=0 or
        snapshot.get("real_precision_at_k") is not None):
        raise ValueError("Operations overview refuses official/live certification")
    modes=snapshot.get("modes")
    if (not isinstance(modes,dict) or set(modes)!=set(MODES) or
        not all(isinstance(v,dict) for v in modes.values()) or
        snapshot.get("local_snapshot_integrity_only") is not True):
        raise ValueError("Missing or unsafe KR/US research scheduler evidence")
    verified_count=sum(v.get("archive_live_bytes_matched") is True
                       for v in modes.values())
    if (type(snapshot.get("archive_live_bytes_matched_modes")) is not int or
        not 0<=verified_count<=3 or
        snapshot["archive_live_bytes_matched_modes"]!=verified_count):
        raise ValueError("Forged operations evidence count")
    rows=[]
    for mode,title in (("price","가격 기반 KR·US 관찰"),
                       ("watch","신규 WATCH·교체 연구"),
                       ("maturity","사전 Top-K 만기 감시")):
        entry=modes[mode]
        state=entry.get("state")
        if (state not in STATES or entry.get("source_reverified_now") is not False or
            type(entry.get("archive_live_bytes_matched")) is not bool):
            raise ValueError("Unsafe operations mode state")
        last=entry.get("run_finished_utc") or "N/A"
        date_text="N/A"
        if mode=="price" and isinstance(entry.get("observations_as_claimed"),dict):
            date_text="KR "+str(entry["observations_as_claimed"].get("KR","N/A"))+" · US "+str(
                entry["observations_as_claimed"].get("US","N/A"))
        elif mode=="maturity" and entry.get("horizon_status_at_last_run_only"):
            date_text="동결 후보 만기 상태: 마지막 완료 기록 시점만 표시"
        integrity="현재 보고서 SHA 일치" if entry["archive_live_bytes_matched"] else "미확인 / 불일치"
        rows.append("<tr>"+"".join("<td>"+escape(str(v))+"</td>" for v in (
            title,LABELS[state],last,date_text,integrity))+"</tr>")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader · 로컬 운영 상태</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 로컬 운영 상태</h1>
<div>한국·미국 미래 대장주 발굴 연구 · 읽기 전용 증거 상태</div></header><main>
<div class="note"><strong>운영 보류 · 실전 적중률 N/A · 공식 확정 대장주 0</strong>
<p>이 화면은 예약 실행 기록, 로컬 백업 SHA와 현재 보고서 파일만 확인합니다.
시장 원천 공시시각·종목군·상폐·기업행동·공급자 PIT를 현재 재감사하지 않았습니다.
오래된 배치·누락된 자료는 신규 매수 신호나 성공/실패로 해석하지 않습니다.</p></div>
<div class="stats">
<div class="stat">검증된 백업·화면 일치 모드<br><strong>{snapshot["archive_live_bytes_matched_modes"]} / 3</strong></div>
<div class="stat">실전 적중률<br><strong>N/A</strong></div>
<div class="stat">자동 알림 전송<br><strong>0 (미연결)</strong></div></div>
<h2>로컬 연구 예약 실행 및 데이터 상태</h2>
<div class="wrap"><table><thead><tr><th>모드</th><th>상태</th><th>마지막 완료(UTC)</th>
<th>관측 범위</th><th>백업 ↔ 현재 파일</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><small>점검 시각 UTC: {escape(str(snapshot["evaluated_at_utc"]))}. 원천 사전 등록·성공 라벨은 재검증하지 않았으며
로컬 파일 무결성은 독립 공급자 진위 확인이 아닙니다.</small></p>
<h2>안전 운영 정책</h2>
<p>로컬 전용, 실시간 외부 API 0, 실전 주문 0, 라이브 텔레그램·이메일 0.
외부 웹 공개/로그인 인증은 아직 구현되지 않았습니다. 로컬 127.0.0.1에서만 이용하세요.</p>
</main><footer>EraLeader · read-only operational research · PIT 미인증</footer></body></html>"""


def publish_operations_overview(project:Path, *,clock:datetime|None=None) -> dict:
    """Write derived operations JSON + local HTML, preserving original ledgers."""
    base=Path(project)
    target=base/"output"/"operations"
    index=target/"site"/"index.html"
    manifest=target/"operations_health_research.json"
    for path in (target,target/"site",index,manifest):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Unsafe linked operations report target")
    instant=clock or datetime.now(timezone.utc)
    before=audit_local_operations(base,clock=instant)
    html=render_operations_overview(before)
    serialized=json.dumps(before,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    # Fail closed if the scheduler changes a checkpoint or live artifact
    # between the initial inspection and publication.
    if audit_local_operations(base,clock=instant)!=before:
        raise RuntimeError("Operations checkpoint or derived evidence revised during audit")
    _atomic_text(index,html)
    _atomic_text(manifest,serialized)
    return {
        "status":"LOCAL_OPERATIONS_OVERVIEW_RESEARCH_ONLY",
        "mode_states":{mode:before["modes"][mode]["state"] for mode in MODES},
        "archive_live_bytes_matched_modes":before["archive_live_bytes_matched_modes"],
        "published_derived_pages":2,
        "source_pit_certified":False,
        "official_leader_promotions":0,
        "live_notifications_sent":0,
        "external_api_calls":0,
    }
