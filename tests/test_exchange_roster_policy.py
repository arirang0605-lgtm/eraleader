"""4_1/6_5: sticky strict source gate after first claimed exchange-roster use.

First-write policy is a local anti-downgrade contract, not official PIT.
Tests use synthetic claimed issuer/market sources; no live data.
"""
from __future__ import annotations

from argparse import Namespace
from hashlib import sha256
from pathlib import Path
import fcntl
import json
from zipfile import ZipFile

import pytest

from eraleader.cli import main,execute_integrated
from eraleader.exchange_roster_policy import (
    SCHEMA,GUARD_SCHEMA,guard_integrated_policy,verify_exchange_roster_policy,
)
from eraleader.local_backup import create_backup,verify_backup,restore_backup
from eraleader.provider_pit_adapter import import_provider_bundle
from test_candidate_exchange_roster_gate import build,cli_flags,sha,update
from test_provider_pair_original_pin_gate import NOW,DECISION,options


def make(tmp_path,market="KR"):
    pair,lineage,members,roster=build(tmp_path,market)
    output=tmp_path/"out";output.mkdir()
    import_provider_bundle(pair[0][3],output/"offline.sqlite",clock=NOW)
    return pair,lineage,roster,output


def run(output,market="KR",*flags):
    return main(["offline-integrated","--market",market,
                 "--as-of",DECISION,"--out",str(output),*flags])


def sealed_files(out,market="KR"):
    lower=market.lower()
    return (out/("provider_exchange_policy_"+lower+".json"),
            out/("provider_exchange_policy_guard_"+lower+".json"),
            out/(".provider_exchange_policy_"+lower+".lock"))


@pytest.mark.parametrize("market",["KR","US"])
def test_first_strict_watch_creates_independent_local_market_policy_and_guard(tmp_path,capsys,market):
    pair,lineage,roster,out=make(tmp_path,market)
    assert verify_exchange_roster_policy(out,market) is None
    run(out,market,*cli_flags(pair,lineage,roster))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert result["new_prospective_research_signals"]==1
    primary,shadow,lock=sealed_files(out,market)
    assert all(p.is_file() for p in (primary,shadow,lock))
    policy=verify_exchange_roster_policy(out,market)
    assert policy["status"]=="LOCAL_PINNED_EXCHANGE_WATCH_POLICY_NOT_PIT_CERTIFIED"
    assert policy["guard_verified"] is True
    assert policy["first_roster_sha256"]==sha(roster)
    assert policy["independent_pit_certified"] is False
    assert policy["official_leader_promotions"]==0
    before={str(p):sha(p) for p in (primary,shadow)}
    # Same strict request is permitted; no rewriting first-write bytes.
    run(out,market,*cli_flags(pair,lineage,roster))
    later=json.loads(capsys.readouterr().out)
    assert later["new_prospective_research_signals"]==0
    assert before=={str(p):sha(p) for p in (primary,shadow)}


@pytest.mark.parametrize("flags_mode",["unflagged","two_suppliers","issuer_without_roster"])
def test_after_strict_watch_all_weaker_modes_denied_before_run_or_db_change(
    tmp_path,capsys,flags_mode
):
    pair,lineage,roster,out=make(tmp_path)
    run(out,"KR",*cli_flags(pair,lineage,roster))
    capsys.readouterr()
    db_sha=sha(out/"offline.sqlite")
    watch=sha(out/"prospective.sqlite")
    runs={p.name:sha(p) for p in (out/"runs").iterdir()}
    gate_sha=sha(out/"provider_candidate_gate_research.json")
    if flags_mode=="unflagged":
        flags=[]
    elif flags_mode=="two_suppliers":
        flags=options(pair)
    else:
        flags=[*options(pair),
               "--require-provider-issuer-class-lineage",
               "--provider-issuer-lineage",str(lineage)]
    with pytest.raises(SystemExit) as exc:
        run(out,"KR",*flags)
    assert exc.value.code==2
    assert "forbids silent downgrade" in capsys.readouterr().err
    assert sha(out/"offline.sqlite")==db_sha
    assert sha(out/"prospective.sqlite")==watch
    assert {p.name:sha(p) for p in (out/"runs").iterdir()}==runs
    assert sha(out/"provider_candidate_gate_research.json")==gate_sha


