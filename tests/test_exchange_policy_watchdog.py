"""6_5: strict WATCH roster first-write policy surveillance, local dry-run only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import sqlite3
import subprocess
import sys

import pytest

from eraleader.exchange_roster_policy import guard_integrated_policy
from eraleader.exchange_policy_watchdog import (
    run_exchange_policy_watchdog, verify_exchange_policy_watchdog,
)


NOW=datetime(2026,10,12,1,0,tzinfo=timezone.utc)
SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"run_exchange_policy_watchdog.py"


def prep(tmp_path):
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    policy=project/"output"/"strict_watch"
    policy.mkdir()
    return project,policy


def pin(out,market="KR",raw="a"*64):
    with guard_integrated_policy(out,market,strict_mode=True) as session:
        session.require_first_write(raw)
    return (
        out/("provider_exchange_policy_"+market.lower()+".json"),
        out/("provider_exchange_policy_guard_"+market.lower()+".json"),
        out/(".provider_exchange_policy_"+market.lower()+".lock"),
    )


def scan(project,policy,*,at=NOW):
    return run_exchange_policy_watchdog(project,policy,clock=at)


def test_missing_never_enabled_both_markets_no_alert(tmp_path):
    p,o=prep(tmp_path)
    result=scan(p,o)
    assert result["status"]=="LOCAL_EXCHANGE_POLICY_DRY_RUN_RECORDED"
    assert result["market_states"]=={"KR":"NOT_ACTIVATED","US":"NOT_ACTIVATED"}
    assert result["new_alerts"]==[]
    assert result["independent_pit_certified"] is False
    assert result["official_leader_promotions"]==0
    assert result["messages_sent"]==0
    assert result["external_api_calls"]==0
    assert verify_exchange_policy_watchdog(p)["check_count"]==1


@pytest.mark.parametrize("market",["KR","US"])
def test_activated_policy_remains_original_and_no_duplicate_alert(tmp_path,market):
    p,o=prep(tmp_path)
    original=pin(o,market)
    hashes=[sha256(f.read_bytes()).hexdigest() for f in original]
    first=scan(p,o)
    assert first["market_states"][market]=="HEALTHY"
    assert first["new_alerts"]==[]
    assert scan(p,o,at=NOW+timedelta(hours=1))["new_alerts"]==[]
    assert [sha256(f.read_bytes()).hexdigest() for f in original]==hashes
    assert verify_exchange_policy_watchdog(p)["check_count"]==2


def test_after_healthy_deleting_all_policy_guard_and_lock_is_caught(tmp_path):
    p,o=prep(tmp_path)
    a,b,lock=pin(o)
    scan(p,o)
    original={f:f.read_bytes() for f in (a,b)}
    for f in (a,b,lock):
        f.unlink()
    result=scan(p,o,at=NOW+timedelta(hours=1))
    assert result["market_states"]["KR"]=="ANOMALY"
    assert "KR:POLICY_DISAPPEARED" in result["new_alerts"]
    assert scan(p,o,at=NOW+timedelta(hours=2))["new_alerts"]==[]
    for f,data in original.items():
        f.write_bytes(data)
    lock.touch()
    restored=scan(p,o,at=NOW+timedelta(hours=3))
    assert restored["market_states"]["KR"]=="HEALTHY"
    assert "KR:POLICY_RESTORED" in restored["new_alerts"]


@pytest.mark.parametrize("damage",["guard_deleted","policy_reformatted","lock_deleted","policy_symlink"])
def test_missing_malformed_or_unsafe_policy_detected_without_source_writes(tmp_path,damage):
    p,o=prep(tmp_path)
    a,b,lock=pin(o)
    scan(p,o)
    before=sha256(b.read_bytes()).hexdigest()
    if damage=="guard_deleted":
        b.unlink()
    elif damage=="policy_reformatted":
        a.write_text(json.dumps(json.loads(a.read_text()),indent=2))
    elif damage=="lock_deleted":
        lock.unlink()
    else:
        a.unlink()
        a.symlink_to(b)
    result=scan(p,o,at=NOW+timedelta(minutes=20))
    assert result["market_states"]["KR"]=="ANOMALY"
    assert any(alert.startswith("KR:") for alert in result["new_alerts"])
    if b.exists():
        assert sha256(b.read_bytes()).hexdigest()==before
    else:
        assert damage=="guard_deleted"


def test_valid_self_resealed_new_policy_is_still_mismatched_with_first_trusted_pin(tmp_path):
    p,o=prep(tmp_path)
    a,b,_=pin(o)
    first=scan(p,o)
    old=first["trusted_policy_sha256"]["KR"]
    # Reconstruct a self-consistent *new* local seal. That is not original evidence.
    obj=json.loads(a.read_text())
    obj["first_roster_sha256"]="b"*64
    body=(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n").encode()
    a.write_bytes(body)
    guard=json.loads(b.read_text())
    guard["policy_sha256"]=sha256(body).hexdigest()
    b.write_bytes((json.dumps(guard,sort_keys=True,ensure_ascii=False,
                separators=(",",":"),allow_nan=False)+"\n").encode())
    second=scan(p,o,at=NOW+timedelta(hours=1))
    assert second["market_states"]["KR"]=="ANOMALY"
    assert second["trusted_policy_sha256"]["KR"]==old
    assert "KR:PINNED_POLICY_REPLACED" in second["new_alerts"]


def test_integrity_chain_corruption_and_source_change_do_not_reset(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    log=p/"output"/"exchange_policy_alerts"/"history.jsonl"
    log.write_bytes(log.read_bytes().replace(b'"HEALTHY"',b'"NOT_ACTIVATED"',1))
    with pytest.raises(ValueError,match="watchdog"):
        scan(p,o,at=NOW+timedelta(hours=1))
    with pytest.raises(ValueError,match="watchdog"):
        verify_exchange_policy_watchdog(p)


def test_root_binding_prevents_scanning_unrelated_output_to_hide_anomaly(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    alternative=p/"output"/"another"
    alternative.mkdir()
    with pytest.raises(ValueError,match="source root"):
        scan(p,alternative,at=NOW+timedelta(hours=1))


def test_report_and_html_sanitized_and_repeated_local_cli(tmp_path):
    p,o=prep(tmp_path)
    pin(o,"US")
    for _ in range(2):
        child=subprocess.run([sys.executable,str(SCRIPT),"--project",str(p),
                              "--policy-out",str(o)],text=True,capture_output=True)
        assert child.returncode==0,child.stderr
        obj=json.loads(child.stdout)
        assert obj["market_states"]["US"]=="HEALTHY"
        assert obj["messages_sent"]==0
        assert obj["external_api_calls"]==0
        assert str(o) not in child.stdout
    folder=p/"output"/"exchange_policy_alerts"
    assert (folder/"report.json").exists()
    html=(folder/"site"/"index.html").read_text()
    assert "KR" in html and "US" in html
    assert "NOT_ACTIVATED" in html
    assert str(o) not in html
    assert verify_exchange_policy_watchdog(p)["check_count"]==2


def test_watcher_rejects_rollback_clock_and_manifest_deletion(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    with pytest.raises(ValueError,match="clock"):
        scan(p,o,at=NOW-timedelta(seconds=1))
    marker=p/"output"/"exchange_policy_alerts"/"genesis.json"
    marker.unlink()
    with pytest.raises(ValueError,match="watchdog"):
        scan(p,o,at=NOW+timedelta(hours=1))


def test_scheduler_opt_in_records_anomaly_without_live_messages(tmp_path,monkeypatch,capsys):
    import eraleader.local_schedule as schedule
    from scripts.run_local_scheduled import main as scheduled_main
    p,o=prep(tmp_path)
    a,b,lock=pin(o,"US")
    monkeypatch.setattr(schedule,"run_scheduled",lambda **kw: {
        "status":"LOCAL_RESEARCH_COMPLETE","messages_sent":0,"external_api_calls":0})
    assert scheduled_main(["--project",str(p),"--exchange-policy-out",str(o)])==0
    first=json.loads(capsys.readouterr().out)
    assert first["exchange_policy_watchdog"]["market_states"]["US"]=="HEALTHY"
    a.unlink();b.unlink();lock.unlink()
    assert scheduled_main(["--project",str(p),"--exchange-policy-out",str(o)])==0
    second=json.loads(capsys.readouterr().out)
    assert second["exchange_policy_watchdog"]["market_states"]["US"]=="ANOMALY"
    assert "US:POLICY_DISAPPEARED" in second["exchange_policy_watchdog"]["new_alerts"]
    assert second["messages_sent"]==0


def test_scheduler_failure_still_checks_policy_and_preserves_primary_error(tmp_path,monkeypatch):
    import eraleader.local_schedule as schedule
    from scripts.run_local_scheduled import main as scheduled_main
    p,o=prep(tmp_path)
    pin(o)
    def broken(**kwargs):
        raise ValueError("existing stale-cache safety stop")
    monkeypatch.setattr(schedule,"run_scheduled",broken)
    with pytest.raises(ValueError,match="existing stale-cache safety stop"):
        scheduled_main(["--project",str(p),"--exchange-policy-out",str(o)])
    assert verify_exchange_policy_watchdog(p)["check_count"]==1


def test_plist_generation_does_not_install_policy_watch_observer(tmp_path):
    from scripts.run_local_scheduled import main as scheduled_main
    p,o=prep(tmp_path)
    generated=tmp_path/"disabled.plist"
    with pytest.raises(ValueError,match="not supported"):
        scheduled_main(["--project",str(p),"--generate-plist",str(generated),
                        "--exchange-policy-out",str(o)])
    assert not generated.exists()
    assert not (p/"output"/"exchange_policy_alerts").exists()

def test_independent_published_head_blocks_valid_prefix_truncation(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    log=p/"output"/"exchange_policy_alerts"/"history.jsonl"
    prefix=log.read_bytes()
    scan(p,o,at=NOW+timedelta(hours=1))
    assert verify_exchange_policy_watchdog(p)["check_count"]==2
    report=p/"output"/"exchange_policy_alerts"/"report.json"
    recorded=json.loads(report.read_bytes())
    assert recorded["chain_head_sha256"]==json.loads(log.read_bytes().splitlines()[-1])["event_sha256"]
    # Both surviving lines are perfectly self-hashed. Only the independent
    # published head can detect the disappearance of the last valid record.
    log.write_bytes(prefix)
    with pytest.raises(ValueError,match="checkpoint|rolled back"):
        scan(p,o,at=NOW+timedelta(hours=2))
    with pytest.raises(ValueError,match="checkpoint|rolled back"):
        verify_exchange_policy_watchdog(p)


def test_missing_or_revised_published_checkpoint_blocks_restart(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    report=p/"output"/"exchange_policy_alerts"/"report.json"
    original=report.read_bytes()
    report.unlink()
    with pytest.raises(ValueError,match="checkpoint"):
        scan(p,o,at=NOW+timedelta(hours=1))
    report.write_bytes(original)
    published=json.loads(original)
    published["chain_head_sha256"]="0"*64
    report.write_text(json.dumps(published))
    with pytest.raises(ValueError,match="checkpoint"):
        verify_exchange_policy_watchdog(p)


def test_different_explicit_original_source_can_be_verified_without_default_guess(tmp_path):
    p,o=prep(tmp_path)
    chosen=p/"output"/"original_watch_v2"
    chosen.mkdir()
    pin(chosen)
    scan(p,chosen)
    assert verify_exchange_policy_watchdog(p,chosen)["chain_verified"] is True
    with pytest.raises(ValueError,match="source root"):
        verify_exchange_policy_watchdog(p,o)

def test_full_log_rollback_and_report_loss_cannot_clear_initial_verified_policy(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    folder=p/"output"/"exchange_policy_alerts"
    assert (folder/"first_event.json").is_file()
    (folder/"history.jsonl").write_bytes(b"")
    (folder/"report.json").unlink()
    with pytest.raises(ValueError,match="first|receipt|watchdog"):
        scan(p,o,at=NOW+timedelta(minutes=5))


@pytest.mark.parametrize("damage",["missing_first_receipt","changed_first_receipt","linked_history"])
def test_first_event_receipt_and_history_path_cannot_silently_reset(tmp_path,damage):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    folder=p/"output"/"exchange_policy_alerts"
    witness=folder/"first_event.json"
    if damage=="missing_first_receipt":
        witness.unlink()
    elif damage=="changed_first_receipt":
        witness.write_bytes(witness.read_bytes()+b" ")
    else:
        history=folder/"history.jsonl"
        replica=tmp_path/"history_backup.log"
        replica.write_bytes(history.read_bytes())
        history.unlink()
        history.symlink_to(replica)
    with pytest.raises(ValueError,match="first|receipt|linked|watchdog"):
        scan(p,o,at=NOW+timedelta(minutes=5))

def test_published_status_cannot_fake_official_success_without_changing_chain(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    report=p/"output"/"exchange_policy_alerts"/"report.json"
    obj=json.loads(report.read_bytes())
    obj["official_leader_promotions"]=1
    report.write_text(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    with pytest.raises(ValueError,match="checkpoint"):
        verify_exchange_policy_watchdog(p)
    with pytest.raises(ValueError,match="checkpoint"):
        scan(p,o,at=NOW+timedelta(minutes=5))


def test_read_only_audit_fails_safe_while_policy_watchdog_writer_lock_is_held(tmp_path):
    p,o=prep(tmp_path)
    pin(o)
    scan(p,o)
    guard=p/"output"/"exchange_policy_alerts"/".checks.lock"
    with guard.open("rb") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            with pytest.raises(RuntimeError,match="currently being updated"):
                verify_exchange_policy_watchdog(p)
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
