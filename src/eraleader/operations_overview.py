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
import re

from .official_company_explorer import canonical
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


def _latest_marketwide_search(root:Path, now:datetime) -> dict|None:
    """Optional local search navigation, never a market/PIT certification."""
    if root.is_symlink() or not root.is_dir():
        return None
    choices=[]
    for folder in root.glob("marketwide_kr_search_*"):
        if (not re.fullmatch(r"marketwide_kr_search_[0-9]{8}(?:_[a-z0-9_-]{1,32})?",folder.name)
                or folder.is_symlink() or not folder.is_dir()):
            continue
        index=folder/"index.html"
        manifest=folder/"manifest.json"
        if (index.is_symlink() or manifest.is_symlink()
                or not index.is_file() or not manifest.is_file()
                or not 1000 <= index.stat().st_size <= 8_000_000
                or not 100 <= manifest.stat().st_size <= 10_000):
            continue
        try:
            doc=json.loads(manifest.read_bytes())
            digest=doc.pop("content_sha256")
            if (type(digest) is not str or sha256(canonical(doc)).hexdigest()!=digest
                    or doc.get("schema")!="eraleader.marketwide_local_search.v1"
                    or doc.get("market")!="KR"
                    or doc.get("research_only") is not True
                    or doc.get("official_leaders")!=0
                    or doc.get("official_100_point_rank_available") is not False
                    or doc.get("formal_selection") is not None
                    or type(doc.get("observed_stocks")) is not int
                    or not 1<=doc["observed_stocks"]<=5000):
                continue
            observed=date.fromisoformat(doc["source_market_session"])
            requested=date.fromisoformat(doc["requested_day"])
            published=datetime.fromisoformat(doc["published_at_utc"])
            if (published.tzinfo is None or not observed<=requested<=now.date()
                    or published.astimezone(timezone.utc)>now
                    or requested.strftime("%Y%m%d") not in folder.name):
                continue
            page=index.read_text(encoding="utf-8")
            marker='<script id="stock-meta" type="application/json">'
            if page.count(marker)!=1 or page.count('id="stock-data"')!=1:
                continue
            embedded=json.loads(page.split(marker,1)[1].split("</script>",1)[0])
            if embedded!={**doc,"content_sha256":digest}:
                continue
            choices.append((observed, published.astimezone(timezone.utc),folder.name,{
                "href":"../../"+folder.name+"/index.html",
                "market_session":observed.isoformat(),
                "requested_day":requested.isoformat(),
                "observed_stocks":doc["observed_stocks"],
                "partial_research_scored":doc.get("research_50_scored",0),
                "stale_warning":bool(doc.get("stale_warning")),
                "source_pit_certified":False,
            }))
        except (OSError,ValueError,KeyError,TypeError,UnicodeError,IndexError,OverflowError):
            continue
    return max(choices,key=lambda row:row[:3])[-1] if choices else None


def _latest_peer_flow(root:Path, now:datetime) -> dict|None:
    """Link only fully reverified, locally published partial peer research."""
    from .sector_peer_flow_research import SCHEMA as PEER_SCHEMA, _html
    base=root/"sector_peer_flow"
    if base.is_symlink() or not base.is_dir():
        return None
    found=[]
    for folder in list(base.iterdir())[:400]:
        if (folder.is_symlink() or not folder.is_dir()
                or not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}",folder.name)):
            continue
        manifest=folder/"peer_flow.json"
        index=folder/"index.html"
        if (manifest.is_symlink() or index.is_symlink()
                or not manifest.is_file() or not index.is_file()
                or not 300<=manifest.stat().st_size<=1_000_000
                or not 1000<=index.stat().st_size<=1_000_000):
            continue
        try:
            content=manifest.read_bytes()
            doc=json.loads(content)
            pin=doc.get("content_sha256")
            base_doc=dict(doc)
            base_doc.pop("content_sha256",None)
            if (type(pin) is not str
                    or sha256(canonical(base_doc)).hexdigest()!=pin
                    or content!=canonical(doc)+b"\n"
                    or doc.get("schema")!=PEER_SCHEMA
                    or doc.get("market")!="KR"
                    or doc.get("formal_leaders")!=0
                    or doc.get("execution_authority") is not False
                    or doc.get("orders_enabled") is not False
                    or doc.get("historical_independent_pit_certified") is not False
                    or doc.get("industry_growth_score_20_available")!=0
                    or doc.get("competitiveness_score_20_available")!=0
                    or doc.get("flow_score_10_available")!=0
                    or folder.name!="KR_"+doc["source_market_session"].replace("-","")+"_"
                           +doc["source_marketwide_sha256"][:16]):
                continue
            observed=date.fromisoformat(doc["source_market_session"])
            built=datetime.fromisoformat(doc["source_built_at_utc"])
            if (observed>now.date() or built.tzinfo is None
                    or built.astimezone(timezone.utc)>now):
                continue
            if index.read_bytes()!=_html(doc):
                continue
            found.append((observed,built,folder.name,{
                "href":"../../sector_peer_flow/"+folder.name+"/index.html",
                "market_session":observed.isoformat(),
                "revenue_peers":doc["observed_revenue_peer_ranks"],
                "operating_peers":doc["observed_operating_peer_ranks"],
                "raw_flow":doc["same_session_raw_broker_flow"],
                "formal_leaders":0,
            }))
        except (ValueError,KeyError,TypeError,OSError,UnicodeError,OverflowError):
            continue
    return max(found,key=lambda row:row[:3])[-1] if found else None