def test_bad_first_strict_evidence_pins_policy_and_prevents_fallback(tmp_path,capsys):
    pair,lineage,roster,out=make(tmp_path)
    update(roster,lambda data:data["security_classes"].append({
        "security_id":"KR:CORP99999999:ISSUE:OMITTED",
        "ticker":"888888","valid_from":"2022-01-01","valid_to":None,
    }))
    run(out,"KR",*cli_flags(pair,lineage,roster))
    blocked=json.loads(capsys.readouterr().out)
    assert blocked["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert not (out/"prospective.sqlite").exists()
    assert verify_exchange_roster_policy(out,"KR") is not None
    with pytest.raises(SystemExit):
        run(out,"KR")
    assert "forbids silent downgrade" in capsys.readouterr().err
    # Repairing claimed evidence under still-strict SHA proof may continue;
    # the local mode seal does not certify its publisher or actual universe.
    update(roster,lambda data:data["security_classes"].pop())
    run(out,"KR",*cli_flags(pair,lineage,roster))
    repaired=json.loads(capsys.readouterr().out)
    assert repaired["new_prospective_research_signals"]==1
    assert repaired["official_leaders"]==0


@pytest.mark.parametrize("which",["primary_missing","guard_missing","both_missing","bad_primary","bad_guard"])
def test_policy_partial_deletion_reformat_rewrite_or_total_loss_block_all_runs(
    tmp_path,capsys,which
):
    pair,lineage,roster,out=make(tmp_path)
    run(out,"KR",*cli_flags(pair,lineage,roster))
    capsys.readouterr()
    primary,shadow,lock=sealed_files(out)
    original={p:p.read_bytes() for p in (primary,shadow)}
    if which=="primary_missing":primary.unlink()
    elif which=="guard_missing":shadow.unlink()
    elif which=="both_missing":
        primary.unlink();shadow.unlink()
    elif which=="bad_primary":
        primary.write_bytes(primary.read_bytes()+b" ")
    else:
        shadow.write_bytes(shadow.read_bytes()+b" ")
    old_watch=sha(out/"prospective.sqlite")
    for flags in ([],cli_flags(pair,lineage,roster)):
        with pytest.raises(SystemExit) as exc:
            run(out,"KR",*flags)
        assert exc.value.code==2
        capsys.readouterr()
    assert sha(out/"prospective.sqlite")==old_watch
    # Recover the same local content only for this test, not automatically.
    for p,raw in original.items():p.write_bytes(raw)
    assert verify_exchange_roster_policy(out,"KR") is not None


def test_preflight_rejects_incomplete_strict_flags_without_creating_policy(tmp_path,capsys):
    out=tmp_path/"out";out.mkdir()
    with pytest.raises(SystemExit) as exc:
        run(out,"KR","--require-provider-exchange-roster")
    assert exc.value.code==2
    assert "complete pinned" in capsys.readouterr().err
    assert verify_exchange_roster_policy(out,"KR") is None
    assert not any(p.exists() for p in sealed_files(out))
    assert not (out/"offline.sqlite").exists()


def test_market_seals_are_independent_in_same_output_root(tmp_path):
    out=tmp_path/"output";out.mkdir()
    a="a"*64
    b="b"*64
    with guard_integrated_policy(out,"KR",strict_mode=True) as session:
        session.require_first_write(a)
    assert verify_exchange_roster_policy(out,"KR")["first_roster_sha256"]==a
    assert verify_exchange_roster_policy(out,"US") is None
    with guard_integrated_policy(out,"US",strict_mode=False) as session:
        assert session.existing is None
    with guard_integrated_policy(out,"US",strict_mode=True) as session:
        session.require_first_write(b)
    assert verify_exchange_roster_policy(out,"KR")["first_roster_sha256"]==a
    assert verify_exchange_roster_policy(out,"US")["first_roster_sha256"]==b
    with pytest.raises(ValueError,match="forbids silent downgrade"):
        with guard_integrated_policy(out,"KR",strict_mode=False):pass
    with pytest.raises(ValueError,match="forbids silent downgrade"):
        with guard_integrated_policy(out,"US",strict_mode=False):pass


def test_sealed_policy_enforces_minimum_not_one_immutable_daily_roster_sha(tmp_path):
    out=tmp_path/"output";out.mkdir()
    with guard_integrated_policy(out,"KR",strict_mode=True) as policy:
        before=policy.require_first_write("a"*64)
    with guard_integrated_policy(out,"KR",strict_mode=True) as policy:
        after=policy.require_first_write("b"*64)
    assert after==before
    assert after["first_roster_sha256"]=="a"*64
    # The next day's independently claimed roster still passes the pre-WATCH
    # hash-vintage validator; the policy pins the gate mode, not today's symbols.


def test_preexisting_lock_and_wiped_primary_guard_refuse_fake_first_use(tmp_path):
    out=tmp_path/"out";out.mkdir()
    with guard_integrated_policy(out,"KR",strict_mode=True) as session:
        session.require_first_write("c"*64)
    primary,guard,lock=sealed_files(out)
    primary.unlink();guard.unlink()
    assert lock.is_file()
    with pytest.raises(ValueError,match="no sealed receipts"):
        with guard_integrated_policy(out,"KR",strict_mode=True):pass


def test_symlink_primary_or_guard_or_lock_never_followed(tmp_path):
    out=tmp_path/"out";out.mkdir()
    outside=tmp_path/"outside.txt";outside.write_text("DO_NOT_TOUCH")
    for file in sealed_files(out):
        file.symlink_to(outside)
        with pytest.raises(ValueError,match="Unsafe"):
            with guard_integrated_policy(out,"KR",strict_mode=True):pass
        file.unlink()
    assert outside.read_text()=="DO_NOT_TOUCH"


def test_concurrent_strict_run_refuses_to_bypass_original_guard(tmp_path):
    out=tmp_path/"out";out.mkdir()
    with guard_integrated_policy(out,"KR",strict_mode=True) as session:
        session.require_first_write("b"*64)
    lock=sealed_files(out)[2]
    with lock.open("rb+") as file:
        fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            with pytest.raises(RuntimeError,match="Concurrent"):
                with guard_integrated_policy(out,"KR",strict_mode=True):pass
        finally:
            fcntl.flock(file.fileno(),fcntl.LOCK_UN)


def test_inprocess_policy_tamper_between_audit_and_watch_blocks_before_gate_report(
    tmp_path,monkeypatch,capsys
):
    import eraleader.cli as cli
    pair,lineage,roster,out=make(tmp_path)
    original=cli.audit_candidate_provider_gate
    primary=sealed_files(out)[0]
    def altered(*args,**kwargs):
        gate=original(*args,**kwargs)
        primary.write_bytes(primary.read_bytes()+b" ")
        return gate
    monkeypatch.setattr(cli,"audit_candidate_provider_gate",altered)
    with pytest.raises(SystemExit) as exc:
        run(out,"KR",*cli_flags(pair,lineage,roster))
    assert exc.value.code==2
    assert "policy" in capsys.readouterr().err.lower()
    assert not (out/"prospective.sqlite").exists()
    assert not (out/"provider_candidate_gate_research.json").exists()


def test_backup_only_sanitized_first_write_pins_and_restored_guard_rejects_downgrade(
    tmp_path,capsys
):
    pair,lineage,roster,out=make(tmp_path)
    run(out,"KR",*cli_flags(pair,lineage,roster))
    capsys.readouterr()
    original=verify_exchange_roster_policy(out,"KR")
    archive=tmp_path/"market_policy_derived.zip"
    snap=create_backup(out,archive)
    assert snap["status"]=="LOCAL_BACKUP_CREATED"
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as f:
        files=set(f.namelist())
    assert "provider_exchange_policy_kr.json" in files
    assert "provider_exchange_policy_guard_kr.json" in files
    assert ".provider_exchange_policy_kr.lock" not in files
    assert str(roster) not in json.dumps(original)
    restored=tmp_path/"restored"
    assert restore_backup(archive,restored)["status"]=="LOCAL_BACKUP_RESTORED"
    again=verify_exchange_roster_policy(restored,"KR")
    assert again==original
    with pytest.raises(SystemExit):
        run(restored,"KR")
    assert "forbids silent downgrade" in capsys.readouterr().err


def test_batch_direct_entrypoint_cannot_downgrade_after_cli_strict(tmp_path,capsys):
    pair,lineage,roster,out=make(tmp_path)
    run(out,"KR",*cli_flags(pair,lineage,roster))
    capsys.readouterr()
    with pytest.raises(ValueError,match="forbids silent downgrade"):
        execute_integrated(Namespace(out=str(out),market="KR"))
    assert (out/"prospective.sqlite").is_file()


def test_existing_default_no_strict_root_has_no_policy_side_effect(tmp_path,capsys):
    pair,lineage,roster,out=make(tmp_path)
    before=set(out.iterdir())
    run(out,"KR")
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert response["provider_research_watch_allowed"] is False
    assert verify_exchange_roster_policy(out,"KR") is None
    assert not any(path.exists() for path in sealed_files(out))
    assert (out/"offline.sqlite") in before


def test_untrusted_policy_cannot_claim_official_pit(tmp_path):
    out=tmp_path/"out";out.mkdir()
    with guard_integrated_policy(out,"KR",strict_mode=True) as session:
        session.require_first_write("a"*64)
    primary,guard,_=sealed_files(out)
    data=json.loads(primary.read_text())
    data["independent_pit_certified"]=True
    primary.write_text(json.dumps(data,sort_keys=True))
    with pytest.raises(ValueError,match="first-write|policy|Rewritten|forged"):
        verify_exchange_roster_policy(out,"KR")
