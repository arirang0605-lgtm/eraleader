"""Prospective WATCH observations bound to two immutable atomic pair vintages.

Only synthetic KR/US sources and actual offline-integrated -> SQLite -> audit.
No external provider, real issuer, live message, or first-native modifications.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import copy
import json
import shutil
import sqlite3
import subprocess
import sys

import pytest

from eraleader.cli import main
from eraleader.provider_pair_atomic_onboard import onboard_staged_provider_pair
from eraleader.provider_pair_vintage_watch import (
    STATUS, audit_pinned_pair_vintage_watch,
)
from test_provider_export_normalizer import rows_for, stage_fixture

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "audit_pair_vintage_watch.py"


def rich_rows(market, latest_revenue, *, revision=1, correction_at=None):
    inputs = rows_for(market)
    fact = inputs["fundamentals"][0]
    base = {k: copy.deepcopy(v) for k, v in fact.items()
            if k not in ("metric", "period_end", "value", "published_at")}
    past = "2024-12-31"
    latest = "2025-12-31"
    def item(metric, period, value):
        row = dict(base, metric=metric, period_end=period, value=value)
        row["published_at"] = ("2025-03-01T12:00:00+09:00"
                               if period == past else
                               "2026-03-01T12:00:00+09:00")
        if period == latest and metric == "revenue" and correction_at is not None:
            row["revision"] = revision
            row["published_at"] = correction_at
        return row
    inputs["fundamentals"] = [
        item("revenue", past, 123),
        item("revenue", latest, latest_revenue),
        item("operating_income", past, 50),
        item("operating_income", latest, 75),
    ]
    one = inputs["industry"][0]
    inputs["industry"] = [
        dict(one, metric="revenue", period_end=past, value=321,
             published_at="2025-03-01T12:00:00+09:00"),
        dict(one, metric="revenue", period_end=latest, value=385,
             published_at="2026-03-01T12:00:00+09:00"),
    ]
    return inputs


def make_rich_pair(root, market, revenue, at, *, revised=False, action_ratio=None):
    root.mkdir(parents=True)
    patch_time=(at-timedelta(milliseconds=50)).isoformat() if revised else None
    values=rich_rows(market,revenue,revision=2 if revised else 1,
                     correction_at=patch_time)
    if action_ratio is not None:
        values["actions"][0]["ratio"]=action_ratio
        values["actions"][0]["revision"]=2
        values["actions"][0]["published_at"]=patch_time
    claimed=(at-timedelta(milliseconds=20) if revised else
             at-timedelta(minutes=20)).isoformat()
    raw_a=stage_fixture(root/"a",market=market,rows=values,retrieved=claimed)
    raw_b=stage_fixture(root/"b",market=market,rows=values,retrieved=claimed)
    declared=json.loads(raw_b.read_bytes())
    declared["source_id"]="SYNTHETIC_DISTINCT_VINTAGE_FEED_B"
    declared["publisher_id_claimed"]="SYNTHETIC_OTHER_UNAUTHENTICATED"
    raw_b.write_text(json.dumps(declared,sort_keys=True))
    private=root/"private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    bundle=private/"first_pair"
    receipt=onboard_staged_provider_pair(raw_a,raw_b,bundle,clock=at)
    return bundle,receipt["first_pair_receipt_sha256"],(raw_a,raw_b)


def paired_trial(tmp_path,capsys,*,market="KR",old_revenue=160,new_revenue=130,
                 new_action_ratio=None):
    out=tmp_path/"derived"
    out.mkdir()
    observed_paths=[]
    first_contents=[]
    pairs=[]
    for i,revenue in enumerate((old_revenue,new_revenue)):
        # Actual first receipt and old registered WATCH precede the second
        # vintage's first ingestion; never backdate the registration clock.
        when=(datetime.now(timezone.utc)-timedelta(seconds=2) if i==0
              else datetime.now(timezone.utc))
        current_pair=make_rich_pair(
            tmp_path/("before" if i==0 else "after"),
            market,revenue,when,revised=(i==1),
            action_ratio=new_action_ratio if i==1 else None)
        pairs.append(current_pair)
        root,pinned,raw=current_pair
        # This derived working database is swappable; first source originals,
        # published pair receipts and registered screen history are immutable.
        shutil.copy2(root/"source_a"/"offline.sqlite",out/"offline.sqlite")
        args=["offline-integrated","--market",market,
              "--as-of",when.isoformat(),
              "--out",str(out),
              "--provider-atomic-pair-root",str(root),
              "--provider-first-pair-sha256",pinned]
        main(args)
        summary=json.loads(capsys.readouterr().out)
        assert summary["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
        assert summary["provider_research_watch_allowed"] is True
        assert summary["pit_certified"] is False
        current=list((out/"runs").glob("joined_*.json"))
        run_paths=[p for p in current if p not in observed_paths]
        assert len(run_paths)==1
        observed_paths.append(run_paths[0])
        doc=json.loads(run_paths[0].read_bytes())
        assert len(doc["company_rows"])==1
        assert doc["company_rows"][0]["research_screen_evaluated"] is True, doc["company_rows"][0]
        first_contents.append(doc["company_rows"][0]["research_growth_screen_hit"])
    assert first_contents==[old_revenue>=148,new_revenue>=148]
    return pairs[0],pairs[1],observed_paths,out


def examine(trial,*,market="KR",clock=None,sha=None,second_run=None,ledger=None):
    old,new,runs,out=trial
    cutoff=clock or datetime.now(timezone.utc)
    return audit_pinned_pair_vintage_watch(
        old[0],old[1],new[0],new[1] if sha is None else sha,
        runs[0],runs[1] if second_run is None else second_run,
        out/"prospective.sqlite" if ledger is None else ledger,
        market=market,evaluated_at=cutoff.isoformat(),clock=cutoff)


@pytest.mark.parametrize("market",["KR","US"])
def test_actual_two_pinned_vintages_preserve_first_watch_and_detect_explicit_weakening(tmp_path,capsys,market):
    trial=paired_trial(tmp_path,capsys,market=market)
    old,new,runs,out=trial
    old_first=[sha256(p.read_bytes()).hexdigest()
               for root,_,raw in (old,new) for p in (root/"first_pair_receipt.json",*raw)]
    first_screen=json.loads(runs[0].read_bytes())
    assert first_screen["company_rows"][0]["research_growth_screen_hit"] is True
    cutoff=datetime.now(timezone.utc)
    report=examine(trial,market=market,clock=cutoff)
    assert report["status"]==STATUS
    assert report["explicit_one_screen_weakening_only"]==1
    assert report["explicit_one_screen_emerging_only"]==0
    assert report["paired_screens_not_comparable_or_deferred"]==0
    assert report["pair_linked_existing_rotation_hypotheses"]==0
    assert report["existing_rotation_research_hypothesis_count"]==0
    assert report["source_delta_counts"]["fundamentals"]["revised_prior_period_keys"]==1
    assert report["old_active_declared_issuer_count"]==1
    assert report["new_active_declared_issuer_count"]==1
    assert report["old_active_missing_from_new_vintage_not_a_weakness"]==0
    assert report["official_leader_replacements"]==0
    assert report["official_leader_promotions"]==0
    assert report["historic_pit_certified"] is False
    assert report["actual_prediction_accuracy_certified"] is False
    assert report["external_api_calls"]==report["messages_sent"]==0
    # No private raw document path/security identity in a public summary.
    emitted=json.dumps(report,ensure_ascii=False)
    assert str(old[2][0]) not in emitted and str(new[2][0]) not in emitted
    assert "00001234" not in emitted and "123456" not in emitted
    assert [sha256(p.read_bytes()).hexdigest()
            for root,_,raw in (old,new) for p in (root/"first_pair_receipt.json",*raw)]==old_first
    assert json.loads(runs[0].read_bytes())==first_screen
    assert examine(trial,market=market,clock=cutoff)==report


def test_prior_decision_backfilled_after_successor_intake_cannot_claim_early_weakening(tmp_path,capsys):
    trial=paired_trial(tmp_path,capsys)
    old,new,runs,out=trial
    old_asof=json.loads(runs[0].read_bytes())["as_of"]
    with sqlite3.connect(out/"prospective.sqlite") as db:
        fresh=db.execute(
            "SELECT recorded_at_utc FROM research_screen_observations WHERE observed_as_of=?",
            (json.loads(runs[1].read_bytes())["as_of"],)).fetchone()[0]
        new_receipt=json.loads((new[0]/"first_pair_receipt.json").read_bytes())
        first=datetime.fromisoformat(new_receipt["first_ingest_at_utc"])
        last=datetime.fromisoformat(fresh)
        assert first<last
        replay=(first+(last-first)/2).isoformat()
        assert first<datetime.fromisoformat(replay)<last
        db.execute("UPDATE research_screen_observations SET recorded_at_utc=? WHERE observed_as_of=?",
                   (replay,old_asof))
        db.execute("UPDATE prospective_signals SET recorded_at_utc=? WHERE observed_as_of=?",
                   (replay,old_asof))
    study=examine(trial)
    assert study["paired_old_screens_registered_after_new_vintage_censored"]==1
    assert study["explicit_one_screen_weakening_only"]==0
    assert study["pair_linked_existing_rotation_hypotheses"]==0


def test_corrected_old_split_terms_without_negative_screen_are_not_weakening(tmp_path,capsys):
    trial=paired_trial(tmp_path,capsys,old_revenue=160,new_revenue=160,
                       new_action_ratio=3)
    result=examine(trial)
    assert result["source_delta_counts"]["actions"]["revised_existing_event_terms"]==1
    assert result["explicit_one_screen_weakening_only"]==0
    assert result["explicit_screen_persistence"]==1
    assert result["official_leader_replacements"]==0


def test_change_from_explicit_negative_to_new_watch_is_only_emerging(tmp_path,capsys):
    trial=paired_trial(tmp_path,capsys,old_revenue=130,new_revenue=160)
    result=examine(trial)
    assert result["explicit_one_screen_emerging_only"]==1
    assert result["explicit_one_screen_weakening_only"]==0
    assert result["pair_linked_existing_rotation_hypotheses"]==0


@pytest.mark.parametrize("case",[
    "wrong_sha","same_pair","reversed_order","future_cutoff","wrong_market",
    "old_run_substitution","new_run_deleted","source_changed",
    "new_run_company_changed","prospective_hash_changed","missing_observation",
])
def test_no_weakening_if_first_evidence_or_prospective_chain_untrusted(tmp_path,capsys,case):
    trial=paired_trial(tmp_path,capsys)
    old,new,runs,out=trial
    wrong_sha=None
    old_root,new_root=old[0],new[0]
    old_run,new_run=runs
    now=datetime.now(timezone.utc)
    market="KR"
    if case=="wrong_sha":
        wrong_sha="0"*64
    elif case=="same_pair":
        new_root=old_root
    elif case=="reversed_order":
        old_root,new_root=new_root,old_root
        old_run,new_run=new_run,old_run
    elif case=="future_cutoff":
        now=now+timedelta(days=1)
    elif case=="wrong_market":
        market="US"
    elif case=="old_run_substitution":
        old_run=new_run
    elif case=="new_run_deleted":
        new_run.unlink()
    elif case=="source_changed":
        src=new[2][1].parent/"fundamentals.jsonl"
        src.write_bytes(src.read_bytes()+b"\n")
    elif case=="new_run_company_changed":
        doc=json.loads(new_run.read_bytes())
        doc["company_rows"][0]["research_growth_screen_hit"]=True
        new_run.write_text(json.dumps(doc,sort_keys=True))
    elif case in ("prospective_hash_changed","missing_observation"):
        second_asof=json.loads(runs[1].read_bytes())["as_of"]
        db=sqlite3.connect(out/"prospective.sqlite")
        if case=="prospective_hash_changed":
            db.execute("UPDATE research_screen_observations SET payload_hash=? WHERE observed_as_of=?",
                       ("0"*64, second_asof))
        else:
            db.execute("DELETE FROM research_screen_observations WHERE observed_as_of=?",
                       (second_asof,))
        db.commit()
        db.close()
    with pytest.raises((ValueError,RuntimeError,sqlite3.DatabaseError,OSError)):
        audit_pinned_pair_vintage_watch(
            old_root,old[1],new_root,new[1] if wrong_sha is None else wrong_sha,
            old_run,new_run,out/"prospective.sqlite",
            market=market,evaluated_at=(now+timedelta(days=2)).isoformat()
            if case=="future_cutoff" else now.isoformat(),clock=now)
    assert not (out/"provider_pair_vintage_repair.sqlite").exists()


def test_cli_readonly_safe_summary_and_wrong_sha_exit2(tmp_path,capsys):
    trial=paired_trial(tmp_path,capsys)
    old,new,runs,out=trial
    flags=[
        "--project",str(PROJECT),"--market","KR",
        "--old-pair-root",str(old[0]),"--old-first-sha",old[1],
        "--new-pair-root",str(new[0]),"--new-first-sha",new[1],
        "--old-run",str(runs[0]),"--new-run",str(runs[1]),
        "--prospective-ledger",str(out/"prospective.sqlite"),
        "--evaluated-at",datetime.now(timezone.utc).isoformat(),
    ]
    result=subprocess.run([sys.executable,str(SCRIPT),*flags],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report["explicit_one_screen_weakening_only"]==1
    assert report["status"]==STATUS
    assert not result.stderr
    assert str(old[0]) not in result.stdout and str(new[0]) not in result.stdout
    flags[flags.index("--new-first-sha")+1]="0"*64
    result=subprocess.run([sys.executable,str(SCRIPT),*flags],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==2
    assert result.stdout==""
    assert str(old[0]) not in result.stderr and str(new[0]) not in result.stderr