def _latest_flow_coverage(root:Path, now:datetime) -> dict|None:
    from .marketwide_flow_coverage import SCHEMA as COVERAGE,_render
    folder=root/"marketwide_flow_coverage"
    if folder.is_symlink() or not folder.is_dir():
        return None
    found=[]
    for batch in list(folder.iterdir())[:500]:
        if (batch.is_symlink() or not batch.is_dir() or
                not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}",batch.name)):
            continue
        metadata=batch/"manifest.json"
        page=batch/"index.html"
        if (metadata.is_symlink() or page.is_symlink() or
                not metadata.is_file() or not page.is_file()
                or metadata.stat().st_size>2_000_000 or
                page.stat().st_size>2_000_000):
            continue
        try:
            doc=json.loads(metadata.read_bytes())
            without=dict(doc)
            pin=without.pop("content_sha256",None)
            if (doc.get("schema")!=COVERAGE or doc.get("market")!="KR"
                    or doc.get("mode")!="demo" or
                    doc.get("selected_stocks_research_only") is not True or
                    doc.get("orders_enabled") is not False or
                    doc.get("formal_leaders")!=0 or
                    doc.get("investment_flow_score_available") is not False or
                    pin!=sha256(canonical(without)).hexdigest() or
                    metadata.read_bytes()!=canonical(doc)+b"\n" or
                    page.read_bytes()!=_render(doc)):
                continue
            market=date.fromisoformat(doc["source_market_session"])
            built=datetime.fromisoformat(doc["source_built_at_utc"])
            if (market>now.date() or built.tzinfo is None or
                    built.astimezone(timezone.utc)>now):
                continue
            pins=doc.get("batch_sha256")
            if type(pins) is not list or doc.get("published_batches")!=len(pins):
                continue
            digest=sha256(canonical({
                "source":doc["source_marketwide_sha256"],"batches":pins
            })).hexdigest()[:12]
            if batch.name!="KR_"+market.strftime("%Y%m%d")+"_"+doc["source_marketwide_sha256"][:16]+"_"+digest:
                continue
            found.append((market,len(pins),batch.name,{
                "href":"../../marketwide_flow_coverage/"+batch.name+"/index.html",
                "market_session":market.isoformat(),
                "collected_stocks":doc["collected_stocks"],
                "complete_20":doc["complete_20_observed_sessions"],
                "orders":0,
            }))
        except (KeyError,TypeError,ValueError,OSError,OverflowError,UnicodeError):
            continue
    return max(found,key=lambda x:x[:3])[-1] if found else None


