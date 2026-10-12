"""5_5/6_5 opt-in evidence-archive handoff: first-WATCH never reissued."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import shutil

import pytest

from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_evidence_archive import verify_native_evidence_archive
from eraleader.native_first_capture import capture_first_native_topk
from test_native_first_capture import prepare, NOW


def setup(tmp_path, *, market="KR", scored=True):
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    b,rule,plan,unused=prepare(tmp_path/"fixtures",market=market,scored=scored)
    capture_root=project/"output"/"native_first_captures"
    return project,b,plan,capture_root


def run_archive(project,plan,capture_root,capture_result,clock=NOW):
    return archive_captured_native_plan(
        project,plan,capture_root,capture_result,clock=clock)


@pytest.mark.parametrize("market",["KR","US"])
def test_opt_in_after_real_native_capture_seals_private_zip_and_separate_sha(tmp_path,market):
    project,b,plan,root=setup(tmp_path,market=market)
    first=capture_first_native_topk(plan,root,clock=NOW)
    result=run_archive(project,plan,root,first)
    assert result["status"]=="FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED"
    assert result["market"]==market
    assert result["archive_original_sha256"]!=("0"*64)
    assert result["separate_local_first_sha_receipt_verified"] is True
    assert result["external_timestamp_attested"] is False
    assert result["official_leader_promotions"]==0
    assert result["messages_sent"]==result["external_api_calls"]==0
    evidence=project/"output"/"native_first_private_archives"
    records=project/"output"/"native_first_archive_receipts"
    zips=list(evidence.glob("native_*.zip"))
    assert len(zips)==1
    assert sha256(zips[0].read_bytes()).hexdigest()==result["archive_original_sha256"]
    assert verify_native_evidence_archive(zips[0],expected_sha256=result["archive_original_sha256"])["market"]==market
    assert len(list(records.glob("native_*.json")))==2
    assert not list(project.rglob("future_outcomes.json"))
    # The original first receipts are never re-frozen.
    before=sha256((root/list(root.glob("native_*"))[0].name/"capture_receipt.json").read_bytes()).hexdigest()
    repeated=capture_first_native_topk(plan,root,clock=NOW+timedelta(minutes=5))
    again=run_archive(project,plan,root,repeated,clock=NOW+timedelta(minutes=5))
    assert again["status"]=="EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED"
    assert again["archive_original_sha256"]==result["archive_original_sha256"]
    assert len(list(evidence.glob("*.zip")))==1
    assert sha256((root/list(root.glob("native_*"))[0].name/"capture_receipt.json").read_bytes()).hexdigest()==before


def test_wait_for_missing_native_score_creates_no_archive_receipt_or_lock(tmp_path):
    project,b,plan,root=setup(tmp_path,scored=False)
    waiting=capture_first_native_topk(plan,root,clock=NOW)
    assert waiting["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
    result=run_archive(project,plan,root,waiting)
    assert result["status"]=="WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN"
    assert result["messages_sent"]==result["external_api_calls"]==0
    assert not (project/"output"/"native_first_private_archives").exists()
    assert not (project/"output"/"native_first_archive_receipts").exists()


@pytest.mark.parametrize("loss",["archive","receipt","guard","both_receipts","lock"])
def test_loss_of_original_zip_or_separate_sha_receipt_never_resets_anchor(tmp_path,loss):
    project,b,plan,root=setup(tmp_path)
    first=capture_first_native_topk(plan,root,clock=NOW)
    run_archive(project,plan,root,first)
    archives=project/"output"/"native_first_private_archives"
    receipts=project/"output"/"native_first_archive_receipts"
    archive=next(archives.glob("native_*.zip"))
    receipt=next(receipts.glob("native_*_receipt.json"))
    guard=next(receipts.glob("native_*_guard.json"))
    lock=next(receipts.glob(".native_*.lock"))
    if loss=="archive": archive.unlink()
    if loss=="receipt": receipt.unlink()
    if loss=="guard": guard.unlink()
    if loss=="both_receipts":
        receipt.unlink();guard.unlink()
    if loss=="lock": lock.unlink()
    with pytest.raises((ValueError,RuntimeError),match="partial|missing|lock|receipt|sealed|original"):
        run_archive(project,plan,root,first,clock=NOW+timedelta(minutes=1))
    assert first["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"


def test_archive_content_corruption_or_guard_rewrite_fail_closed(tmp_path):
    project,b,plan,root=setup(tmp_path)
    first=capture_first_native_topk(plan,root,clock=NOW)
    run_archive(project,plan,root,first)
    archive=next((project/"output"/"native_first_private_archives").glob("native_*.zip"))
    receipt=next((project/"output"/"native_first_archive_receipts").glob("*_receipt.json"))
    before=receipt.read_bytes()
    archive.write_bytes(archive.read_bytes()+b"tamper")
    with pytest.raises(ValueError,match="SHA"):
        run_archive(project,plan,root,first,clock=NOW+timedelta(minutes=1))
    assert receipt.read_bytes()==before
    # Even if replaced archive is restored, a rewritten local first SHA seal fails.
    archive.write_bytes(archive.read_bytes()[:-6])
    receipt.write_bytes(receipt.read_bytes()+b" ")
    with pytest.raises(ValueError,match="receipt|canonical|rewritten"):
        run_archive(project,plan,root,first,clock=NOW+timedelta(minutes=2))


def test_different_capture_plan_cannot_be_backfilled_into_existing_archive_slot(tmp_path):
    project,b,plan,root=setup(tmp_path)
    first=capture_first_native_topk(plan,root,clock=NOW)
    run_archive(project,plan,root,first)
    obj=json.loads(plan.read_text())
    obj["cohort_id"]="RENAMED_RETROSPECTIVE_FIRST"
    plan.write_text(json.dumps(obj,sort_keys=True))
    with pytest.raises(ValueError,match="receipt|plan|first|capture"):
        run_archive(project,plan,root,first,clock=NOW+timedelta(minutes=2))


def test_unsafe_or_skipped_status_never_creates_private_archive(tmp_path):
    project,b,plan,root=setup(tmp_path)
    for fake in (
        {"status":"SKIPPED_CONCURRENT_NATIVE_CAPTURE","messages_sent":0,
         "external_api_calls":0,"official_leader_promotions":0,
         "real_future_leader_accuracy_certified":False},
        {"status":"FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED",
         "messages_sent":1,"external_api_calls":0,"official_leader_promotions":0,
         "real_future_leader_accuracy_certified":False},
    ):
        with pytest.raises(ValueError,match="unsafe|unverified|original|capture"):
            run_archive(project,plan,root,fake)
    assert not (project/"output"/"native_first_archive_receipts").exists()


def test_no_automatic_reanchor_after_interrupted_archive_publish(tmp_path):
    project,b,plan,root=setup(tmp_path)
    first=capture_first_native_topk(plan,root,clock=NOW)
    # A stranded final ZIP without a first witness is not a valid receipt.
    dest=project/"output"/"native_first_private_archives"
    dest.mkdir()
    plan_obj=json.loads(plan.read_text())
    from eraleader.native_evidence_archive import _slot
    (dest/("native_"+_slot(plan_obj)+".zip")).write_bytes(b"incomplete")
    with pytest.raises(ValueError,match="partial|unsealed|original|receipt"):
        run_archive(project,plan,root,first)
    assert not (project/"output"/"native_first_archive_receipts").exists()


@pytest.fixture
def scheduled_project(tmp_path,monkeypatch):
    from eraleader import local_schedule,native_first_capture,scheduled_native_archive
    project,b,plan,root=setup(tmp_path)
    local_capture=native_first_capture.capture_first_native_topk
    local_archive=scheduled_native_archive.archive_captured_native_plan
    seen=[]
    def job(**kwargs):
        seen.append("job")
        return {"status":"LOCAL_RESEARCH_SYNTHETIC_ONLY",
                "messages_sent":0,"external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",job)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:local_capture(p,r,clock=NOW))
    monkeypatch.setattr(scheduled_native_archive,"archive_captured_native_plan",
                        lambda proj,p,r,result:local_archive(
                            proj,p,r,result,clock=NOW))
    return project,plan,root,seen


def test_scheduler_flag_opt_in_captures_archives_repeats_without_double_first_claim(
        scheduled_project,capsys):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    args=["--project",str(project),
          "--native-first-capture-plan",str(plan),
          "--native-first-private-archive"]
    assert main(args)==0
    first=json.loads(capsys.readouterr().out)
    archive=first["native_first_capture"]["private_original_archive"]
    assert archive["status"]=="FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED"
    assert archive["archive_created"] is True
    assert first["messages_sent"]==first["external_api_calls"]==0
    assert first["actual_future_leader_skill_certified"] is False
    assert main(args)==0
    second=json.loads(capsys.readouterr().out)
    again=second["native_first_capture"]["private_original_archive"]
    assert again["status"]=="EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED"
    assert again["archive_created"] is False
    assert again["archive_original_sha256"]==archive["archive_original_sha256"]
    assert len(list((project/"output"/"native_first_private_archives").glob("*.zip")))==1
    assert seen==["job","job"]


def test_scheduler_without_new_flag_still_captures_only_no_archive(
        scheduled_project,capsys):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    main(["--project",str(project),"--native-first-capture-plan",str(plan)])
    result=json.loads(capsys.readouterr().out)
    assert "private_original_archive" not in result["native_first_capture"]
    assert not (project/"output"/"native_first_private_archives").exists()
    assert not (project/"output"/"native_first_archive_receipts").exists()


def test_scheduler_requires_explicit_capture_plan_before_any_side_effect(
        scheduled_project,capsys):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    with pytest.raises(ValueError,match="plan"):
        main(["--project",str(project),"--native-first-private-archive"])
    assert seen==[]
    assert not root.exists()
    assert not capsys.readouterr().out


def test_scheduler_archive_failure_blocks_success_and_does_not_reissue_watch(
        scheduled_project,monkeypatch,capsys):
    from scripts.run_local_scheduled import main
    from eraleader import scheduled_native_archive
    project,plan,root,seen=scheduled_project
    def broken(*args,**kwargs):
        raise ValueError("private SHA receipt could not be sealed")
    monkeypatch.setattr(scheduled_native_archive,"archive_captured_native_plan",broken)
    with pytest.raises(ValueError,match="SHA receipt could not be sealed"):
        main(["--project",str(project),"--native-first-capture-plan",str(plan),
              "--native-first-private-archive"])
    assert (root).is_dir()
    assert not capsys.readouterr().out


def test_scheduler_keeps_primary_stale_error_but_attempts_private_archive(
        scheduled_project,monkeypatch):
    from scripts.run_local_scheduled import main
    from eraleader import local_schedule
    project,plan,root,seen=scheduled_project
    monkeypatch.setattr(local_schedule,"run_scheduled",
                        lambda **_: (_ for _ in ()).throw(ValueError(
                            "original stale-cache hard stop")))
    with pytest.raises(ValueError,match="original stale-cache hard stop"):
        main(["--project",str(project),"--native-first-capture-plan",str(plan),
              "--native-first-private-archive"])
    assert len(list((project/"output"/"native_first_private_archives").glob("*.zip")))==1


def test_generate_plist_disallows_auto_private_source_archive(
        scheduled_project,tmp_path):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    path=tmp_path/"dont_install.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(["--project",str(project),"--generate-plist",str(path),
              "--native-first-capture-plan",str(plan),
              "--native-first-private-archive"])
    assert not path.exists() and not root.exists()


def test_scheduler_same_model_other_plan_label_rejected_before_first_capture(
        scheduled_project,tmp_path):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    duplicate=tmp_path/"other_name_plan.json"
    doc=json.loads(plan.read_text())
    doc["cohort_id"]="AFTER_WINNER_CHOSEN"
    duplicate.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="Duplicate.*model|same.*model"):
        main(["--project",str(project),
              "--native-first-capture-plan",str(plan),
              "--native-first-capture-plan",str(duplicate),
              "--native-first-private-archive"])
    assert not root.exists()
    assert not (project/"output"/"native_first_archive_receipts").exists()


def test_scheduler_two_markets_archive_both_originals_and_verify_on_repeat(
        tmp_path,monkeypatch,capsys):
    from eraleader import local_schedule,native_first_capture,scheduled_native_archive
    from scripts.run_local_scheduled import main
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    kr=prepare(tmp_path/"KR",market="KR")
    us=prepare(tmp_path/"US",market="US")
    local_capture=native_first_capture.capture_first_native_topk
    local_archive=scheduled_native_archive.archive_captured_native_plan
    monkeypatch.setattr(local_schedule,"run_scheduled",lambda **kw:{
        "status":"LOCAL_TWO_MARKET_OFFLINE_SYNTHETIC",
        "messages_sent":0,"external_api_calls":0,
    })
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:local_capture(p,r,clock=NOW))
    monkeypatch.setattr(scheduled_native_archive,"archive_captured_native_plan",
                        lambda proj,p,r,result:local_archive(
                            proj,p,r,result,clock=NOW))
    args=["--project",str(project),
          "--native-first-capture-plan",str(kr[2]),
          "--native-first-capture-plan",str(us[2]),
          "--native-first-private-archive"]
    assert main(args)==0
    output=json.loads(capsys.readouterr().out)
    reports=[x["private_original_archive"]
             for x in output["native_first_capture"]["cohorts"]]
    assert len(reports)==2
    assert all(r["status"]=="FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED"
               for r in reports)
    assert set(r["market"] for r in reports)=={"KR","US"}
    archives=list((project/"output"/"native_first_private_archives").glob("*.zip"))
    assert len(archives)==2
    assert len(set(x["archive_original_sha256"] for x in reports))==2
    assert main(args)==0
    again=json.loads(capsys.readouterr().out)
    assert all(x["private_original_archive"]["status"]==
               "EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED"
               for x in again["native_first_capture"]["cohorts"])
    assert len(list((project/"output"/"native_first_private_archives").glob("*.zip")))==2


def test_scheduler_missing_native_score_waits_without_ever_creating_archive(tmp_path,monkeypatch,capsys):
    from eraleader import local_schedule,native_first_capture
    from scripts.run_local_scheduled import main
    project,b,plan,root=setup(tmp_path,scored=False)
    local_capture=native_first_capture.capture_first_native_topk
    monkeypatch.setattr(local_schedule,"run_scheduled",lambda **kw:{
        "status":"LOCAL_SYNTHETIC","messages_sent":0,"external_api_calls":0,
    })
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:local_capture(p,r,clock=NOW))
    assert main(["--project",str(project),
                 "--native-first-capture-plan",str(plan),
                 "--native-first-private-archive"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["native_first_capture"]["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
    assert report["native_first_capture"]["private_original_archive"]["status"]==(
        "WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN")
    assert not root.exists()
    assert not (project/"output"/"native_first_archive_receipts").exists()


def test_scheduler_original_archive_missing_guard_stops_without_false_success(
        scheduled_project,capsys):
    from scripts.run_local_scheduled import main
    project,plan,root,seen=scheduled_project
    args=["--project",str(project),"--native-first-capture-plan",str(plan),
          "--native-first-private-archive"]
    assert main(args)==0
    capsys.readouterr()
    receipt_root=project/"output"/"native_first_archive_receipts"
    guard=next(receipt_root.glob("*_guard.json"))
    guard.unlink()
    with pytest.raises(ValueError,match="partial|missing|receipt"):
        main(args)
    assert not capsys.readouterr().out


def test_scheduler_native_capture_skipped_concurrent_never_runs_archive(
        scheduled_project,monkeypatch):
    from scripts.run_local_scheduled import main
    from eraleader import native_first_capture
    project,plan,root,seen=scheduled_project
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda *a,**k:{
                            "status":"SKIPPED_CONCURRENT_NATIVE_CAPTURE",
                            "messages_sent":0,"external_api_calls":0,
                            "official_leader_promotions":0,
                            "real_future_leader_accuracy_certified":False,
                        })
    with pytest.raises(RuntimeError,match="Unsafe or skipped"):
        main(["--project",str(project),
              "--native-first-capture-plan",str(plan),
              "--native-first-private-archive"])
    assert not (project/"output"/"native_first_archive_receipts").exists()
