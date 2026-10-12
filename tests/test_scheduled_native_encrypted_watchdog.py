"""6_5 opt-in native encrypted DRY-RUN scheduler and local dashboard."""
from __future__ import annotations

import json

import pytest

from eraleader import local_schedule, native_sha_witness
from scripts.run_local_scheduled import main
from test_native_encrypted_watchdog import rig as prepared, create


@pytest.fixture
def rig(prepared,monkeypatch):
    jobs=[]
    def research(**kwargs):
        jobs.append("regular research")
        return {"status":"LOCAL_SYNTHETIC_JOB","messages_sent":0,
                "external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",research)
    return prepared,jobs


def args(rig,*,slots=None):
    setup,_=rig
    slots=setup["slots"] if slots is None else slots
    result=["--project",str(setup["project"]),
            "--native-encrypted-watch-vault-root",str(setup["vault"]),
            "--native-encrypted-watch-witness-root",str(setup["witness"]),
            "--native-encrypted-watch-cert",str(setup["cert"])]
    for slot in slots:
        result.extend(["--native-encrypted-watch-slot",slot])
    return result


def test_opt_in_schedule_reads_two_original_encrypted_shas_and_creates_only_alerts(
        rig,capsys):
    setup,jobs=rig
    create(setup,0);create(setup,1)
    (setup["project"]/"output"/"site").mkdir()
    (setup["project"]/"output"/"site"/"index.html").write_text(
        "<html><body>EraLeader research</body></html>")
    assert main(args(rig))==0
    out=json.loads(capsys.readouterr().out)
    report=out["native_encrypted_watchdog"]
    assert report["status"]=="LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED"
    assert len(report["cohorts"])==2
    assert not report["new_alerts"]
    assert report["authenticated_plaintext_verified"] is False
    assert out["external_api_calls"]==out["messages_sent"]==0
    assert jobs==["regular research"]
    assert (setup["project"]/"output"/"site"/"native_encrypted_dry_run.html").is_file()
    assert main(args(rig))==0
    again=json.loads(capsys.readouterr().out)["native_encrypted_watchdog"]
    assert again["check_count"]==2
    assert not again["new_alerts"]
    assert len(jobs)==2


def test_deleted_cipher_induces_local_warning_without_backup_recreation(rig,capsys):
    setup,jobs=rig
    create(setup,0)
    flags=args(rig,slots=setup["slots"][:1])
    assert main(flags)==0
    capsys.readouterr()
    cipher=next(setup["vault"].glob("*.cms"))
    cipher.unlink()
    assert main(flags)==0
    report=json.loads(capsys.readouterr().out)["native_encrypted_watchdog"]
    assert len(report["new_alerts"])==1
    assert next(iter(report["cohorts"].values()))["state"]=="ANOMALY"
    assert len(jobs)==2
    assert not list(setup["vault"].glob("*.cms"))


@pytest.mark.parametrize("absent",["slot","vault","witness","cert"])
def test_partial_encrypted_watch_flags_refused_before_market_job(rig,absent):
    setup,jobs=rig
    flags=args(rig)
    names={
        "slot":"--native-encrypted-watch-slot",
        "vault":"--native-encrypted-watch-vault-root",
        "witness":"--native-encrypted-watch-witness-root",
        "cert":"--native-encrypted-watch-cert",
    }
    arg=names[absent]
    if absent=="slot":
        flags=[x for x in flags if x not in (arg,*setup["slots"])]
    else:
        i=flags.index(arg)
        flags=flags[:i]+flags[i+2:]
    with pytest.raises(ValueError,match="requires"):
        main(flags)
    assert jobs==[]
    assert not (setup["project"]/"output"/"native_encrypted_alerts").exists()


def test_plist_flags_cannot_auto_install_encrypted_monitor(rig,tmp_path):
    setup,jobs=rig
    dest=tmp_path/"NEVER_INSTALLED.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(args(rig)+["--generate-plist",str(dest)])
    assert jobs==[] and not dest.exists()


def test_primary_stale_failure_does_not_mask_audit_or_claim_success(rig,monkeypatch):
    setup,jobs=rig
    create(setup,0)
    def stale(**kwargs):
        jobs.append("stale")
        raise ValueError("STALENESS_KEPT")
    monkeypatch.setattr(local_schedule,"run_scheduled",stale)
    with pytest.raises(ValueError,match="STALENESS_KEPT"):
        main(args(rig,slots=setup["slots"][:1]))
    report=setup["project"]/"output"/"native_encrypted_alerts"/"report.json"
    assert report.is_file()
    record=json.loads(report.read_bytes())
    assert record["status"]=="LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED"
    assert record["messages_sent"]==0
    assert jobs==["stale"]


def test_default_schedule_without_encrypted_flag_preserves_original_behavior(rig,capsys):
    setup,jobs=rig
    assert main(["--project",str(setup["project"])])==0
    out=json.loads(capsys.readouterr().out)
    assert out["status"]=="LOCAL_SYNTHETIC_JOB"
    assert jobs==["regular research"]
    assert not (setup["project"]/"output"/"native_encrypted_alerts").exists()
    assert not setup["vault"].exists()


def test_invalid_same_device_or_duplicate_slots_preflight_blocks_market_job(rig,monkeypatch):
    setup,jobs=rig
    with pytest.raises(ValueError,match="Duplicate"):
        main(args(rig,slots=[setup["slots"][0],setup["slots"][0]]))
    setup["vault"].mkdir(mode=0o700,parents=True,exist_ok=True)
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda p,q:False)
    with pytest.raises(ValueError,match="different filesystem"):
        main(args(rig,slots=setup["slots"][:1]))
    assert jobs==[]
