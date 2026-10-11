"""6_4/6_5: independent native Top-K horizon scheduler, zero live outcomes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import plistlib
import subprocess
import sys

import pytest

from eraleader import local_schedule as scheduler
from eraleader.scheduled_maturity_bridge import (
    read_maturity_schedule_config, audit_maturity_schedule_sources,
    publish_scheduled_maturity_reports,
)
from eraleader.local_backup import verify_backup, restore_backup
from test_ranked_maturity import setup


def make_config(tmp_path):
    market_sources={}
    for market in ("KR","US"):
        b,rule,freeze=setup(tmp_path/market,market=market)
        market_sources[market]={
            "freeze":str(freeze.resolve()),
            "definition_file":str(rule.resolve()),
            "score_ledger":str(b[4].resolve()),
            "watch_ledger":str(b[1].resolve()),
            "features_dir":str(b[2].resolve()),
        }
    doc={"schema_version":"eraleader.scheduled_ranked_maturity.v1",
         "markets":market_sources}
    config=tmp_path/"ranked_schedule.json"
    config.write_text(json.dumps(doc,sort_keys=True))
    return config,market_sources


def folders(tmp_path):
    return {"out":tmp_path/"derived","control":tmp_path/"control",
            "backups":tmp_path/"backups"}


def run(root,config,**kwargs):
    return scheduler.run_scheduled_maturity_only(
        **folders(root),ranked_maturity_config=config,**kwargs)


def read_checkpoint(root):
    return json.loads((folders(root)["control"]/
                       "last_verified_ranked_maturity_only.json").read_text())


def test_two_old_watch_cohorts_are_audited_even_when_last_watch_is_over_180_days(tmp_path,monkeypatch):
    config,markets=make_config(tmp_path)
    def no_price(*args,**kwargs):
        pytest.fail("Ranked maturity scheduler MUST NOT touch price or normal WATCH freshness")
    monkeypatch.setattr(scheduler,"latest_cached_sessions",no_price)
    monkeypatch.setattr(scheduler,"execute_local_batch",no_price)
    monkeypatch.setattr(scheduler,"audit_watch_schedule_sources",no_price)
    output=run(tmp_path,config)
    assert output["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert output["ranked_maturity_report_pages"]==16
    assert output["price_batch_runs"]==0
    assert output["watch_operating_report_pages"]==0
    assert output["messages_sent"]==output["external_api_calls"]==0
    assert output["official_leaders_confirmed"]==0
    assert output["actual_future_leader_skill_certified"] is False
    assert set(output["ranked_market_run_ids"])=={"KR","US"}
    assert len(output["ranked_market_run_ids"]["KR"])==20
    for market in ("kr","us"):
        path=tmp_path/"derived"
        json_report=json.loads((path/f"ranked_maturity_{market}_research.json").read_text())
        assert json_report["selected_top_k_count"]==1
        assert json_report["full_horizon_elapsed_count"]==1
        assert json_report["awaiting_mature_outcome_evidence_count"]==1
        assert json_report["precision_at_k"] is None
        assert json_report["known_failures"] is None
        assert json_report["outcome_labels_read"] is False
        assert (path/"site"/f"ranked_maturity_{market}.html").is_file()
        for period in ("daily","weekly","monthly"):
            md=(path/"reports"/f"ranked_maturity_{period}_{market}.md").read_text()
            html=(path/"site"/f"ranked_maturity_{period}_{market}.html").read_text()
            assert "N/A" in md and "미확인" in md
            assert "N/A" in html and "확정 대장주 0" in html
    verify_backup(Path(output["archive"]))
    with ZipFile(output["archive"]) as z:
        filenames=z.namelist()
        assert len(filenames)==17  # 16 derived + backup MANIFEST
        assert all("sqlite" not in f and "jsonl" not in f and
                   "source" not in f for f in filenames if f!="MANIFEST.json")
        assert all("ranked_schedule.json" not in f for f in filenames)
    restored=tmp_path/"restored"
    restore_backup(Path(output["archive"]),restored)
    assert (restored/"site"/"ranked_maturity_daily_kr.html").read_bytes()==(
        tmp_path/"derived"/"site"/"ranked_maturity_daily_kr.html").read_bytes()
    assert read_checkpoint(tmp_path)["archive"]==output["archive"]


def test_identical_same_day_skips_verified_archive_without_rewriting(tmp_path):
    config,_=make_config(tmp_path)
    first=run(tmp_path,config)
    before=(tmp_path/"derived"/"site"/"ranked_maturity_kr.html").read_bytes()
    second=run(tmp_path,config)
    assert second["status"]=="SKIPPED_UNCHANGED_RANKED_MATURITY_EVIDENCE"
    assert second["last_archive"]==first["archive"]
    assert (tmp_path/"derived"/"site"/"ranked_maturity_kr.html").read_bytes()==before
    assert len(list((tmp_path/"backups").glob("*.zip")))==1
    assert second["messages_sent"]==0


def test_missing_archive_or_corrupted_zip_reruns_without_fake_data(tmp_path):
    config,_=make_config(tmp_path)
    first=run(tmp_path,config)
    Path(first["archive"]).unlink()
    second=run(tmp_path,config)
    assert second["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    Path(second["archive"]).write_bytes(b"corrupted archive")
    third=run(tmp_path,config)
    assert third["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert verify_backup(Path(third["archive"]))["status"]=="LOCAL_BACKUP_VERIFIED"


def test_no_us_source_blocks_before_any_derived_or_checkpoint(tmp_path):
    config,sources=make_config(tmp_path)
    Path(sources["US"]["watch_ledger"]).unlink()
    with pytest.raises(ValueError,match="Missing|watch|source|original"):
        run(tmp_path,config)
    assert not (tmp_path/"derived").exists()
    assert not (tmp_path/"control"/"last_verified_ranked_maturity_only.json").exists()


def test_feature_source_corruption_blocks_before_publishing_any_period(tmp_path):
    config,inputs=make_config(tmp_path)
    (Path(inputs["KR"]["features_dir"])/"A.json").write_text('{"replaced":"before schedule"}')
    with pytest.raises(ValueError,match="feature|formula|source|native"):
        run(tmp_path,config)
    assert not (tmp_path/"derived").exists()
    assert not (tmp_path/"control"/"last_verified_ranked_maturity_only.json").exists()


def test_rule_bytes_modified_before_schedule_are_fail_closed(tmp_path):
    config,inputs=make_config(tmp_path)
    Path(inputs["US"]["definition_file"]).write_text('{"changed":"outcome rule"}')
    with pytest.raises(ValueError,match="rule|label|SHA"):
        run(tmp_path,config)
    assert not (tmp_path/"derived").exists()


def test_schedule_config_strict_invalid_fields_and_duplicate_keys(tmp_path):
    config,raw=make_config(tmp_path)
    bad=json.loads(config.read_text())
    bad["markets"]["US"]["outcomes_file"]="/tmp/unknown_future_label.json"
    config.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match="field|schema|outcome|path"):
        read_maturity_schedule_config(config)
    doc='{"schema_version":"eraleader.scheduled_ranked_maturity.v1","markets":{},"markets":{}}'
    config.write_text(doc)
    with pytest.raises(ValueError,match="duplicate|Duplicate|schema"):
        read_maturity_schedule_config(config)


@pytest.mark.parametrize("field",[
    "freeze","definition_file","score_ledger","watch_ledger","features_dir"
])
def test_missing_required_source_path_blocks_both_markets(tmp_path,field):
    config,_=make_config(tmp_path)
    doc=json.loads(config.read_text())
    del doc["markets"]["US"][field]
    config.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="field|config|path|Missing"):
        read_maturity_schedule_config(config)


def test_source_path_symlink_or_non_absolute_rejected(tmp_path):
    config,info=make_config(tmp_path)
    doc=json.loads(config.read_text())
    doc["markets"]["US"]["freeze"]="us/frozen.json"
    config.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="absolute"):
        read_maturity_schedule_config(config)
    doc["markets"]["US"]["freeze"]=str((tmp_path/"alias.json").resolve())
    (tmp_path/"alias.json").symlink_to(Path(info["US"]["freeze"]))
    config.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="symlink|linked"):
        read_maturity_schedule_config(config)


def test_wrong_market_seal_not_reported_under_other_country(tmp_path):
    config,info=make_config(tmp_path)
    doc=json.loads(config.read_text())
    doc["markets"]["KR"]["freeze"]=info["US"]["freeze"]
    config.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="market|KR|US|seal"):
        run(tmp_path,config)


def test_mid_report_witness_mutation_cannot_advance_checkpoint(tmp_path,monkeypatch):
    config,sources=make_config(tmp_path)
    original=scheduler.publish_scheduled_maturity_reports
    called=[0]
    def revised(audited,out):
        value=original(audited,out)
        called[0]+=1
        (Path(sources["US"]["features_dir"])/"A.json").write_text('{"changed":true}')
        return value
    monkeypatch.setattr(scheduler,"publish_scheduled_maturity_reports",revised)
    with pytest.raises((ValueError,RuntimeError),match="source|feature|formula|changed|revised"):
        run(tmp_path,config)
    assert called[0]==1
    assert not (tmp_path/"control"/"last_verified_ranked_maturity_only.json").exists()


def test_source_changed_when_unchanged_backup_skip_is_checked_again(tmp_path,monkeypatch):
    config,sources=make_config(tmp_path)
    first=run(tmp_path,config)
    previous=(tmp_path/"control"/"last_verified_ranked_maturity_only.json").read_bytes()
    old_verify=scheduler.verify_backup
    changed=[False]
    def during_skip(path):
        ok=old_verify(path)
        if not changed[0]:
            changed[0]=True
            (Path(sources["KR"]["features_dir"])/"A.json").write_text('{"mid_skip":true}')
        return ok
    monkeypatch.setattr(scheduler,"verify_backup",during_skip)
    with pytest.raises((ValueError,RuntimeError),match="source|feature|formula|changed"):
        run(tmp_path,config)
    assert (tmp_path/"control"/"last_verified_ranked_maturity_only.json").read_bytes()==previous


def test_config_digest_changed_between_preflight_and_publication_is_blocked(tmp_path,monkeypatch):
    config,_=make_config(tmp_path)
    original=scheduler.publish_scheduled_maturity_reports
    def revised(audited,out):
        result=original(audited,out)
        config.write_text(config.read_text()+"\n  ")
        return result
    monkeypatch.setattr(scheduler,"publish_scheduled_maturity_reports",revised)
    with pytest.raises(RuntimeError,match="config|revised"):
        run(tmp_path,config)
    assert not (tmp_path/"control"/"last_verified_ranked_maturity_only.json").exists()


def test_maturity_threshold_changes_fingerprint_without_new_watch(tmp_path,monkeypatch):
    config,_=make_config(tmp_path)
    specs=read_maturity_schedule_config(config)
    from eraleader.ranked_discovery import _frozen,_time,ZONES
    seal=_frozen(specs["KR"]["freeze"])
    local=_time(seal["snapshot_at_utc"]).astimezone(ZONES["KR"])
    due=(local+timedelta(days=180)).astimezone(timezone.utc)
    old=audit_maturity_schedule_sources(specs,clock=due-timedelta(microseconds=1))
    new=audit_maturity_schedule_sources(specs,clock=due)
    assert old["maturity_market_fingerprints"]["KR"]!=new["maturity_market_fingerprints"]["KR"]
    assert old["reports"]["KR"]["full_horizon_pending_count"]==1
    assert new["reports"]["KR"]["full_horizon_elapsed_count"]==1


def test_report_render_does_not_accept_fake_success_or_html(tmp_path):
    config,_=make_config(tmp_path)
    assessed=audit_maturity_schedule_sources(read_maturity_schedule_config(config),
                                            clock=datetime.now(timezone.utc))
    row=assessed["reports"]["KR"]
    from eraleader.scheduled_maturity_bridge import render_maturity_period_html, render_maturity_period_markdown
    html=render_maturity_period_html(row,"daily")
    md=render_maturity_period_markdown(row,"weekly")
    assert "N/A" in html and "N/A" in md
    assert "확정 대장주 0" in html
    row["precision_at_k"]=0.5
    with pytest.raises(ValueError,match="performance|leader|accuracy|outcome"):
        render_maturity_period_html(row,"daily")


def test_cli_maturity_only_and_prohibited_mixed_flags(tmp_path,capsys):
    config,_=make_config(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_local_scheduled.py"
    project=tmp_path/"project"
    # CLI uses project/output fixed roots, but original absolute config may
    # refer to existing verified synthetic input outside project.
    project.mkdir(parents=True,exist_ok=True)
    (project/"src").symlink_to(Path(__file__).resolve().parents[1]/"src")
    args=[sys.executable,str(script),"--project",str(project),
          "--maturity-only","--ranked-maturity-config",str(config)]
    project.mkdir(exist_ok=True) if not project.exists() else None
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    outcome=json.loads(result.stdout)
    assert outcome["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert outcome["messages_sent"]==0
    result=subprocess.run(args+["--watch-only"],capture_output=True,text=True)
    assert result.returncode==2
    result=subprocess.run([sys.executable,str(script),"--project",str(project),
                           "--ranked-maturity-config",str(config)],capture_output=True,text=True)
    assert result.returncode==2


def test_maturity_only_launchd_generated_without_install_and_no_cache_dependency(tmp_path):
    from eraleader.local_schedule import write_launch_agent
    config,_=make_config(tmp_path)
    project=tmp_path/"project"
    script=project/"scripts"/"run_local_scheduled.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('SYNTHETIC_NO_REAL_SCHEDULER')")
    plist=tmp_path/"ranked.plist"
    bootstrap=tmp_path/"bootstrap.sh"
    write_launch_agent(plist,python=Path(sys.executable),project=project,
                       bootstrap_path=bootstrap,maturity_only=True,
                       ranked_maturity_config=config)
    content=plistlib.loads(plist.read_bytes())
    assert content["ProgramArguments"]==["/bin/sh",str(bootstrap)]
    assert content["Label"]=="org.eraleader.ranked-maturity-research"
    assert content["StandardOutPath"].endswith("ranked_maturity.log")
    assert config.is_file() and json.loads(config.read_text())["schema_version"]==(
        "eraleader.scheduled_ranked_maturity.v1")
    command=bootstrap.read_text()
    assert "--maturity-only" in command
    assert "--ranked-maturity-config" in command
    assert "CycleOS-Lab_BacktestEngine" not in command
    assert "launchctl" not in command
    assert "--watch-only" not in command
    assert not (tmp_path/"control").exists()


def test_no_maturity_optin_price_default_and_watch_only_default_unchanged(tmp_path,monkeypatch):
    from test_scheduled_watch_bridge import create_watch
    watch_config,_=create_watch(tmp_path)
    def forbidden(*args,**kwargs):
        pytest.fail("Unrequested maturity input should never be opened")
    monkeypatch.setattr(scheduler,"audit_maturity_schedule_sources",forbidden,raising=False)
    work=folders(tmp_path)
    from eraleader import local_schedule
    result=local_schedule.run_scheduled_watch_only(
        **work,watch_research_config=watch_config,watch_max_age_days=7)
    assert result["status"]=="WATCH_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert result["watch_operating_report_pages"]==14
    assert result["messages_sent"]==0


def test_same_market_day_horizon_transition_forces_new_verified_cycle(tmp_path,monkeypatch):
    config,_=make_config(tmp_path)
    from eraleader.ranked_discovery import _frozen,_time,ZONES
    source=read_maturity_schedule_config(config)["KR"]["freeze"]
    frozen=_frozen(source)
    local=_time(frozen["snapshot_at_utc"]).astimezone(ZONES["KR"])
    due=(local+timedelta(days=frozen["horizon_days"])).astimezone(timezone.utc)
    moments=[due-timedelta(microseconds=1)]

    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):
            return moments[0] if tz is None else moments[0].astimezone(tz)

    monkeypatch.setattr(scheduler,"datetime",Clock)
    earlier=run(tmp_path,config)
    assert earlier["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert earlier["ranked_maturity_fingerprints"]["KR"]["horizon_pending"]==1
    moments[0]=due
    later=run(tmp_path,config)
    assert later["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert later["ranked_maturity_fingerprints"]["KR"]["horizon_elapsed"]==1
    assert earlier["ranked_maturity_fingerprints"]["KR"]["market_as_of_day"]==(
        later["ranked_maturity_fingerprints"]["KR"]["market_as_of_day"])
    assert earlier["archive"]!=later["archive"]
    assert later["official_leaders_confirmed"]==0


def test_concurrent_lock_blocks_second_maturity_run_without_writes(tmp_path):
    import fcntl
    config,_=make_config(tmp_path)
    control=folders(tmp_path)["control"]
    control.mkdir()
    with (control/"batch.lock").open("a+b") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=run(tmp_path,config)
        assert result["status"]=="SKIPPED_ALREADY_RUNNING"
        assert result["price_batch_runs"]==0
        assert result["messages_sent"]==0
        assert not (tmp_path/"derived").exists()
        assert not (control/"last_verified_ranked_maturity_only.json").exists()


def test_replaced_archive_page_triggers_retry_not_unverified_skip(tmp_path):
    config,_=make_config(tmp_path)
    first=run(tmp_path,config)
    (tmp_path/"derived"/"site"/"ranked_maturity_us.html").unlink()
    second=run(tmp_path,config)
    assert second["status"]=="RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP"
    assert Path(second["archive"]).is_file()
    assert (tmp_path/"derived"/"site"/"ranked_maturity_us.html").is_file()
    assert first["archive"]!=second["archive"]