def _latest_flow_diagnostics(root:Path, now:datetime) -> dict|None:
    from .marketwide_flow_diagnostics import SCHEMA as DIAGNOSTICS, _html
    base=root/"marketwide_flow_diagnostics"
    if base.is_symlink() or not base.is_dir():
        return None
    found=[]
    for folder in list(base.iterdir())[:500]:
        if (folder.is_symlink() or not folder.is_dir() or
                not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}",folder.name)):
            continue
        page=folder/"index.html"
        manifest=folder/"manifest.json"
        if (page.is_symlink() or manifest.is_symlink() or
                not page.is_file() or not manifest.is_file() or
                page.stat().st_size>1_000_000 or
                manifest.stat().st_size>1_000_000):
            continue
        try:
            raw=manifest.read_bytes()
            doc=json.loads(raw)
            unsigned=dict(doc)
            witness=unsigned.pop("content_sha256",None)
            if (type(witness) is not str or
                    witness!=sha256(canonical(unsigned)).hexdigest() or
                    raw!=canonical(doc)+b"\n" or
                    doc.get("schema")!=DIAGNOSTICS or
                    doc.get("market")!="KR" or doc.get("mode")!="demo" or
                    doc.get("shares_proxy_method")!=
                    "KRX_MARKETCAP_DIVIDED_BY_SAME_SESSION_CLOSE_NOT_ACTUAL_FLOAT" or
                    doc.get("independent_historical_pit_certified") is not False or
                    doc.get("formal_leaders")!=0 or
                    doc.get("formal_flow_score_10_available") is not False or
                    doc.get("orders_enabled") is not False or
                    page.read_bytes()!=_html(doc)):
                continue
            observed=date.fromisoformat(doc["source_market_session"])
            built=datetime.fromisoformat(doc["source_built_at_utc"])
            if (observed>now.date() or built.tzinfo is None or
                    built.astimezone(timezone.utc)>now):
                continue
            batches=doc["source_flow_batch_sha256"]
            digest=sha256(canonical({
                "source":doc["source_marketwide_sha256"],
                "batches":batches,"method":DIAGNOSTICS
            })).hexdigest()[:12]
            expected=("KR_"+observed.strftime("%Y%m%d")+"_"
                      +doc["source_marketwide_sha256"][:16]+"_"+digest)
            if folder.name!=expected:
                continue
            found.append((observed,len(batches),folder.name,{
                "href":"../../marketwide_flow_diagnostics/"+folder.name+"/index.html",
                "market_session":observed.isoformat(),
                "observed_stocks":doc["stocks_with_flow"],
                "proxy_denominators":doc["stocks_with_usable_denominator"],
                "formal_flow_score":False,
                "orders":0,
            }))
        except (ValueError,KeyError,TypeError,OSError,OverflowError,UnicodeError):
            continue
    return max(found,key=lambda item:item[:3])[-1] if found else None


def _latest_volume_alignment(root:Path, now:datetime)->dict|None:
    from .marketwide_volume_alignment import SCHEMA as VOL_SCHEMA, _html
    base=root/"marketwide_volume_alignment"
    if base.is_symlink() or not base.is_dir():
        return None
    candidates=[]
    for folder in list(base.iterdir())[:400]:
        if (folder.is_symlink() or not folder.is_dir() or
                not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}",folder.name)):
            continue
        manifest=folder/"manifest.json"
        page=folder/"index.html"
        if (manifest.is_symlink() or page.is_symlink()
                or not manifest.is_file() or not page.is_file()
                or manifest.stat().st_size>2_000_000
                or page.stat().st_size>2_000_000):
            continue
        try:
            raw=manifest.read_bytes()
            doc=json.loads(raw)
            unsigned=dict(doc);digest=unsigned.pop("content_sha256",None)
            if (digest!=sha256(canonical(unsigned)).hexdigest() or
                    raw!=canonical(doc)+b"\n" or
                    doc.get("schema")!=VOL_SCHEMA or doc.get("market")!="KR" or
                    doc.get("flow_score_10_available")!=0 or
                    doc.get("flow_volume_fully_aligned_stocks")!=0 or
                    doc.get("formal_leaders")!=0 or
                    doc.get("orders_enabled") is not False or
                    doc.get("flow_daily_dates_persisted") is not False or
                    page.read_bytes()!=_html(doc)):
                continue
            observed=date.fromisoformat(doc["source_market_session"])
            source_time=datetime.fromisoformat(doc["source_built_at_utc"])
            if (observed>now.date() or source_time.tzinfo is None or
                    source_time.astimezone(timezone.utc)>now):
                continue
            ref=sha256(canonical({
                "source":doc["source_marketwide_sha256"],
                "flow":doc["flow_batch_sha256"],
                "cache":doc["local_cache_sha256"]
            })).hexdigest()[:12]
            expected=("KR_"+observed.strftime("%Y%m%d")+"_"+doc["source_marketwide_sha256"][:16]+"_"+ref)
            if expected!=folder.name:continue
            candidates.append((observed,len(doc["flow_batch_sha256"]),folder.name,{
                "href":"../../marketwide_volume_alignment/"+folder.name+"/index.html",
                "market_session":observed.isoformat(),
                "flow_stocks":doc["flow_stocks"],
                "cache_session_matched":doc["source_session_price_cache_matched"],
                "aligned":0,"orders":0,
            }))
        except (ValueError,TypeError,KeyError,OSError,OverflowError,UnicodeError):
            continue
    return max(candidates,key=lambda c:c[:3])[-1] if candidates else None


