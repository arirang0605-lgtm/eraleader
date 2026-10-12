"""First atomic source SHA -> pre-WATCH native offline integrated provenance.

Synthetic local feeds only. Tests must not modify the unrelated native-first
capture patch or use real APIs / key material / user market-data caches.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import shutil

import pytest

from eraleader.cli import main
from eraleader.provider_pair_candidate_bridge import (
    resolve_atomic_candidate_pair, assert_atomic_candidate_pair_unchanged,
)
from test_provider_pair_atomic_onboard import make_pair, run
from test_provider_export_normalizer import NOW, revise_stream


@pytest.fixture
def onboarded(tmp_path):
    staged=make_pair(tmp_path)
    first=run(staged)
    pair_root=staged[2]/"first_pair"
    out=tmp_path/"out"
    out.mkdir(mode=0o700)
    # Existing candidate's PIT source is an independently read-only snapshot;
    # the original A/B published ledgers remain untouched.
    shutil.copy2(pair_root/"source_a"/"offline.sqlite",out/"offline.sqlite")
    original_hashes=tuple(sha256(p.read_bytes()).hexdigest() for p in (
        staged[0],staged[1],pair_root/"first_pair_receipt.json"))
    return staged,first,pair_root,out,original_hashes


def options(case,*,market="KR",sha=None,decision=None):
    _,first,root,out,_=case
    return [
        "offline-integrated","--market",market,
        "--as-of",decision or NOW.isoformat(),"--out",str(out),
        "--provider-atomic-pair-root",str(root),
        "--provider-first-pair-sha256",first["first_pair_receipt_sha256"] if sha is None else sha,
    ]


def first_hashes(case):
    staged,_,root,_,_=case
    return tuple(sha256(p.read_bytes()).hexdigest() for p in (
        staged[0],staged[1],root/"first_pair_receipt.json"))


@pytest.mark.parametrize("market",["KR","US"])
def test_atomic_first_receipt_full_asof_to_real_watch_and_immutable_run(tmp_path,capsys,market):
    staged=make_pair(tmp_path,market)
    first=run(staged)
    root=staged[2]/"first_pair"
    out=tmp_path/"candidate"
    out.mkdir()
    shutil.copy2(root/"source_a"/"offline.sqlite",out/"offline.sqlite")
    case=(staged,first,root,out,first_hashes((staged,first,root,out,())))
    parsed=resolve_atomic_candidate_pair(
        root,first["first_pair_receipt_sha256"],market=market,decision_at=NOW.isoformat())
    assert parsed.market==market
    assert parsed.pair[0]==root/"source_a"/"offline.sqlite"
    assert parsed.originals[1][0]==staged[1]
    assert_atomic_candidate_pair_unchanged(parsed,root,decision_at=NOW.isoformat())
    main(options(case,market=market))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert result["provider_research_watch_allowed"] is True
    assert result["official_leaders"]==0 and result["pit_certified"] is False
    gate=json.loads((out/"provider_candidate_gate_research.json").read_bytes())
    assert gate["atomic_first_pair_receipt_sha256"]==first["first_pair_receipt_sha256"]
    assert gate["atomic_first_pair_research_only"] is True
    assert gate["official_candidate_promotion_allowed"] is False
    assert gate["original_first_ingest_pins_locally_consistent"] is True
    joined=list((out/"runs").glob("joined_*.json"))
    assert len(joined)==1
    record=json.loads(joined[0].read_bytes())
    assert record["provider_pair_gate"]["atomic_first_pair_receipt_sha256"]==first["first_pair_receipt_sha256"]
    assert first_hashes(case)==case[4]
    assert "00001234" not in json.dumps(gate)
    assert str(staged[0]) not in json.dumps(gate)
    # Repeat must not invent a second first-WATCH or rewrite the published run.
    old_sha=sha256(joined[0].read_bytes()).hexdigest()
    main(options(case,market=market))
    again=json.loads(capsys.readouterr().out)
    assert again["new_prospective_research_signals"]==0
    assert sha256(joined[0].read_bytes()).hexdigest()==old_sha
    assert len(list((out/"runs").glob("joined_*.json")))==1


@pytest.mark.parametrize("failure",[
    "missing_sha","missing_root","wrong_sha","wrong_market","too_early",
    "manual_pins","manual_pair","rewritten_raw","rewritten_first_receipt",
])
def test_atomic_pinned_opt_in_never_falls_back_to_ungated_candidate(onboarded,capsys,failure):
    staged,first,root,out,originals=onboarded
    args=options(onboarded)
    if failure=="missing_sha":
        args=args[:-2]+["--provider-atomic-pair-root",str(root)]
    elif failure=="missing_root":
        args=args[:-4]+["--provider-first-pair-sha256",first["first_pair_receipt_sha256"]]
    elif failure=="wrong_sha":
        args[-1]="0"*64
    elif failure=="wrong_market":
        args[2]="US"
    elif failure=="too_early":
        args[4]=(NOW-timedelta(seconds=1)).isoformat()
    elif failure=="manual_pins":
        args.extend(["--provider-staged-manifest-a",str(staged[0])])
    elif failure=="manual_pair":
        args.extend(["--provider-ledger-a",str(root/"source_a"/"offline.sqlite")])
    elif failure=="rewritten_raw":
        revise_stream(staged[1],"industry",lambda rows: rows[0].update(value=999))
    else:
        file=root/"first_pair_receipt.json"
        file.write_bytes(file.read_bytes()+b"modified")
    with pytest.raises((SystemExit,ValueError)) as caught:
        main(args)
    if isinstance(caught.value,SystemExit):
        assert caught.value.code==2
    assert not (out/"prospective.sqlite").exists()
    assert not (out/"state_history.sqlite").exists()
    assert not (out/"provider_candidate_gate_research.json").exists()
    assert not (out/"runs").exists()
    assert not (out/"site").exists()
    assert not (out/"offline_integrated_research.json").exists()
    assert (out/"offline.sqlite").is_file()
    if failure not in ("rewritten_raw","rewritten_first_receipt"):
        assert first_hashes(onboarded)==originals


def test_atomic_bridge_second_audit_detects_in_flight_source_change_before_watch(onboarded,monkeypatch):
    import eraleader.cli as cli
    staged,_,root,out,_=onboarded
    real=cli.audit_candidate_provider_gate
    def mutate_after_candidate_gate(*args,**kw):
        audited=real(*args,**kw)
        revise_stream(staged[1],"fundamentals",
                      lambda rows: rows[0].update(value=345))
        return audited
    monkeypatch.setattr(cli,"audit_candidate_provider_gate",mutate_after_candidate_gate)
    with pytest.raises((SystemExit,ValueError)):
        main(options(onboarded))
    assert not (out/"provider_candidate_gate_research.json").exists()
    assert not (out/"prospective.sqlite").exists()
    assert not (out/"runs").exists()


@pytest.mark.parametrize("where",["pair","inside_pair","raw","parent"])
def test_first_pair_sources_never_become_watch_output(onboarded,where):
    staged,first,root,_,before=onboarded
    output={"pair":root,"inside_pair":root/"source_a",
            "raw":staged[0].parent,"parent":root.parent}[where]
    argv=options(onboarded)
    argv[6]=str(output)
    with pytest.raises((SystemExit,ValueError)):
        main(argv)
    assert first_hashes(onboarded)==before
    assert not (root/"prospective.sqlite").exists()


def test_legacy_integrated_without_atomic_opt_in_still_works(tmp_path,capsys):
    from eraleader.offline_pit import OfflineLedger
    out=tmp_path/"prior"
    out.mkdir()
    source=OfflineLedger(out/"offline.sqlite")
    source.close()
    main(["offline-integrated","--market","KR","--as-of",NOW.isoformat(),"--out",str(out)])
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert report["pit_certified"] is False
