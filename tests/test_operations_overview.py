"""6_2/6_5 local operations observability — NO live signals, synthetic inputs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import subprocess
import sys
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from eraleader.local_backup import create_backup
from eraleader.operations_overview import audit_local_operations, render_operations_overview, publish_operations_overview

UTC=timezone.utc
NOW=datetime(2026,10,11,12,0,tzinfo=UTC)
MARKETS=("kr","us")
PERIODS=("daily","weekly","monthly")
CONFIG={
    "price":("scheduled","scheduler_control","scheduler_backups",
             "last_verified_batch.json","RESEARCH_ONLY_VERIFIED_BACKUP","eraleader_"),
    "watch":("scheduled_watch","scheduler_watch_control","scheduler_watch_backups",
             "last_verified_watch_only.json","WATCH_ONLY_RESEARCH_VERIFIED_BACKUP","watch_only_"),
    "maturity":("scheduled_maturity","scheduler_maturity_control","scheduler_maturity_backups",
                "last_verified_ranked_maturity_only.json",
                "RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP","ranked_maturity_only_"),
}

def expected(mode):
    if mode=="price":
        paths={"kr_latest.json","us_latest.json","site/kr.html","site/us.html"}
        for market,day in (("kr","2026-10-02"),("us","2026-02-26")):
            for period in PERIODS:
                paths.add(f"reports/{market}_{period}_{day}.md")
        return paths
    prefix="watch" if mode=="watch" else "ranked_maturity"
    paths={f"{'watch_operating' if mode=='watch' else 'ranked_maturity'}_{market}_research.json"
           for market in MARKETS}
    for market in MARKETS:
        if mode=="maturity":
            paths.add(f"site/ranked_maturity_{market}.html")
        for period in PERIODS:
            paths.update((f"site/{prefix}_{period}_{market}.html",
                          f"reports/{prefix}_{period}_{market}.md"))
    return paths


def seed(tmp_path,mode):
    out,control,backups,filename,status,prefix=CONFIG[mode]
    root=tmp_path/"output"
    derived=root/out
    for relative in sorted(expected(mode)):
        dest=derived/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(f"LOCAL RESEARCH MODE {mode}: {relative} N/A\n",encoding="utf-8")
    archive=root/backups/(prefix+"synthetic.zip")
    create_backup(derived,archive)
    record={"status":status,"run_finished_utc":(NOW-timedelta(hours=1)).isoformat(),
            "archive":str(archive),"messages_sent":0,"external_api_calls":0,
            "dry_run_only":True}
    if mode=="price":
        record.update(observations={"KR":"2026-10-02","US":"2026-02-26"},
                      used_stale_override=True,watch_research_enabled=False)
    elif mode=="watch":
        record.update(watch_research_enabled=True,official_leaders_confirmed=0,
                      independent_market_pit_certified=False,
                      real_leader_prediction_certified=False)
    else:
        record.update(ranked_maturity_research_enabled=True,
                      official_leaders_confirmed=0,
                      actual_future_leader_skill_certified=False,
                      outcome_labels_read=False,ranked_maturity_report_pages=16,
                      ranked_maturity_fingerprints={
                         "KR":{"horizon_pending":1,"horizon_elapsed":0},
                         "US":{"horizon_pending":0,"horizon_elapsed":1}})
    checkpoint=root/control/filename
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    checkpoint.write_text(json.dumps(record))
    return checkpoint,archive,derived

def status(snapshot,mode):
    return snapshot["modes"][mode]["state"]


def test_missing_main_modes_never_marked_live_or_healthy(tmp_path):
    snapshot=audit_local_operations(tmp_path,clock=NOW)
    assert all(status(snapshot,m)=="NO_CHECKPOINT" for m in CONFIG)
    assert snapshot["overall_gate"]=="HOLD_UNVERIFIED_RESEARCH"
    assert snapshot["actual_future_leader_skill_certified"] is False
    assert snapshot["official_leader_promotions"]==0
    assert snapshot["live_notifications_sent"]==0
    html=render_operations_overview(snapshot)
    assert "N/A" in html and "원천" in html


def test_price_backup_proven_but_old_us_session_is_stale(tmp_path):
    seed(tmp_path,"price")
    snapshot=audit_local_operations(tmp_path,clock=NOW)
    price=snapshot["modes"]["price"]
    assert price["archive_live_bytes_matched"] is True
    assert price["state"]=="STALE_PRICE_OBSERVATIONS"
    assert price["observations_as_claimed"]["KR"]=="2026-10-02"
    assert price["observations_as_claimed"]["US"]=="2026-02-26"
    assert price["source_reverified_now"] is False
    assert price["market_observation_age_days"]["US"]>100


def test_all_archives_verified_still_not_true_pit_or_live_delivery(tmp_path):
    for mode in CONFIG:
        seed(tmp_path,mode)
    snapshot=audit_local_operations(tmp_path,clock=NOW)
    assert status(snapshot,"price")=="STALE_PRICE_OBSERVATIONS"
    assert status(snapshot,"watch")=="SOURCE_NOT_RECHECKED"
    assert status(snapshot,"maturity")=="SOURCE_NOT_RECHECKED"
    assert snapshot["archive_live_bytes_matched_modes"]==3
    assert snapshot["overall_gate"]=="HOLD_UNVERIFIED_RESEARCH"
    assert snapshot["actual_future_leader_skill_certified"] is False
    assert "N/A" in render_operations_overview(snapshot)


@pytest.mark.parametrize("mode",list(CONFIG))
def test_existing_output_can_be_same_size_forged_and_is_not_accepted(tmp_path,mode):
    _,_,derived=seed(tmp_path,mode)
    sample=sorted(expected(mode))[0]
    path=derived/sample
    before=path.read_bytes()
    path.write_bytes(before.replace(b"N/A",b"100",1))
    assert len(path.read_bytes())==len(before)
    mode_status=audit_local_operations(tmp_path,clock=NOW)["modes"][mode]
    assert mode_status["archive_live_bytes_matched"] is False
    assert mode_status["state"]=="PUBLISHED_BYTES_MISMATCH"


@pytest.mark.parametrize("mode",list(CONFIG))
def test_missing_derived_artifact_fails_closed(tmp_path,mode):
    _,_,derived=seed(tmp_path,mode)
    (derived/sorted(expected(mode))[0]).unlink()
    assert status(audit_local_operations(tmp_path,clock=NOW),mode)=="PUBLISHED_BYTES_MISMATCH"


def test_corrupted_zip_is_not_presented_as_verified(tmp_path):
    _,zip_path,_=seed(tmp_path,"maturity")
    zip_path.write_bytes(b"no zip bytes")
    snapshot=audit_local_operations(tmp_path,clock=NOW)
    assert status(snapshot,"maturity")=="ARCHIVE_UNVERIFIED"


def test_checkpoint_external_archive_pointer_is_rejected_without_following_it(tmp_path,monkeypatch):
    checkpoint,zip_path,_=seed(tmp_path,"watch")
    alternate=tmp_path/"other"/"watch_only_copied.zip"
    alternate.parent.mkdir()
    alternate.write_bytes(zip_path.read_bytes())
    record=json.loads(checkpoint.read_text());record["archive"]=str(alternate)
    checkpoint.write_text(json.dumps(record))
    assert status(audit_local_operations(tmp_path,clock=NOW),"watch")=="ARCHIVE_PATH_REJECTED"


def test_checkpoint_link_and_archive_link_not_accepted(tmp_path):
    checkpoint,zip_path,_=seed(tmp_path,"watch")
    other=checkpoint.with_name("normal.json")
    checkpoint.rename(other)
    checkpoint.symlink_to(other)
    assert status(audit_local_operations(tmp_path,clock=NOW),"watch")=="CHECKPOINT_INVALID"
    checkpoint.unlink();other.rename(checkpoint)
    backup_copy=zip_path.with_name("watch_only_real.zip")
    zip_path.rename(backup_copy)
    zip_path.symlink_to(backup_copy)
    assert status(audit_local_operations(tmp_path,clock=NOW),"watch")=="ARCHIVE_PATH_REJECTED"


@pytest.mark.parametrize("field,value",[
    ("status","SUCCESS_CONFIRMED"),
    ("messages_sent",1),
    ("external_api_calls",1),
    ("dry_run_only",False),
    ("outcome_labels_read",True),
    ("actual_future_leader_skill_certified",True),
    ("official_leaders_confirmed",2),
])
def test_false_success_or_live_claims_are_blocked(tmp_path,field,value):
    checkpoint,_,_=seed(tmp_path,"maturity")
    record=json.loads(checkpoint.read_text())
    record[field]=value
    checkpoint.write_text(json.dumps(record))
    assert status(audit_local_operations(tmp_path,clock=NOW),"maturity")=="CHECKPOINT_INVALID"


@pytest.mark.parametrize("mutation",[
    lambda b:b'{"status":"fake","status":"second"}',
    lambda b:b" " * 70000,
    lambda b:b"not JSON",
])
def test_corrupt_duplicate_or_oversized_checkpoint_is_untrusted(tmp_path,mutation):
    checkpoint,_,_=seed(tmp_path,"maturity")
    checkpoint.write_bytes(mutation(checkpoint.read_bytes()))
    assert status(audit_local_operations(tmp_path,clock=NOW),"maturity")=="CHECKPOINT_INVALID"


@pytest.mark.parametrize("shift",[
    lambda now: (now+timedelta(days=2)).isoformat(),
    lambda now: now.replace(tzinfo=None).isoformat(),
])
def test_future_or_naive_checkpoint_clock_is_untrusted(tmp_path,shift):
    checkpoint,_,_=seed(tmp_path,"maturity")
    record=json.loads(checkpoint.read_text());record["run_finished_utc"]=shift(NOW)
    checkpoint.write_text(json.dumps(record))
    assert status(audit_local_operations(tmp_path,clock=NOW),"maturity")=="CHECKPOINT_INVALID"


def test_old_watch_run_does_not_carry_lifetime_freshness_claim(tmp_path):
    checkpoint,_,_=seed(tmp_path,"watch")
    record=json.loads(checkpoint.read_text());record["run_finished_utc"]=(NOW-timedelta(days=31)).isoformat()
    checkpoint.write_text(json.dumps(record))
    assert status(audit_local_operations(tmp_path,clock=NOW),"watch")=="OUTDATED_RESEARCH_SNAPSHOT"


def test_render_injected_snapshot_must_fail_closed():
    snapshot={"schema_version":"made.up","overall_gate":"SAFE","modes":{}}
    with pytest.raises(ValueError):
        render_operations_overview(snapshot)


def test_publishing_atomic_static_html_and_json_never_mutates_checkpoint(tmp_path):
    for mode in CONFIG:
        seed(tmp_path,mode)
    before={f:sha256(f.read_bytes()).hexdigest() for f in tmp_path.glob("output/**/last_verified_*.json")}
    publication=publish_operations_overview(tmp_path,clock=NOW)
    assert publication["status"]=="LOCAL_OPERATIONS_OVERVIEW_RESEARCH_ONLY"
    site=tmp_path/"output"/"operations"/"site"/"index.html"
    summary=tmp_path/"output"/"operations"/"operations_health_research.json"
    assert site.is_file() and summary.is_file()
    assert json.loads(summary.read_text())["overall_gate"]=="HOLD_UNVERIFIED_RESEARCH"
    assert "실전 적중률 N/A" in site.read_text()
    assert {f:sha256(f.read_bytes()).hexdigest() for f in before}==before
    handler=partial(SimpleHTTPRequestHandler,directory=str(site.parent))
    with ThreadingHTTPServer(("127.0.0.1",0),handler) as server:
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
                assert response.status==200 and "EraLeader".encode() in response.read()
        finally:
            server.shutdown();thread.join(timeout=4)


def test_operations_publication_must_not_follow_symlink_site(tmp_path):
    output=tmp_path/"output"/"operations"
    output.mkdir(parents=True)
    (output/"site").symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match="linked|symlink|Unsafe"):
        publish_operations_overview(tmp_path,clock=NOW)


def test_mid_audit_checkpoint_mutation_blocks_publication(tmp_path,monkeypatch):
    checkpoint,_,_=seed(tmp_path,"maturity")
    import eraleader.operations_overview as mod
    real=mod.audit_local_operations
    calls=[0]
    def changing(*args,**kwargs):
        result=real(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            doc=json.loads(checkpoint.read_text())
            doc["run_finished_utc"]=(NOW-timedelta(hours=5)).isoformat()
            checkpoint.write_text(json.dumps(doc))
        return result
    monkeypatch.setattr(mod,"audit_local_operations",changing)
    with pytest.raises(RuntimeError,match="revised|changed"):
        mod.publish_operations_overview(tmp_path,clock=NOW)
    assert not (tmp_path/"output"/"operations").exists()


def test_serve_workflow_has_no_network_or_live_scheduler(tmp_path):
    for mode in CONFIG:
        seed(tmp_path,mode)
    project=Path(__file__).resolve().parents[1]
    command=[sys.executable,str(project/"scripts"/"render_local_operations.py"),
             "--project",str(tmp_path)]
    completed=subprocess.run(command,capture_output=True,text=True,check=True)
    assert json.loads(completed.stdout)["status"]=="LOCAL_OPERATIONS_OVERVIEW_RESEARCH_ONLY"
    assert (tmp_path/"output"/"operations"/"site"/"index.html").exists()


def test_legacy_price_checkpoint_without_optional_watch_flag_is_still_auditable(tmp_path):
    """Existing old scheduler's valid price checkpoint predates WATCH opt-in."""
    checkpoint,_,_=seed(tmp_path,"price")
    contents=json.loads(checkpoint.read_text())
    contents.pop("watch_research_enabled")
    checkpoint.write_text(json.dumps(contents))
    price=audit_local_operations(tmp_path,clock=NOW)["modes"]["price"]
    assert price["archive_live_bytes_matched"] is True
    assert price["state"]=="STALE_PRICE_OBSERVATIONS"


def test_renderer_rejects_forged_counter_and_escapes_untrusted_clock(tmp_path):
    snapshot=audit_local_operations(tmp_path,clock=NOW)
    snapshot["archive_live_bytes_matched_modes"]="<img src=x onerror=alert(1)>"
    with pytest.raises(ValueError):
        render_operations_overview(snapshot)
    snapshot["archive_live_bytes_matched_modes"]=3
    with pytest.raises(ValueError):
        render_operations_overview(snapshot)
    snapshot["archive_live_bytes_matched_modes"]=0
    snapshot["evaluated_at_utc"]="<svg/onload=alert(1)>"
    html=render_operations_overview(snapshot)
    assert "<svg" not in html and "&lt;svg" in html
