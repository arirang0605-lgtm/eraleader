"""Atomic dual-source offline PIT first-ingest; only synthetic declared feeds."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from eraleader import provider_pair_atomic_onboard as pipeline
from eraleader.provider_dual_source_audit import (
    audit_provider_source_pair, STATUS_CONSISTENT)
from eraleader.provider_pit_adapter import audit_registered_provider_asof
from eraleader.provider_staged_lineage import (
    audit_staged_source_lineage, STATUS_MATCHED)
from test_provider_export_normalizer import (
    stage_fixture, revise_stream, NOW, rows_for)

SRC=Path(__file__).resolve().parents[1]
SCRIPT=SRC/"scripts"/"onboard_provider_pair.py"


def make_pair(tmp_path, market="KR"):
    first=stage_fixture(tmp_path/"a",market=market)
    second=stage_fixture(tmp_path/"b",market=market)
    content=json.loads(second.read_bytes())
    content["source_id"]="SYNTHETIC_DISTINCT_FEED_B"
    content["publisher_id_claimed"]="OTHER_DECLARED_NOT_AUTHENTICATED"
    second.write_text(json.dumps(content,sort_keys=True))
    root=tmp_path/"private_pairs"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return first,second,root


def run(pair,at=NOW):
    a,b,root=pair
    return pipeline.onboard_staged_provider_pair(
        a,b,root/"first_pair",clock=at)


@pytest.mark.parametrize("market",["KR","US"])
def test_complete_two_provider_original_shas_registered_as_one_commit(tmp_path,market):
    a,b,root=make_pair(tmp_path,market)
    original={x:sha256(x.read_bytes()).hexdigest()
              for source in (a,b) for x in source.parent.glob("*")}
    result=run((a,b,root))
    target=root/"first_pair"
    assert result["status"]==pipeline.STATUS
    assert result["market"]==market
    assert result["all_or_nothing_published"] is True
    assert result["two_original_first_ingest_receipts_pinned"] is True
    assert result["matched_active_declared_securities"]==1
    assert result["matched_corporate_events"]==1
    assert result["matched_fundamental_facts"]==1
    assert result["matched_industry_facts"]==1
    assert result["original_publisher_independently_authenticated"] is False
    assert result["legal_issuer_security_class_pit_certified"] is False
    assert result["complete_historical_exchange_universe_certified"] is False
    assert result["actual_future_leader_skill_certified"] is False
    assert result["external_api_calls"]==result["messages_sent"]==0
    assert target.is_dir()
    assert sorted(x.name for x in target.iterdir())==["source_a","source_b"]
    digests=[]
    for letter,source in (("a",a),("b",b)):
        path=target/("source_"+letter)
        manifest=path/"normalized"/"manifest.json"
        db=path/"offline.sqlite"
        assert manifest.is_file() and db.is_file()
        lineage=audit_staged_source_lineage(
            source,manifest,ledger_file=db,decision_at=NOW.isoformat(),
            clock=NOW,require_original_first_ingest_pin=True)
        assert lineage["status"]==STATUS_MATCHED
        assert lineage["first_ingest_raw_and_witness_pin_present"] is True
        normalized=sha256(manifest.read_bytes()).hexdigest()
        assert audit_registered_provider_asof(
            db,normalized,decision_at=NOW.isoformat(),clock=NOW)[
                "eligible_for_contemporaneous_research"] is True
        digests.append(normalized)
    paired=audit_provider_source_pair(
        target/"source_a"/"offline.sqlite",digests[0],
        target/"source_b"/"offline.sqlite",digests[1],
        decision_at=NOW.isoformat(),clock=NOW,require_original_pins=True,
        original_sources=(
            (a,target/"source_a"/"normalized"/"manifest.json"),
            (b,target/"source_b"/"normalized"/"manifest.json")))
    assert paired["status"]==STATUS_CONSISTENT
    assert paired["official_historical_universe_pit_certified"] is False
    assert {x:sha256(x.read_bytes()).hexdigest() for x in original}==original
    assert not list(root.glob(".eraleader_pair_ingest_*"))
    public=json.dumps(result)
    assert "00001234" not in public and "123456" not in public
    assert str(a) not in public and str(b) not in public


@pytest.mark.parametrize("reason",["same_staged","same_source",
                                   "same_publisher","different_market",
                                   "missing_second","second_rehashed_corrupt",
                                   "future_retrieval","invalid_first"])
def test_pair_preflight_blocks_before_publishing(tmp_path,reason):
    a,b,root=make_pair(tmp_path)
    if reason=="same_staged":
        b=a
    elif reason in ("same_source","same_publisher"):
        data=json.loads(b.read_text())
        if reason=="same_source":
            data["source_id"]=json.loads(a.read_text())["source_id"]
        else:
            data["publisher_id_claimed"]=json.loads(a.read_text())["publisher_id_claimed"]
        b.write_text(json.dumps(data,sort_keys=True))
    elif reason=="different_market":
        b=stage_fixture(tmp_path/"us",market="US")
    elif reason=="missing_second":
        b.unlink()
    elif reason=="second_rehashed_corrupt":
        (b.parent/"membership.jsonl").write_text("not JSON\n")
        data=json.loads(b.read_text())
        spec=next(z for z in data["streams"] if z["kind"]=="membership")
        spec["sha256"]=sha256((b.parent/"membership.jsonl").read_bytes()).hexdigest()
        b.write_text(json.dumps(data))
    elif reason=="future_retrieval":
        data=json.loads(b.read_text())
        data["retrieved_at_claimed"]=(NOW+timedelta(days=1)).isoformat()
        b.write_text(json.dumps(data))
    elif reason=="invalid_first":
        (a.parent/"membership.jsonl").write_text("[]\n")
    with pytest.raises((ValueError,OSError,TypeError)):
        run((a,b,root))
    assert not (root/"first_pair").exists()
    assert not list(root.iterdir())


@pytest.mark.parametrize("field,update",[
    ("membership",{"stock_code":"999999"}),
    ("actions",{"ratio":3}),
    ("fundamentals",{"value":456.0}),
    ("industry",{"unit":"SOME_OTHER_UNIT"}),
])
def test_two_locally_valid_but_semantically_disagreeing_feeds_atomic_abort(tmp_path,field,update):
    a,b,root=make_pair(tmp_path)
    revise_stream(b,field,lambda rows:rows[0].update(update))
    with pytest.raises(ValueError,match="pair|corroborate|source"):
        run((a,b,root))
    assert not (root/"first_pair").exists()
    assert not list(root.iterdir())


def test_raw_input_is_not_silently_overwritten_or_imported_twice(tmp_path):
    a,b,root=make_pair(tmp_path)
    first=run((a,b,root))
    old={x:sha256(x.read_bytes()).hexdigest()
         for x in (root/"first_pair").rglob("*") if x.is_file()}
    with pytest.raises(ValueError,match="NEW|exists|overwrite"):
        run((a,b,root))
    assert {x:sha256(x.read_bytes()).hexdigest() for x in old}==old
    assert first["two_original_first_ingest_receipts_pinned"] is True


def test_second_import_error_does_not_leave_first_db_or_bundle(tmp_path,monkeypatch):
    a,b,root=make_pair(tmp_path)
    original=pipeline.import_provider_bundle
    calls=[0]
    def fails_after_first(*args,**kwargs):
        calls[0]+=1
        if calls[0]==2:
            raise RuntimeError("Synthetic provider B first-ingest failure")
        return original(*args,**kwargs)
    monkeypatch.setattr(pipeline,"import_provider_bundle",fails_after_first)
    with pytest.raises(RuntimeError,match="provider B"):
        run((a,b,root))
    assert calls==[2]
    assert not (root/"first_pair").exists()
    assert not list(root.iterdir())


def test_source_document_changes_at_commit_boundary_block_publication(tmp_path,monkeypatch):
    a,b,root=make_pair(tmp_path)
    original=pipeline._preflight
    calls=[0]
    def mutated(*args,**kwargs):
        calls[0]+=1
        if calls[0]==3:
            # Input changes just BEFORE pre-publish re-read. The manifest
            # still carries the old SHA, so the original reader must refuse.
            stream=b.parent/"membership.jsonl"
            stream.write_bytes(stream.read_bytes()+b"\n")
        return original(*args,**kwargs)
    monkeypatch.setattr(pipeline,"_preflight",mutated)
    with pytest.raises(ValueError):
        run((a,b,root))
    assert calls[0]>=4
    assert not (root/"first_pair").exists()
    assert not list(root.iterdir())


@pytest.mark.parametrize("reason",["existing","symlink","public_parent","inside_source","relative"])
def test_destination_security_and_immutable_boundary(tmp_path,reason):
    a,b,root=make_pair(tmp_path)
    target=root/"first_pair"
    if reason=="existing":
        target.mkdir()
    elif reason=="symlink":
        target.symlink_to(tmp_path,target_is_directory=True)
    elif reason=="public_parent":
        root.chmod(0o755)
    elif reason=="inside_source":
        target=a.parent/"inside_raw"
    else:
        target=Path("relative_under_current_working_dir")
    try:
        with pytest.raises((ValueError,OSError)):
            pipeline.onboard_staged_provider_pair(a,b,target,clock=NOW)
    finally:
        root.chmod(0o700)
    if reason not in ("existing","symlink"):
        assert not (root/"first_pair").exists()


def test_cli_real_clock_and_privacy_contract(tmp_path):
    a,b,root=make_pair(tmp_path)
    cmd=[sys.executable,str(SCRIPT),"--project",str(SRC),
         "--staged-a",str(a),"--staged-b",str(b),
         "--target",str(root/"first_pair")]
    completed=subprocess.run(cmd,cwd=SRC,text=True,capture_output=True)
    assert completed.returncode==0,completed.stderr
    report=json.loads(completed.stdout)
    assert report["status"]==pipeline.STATUS
    assert report["all_or_nothing_published"] is True
    assert report["official_leader_promotions"]==0
    assert str(a) not in completed.stdout and str(b) not in completed.stdout
    denied=subprocess.run(cmd,cwd=SRC,text=True,capture_output=True)
    assert denied.returncode==2
    assert str(a) not in denied.stderr and str(b) not in denied.stderr
    assert not list(root.glob(".eraleader_pair_ingest_*"))
