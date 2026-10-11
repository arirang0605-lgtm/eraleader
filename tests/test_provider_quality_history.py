"""6_2/6_5 quality-transition receipts: local history, not official PIT."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import sqlite3

import pytest

from eraleader.cli import main
from eraleader.local_backup import create_backup, restore_backup, verify_backup
from eraleader.provider_quality_history import (
    audit_quality_history, record_quality_snapshot, render_quality_history,
)
from eraleader.provider_pit_adapter import import_provider_bundle
from test_provider_gate_quality_view import case_with_lineage
from test_provider_pair_original_pin_gate import options, NOW, DECISION
from test_provider_candidate_gate import setup_case, args as legacy_args
from test_provider_dual_source_audit import edit_stream

CLOCK=datetime(2026,10,12,3,tzinfo=timezone.utc)


def fixture(tmp_path, market="KR"):
    _, _, gate=case_with_lineage(tmp_path/"feeds", market)
    home=tmp_path/"history"
    home.mkdir()
    return home,gate


def changed(gate, *, decision="2026-10-12T09:30:00+09:00",
            permitted=False, strict=None, cls=None,
            reason="ISSUER_CLASS_CANDIDATE_CLASS_MEMBERSHIP_MISMATCH"):
    result=deepcopy(gate)
    result["decision_at_utc"]=decision
    result["source_pair_digest_sha256"]=sha256(
        (gate["source_pair_digest_sha256"]+decision+str(permitted)+reason+
         str(strict)+str(cls)).encode()).hexdigest()
    result["research_watch_allowed"]=permitted
    result["status"]=(
        "LOCAL_CANDIDATE_PIT_PAIR_MATCHED_WATCH_RESEARCH_ONLY" if permitted
        else "BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    )
    result["blocker_counts"]={} if permitted else {reason:1}
    result["blocker_count"]=0 if permitted else 1
    if strict is False:
        result["require_original_first_ingest_pins"]=False
        result["original_first_ingest_pins_locally_consistent"]=False
        result["source_pair_original_pin_sha256"]=None
        result["issuer_class_bridge_required"]=False
        result["issuer_class_bridge_status"]=None
        result["issuer_class_evidence_sha256"]=None
        result["issuer_class_matched_candidates"]=0
    elif cls is False:
        result["issuer_class_bridge_required"]=False
        result["issuer_class_bridge_status"]=None
        result["issuer_class_evidence_sha256"]=None
        result["issuer_class_matched_candidates"]=0
    elif cls is True:
        result["issuer_class_bridge_required"]=True
        result["issuer_class_bridge_status"] = (
            "LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
            if permitted else "BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
        )
        result["issuer_class_matched_candidates"] = (
            result["candidate_issuer_count"] if permitted else 0)
    elif not permitted:
        result["issuer_class_matched_candidates"]=0
        result["issuer_class_bridge_status"]="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    return result


@pytest.mark.parametrize("market",["KR","US"])
def test_first_actual_gate_receipt_is_local_and_sanitized(tmp_path,market):
    root,gate=fixture(tmp_path,market)
    result=record_quality_snapshot(root,gate,clock=CLOCK)
    assert result["event_added"] is True
    assert result["global_event_count"] == 1
    assert result["transition"]=="FIRST_LOCAL_OBSERVATION"
    assert result["research_gate_only"] is True
    assert result["official_leader_promotions"]==0
    assert result["independently_attested_timestamp"] is False
    report=audit_quality_history(root,market=market)
    assert report["chain_verified"] is True
    assert report["market_event_count"]==1
    assert report["last_gate_allowed"] is True
    assert report["last_transition"]=="FIRST_LOCAL_OBSERVATION"
    assert report["real_future_leader_precision"] is None
    assert report["first_observed_at_utc"]==CLOCK.isoformat()
    assert report["recent_events"][0]["decision_at_utc"]==gate["decision_at_utc"]
    assert report["recent_events"][0]["retrospective_replay"] is True
    html=render_quality_history(report)
    assert "변화 이력" in html and "실전 적중률 N/A" in html
    assert "공식 확정 대장주 0" in html
    assert "로컬 시각" in html
    assert gate["source_pair_digest_sha256"] not in html
    raw=(root/"provider_quality_history.sqlite").read_bytes()
    assert b"CORP00001234" not in raw
    assert b"CIK0000012345" not in raw
    assert b"SYNTHETIC_DOC" not in raw


def test_idempotent_identical_input_does_not_append_and_replay_clock_is_not_first_day(tmp_path):
    root,gate=fixture(tmp_path)
    first=record_quality_snapshot(root,gate,clock=CLOCK)
    again=record_quality_snapshot(root,gate,clock=CLOCK+timedelta(hours=2))
    assert again["event_added"] is False
    assert again["global_event_count"]==1
    assert again["head_sha256"]==first["head_sha256"]
    assert audit_quality_history(root,market="KR")["recent_events"][0]["recorded_at_utc"]==CLOCK.isoformat()


def test_allowed_to_blocked_and_back_to_research_is_not_certified_upgrade(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    blocked=changed(gate,decision="2026-10-12T10:00:00+09:00")
    one=record_quality_snapshot(root,blocked,clock=CLOCK+timedelta(hours=1))
    assert one["transition"]=="WATCH_GATE_BLOCKED"
    reopened=changed(gate,decision="2026-10-12T11:00:00+09:00",permitted=True)
    two=record_quality_snapshot(root,reopened,clock=CLOCK+timedelta(hours=2))
    assert two["transition"]=="WATCH_GATE_REOPENED_RESEARCH_ONLY"
    report=audit_quality_history(root,market="KR")
    assert report["transition_counts"]["WATCH_GATE_BLOCKED"]==1
    assert report["transition_counts"]["WATCH_GATE_REOPENED_RESEARCH_ONLY"]==1
    assert report["market_event_count"]==3
    assert report["last_gate_allowed"] is True
    assert report["official_leader_promotions"]==0
    assert report["real_future_leader_precision"] is None


def test_evidence_level_downgrade_is_reported_without_fake_certification(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    weaker=changed(gate,decision="2026-10-12T10:15:00+09:00",permitted=True,strict=False)
    result=record_quality_snapshot(root,weaker,clock=CLOCK+timedelta(hours=1))
    assert result["transition"]=="EVIDENCE_WEAKENED"
    report=audit_quality_history(root,market="KR")
    assert report["last_first_ingest_pin_required"] is False
    assert report["last_issuer_class_required"] is False
    assert report["independently_attested_timestamp"] is False


def test_evidence_level_strengthened_from_weak_pair_claims_only(tmp_path):
    root,gate=fixture(tmp_path)
    weak=changed(gate,decision="2026-10-12T10:15:00+09:00",permitted=True,strict=False)
    record_quality_snapshot(root,weak,clock=CLOCK)
    upgraded=changed(gate,decision="2026-10-12T11:15:00+09:00",permitted=True)
    assert record_quality_snapshot(root,upgraded,clock=CLOCK+timedelta(hours=1))["transition"]=="EVIDENCE_STRENGTHENED"


def test_reassessment_of_same_decision_kept_as_new_event_not_replaced(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    revised=changed(gate,decision=gate["decision_at_utc"])
    result=record_quality_snapshot(root,revised,clock=CLOCK+timedelta(minutes=1))
    assert result["transition"]=="REVISED_SAME_DECISION_REVIEW"
    assert audit_quality_history(root,market="KR")["market_event_count"]==2


def test_regressive_decision_time_is_recorded_as_replay_not_predictive(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    backdated=changed(gate,decision="2026-10-10T09:30:00+09:00",permitted=False)
    second=record_quality_snapshot(root,backdated,clock=CLOCK+timedelta(minutes=5))
    assert second["transition"]=="OLDER_DECISION_REPLAY_NOT_PREDICTION"
    assert audit_quality_history(root,market="KR")["recent_events"][-1]["retrospective_replay"] is True


def test_future_decision_or_regressed_local_clock_rejected(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    with pytest.raises(ValueError,match="clock|backdat|earlier"):
        record_quality_snapshot(root,changed(gate),clock=CLOCK-timedelta(seconds=1))
    future=changed(gate,decision="2026-10-14T00:00:00+09:00")
    with pytest.raises(ValueError,match="Future|decision"):
        record_quality_snapshot(root,future,clock=CLOCK)
    assert audit_quality_history(root,market="KR")["market_event_count"]==1


def test_independent_markets_have_distinct_quality_timelines_single_global_chain(tmp_path):
    root,kr=fixture(tmp_path/"k","KR")
    _,us=fixture(tmp_path/"u","US")
    one=record_quality_snapshot(root,kr,clock=CLOCK)
    two=record_quality_snapshot(root,us,clock=CLOCK+timedelta(minutes=1))
    assert one["global_event_count"]==1
    assert two["global_event_count"]==2
    a=audit_quality_history(root,market="KR")
    b=audit_quality_history(root,market="US")
    assert a["market_event_count"]==1 and b["market_event_count"]==1
    assert a["global_event_count"]==2 and b["global_event_count"]==2
    assert a["last_gate_allowed"] and b["last_gate_allowed"]


def test_chain_verification_detects_changed_or_deleted_payload_and_counters(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    path=root/"provider_quality_history.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE quality_events SET payload_json=? WHERE event_no=1",('{"fraud":true}',))
    with pytest.raises(ValueError,match="chain|digest|audit|payload|corrupt"):
        audit_quality_history(root,market="KR")


def test_chain_verification_detects_deleted_rows_even_if_meta_unmodified(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    with sqlite3.connect(root/"provider_quality_history.sqlite") as db:
        db.execute("DELETE FROM quality_events")
    with pytest.raises(ValueError,match="count|chain|corrupt"):
        audit_quality_history(root,market="KR")


def test_deleted_first_write_marker_or_database_alone_fails_closed(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    seal=root/"provider_quality_history_genesis.json"
    seal.unlink()
    with pytest.raises(ValueError,match="genesis|seal|marker|missing"):
        record_quality_snapshot(root,changed(gate),clock=CLOCK+timedelta(minutes=1))
    with pytest.raises(ValueError,match="genesis|seal|marker|missing"):
        audit_quality_history(root,market="KR")


def test_missing_database_with_existing_genesis_does_not_silently_reinitialize(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    (root/"provider_quality_history.sqlite").unlink()
    with pytest.raises(ValueError,match="ledger|database|missing|orphan"):
        record_quality_snapshot(root,gate,clock=CLOCK+timedelta(minutes=1))


def test_marker_content_modification_cannot_be_silently_accepted(tmp_path):
    root,gate=fixture(tmp_path)
    record_quality_snapshot(root,gate,clock=CLOCK)
    marker=root/"provider_quality_history_genesis.json"
    marker.write_bytes(marker.read_bytes()+b" ")
    with pytest.raises(ValueError,match="genesis|marker|seal|integrity"):
        audit_quality_history(root,market="KR")


@pytest.mark.parametrize("target",["provider_quality_history.sqlite","provider_quality_history_genesis.json"])
def test_symlink_or_repointed_ledger_rejected(tmp_path,target):
    root,gate=fixture(tmp_path)
    victim=tmp_path/"outside.txt"
    victim.write_text("DO_NOT_OVERWRITE")
    (root/target).symlink_to(victim)
    with pytest.raises(ValueError,match="symlink|unsafe|Unsafe|linked"):
        record_quality_snapshot(root,gate,clock=CLOCK)
    assert victim.read_text()=="DO_NOT_OVERWRITE"


def test_parallel_identical_submissions_do_not_double_record(tmp_path):
    root,gate=fixture(tmp_path)
    def submit(_):
        return record_quality_snapshot(root,gate,clock=CLOCK)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(submit,range(4)))
    assert sum(r["event_added"] for r in results)==1
    assert audit_quality_history(root,market="KR")["market_event_count"]==1


@pytest.mark.parametrize("field,bad",[
    ("official_candidate_promotion_allowed",True),
    ("leader_accuracy_certified",True),
    ("official_leader_promotions",1),
    ("source_pair_digest_sha256","FAKE"),
    ("blocker_counts",{"<script>":1}),
])
def test_refuse_invalid_raw_gate_before_any_ledger_files(tmp_path,field,bad):
    root,gate=fixture(tmp_path)
    forged={**gate,field:bad}
    with pytest.raises(ValueError):
        record_quality_snapshot(root,forged,clock=CLOCK)
    assert not (root/"provider_quality_history.sqlite").exists()
    assert not (root/"provider_quality_history_genesis.json").exists()


def test_snapshots_and_html_backup_restore_are_sanitized(tmp_path):
    root,gate=fixture(tmp_path)
    rec=record_quality_snapshot(root,gate,clock=CLOCK)
    html=root/"site"/"provider_quality_history_kr.html"
    report=root/"provider_quality_history_kr_research.json"
    assert html.is_file() and report.is_file()
    assert rec["html_path"]==str(html)
    assert rec["report_path"]==str(report)
    archive=tmp_path/"provider-history-backup.zip"
    create_backup(root,archive)
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert "provider_quality_history.sqlite" in z.namelist()
        assert "provider_quality_history_genesis.json" in z.namelist()
        assert "provider_quality_history_kr_research.json" in z.namelist()
        assert "site/provider_quality_history_kr.html" in z.namelist()
        assert all("vendor" not in p and "staged" not in p for p in z.namelist())
    restore_backup(archive,tmp_path/"restored")
    verified=audit_quality_history(tmp_path/"restored",market="KR")
    assert verified["chain_verified"] and verified["market_event_count"]==1
    assert (tmp_path/"restored"/"site"/html.name).read_bytes()==html.read_bytes()


def test_cli_default_leaves_history_absent(tmp_path,capsys):
    root,pair=setup_case(tmp_path)
    main(legacy_args(root,pair))
    capsys.readouterr()
    assert not (root/"provider_quality_history.sqlite").exists()
    assert not (root/"site"/"provider_quality_history_kr.html").exists()


@pytest.mark.parametrize("suffix",[
    ["--record-provider-quality-history"],
    ["--record-provider-quality-history","--show-provider-gate-quality"],
])
def test_cli_history_requires_provider_and_explicit_view_before_writes(tmp_path,capsys,suffix):
    out=tmp_path/"out"
    with pytest.raises(SystemExit) as caught:
        main(["offline-integrated","--market","KR","--as-of",DECISION,
              "--out",str(out),*suffix])
    assert caught.value.code==2
    assert not out.exists()


@pytest.mark.parametrize("market",["KR","US"])
def test_real_opt_in_cli_writes_history_for_actual_pair_and_quality_web(
    tmp_path,capsys,market,
):
    pair,lineage,_=case_with_lineage(tmp_path,market)
    out=tmp_path/"out"
    out.mkdir()
    import_provider_bundle(pair[0][3],out/"offline.sqlite",clock=NOW)
    before=sha256((out/"offline.sqlite").read_bytes()).hexdigest()
    arguments=["offline-integrated","--market",market,"--as-of",DECISION,
               "--out",str(out),*options(pair),
               "--require-provider-issuer-class-lineage","--provider-issuer-lineage",str(lineage),
               "--show-provider-gate-quality","--record-provider-quality-history"]
    main(arguments)
    done=json.loads(capsys.readouterr().out)
    assert done["new_prospective_research_signals"]==1
    assert done["official_leaders"]==0 and done["pit_certified"] is False
    assert done["provider_quality_history"]["event_added"]
    assert done["provider_quality_history"]["transition"]=="FIRST_LOCAL_OBSERVATION"
    assert audit_quality_history(out,market=market)["market_event_count"]==1
    assert (out/"site"/f"provider_quality_history_{market.lower()}.html").is_file()
    assert f"provider_quality_history_{market.lower()}.html" in (
        out/"site"/f"provider_quality_{market.lower()}.html").read_text()
    assert sha256((out/"offline.sqlite").read_bytes()).hexdigest()==before
    main(arguments)
    again=json.loads(capsys.readouterr().out)
    assert again["provider_quality_history"]["event_added"] is False
    assert audit_quality_history(out,market=market)["market_event_count"]==1


def test_blocked_cli_still_tracks_quality_but_no_new_watch(tmp_path,capsys):
    root,pair=setup_case(tmp_path,change_b=lambda m:edit_stream(
        m,"actions",lambda rows:rows[0].update(ratio=4)))
    main([*legacy_args(root,pair),
          "--show-provider-gate-quality","--record-provider-quality-history"])
    done=json.loads(capsys.readouterr().out)
    assert done["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert done["new_prospective_research_signals"]==0
    assert done["provider_quality_history"]["event_added"] is True
    assert (root/"site"/"provider_quality_history_kr.html").is_file()
    assert not (root/"prospective.sqlite").exists()
    assert not (root/"runs").exists()
    assert audit_quality_history(root,market="KR")["last_gate_allowed"] is False
