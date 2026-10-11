"""6_5 opt-in WATCH scheduler bridge, without installing launchd or using APIs."""
from __future__ import annotations

from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json

import pytest

from eraleader import local_schedule as scheduler
from eraleader.prospective import ProspectiveRegistry
from eraleader.watch_operating_reports import compile_watch_operating_report
from test_watch_progression import snapshot,MODEL


@pytest.fixture
def folders(tmp_path):
    return {
        "out":tmp_path/"out","control":tmp_path/"control",
        "backups":tmp_path/"backups","legacy":tmp_path/"legacy",
    }


def create_watch(tmp_path, *, aged=False, us_missing=False):
    """Actually write both market WATCH screen + positive signal events.

    Pure synthetic inputs with wall clock registered_at; never real markets.
    """
    path=tmp_path/"watch.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        for market in ("KR", "US"):
            if market=="US" and us_missing:
                continue
            observation=datetime.now(timezone.utc)-timedelta(days=20 if aged else 0,minutes=2)
            original=snapshot(observation,security="TEST-"+market,hit=True,market=market)
            original["run_id"]=f"fixture-{market}-{observation.isoformat()}"
            reg.record_integrated(original,clock=observation)
    finally:
        reg.close()
    config=tmp_path/"watch_schedule.json"
    config.write_text(json.dumps({
        "schema_version":"eraleader.scheduled_watch_research.v1",
        "markets":{
            "KR":{"watch_ledger":str(path.resolve()),"model_version":MODEL},
            "US":{"watch_ledger":str(path.resolve()),"model_version":MODEL},
        }
    }),encoding="utf-8")
    return config,path


def stub_price_batch(monkeypatch, folders):
    counts={"batch":0}
    def batch(args):
        counts["batch"]+=1
        folder=folders["out"]
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"batch_manifest.json").write_text(
            json.dumps({"status":"OFFLINE_BATCH_RESEARCH_ONLY",
                        "official_leaders_confirmed":0,
                        "dry_run_only":True,
                        "external_api_calls":0,"messages_sent":0}))
        return {"market_count":2,"reports_created":6}
    monkeypatch.setattr(scheduler,"execute_local_batch",batch)
    return counts


def execute(folders,config,**kwargs):
    return scheduler.run_scheduled(
        **folders, today=date.today(),
        sessions={"KR":date.today(),"US":date.today()},
        watch_research_config=config,**kwargs)