def _latest_dated_exact_volume(root:Path, now:datetime, *, all_stocks:bool=False)->dict|list|None:
    from .marketwide_dated_volume import SCHEMA as DATED_SCHEMA,_html
    base=root/"marketwide_dated_volume"
    if base.is_symlink() or not base.is_dir():
        return [] if all_stocks else None
    found=[]
    for folder in list(base.iterdir())[:400]:
        if (folder.is_symlink() or not folder.is_dir() or
                not re.fullmatch(r"KR_[0-9]{8}_[0-9]{6}_[a-f0-9]{12}",folder.name)):
            continue
        manifest=folder/"manifest.json"
        index=folder/"index.html"
        if (manifest.is_symlink() or index.is_symlink()
                or not manifest.is_file() or not index.is_file()
                or manifest.stat().st_size>100_000 or
                index.stat().st_size>100_000):
            continue
        try:
            raw=manifest.read_bytes()
            payload=json.loads(raw)
            unsigned=dict(payload)
            digest=unsigned.pop("content_sha256",None)
            if (type(digest) is not str or
                    digest!=sha256(canonical(unsigned)).hexdigest()
                    or raw!=canonical(payload)+b"\n"
                    or payload.get("schema")!=DATED_SCHEMA
                    or payload.get("market")!="KR"
                    or payload.get("mode")!="demo"
                    or payload.get("formal_flow_score_10") is not None
                    or payload.get("formal_leaders")!=0
                    or payload.get("orders_enabled") is not False
                    or payload.get("order_instructions") is not False
                    or index.read_bytes()!=_html(payload)):
                continue
            observed=date.fromisoformat(payload["source_market_session"])
            if observed>now.date():
                continue
            pinned={
                "market":payload["source_marketwide_sha256"],
                "flow":payload["dated_flow_sha256"],
                "cache":payload["cache_file_sha256"],
            }
            if payload.get("official_volume_overlay_sha256") is not None:
                pinned["official_volume_overlay"]=payload["official_volume_overlay_sha256"]
            version=sha256(canonical(pinned)).hexdigest()[:12]
            expected=("KR_"+observed.strftime("%Y%m%d")+"_"+
                      payload["stock_code"]+"_"+version)
            if expected!=folder.name:
                continue
            periods=payload["periods"]
            if set(periods)!={"5","20"}:
                continue
            found.append((observed,periods["20"]["matched_price_volume_days"],
                          periods["5"]["matched_price_volume_days"],folder.name,{
                "href":"../../marketwide_dated_volume/"+folder.name+"/index.html",
                "market_session":observed.isoformat(),
                "code":payload["stock_code"],
                "volume_days_5":periods["5"]["matched_price_volume_days"],
                "volume_days_20":periods["20"]["matched_price_volume_days"],
                "orders":0,
            }))
        except (OSError,ValueError,KeyError,TypeError,OverflowError,UnicodeError):
            continue
    if not found:
        return [] if all_stocks else None
    if all_stocks:
        # Same SHA-verification path as the existing single best link;
        # keep the best immutable version PER stock (not one overall).
        preferred={}
        for row in found:
            code=row[-1]["code"]
            if code not in preferred or row[:4]>preferred[code][:4]:
                preferred[code]=row
        return [preferred[code][-1] for code in sorted(preferred)]
    return max(found,key=lambda v:v[:4])[-1]


def _latest_flow_research_score(root:Path, now:datetime)->dict|None:
    from .marketwide_flow_research_score import read_flow_research
    folder=root/"research_flow10_assessments"
    if folder.is_symlink() or not folder.is_dir():
        return None
    valid=[]
    for f in list(folder.iterdir())[:400]:
        if (f.is_symlink() or not f.is_file() or
                not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}\.json",f.name)):
            continue
        try:
            raw=json.loads(f.read_bytes())
            statement=read_flow_research(
                f,expected_market_sha=raw["source_marketwide_sha256"],
                clock=now)
            dt=datetime.fromisoformat(statement["computed_at_utc"])
            if (dt.tzinfo is None or dt.astimezone(timezone.utc)>now or
                    date.fromisoformat(statement["source_market_session"])>now.date()):
                continue
            rows=statement["rows"]
            scores=[{"code":r["security_id"],"research_score_10":r["research_score_10"]}
                    for r in rows]
            valid.append((dt,statement["content_sha256"],{
                "source_market_session":statement["source_market_session"],
                "computed_at_utc":statement["computed_at_utc"],
                "research_scores":scores,
                "formal_scores_available":False,"orders":0,
            }))
        except (OSError,ValueError,KeyError,TypeError,OverflowError,UnicodeError):
            continue
    return max(valid,key=lambda x:x[:2])[-1] if valid else None


