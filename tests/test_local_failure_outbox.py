"""6_4 / 6_5: fail-closed, opt-in, local-only operational failure outbox.

Every market/evidence input is synthetic. No external mail or alerts exist.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from zipfile import ZipFile
import fcntl
import json
import sqlite3
import subprocess
import sys
import urllib.request

import pytest

from eraleader.local_backup import restore_backup, verify_backup
from eraleader.local_failure_outbox import run_local_failure_outbox, read_local_failure_outbox
from test_operations_overview import seed, NOW


def run(project,at=NOW):
    return run_local_failure_outbox(project,clock=at)


def database(project):
    return project/"output"/"local_failure_outbox"/"dry_run_alerts.sqlite"


def events(project):
    return read_local_failure_outbox(database(project))["events"]


def page(project):
    return project/"output"/"local_failure_outbox"/"site"/"index.html"


def alter_live(project,mode):
    p=project/"output"/{
        "price":"scheduled/site/kr.html",
        "watch":"scheduled_watch/site/watch_daily_us.html",
        "maturity":"scheduled_maturity/site/ranked_maturity_us.html",
    }[mode]
    prior=p.read_bytes()
    p.write_bytes(prior+b"\nUNTRUSTED_REPORT")
    return p,prior


def test_first_stale_price_writes_one_dry_run_failure_without_sending(tmp_path):
    seed(tmp_path,"price")
    result=run(tmp_path)
    assert result["status"]=="LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
    assert result["new_events"]==1
    assert result["active_local_faults"]==1
    assert result["messages_sent"]==0
    assert result["external_api_calls"]==0
    assert result["official_leaders_confirmed"]==0
    assert [e["type"] for e in events(tmp_path)]==["DATA_FAILURE_LOCAL"]
    event=events(tmp_path)[0]
    assert event["reason"]=="STALE_PRICE_OBSERVATIONS"
    assert event["mode"]=="price"
    assert event["delivery_channel"]=="LOCAL_PREVIEW_ONLY"
    assert event["delivery_status"]=="DRY_RUN_NEVER_SENT"
    assert event["attempt_count"]==0
    assert event["sent_at_utc"] is None
    assert len(event["event_id"])==64
    assert verify_backup(Path(result["archive"]))["file_count"]==3


def test_missing_untouched_watch_or_maturity_is_not_a_vendor_outage(tmp_path):
    output=run(tmp_path)
    assert output["new_events"]==0
    assert output["active_local_faults"]==0
    assert output["not_configured_modes"]==["maturity","price","watch"]
    assert events(tmp_path)==[]
    assert "원천 PIT 미인증" in page(tmp_path).read_text()


def test_identical_failure_after_restart_is_deduplicated(tmp_path):
    seed(tmp_path,"price")
    first=run(tmp_path)
    second=run(tmp_path)
    assert first["new_events"]==1 and second["new_events"]==0
    assert len(events(tmp_path))==1
    assert first["archive"]!=second["archive"]  # individually verified local snapshots


def test_change_in_bad_reason_emits_one_new_failure_not_false_recovery(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    alter_live(tmp_path,"price")
    second=run(tmp_path)
    assert second["new_events"]==1
    assert [e["type"] for e in events(tmp_path)]==["DATA_FAILURE_LOCAL"]*2
    assert events(tmp_path)[1]["reason"]=="PUBLISHED_BYTES_MISMATCH"
    assert run(tmp_path)["new_events"]==0


def test_prior_clean_watch_missing_checkpoint_is_failure_not_recovery(tmp_path):
    checkpoint,_,_=seed(tmp_path,"watch")
    assert run(tmp_path)["new_events"]==0
    checkpoint.unlink()
    second=run(tmp_path)
    assert second["new_events"]==1
    assert second["active_local_faults"]==1
    assert events(tmp_path)[0]["reason"]=="NO_CHECKPOINT_AFTER_PRIOR_RUN"
    assert run(tmp_path)["new_events"]==0


def test_missing_checkpoint_after_known_failure_cannot_be_treated_as_recovered(tmp_path):
    checkpoint,_,_=seed(tmp_path,"price")
    run(tmp_path)
    checkpoint.unlink()
    next_run=run(tmp_path)
    assert next_run["new_events"]==1
    assert next_run["active_local_faults"]==1
    assert events(tmp_path)[-1]["type"]=="DATA_FAILURE_LOCAL"
    assert events(tmp_path)[-1]["reason"]=="NO_CHECKPOINT_AFTER_PRIOR_RUN"


def test_watch_corrupted_page_then_repaired_emits_local_only_recovery(tmp_path):
    seed(tmp_path,"watch")
    assert run(tmp_path)["new_events"]==0
    path,original=alter_live(tmp_path,"watch")
    broken=run(tmp_path)
    assert broken["new_events"]==1
    path.write_bytes(original)
    restored=run(tmp_path)
    assert restored["new_events"]==1
    assert restored["active_local_faults"]==0
    assert [e["type"] for e in events(tmp_path)]==[
        "DATA_FAILURE_LOCAL","LOCAL_ARTIFACTS_RESTORED"]
    assert events(tmp_path)[-1]["reason"]=="SOURCE_NOT_RECHECKED"
    assert events(tmp_path)[-1]["delivery_status"]=="DRY_RUN_NEVER_SENT"
    assert run(tmp_path)["new_events"]==0
    assert "실제 시장 원천 복구 또는 PIT 인증 아님" in page(tmp_path).read_text()


@pytest.mark.parametrize("mode",["price","watch","maturity"])
def test_all_modes_real_byte_mismatch_produces_local_failure(tmp_path,mode):
    seed(tmp_path,mode)
    assert run(tmp_path)["new_events"]==(1 if mode=="price" else 0)
    path,_=alter_live(tmp_path,mode)
    assert path.is_file()
    result=run(tmp_path)
    assert result["new_events"]==1
    assert events(tmp_path)[-1]["mode"]==mode
    assert events(tmp_path)[-1]["reason"]=="PUBLISHED_BYTES_MISMATCH"


def test_regression_different_subsystem_failure_does_not_auto_promote_candidate(tmp_path):
    for market in ("price","watch","maturity"):
        seed(tmp_path,market)
    result=run(tmp_path)
    assert result["new_events"]==1
    assert result["official_leaders_confirmed"]==0
    assert result["actual_future_leader_skill_certified"] is False
    assert "실전 적중률 N/A" in page(tmp_path).read_text()
    assert not any(e["type"]=="CONFIRMED_LEADER" for e in events(tmp_path))


def test_tampered_delivery_state_fail_closed_no_new_event_or_report(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    path=database(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute("UPDATE alert_events SET delivery_status='SENT',attempt_count=1 WHERE event_no=1")
    with pytest.raises(ValueError,match="Corrupt|corrupt|chain|delivery|hash|integrity"):
        run(tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM alert_events").fetchone()[0]==1


def test_deleted_historical_event_is_detected_by_pinned_event_count(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("DELETE FROM alert_events")
    with pytest.raises(ValueError,match="corrupt|chain|count|integrity"):
        run(tmp_path)


def test_corrupted_sqlite_bytes_do_not_create_fake_recovery(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    database(tmp_path).write_bytes(b"not a sqlite database")
    with pytest.raises((ValueError,sqlite3.DatabaseError)):
        run(tmp_path)


def test_failure_during_db_append_rolls_back_all_new_alerts(tmp_path,monkeypatch):
    seed(tmp_path,"price")
    seed(tmp_path,"watch")
    alter_live(tmp_path,"watch")
    import eraleader.local_failure_outbox as service
    original=service._append_event
    counter=[0]
    def broken(*args,**kwargs):
        counter[0]+=1
        if counter[0]==2:
            raise RuntimeError("injected append failure")
        return original(*args,**kwargs)
    monkeypatch.setattr(service,"_append_event",broken)
    with pytest.raises(RuntimeError,match="injected append"):
        run(tmp_path)
    assert service.read_local_failure_outbox(database(tmp_path))["events"]==[]
    monkeypatch.setattr(service,"_append_event",original)
    assert run(tmp_path)["new_events"]==2
    assert len(events(tmp_path))==2


def test_ledger_backup_failure_retries_idempotently(tmp_path,monkeypatch):
    seed(tmp_path,"price")
    import eraleader.local_failure_outbox as service
    original=service.create_backup
    def fail(*args,**kwargs):
        raise RuntimeError("inject backup failure")
    monkeypatch.setattr(service,"create_backup",fail)
    with pytest.raises(RuntimeError,match="inject backup"):
        run(tmp_path)
    assert len(events(tmp_path))==1
    assert not (tmp_path/"output"/"local_failure_outbox_control"/"verified.json").exists()
    monkeypatch.setattr(service,"create_backup",original)
    recovered=run(tmp_path)
    assert recovered["new_events"]==0
    assert recovered["status"]=="LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
    assert verify_backup(Path(recovered["archive"]))["status"]=="LOCAL_BACKUP_VERIFIED"


def test_source_changes_mid_audit_prevents_initial_ledger(tmp_path,monkeypatch):
    seed(tmp_path,"price")
    import eraleader.local_failure_outbox as service
    original=service.audit_local_operations
    counts=[0]
    def race(*args,**kwargs):
        value=original(*args,**kwargs)
        counts[0]+=1
        if counts[0]==1:
            alter_live(tmp_path,"price")
        return value
    monkeypatch.setattr(service,"audit_local_operations",race)
    with pytest.raises(RuntimeError,match="changed|revised"):
        run(tmp_path)
    assert not database(tmp_path).exists()


def test_source_changes_while_transaction_is_open_rolls_back(tmp_path,monkeypatch):
    seed(tmp_path,"price")
    import eraleader.local_failure_outbox as service
    original=service.audit_local_operations
    counter=[0]
    def racing(*args,**kwargs):
        out=original(*args,**kwargs)
        counter[0]+=1
        if counter[0]==2:
            alter_live(tmp_path,"price")
        return out
    monkeypatch.setattr(service,"audit_local_operations",racing)
    with pytest.raises(RuntimeError,match="changed|revised"):
        run(tmp_path)
    if database(tmp_path).exists():
        assert service.read_local_failure_outbox(database(tmp_path))["events"]==[]


def test_clock_cannot_backdate_existing_first_recorded_event(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    with pytest.raises(ValueError,match="backdate|older|clock"):
        run(tmp_path,NOW-timedelta(days=1))
    assert len(events(tmp_path))==1


def test_parallel_lock_returns_not_running_and_creates_no_ledger(tmp_path):
    seed(tmp_path,"price")
    lock=tmp_path/"output"/"local_failure_outbox_control"/"batch.lock"
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open("a+b") as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            result=run(tmp_path)
            assert result["status"]=="SKIPPED_ALREADY_RUNNING"
        finally:
            fcntl.flock(stream,fcntl.LOCK_UN)
    assert not database(tmp_path).exists()


def test_dry_run_archive_contains_consistent_sqlite_and_only_derived_pages(tmp_path):
    seed(tmp_path,"price")
    output=run(tmp_path)
    archive=Path(output["archive"])
    with ZipFile(archive) as z:
        names=set(z.namelist())
        assert names=={"dry_run_alerts.sqlite","dry_run_alerts_research.json",
                       "site/index.html","MANIFEST.json"}
        assert all("price" not in name and ".env" not in name for name in names)
    restore=tmp_path/"restored"
    restore_backup(archive,restore)
    assert read_local_failure_outbox(restore/"dry_run_alerts.sqlite")["events"]==events(tmp_path)
    assert (restore/"site"/"index.html").read_bytes()==page(tmp_path).read_bytes()


def test_local_web_preview_http_200_and_no_exec_script(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    handler=partial(SimpleHTTPRequestHandler,directory=str(page(tmp_path).parent))
    with ThreadingHTTPServer(("127.0.0.1",0),handler) as server:
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/",timeout=3) as response:
                markup=response.read().decode("utf-8")
                assert response.status==200
                assert "DRY_RUN_NEVER_SENT" in markup
                assert "실전 적중률 N/A" in markup
                assert "<script" not in markup
        finally:
            server.shutdown();thread.join(timeout=5)


def test_cli_works_with_local_project_path_and_never_calls_a_network(tmp_path):
    seed(tmp_path,"price")
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_local_failure_outbox.py"
    process=subprocess.run([sys.executable,str(script),"--project",str(tmp_path)],
                           capture_output=True,text=True,check=True,timeout=20)
    doc=json.loads(process.stdout)
    assert doc["status"]=="LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
    assert doc["messages_sent"]==0
    assert events(tmp_path)[0]["reason"]=="STALE_PRICE_OBSERVATIONS"


def test_output_symlink_blocks_database_or_html_creation(tmp_path):
    seed(tmp_path,"price")
    output=tmp_path/"output"/"local_failure_outbox"
    output.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match="symlink|linked|Unsafe"):
        run(tmp_path)
    assert not database(tmp_path).exists()


def test_relative_path_reader_and_runner_use_existing_local_project(tmp_path,monkeypatch):
    seed(tmp_path,"price")
    monkeypatch.chdir(tmp_path)
    from eraleader.local_failure_outbox import run_local_failure_outbox, read_local_failure_outbox
    assert run_local_failure_outbox(Path("."),clock=NOW)["new_events"]==1
    relative=Path("output/local_failure_outbox/dry_run_alerts.sqlite")
    assert len(read_local_failure_outbox(relative)["events"])==1


def test_local_failure_lock_symlink_is_rejected_without_opening_target(tmp_path):
    seed(tmp_path,"price")
    control=tmp_path/"output"/"local_failure_outbox_control"
    control.mkdir()
    untouched=tmp_path/"protected.txt"
    untouched.write_bytes(b"PROTECTED")
    (control/"batch.lock").symlink_to(untouched)
    with pytest.raises(ValueError,match="Unsafe|linked|symlink"):
        run(tmp_path)
    assert untouched.read_bytes()==b"PROTECTED"
    assert not database(tmp_path).exists()


def test_conditions_state_tamper_detected_before_new_event(tmp_path):
    seed(tmp_path,"price")
    run(tmp_path)
    with sqlite3.connect(database(tmp_path)) as db:
        db.execute("UPDATE mode_conditions SET reason='SOURCE_NOT_RECHECKED' WHERE mode='price'")
    with pytest.raises(ValueError,match="Corrupt|corrupt|state|seal"):
        run(tmp_path)


def test_repeated_failure_after_local_repair_has_new_chain_event(tmp_path):
    seed(tmp_path,"watch")
    run(tmp_path)
    path,original=alter_live(tmp_path,"watch")
    run(tmp_path)
    path.write_bytes(original)
    run(tmp_path)
    alter_live(tmp_path,"watch")
    result=run(tmp_path)
    assert result["new_events"]==1
    assert [x["type"] for x in events(tmp_path)]==[
        "DATA_FAILURE_LOCAL","LOCAL_ARTIFACTS_RESTORED","DATA_FAILURE_LOCAL"]
    assert len(set(x["event_id"] for x in events(tmp_path)))==3