def test_price_only_default_unchanged_and_never_reads_watch(tmp_path,folders,monkeypatch):
    calls=stub_price_batch(monkeypatch,folders)
    result=execute(folders,None)
    assert result["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert calls["batch"]==1
    assert result["messages_sent"]==0
    assert result["watch_research_enabled"] is False
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_two_fresh_markets_publish_14_derived_pages_only_after_verified_backup(tmp_path,folders,monkeypatch):
    config,ledger=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    original=sha256(ledger.read_bytes()).hexdigest()
    first=execute(folders,config)
    assert first["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert first["watch_research_enabled"] is True
    assert first["watch_operating_report_pages"]==14
    assert first["watch_market_run_ids"]["KR"]!=first["watch_market_run_ids"]["US"]
    assert calls["batch"]==1
    assert first["messages_sent"]==0 and first["external_api_calls"]==0
    assert sha256(ledger.read_bytes()).hexdigest()==original
    out=folders["out"]
    for market in ("kr","us"):
        assert (out/f"watch_operating_{market}_research.json").is_file()
        for period in ("daily","weekly","monthly"):
            assert (out/"reports"/f"watch_{period}_{market}.md").is_file()
            assert (out/"site"/f"watch_{period}_{market}.html").is_file()
    assert "WATCH" in (out/"reports"/"watch_daily_kr.md").read_text()
    with ZipFile(first["archive"]) as z:
        names=z.namelist()
        assert "watch_operating_kr_research.json" in names
        assert "watch_operating_us_research.json" in names
        assert all("watch.sqlite" not in entry for entry in names)
        assert all("watch_schedule.json" not in entry for entry in names)
    from eraleader.local_backup import verify_backup
    assert verify_backup(Path(first["archive"]))["status"]=="LOCAL_BACKUP_VERIFIED"


def test_unchanged_price_and_watch_skips_duplicate_cycle(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    first=execute(folders,config)
    assert execute(folders,config)["status"]=="SKIPPED_UNCHANGED_CACHE"
    assert calls["batch"]==1
    assert first["watch_research_sha256"]["KR"]["watch_local_sha256"]


def test_new_watch_event_same_price_day_triggers_new_cycle(tmp_path,folders,monkeypatch):
    config,ledger=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    first=execute(folders,config)
    assert calls["batch"]==1
    t=datetime.now(timezone.utc)-timedelta(minutes=1)
    reg=ProspectiveRegistry(ledger)
    try:
        reg.record_integrated(snapshot(t,security="NEW-KR",hit=True,market="KR"),clock=t)
    finally:reg.close()
    second=execute(folders,config)
    assert calls["batch"]==2
    assert second["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert second["watch_research_sha256"]["KR"]!=first["watch_research_sha256"]["KR"]
    assert second["watch_research_sha256"]["US"]==first["watch_research_sha256"]["US"]


def test_missing_us_watch_blocks_entire_batch_before_any_price_side_effect(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path,us_missing=True)
    calls=stub_price_batch(monkeypatch,folders)
    result=execute(folders,config)
    assert result["status"]=="SKIPPED_WATCH_RESEARCH_NOT_CURRENT"
    assert calls["batch"]==0
    assert not (folders["control"]/"last_verified_batch.json").exists()
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_aged_watch_fails_closed_even_with_price_stale_override(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path,aged=True)
    calls=stub_price_batch(monkeypatch,folders)
    result=execute(folders,config,allow_stale_research=True)
    assert result["status"]=="SKIPPED_WATCH_RESEARCH_NOT_CURRENT"
    assert calls["batch"]==0
    assert result["watch_freshness_status"]["KR"]=="STALE_RESEARCH_OBSERVATIONS_NOT_CURRENT"


def test_failed_second_market_input_is_not_rewritten_or_published(tmp_path,folders,monkeypatch):
    config,ledger=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    configdata=json.loads(config.read_text())
    configdata["markets"]["US"]["model_version"]="UNREGISTERED_MODEL"
    config.write_text(json.dumps(configdata))
    result=execute(folders,config)
    assert result["status"]=="SKIPPED_WATCH_RESEARCH_NOT_CURRENT"
    assert calls["batch"]==0
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_watch_source_mutated_during_batch_cannot_advance_checkpoint(tmp_path,folders,monkeypatch):
    config,ledger=create_watch(tmp_path)
    calls={"n":0}
    def batch(args):
        calls["n"]+=1
        reg=ProspectiveRegistry(ledger)
        now=datetime.now(timezone.utc)-timedelta(seconds=1)
        try:
            reg.record_integrated(snapshot(now,security="NEW-KR",market="KR"),clock=now)
        finally:reg.close()
        return {"market_count":2,"reports_created":6}
    monkeypatch.setattr(scheduler,"execute_local_batch",batch)
    with pytest.raises(RuntimeError,match="WATCH.*revised|WATCH.*changed"):
        execute(folders,config)
    assert calls["n"]==1
    assert not (folders["control"]/"last_verified_batch.json").exists()
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_failure_in_watch_render_before_backup_cannot_claim_completed_cycle(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    def fail(*args,**kwargs): raise ValueError("synthetic HTML renderer broken")
    monkeypatch.setattr("eraleader.scheduled_watch_bridge.render_watch_operating_html",fail)
    with pytest.raises(ValueError,match="HTML renderer broken"):
        execute(folders,config)
    assert calls["batch"]==0
    assert not (folders["control"]/"last_verified_batch.json").exists()


def test_backup_failure_after_reports_requires_retry_and_same_watch_snapshot(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    real_verify=scheduler.verify_backup
    count={"n":0}
    def sometimes(archive):
        count["n"]+=1
        if count["n"]==1: raise ValueError("bad synthetic backup")
        return real_verify(archive)
    monkeypatch.setattr(scheduler,"verify_backup",sometimes)
    with pytest.raises(ValueError,match="bad synthetic backup"):
        execute(folders,config)
    assert not (folders["control"]/"last_verified_batch.json").exists()
    recovered=execute(folders,config)
    assert recovered["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert calls["batch"]==2


def test_existing_price_only_checkpoint_does_not_suppress_new_watch_optin(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    first=execute(folders,None)
    assert first["watch_research_enabled"] is False
    second=execute(folders,config)
    assert second["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert second["watch_research_enabled"] is True
    assert calls["batch"]==2


def test_scoped_config_explicit_both_markets_strict_fields_and_symlink(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    stub_price_batch(monkeypatch,folders)
    document=json.loads(config.read_text())
    for changed in [
        {"schema_version":"UNKNOWN","markets":document["markets"]},
        {"schema_version":document["schema_version"],"markets":{"KR":document["markets"]["KR"]}},
        {"schema_version":document["schema_version"],"markets":document["markets"],"secret":"password"},
    ]:
        config.write_text(json.dumps(changed))
        with pytest.raises(ValueError,match="config|schema|market|field"):
            execute(folders,config)
    config.write_text(json.dumps(document))
    link=tmp_path/"watch_alias.json"
    link.symlink_to(config)
    with pytest.raises(ValueError,match="symlink"):
        execute(folders,link)


def test_optional_peer_score_fields_must_appear_together(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    stub_price_batch(monkeypatch,folders)
    data=json.loads(config.read_text())
    data["markets"]["KR"]["score_ledger"]=str(tmp_path/"missing.sqlite")
    config.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="paired|both|feature"):
        execute(folders,config)


def test_missing_watch_ledger_does_not_create_file_or_change_checkpoint(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    stub_price_batch(monkeypatch,folders)
    missing=tmp_path/"nonexistent.sqlite"
    doc=json.loads(config.read_text())
    doc["markets"]["US"]["watch_ledger"]=str(missing)
    config.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="Missing|ledger|symlink"):
        execute(folders,config)
    assert not missing.exists()
    assert not (folders["control"]/"last_verified_batch.json").exists()


def test_config_change_even_same_source_data_triggers_new_cycle(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    first=execute(folders,config)
    doc=json.loads(config.read_text())
    doc["markets"]["KR"]["model_version"]=MODEL+"-V2"
    config.write_text(json.dumps(doc))
    second=execute(folders,config)
    assert second["status"]=="SKIPPED_WATCH_RESEARCH_NOT_CURRENT"
    assert calls["batch"]==1
    assert not second.get("archive")
    assert first["watch_research_sha256"]["KR"]["model_version"]==MODEL


def test_script_watch_config_optin_is_declared_but_no_install(tmp_path):
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_local_scheduled.py"
    assert "--watch-research-config" in script.read_text()
    assert "--watch-max-age-days" in script.read_text()


def test_unmodified_source_but_explicit_config_revision_forces_reverified_cycle(
    tmp_path,folders,monkeypatch,
):
    config,_=create_watch(tmp_path)
    calls=stub_price_batch(monkeypatch,folders)
    first=execute(folders,config)
    assert calls["batch"]==1
    config.write_text(config.read_text()+"\n ")
    second=execute(folders,config)
    assert calls["batch"]==2
    assert second["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert (first["watch_research_config_sha256"] !=
            second["watch_research_config_sha256"])


def test_input_watch_changed_while_verifying_skip_cannot_be_reported_unchanged(
    tmp_path,folders,monkeypatch,
):
    config,ledger=create_watch(tmp_path)
    stub_price_batch(monkeypatch,folders)
    first=execute(folders,config)
    old_checkpoint=(folders["control"]/"last_verified_batch.json").read_bytes()
    old_verify=scheduler.verify_backup
    times={"n":0}
    def mutate_on_skip(archive):
        result=old_verify(archive)
        times["n"]+=1
        if times["n"]==1:
            at=datetime.now(timezone.utc)-timedelta(milliseconds=500)
            reg=ProspectiveRegistry(ledger)
            try:
                reg.record_integrated(snapshot(
                    at,security="NEW-AFTER-CHECK",market="US"),clock=at)
            finally:reg.close()
        return result
    monkeypatch.setattr(scheduler,"verify_backup",mutate_on_skip)
    with pytest.raises(RuntimeError,match="WATCH.*revised|WATCH.*changed"):
        execute(folders,config)
    assert times["n"]==1
    assert (folders["control"]/"last_verified_batch.json").read_bytes()==old_checkpoint


def test_watch_new_input_during_zip_backup_blocks_success_marker(
    tmp_path,folders,monkeypatch,
):
    config,ledger=create_watch(tmp_path)
    stub_price_batch(monkeypatch,folders)
    old_backup=scheduler.create_backup
    def mutate_in_backup(out,archive):
        saved=old_backup(out,archive)
        at=datetime.now(timezone.utc)-timedelta(milliseconds=500)
        reg=ProspectiveRegistry(ledger)
        try:
            reg.record_integrated(snapshot(
                at,security="LATE-ON-BACKUP",market="KR"),clock=at)
        finally:reg.close()
        return saved
    monkeypatch.setattr(scheduler,"create_backup",mutate_in_backup)
    with pytest.raises(RuntimeError,match="WATCH.*revised"):
        execute(folders,config)
    assert not (folders["control"]/"last_verified_batch.json").exists()


def test_written_launchd_bootstrap_propagates_only_explicit_watch_flags(
    tmp_path,
):
    root=tmp_path/"project with spaces"
    (root/"scripts").mkdir(parents=True)
    (root/"scripts"/"run_local_scheduled.py").write_text("print('OK')")
    original_config,_=create_watch(tmp_path)
    config=tmp_path/"watch research config.json"
    original_config.rename(config)
    helper=tmp_path/"launcher.sh"
    plist=tmp_path/"scheduler.plist"
    scheduler.write_launch_agent(
        plist,python=Path("/usr/bin/python3"),project=root,
        bootstrap_path=helper,watch_research_config=config,
        watch_max_age_days=4,
    )
    contents=helper.read_text()
    assert "--watch-research-config" in contents
    assert str(config) in contents
    assert "--watch-max-age-days 4" in contents
    # Does not install a background service or invoke the launcher.
    assert "launchctl load" not in contents
    assert "launchctl bootstrap" not in contents
    import plistlib
    props=plistlib.loads(plist.read_bytes())
    assert props["ProgramArguments"]==["/bin/sh",str(helper)]
    assert props["StartInterval"]==3600


def test_default_launchd_bootstrap_remains_price_only(tmp_path):
    root=tmp_path/"project"
    (root/"scripts").mkdir(parents=True)
    (root/"scripts"/"run_local_scheduled.py").write_text("print('OK')")
    helper=tmp_path/"launcher.sh"
    scheduler.write_launch_agent(
        tmp_path/"agent.plist",python=Path("/usr/bin/python3"),
        project=root,bootstrap_path=helper,
    )
    assert "--watch-research-config" not in helper.read_text()


def watch_only(folders,config,**kw):
    return scheduler.run_scheduled_watch_only(
        out=folders["out"],control=folders["control"],
        backups=folders["backups"],watch_research_config=config,**kw)


def test_watch_only_runs_with_no_price_cache_and_without_invoking_price_batch(
    tmp_path,folders,monkeypatch,
):
    config,watch=create_watch(tmp_path)
    monkeypatch.setattr(scheduler,"execute_local_batch",
                        lambda *_:pytest.fail("WATCH-only cannot invoke legacy price batch"))
    r=watch_only(folders,config)
    assert r["status"]=="WATCH_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert r["price_batch_runs"]==0
    assert r["watch_operating_report_pages"]==14
    assert r["messages_sent"]==0 and r["external_api_calls"]==0
    assert r["official_leaders_confirmed"]==0
    assert (folders["control"]/"last_verified_watch_only.json").is_file()
    assert not (folders["control"]/"last_verified_batch.json").exists()
    from eraleader.local_backup import verify_backup
    assert verify_backup(Path(r["archive"]))["status"]=="LOCAL_BACKUP_VERIFIED"
    assert not (folders["out"]/"batch_manifest.json").exists()


def test_watch_only_identical_sources_skip_and_new_watch_change_retriggers(
    tmp_path,folders,monkeypatch,
):
    config,watch=create_watch(tmp_path)
    monkeypatch.setattr(scheduler,"execute_local_batch",
                        lambda *_:pytest.fail("WATCH-only cannot execute prices"))
    first=watch_only(folders,config)
    assert watch_only(folders,config)["status"]=="SKIPPED_UNCHANGED_WATCH_EVIDENCE"
    at=datetime.now(timezone.utc)-timedelta(seconds=1)
    db=ProspectiveRegistry(watch)
    try:db.record_integrated(snapshot(at,security="UPGRADE-US",market="US"),clock=at)
    finally:db.close()
    second=watch_only(folders,config)
    assert second["status"]=="WATCH_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert first["watch_research_sha256"]["US"]!=second["watch_research_sha256"]["US"]
    assert first["watch_market_run_ids"]["US"]!=second["watch_market_run_ids"]["US"]


def test_watch_only_missing_market_or_old_watch_never_publishes(
    tmp_path,folders,monkeypatch,
):
    config,_=create_watch(tmp_path,us_missing=True)
    monkeypatch.setattr(scheduler,"execute_local_batch",
                        lambda *_:pytest.fail("no legacy batch"))
    r=watch_only(folders,config)
    assert r["status"]=="SKIPPED_WATCH_RESEARCH_NOT_CURRENT"
    assert not (folders["control"]/"last_verified_watch_only.json").exists()
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_watch_only_cannot_run_without_explicit_config(folders):
    with pytest.raises(ValueError,match="config|required"):
        watch_only(folders,None)
    assert not (folders["out"]/"watch_operating_kr_research.json").exists()


def test_watch_only_source_mutation_during_archive_fails_closed(tmp_path,folders,monkeypatch):
    config,watch=create_watch(tmp_path)
    real=scheduler.create_backup
    def mutating_backup(out,archive):
        result=real(out,archive)
        at=datetime.now(timezone.utc)-timedelta(milliseconds=100)
        db=ProspectiveRegistry(watch)
        try:
            db.record_integrated(snapshot(at,security="LATER-KR",market="KR"),clock=at)
        finally:db.close()
        return result
    monkeypatch.setattr(scheduler,"create_backup",mutating_backup)
    with pytest.raises(RuntimeError,match="WATCH.*revised"):
        watch_only(folders,config)
    assert not (folders["control"]/"last_verified_watch_only.json").exists()


def test_watch_only_unverified_archive_must_retry(tmp_path,folders,monkeypatch):
    config,_=create_watch(tmp_path)
    real=scheduler.verify_backup
    hit={"count":0}
    def broken_first_archive(path):
        hit["count"]+=1
        if hit["count"]==1:raise ValueError("Synthetic corrupt watch-only backup")
        return real(path)
    monkeypatch.setattr(scheduler,"verify_backup",broken_first_archive)
    with pytest.raises(ValueError,match="corrupt watch-only backup"):
        watch_only(folders,config)
    assert not (folders["control"]/"last_verified_watch_only.json").exists()
    assert watch_only(folders,config)["status"]=="WATCH_ONLY_RESEARCH_VERIFIED_BACKUP"


def test_watch_only_bootstrap_is_not_dependent_on_old_price_cache(
    tmp_path,monkeypatch,
):
    from subprocess import run
    import sys
    config,_=create_watch(tmp_path)
    project=tmp_path/"External T5DATA"/"eraleader"
    script=project/"scripts"/"run_local_scheduled.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('MOCK_WATCH_ONLY_EXECUTED')")
    cache=tmp_path/"missing_price_cache"
    monkeypatch.setattr(scheduler,"LEGACY_DEFAULT",cache)
    helper=tmp_path/"home"/"launcher.sh"
    scheduler.write_launch_agent(
        tmp_path/"watch_only.plist",project=project,
        python=Path(sys.executable),bootstrap_path=helper,
        watch_research_config=config,watch_only=True,
    )
    output=run(["/bin/sh",str(helper)],check=True,capture_output=True,text=True)
    assert "MOCK_WATCH_ONLY_EXECUTED" in output.stdout
    assert "--watch-only" in helper.read_text()
    assert str(cache) not in helper.read_text()
    # Absence of an active SSD script should safely skip without touching Mac settings.
    script.unlink()
    skipped=run(["/bin/sh",str(helper)],check=True,capture_output=True,text=True)
    assert "SKIPPED_EXTERNAL_SSD_UNAVAILABLE" in skipped.stdout


def test_watch_only_mode_requires_explicit_config_and_no_scheduler_install(tmp_path):
    project=tmp_path/"project"
    (project/"scripts").mkdir(parents=True)
    (project/"scripts"/"run_local_scheduled.py").touch()
    with pytest.raises(ValueError,match="config|required"):
        scheduler.write_launch_agent(
            tmp_path/"not_created.plist",project=project,
            python=Path("/usr/bin/python3"),bootstrap_path=tmp_path/"runner.sh",
            watch_only=True)
    assert not (tmp_path/"not_created.plist").exists()