def _latest_early_watch(root:Path,now:datetime)->dict|None:
    from .early_leader_watch_queue import _validated,_html
    base=root/"early_leader_watch_queue"
    if base.is_symlink() or not base.is_dir():
        return None
    valid=[]
    for sub in list(base.iterdir())[:400]:
        if (sub.is_symlink() or not sub.is_dir() or
                not re.fullmatch(r"KR_[0-9]{8}_[a-f0-9]{16}",sub.name)):
            continue
        manifest=sub/"watch_queue.json"
        page=sub/"index.html"
        if (manifest.is_symlink() or page.is_symlink()
                or not manifest.is_file() or not page.is_file()
                or manifest.stat().st_size>4_000_000
                or page.stat().st_size>700_000):
            continue
        try:
            content=_validated(manifest,clock=now)
            version=sha256(canonical({
                "market":content["source_marketwide_sha256"],
                "factor":content["source_factor_assessment_sha256"],
                "top":content["requested_top"],
                "peer_method":content["sector_peer_context_method"],
                **({"profitability_method":content["dart_profitability_method"],
                    "receipts":[((r["security_id"],r["dart_cfs_first_receipt_sha256"],
                                  r.get("dart_cfs_previous_first_receipt_sha256"))
                                 if content["dart_profitability_method"].endswith("_V2")
                                 else (r["security_id"],r["dart_cfs_first_receipt_sha256"]))
                                for r in content["review_queue"]]}
                   if content.get("dart_profitability_method") is not None else {}),
            })).hexdigest()[:16]
            observed=date.fromisoformat(content["source_market_session"])
            first=datetime.fromisoformat(content["watch_published_at_utc"])
            if (sub.name!="KR_"+observed.strftime("%Y%m%d")+"_"+version
                    or observed>now.date() or page.read_bytes()!=_html(content)):
                continue
            val={
                "href":"../../early_leader_watch_queue/"+sub.name+"/index.html",
                "market_session":observed.isoformat(),
                "count":content["review_candidates"],
                "tier_counts":content["tier_available_counts"],
                "receiver_neutral":True,"orders":0,
            }
            valid.append((observed,first,sub.name,val))
        except (KeyError,ValueError,OSError,TypeError,UnicodeError,OverflowError):
            continue
    return max(valid,key=lambda entry:entry[:3])[-1] if valid else None


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
        "kr_marketwide_search":_latest_marketwide_search(root,now),
        "kr_peer_flow_research":_latest_peer_flow(root,now),
        "kr_marketwide_flow_coverage":_latest_flow_coverage(root,now),
        "kr_marketwide_flow_diagnostics":_latest_flow_diagnostics(root,now),
        "kr_marketwide_volume_alignment":_latest_volume_alignment(root,now),
        "kr_marketwide_dated_exact_volume":_latest_dated_exact_volume(root,now),
        "kr_marketwide_dated_all_stocks":_latest_dated_exact_volume(root,now,all_stocks=True),
        "kr_flow10_heuristic_research":_latest_flow_research_score(root,now),
        "kr_early_leader_watch":_latest_early_watch(root,now),
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
    search=snapshot.get("kr_marketwide_search")
    if search is None:
        search_html="<p>한국시장 전체 종목 검색 화면: 검증 가능한 로컬 발행본 없음 (N/A).</p>"
    else:
        if (type(search) is not dict or
                set(search)!={"href","market_session","requested_day","observed_stocks",
                              "partial_research_scored","stale_warning","source_pit_certified"} or
                search["source_pit_certified"] is not False or
                type(search["observed_stocks"]) is not int or
                type(search["partial_research_scored"]) is not int or
                type(search["stale_warning"]) is not bool or
                not re.fullmatch(r"\.\./\.\./marketwide_kr_search_[0-9]{8}(?:_[a-z0-9_-]{1,32})?/index\.html",
                                 search["href"])):
            raise ValueError("Unsafe marketwide search link")
        search_html=('<p><a href="'+escape(search["href"],quote=True)+'">'
                     '한국시장 전체 종목 검색 열기</a> · 관측일 '
                     +escape(search["market_session"])+' · '+str(search["observed_stocks"])
                     +'종목 · 연구용 부분점수 '+str(search["partial_research_scored"])
                     +'종목 · '+("자료 지연 / 오늘 시세 아님" if search["stale_warning"]
                                else "오늘 시세 인증 아님")+'</p>')
    peer=snapshot.get("kr_peer_flow_research")
    if peer is None:
        peer_html="<p>동종기업 성장·수급 비교: 검증된 로컬 발행본 없음 (N/A).</p>"
    else:
        if (type(peer) is not dict or
                set(peer)!={"href","market_session","revenue_peers",
                            "operating_peers","raw_flow","formal_leaders"}
                or peer["formal_leaders"]!=0
                or any(type(peer[key]) is not int or peer[key]<0
                       for key in ("revenue_peers","operating_peers","raw_flow"))
                or not re.fullmatch(r"\.\./\.\./sector_peer_flow/KR_[0-9]{8}_[a-f0-9]{16}/index\.html",peer["href"])):
            raise ValueError("Unsafe sector peer flow research link")
        peer_html=('<p><a href="'+escape(peer["href"],quote=True)+'">'
                   '한국 동종기업 성장·수급 비교 보기</a> · 관측일 '
                   +escape(peer["market_session"])+ ' · 동종 매출 순위 '
                   +str(peer["revenue_peers"])+'사 · 영업성장 순위 '
                   +str(peer["operating_peers"])+'사 · 원시 수급 '
                   +str(peer["raw_flow"])+'사 · 정식 성장/경쟁력/수급 점수 N/A</p>')
    coverage=snapshot.get("kr_marketwide_flow_coverage")
    if coverage is None:
        coverage_html="<p>키움 누적 선택종목 수급: 검증된 발행본 없음 (N/A).</p>"
    else:
        if (type(coverage) is not dict or
                set(coverage)!={"href","market_session","collected_stocks",
                                "complete_20","orders"}
                or coverage["orders"]!=0 or
                type(coverage["collected_stocks"]) is not int or
                type(coverage["complete_20"]) is not int or
                not 0<=coverage["complete_20"]<=coverage["collected_stocks"] or
                not re.fullmatch(r"\.\./\.\./marketwide_flow_coverage/KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}/index\.html",coverage["href"])):
            raise ValueError("Unsafe marketwide flow coverage link")
        coverage_html=('<p><a href="'+escape(coverage["href"],quote=True)+'">'
                       '키움 기관·외국인 누적 관찰 보기</a> · 원시 수급 '
                       +str(coverage["collected_stocks"])+'종목 · 20관측 완성 '
                       +str(coverage["complete_20"])+'종목 · 연구용 / 주문 0</p>')
    diagnostic=snapshot.get("kr_marketwide_flow_diagnostics")
    if diagnostic is None:
        diagnostic_html="<p>수급·추정 주식수 비율: 검증된 로컬 발행본 없음 (N/A).</p>"
    else:
        if (type(diagnostic) is not dict or
                set(diagnostic)!={"href","market_session","observed_stocks",
                                  "proxy_denominators","formal_flow_score","orders"}
                or diagnostic["formal_flow_score"] is not False
                or diagnostic["orders"]!=0
                or type(diagnostic["observed_stocks"]) is not int
                or type(diagnostic["proxy_denominators"]) is not int
                or not 0<=diagnostic["proxy_denominators"]<=diagnostic["observed_stocks"]
                or not re.fullmatch(r"\.\./\.\./marketwide_flow_diagnostics/KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}/index\.html",diagnostic["href"])):
            raise ValueError("Unsafe marketwide flow diagnostic link")
        diagnostic_html=('<p><a href="'+escape(diagnostic["href"],quote=True)+'">'
                         '키움 수급 추정 발행주식수 대비 보기</a> · 수급 '
                         +str(diagnostic["observed_stocks"])+'종목 · 분모 가용 '
                         +str(diagnostic["proxy_denominators"])
                         +'종목 · 실물 수급점수 N/A / 주문 0</p>')
    volume=snapshot.get("kr_marketwide_volume_alignment")
    if volume is None:
        volume_html="<p>기관·외국인 수급의 거래량 날짜 일치 보고서: 없음 (N/A).</p>"
    else:
        if (type(volume) is not dict or
                set(volume)!={"href","market_session","flow_stocks",
                              "cache_session_matched","aligned","orders"}
                or volume["orders"]!=0 or volume["aligned"]!=0
                or any(type(volume[x]) is not int or volume[x]<0
                       for x in ("flow_stocks","cache_session_matched"))
                or volume["cache_session_matched"]>volume["flow_stocks"]
                or not re.fullmatch(r"\.\./\.\./marketwide_volume_alignment/KR_[0-9]{8}_[a-f0-9]{16}_[a-f0-9]{12}/index\.html",volume["href"])):
            raise ValueError("Unsafe marketwide volume alignment link")
        volume_html=('<p><a href="'+escape(volume["href"],quote=True)+'">'
                     '기관·외국인 수급과 거래량 날짜 일치 보기</a> · 관측일 '
                     +escape(volume["market_session"])+' · 수급 '
                     +str(volume["flow_stocks"])+'종목 · 거래량 동일날짜 '
                     +str(volume["cache_session_matched"])
                     +'종목 · 수급-거래량 5/20 정합 0 · flow10 점수 N/A</p>')
    exact=snapshot.get("kr_marketwide_dated_exact_volume")
    if exact is None:
        exact_html="<p>정확한 날짜별 키움 수급·거래량 비교: 발행자료 없음 (N/A).</p>"
    else:
        if (type(exact) is not dict or
                set(exact)!={"href","market_session","code","volume_days_5",
                             "volume_days_20","orders"}
                or exact["orders"]!=0
                or any(type(exact[k]) is not int or not 0<=exact[k]<=n
                       for k,n in (("volume_days_5",5),("volume_days_20",20)))
                or not re.fullmatch(r"\.\./\.\./marketwide_dated_volume/KR_[0-9]{8}_[0-9]{6}_[a-f0-9]{12}/index\.html",exact["href"])):
            raise ValueError("Unsafe dated exact flow link")
        exact_html=('<p><a href="'+escape(exact["href"],quote=True)+'">'
                    '키움 수급 날짜별 거래량 대조 보기</a> · 관측일 '
                    +escape(exact["market_session"])+' · 종목 '
                    +escape(exact["code"])+' · 5개 중 '
                    +str(exact["volume_days_5"])+'개/20개 중 '
                    +str(exact["volume_days_20"])+'개 거래량 날짜 확인 · 공인 수급점수 N/A</p>')
    all_dated=snapshot.get("kr_marketwide_dated_all_stocks",[])
    if (type(all_dated) is not list or len(all_dated)>400 or
            len({v.get("code") for v in all_dated if type(v) is dict})!=len(all_dated)):
        raise ValueError("Unsafe multi-stock dated flow comparison")
    if all_dated:
        parts=[]
        for entry in all_dated:
            if (type(entry) is not dict or
                    set(entry)!={"href","market_session","code",
                                 "volume_days_5","volume_days_20","orders"} or
                    entry["orders"]!=0 or
                    type(entry["code"]) is not str or
                    not re.fullmatch(r"[0-9]{6}",entry["code"]) or
                    any(type(entry[k]) is not int or not 0<=entry[k]<=limit
                        for k,limit in (("volume_days_5",5),("volume_days_20",20))) or
                    not re.fullmatch(r"\.\./\.\./marketwide_dated_volume/KR_[0-9]{8}_[0-9]{6}_[a-f0-9]{12}/index\.html",entry["href"])):
                raise ValueError("Unsafe multi-stock dated flow link")
            parts.append('<tr><td>'+escape(entry["code"])+'</td><td>'
                         +escape(entry["market_session"])+'</td><td>'
                         +str(entry["volume_days_5"])+'/5</td><td>'
                         +str(entry["volume_days_20"])+'/20</td><td><a href="'
                         +escape(entry["href"],quote=True)
                         +'">날짜별 수급·거래량 보기</a></td></tr>')
        all_dated_html=('<div class="wrap"><table><thead><tr><th>종목코드</th>'
                        '<th>시장관측일</th><th>최근5</th><th>최근20</th>'
                        '<th>개별 검증본</th></tr></thead><tbody>'
                        +''.join(parts)+'</tbody></table></div>'
                        '<p><small>이 표는 수급 검증본의 종목별 관측 커버리지이며 '
                        '대장주 순위·정식 수급10점이 아닙니다.</small></p>')
    else:
        all_dated_html="<p>종목별 검증된 날짜별 수급 보고서가 없습니다 (N/A).</p>"
    heuristic=snapshot.get("kr_flow10_heuristic_research")
    if heuristic is None:
        heuristic_html="<p>기간별 수급 가중 연구점수: 검증된 평가자료 없음 (N/A).</p>"
    else:
        if (type(heuristic) is not dict or
                set(heuristic)!={"source_market_session","computed_at_utc",
                                "research_scores","formal_scores_available","orders"}
                or heuristic["formal_scores_available"] is not False
                or heuristic["orders"]!=0
                or type(heuristic["research_scores"]) is not list
                or len(heuristic["research_scores"])>20):
            raise ValueError("Unsafe flow research score overview")
        score_rows=[]
        seen=set()
        for item in heuristic["research_scores"]:
            if (type(item) is not dict or
                    set(item)!={"code","research_score_10"} or
                    type(item["code"]) is not str or
                    not re.fullmatch(r"[0-9]{6}",item["code"]) or
                    item["code"] in seen or
                    type(item["research_score_10"]) not in (int,float) or
                    not 0<=item["research_score_10"]<=10):
                raise ValueError("Unsafe flow research score row")
            seen.add(item["code"])
            score_rows.append('<tr><td>'+escape(item["code"])+'</td><td>'
                              +escape(str(item["research_score_10"]))+
                              '/10 (연구용)</td></tr>')
        heuristic_html=('<p>시장 관측일 '+escape(heuristic["source_market_session"])+
                        ' · 최초 연구평가시각 '+escape(heuristic["computed_at_utc"])+
                        ' · 산업/경쟁력 미충족, 공식 수급10점 N/A</p><div class="wrap">'
                        '<table><thead><tr><th>종목코드</th><th>가중 수급 연구점수</th>'
                        '</tr></thead><tbody>'+''.join(score_rows)+
                        '</tbody></table></div>'
                        '<p><small>검증된 날짜별 순매매/거래량을 임시 고정 산식으로 '
                        '변환했을 뿐 대장주 순위·실전 매수/매도 신호가 아닙니다.</small></p>')

    early=snapshot.get("kr_early_leader_watch")
    if early is None:
        early_html="<p>대장주 후보 관찰 작업목록: 발행된 검증자료 없음 (N/A).</p>"
    else:
        if (type(early) is not dict or
                set(early)!={"href","market_session","count","tier_counts",
                             "receiver_neutral","orders"}
                or early["receiver_neutral"] is not True
                or early["orders"]!=0
                or type(early["count"]) is not int or
                not 1<=early["count"]<=100
                or type(early["tier_counts"]) is not dict
                or set(early["tier_counts"])!={
                    "A_PRICE_EARNINGS_OBSERVED","B_PRICE_FLOW_OBSERVED",
                    "C_KRX_PRICE_TOP20","D_PRICE_STRENGTH_OBSERVED"}
                or any(type(x) is not int or x<0
                       for x in early["tier_counts"].values())
                or not re.fullmatch(r"\.\./\.\./early_leader_watch_queue/KR_[0-9]{8}_[a-f0-9]{16}/index\.html",
                                    early["href"])):
            raise ValueError("Unsafe early leader watch link")
        early_html=('<p><a href="'+escape(early["href"],quote=True)+'">'
                    '한국 대장주 후보 관찰 우선목록 보기</a> · 거래일 '
                    +escape(early["market_session"])+' · 우선 관찰 '
                    +str(early["count"])+'종목 · 가격+실적 '
                    +str(early["tier_counts"]["A_PRICE_EARNINGS_OBSERVED"])
                    +'종목 · 가격+수급 '
                    +str(early["tier_counts"]["B_PRICE_FLOW_OBSERVED"])
                    +'종목 · 공식 선정 0 / 주문 0</p>')
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
<h2>한국 전체시장 종목 검색</h2>\n{search_html}\n<p><small>부분 연구점수는 투자 1~20위·공인 대장주 확정이 아닙니다.</small></p>\n<h2>산업 내 성장·수급 비교</h2>\n{peer_html}\n<h2>키움 선택종목 수급 누적</h2>\n{coverage_html}\n<h2>추정 발행주식수 대비 수급 비율</h2>\n{diagnostic_html}\n<h2>키움 수급과 기존 거래량 캐시 날짜 일치 확인</h2>\n{volume_html}\n<h2>실제 수급일자별 거래량 비교</h2>\n{exact_html}\n<h2>수급·거래량 검증 종목 전체</h2>\n{all_dated_html}\n<h2>가중 수급 연구점수 (정식 10점 아님)</h2>\n{heuristic_html}\n<h2>미래 대장주 우선 관찰 작업목록</h2>\n{early_html}\n<h2>로컬 연구 예약 실행 및 데이터 상태</h2>
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
