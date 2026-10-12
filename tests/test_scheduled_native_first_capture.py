"""5_5 optional scheduled native first-WATCH Top-K capture (no live alerts)."""
from __future__ import annotations

import json

import pytest
from eraleader import local_schedule,native_first_capture
from test_scheduled_failure_outbox_bridge import load_script

ALLOWED={
    "status":"FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED",
    "messages_sent":0,"external_api_calls":0,"official_leader_promotions":0,
    "real_future_leader_accuracy_certified":False,
}


@pytest.fixture
def setup(tmp_path,monkeypatch):
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    plan=tmp_path/"predeclared.json";plan.write_text("{}")
    seen=[]
    def schedule(**kw):
        seen.append(("scheduled",kw))
        return {"status":"SKIPPED_STALE_CACHE","messages_sent":0,
                "external_api_calls":0}
    def capture(plan_file,root):
        seen.append(("first_capture",(plan_file,root)))
        return dict(ALLOWED)
    monkeypatch.setattr(local_schedule,"run_scheduled",schedule)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",capture)
    return project,plan,seen


def test_default_scheduler_remains_unmodified_and_no_native_evidence_read(setup,capsys):
    project,plan,seen=setup
    assert load_script().main(["--project",str(project)])==0
    payload=json.loads(capsys.readouterr().out)
    assert payload["status"]=="SKIPPED_STALE_CACHE"
    assert [k for k,_ in seen]==["scheduled"]
    assert "native_first_capture" not in payload


@pytest.mark.parametrize("research_status",[
    "FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED",
    "ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY",
    "WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE",
])
def test_explicit_post_schedule_native_capture_validated_without_delivery(
        setup,monkeypatch,capsys,research_status):
    project,plan,seen=setup
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:{**ALLOWED,"status":research_status})
    assert load_script().main(["--project",str(project),
                               "--native-first-capture-plan",str(plan)])==0
    result=json.loads(capsys.readouterr().out)
    assert result["native_first_capture"]["status"]==research_status
    assert result["messages_sent"]==0
    assert result["official_leaders_confirmed"]==0
    assert result["actual_future_leader_skill_certified"] is False
    assert [k for k,_ in seen]==["scheduled"]


def test_scheduler_calls_exact_planned_first_native_out_dir(setup,capsys):
    project,plan,seen=setup
    load_script().main(["--project",str(project),
                        "--native-first-capture-plan",str(plan)])
    capsys.readouterr()
    assert [kind for kind,_ in seen]==["scheduled","first_capture"]
    assert seen[-1][1]==(plan,project/"output"/"native_first_captures")


@pytest.mark.parametrize("fake",[
    {"status":"SKIPPED_CONCURRENT_NATIVE_CAPTURE"},
    {**ALLOWED,"messages_sent":1},
    {**ALLOWED,"external_api_calls":1},
    {**ALLOWED,"official_leader_promotions":1},
    {**ALLOWED,"real_future_leader_accuracy_certified":True},
    {**ALLOWED,"status":"FAKE_OFFICIAL_LEADER"},
])
def test_scheduler_rejects_fake_capture_success_and_does_not_print_success(
        setup,monkeypatch,capsys,fake):
    project,plan,seen=setup
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:fake)
    with pytest.raises(RuntimeError,match="Unsafe or skipped"):
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan)])
    assert not capsys.readouterr().out


def test_stale_primary_schedule_failure_kept_even_if_capture_runs(setup,monkeypatch):
    project,plan,seen=setup
    def bad(**kw):
        seen.append(("bad_schedule",kw))
        raise ValueError("origin-stale-research")
    monkeypatch.setattr(local_schedule,"run_scheduled",bad)
    with pytest.raises(ValueError,match="origin-stale-research"):
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan)])
    assert [kind for kind,_ in seen]==["bad_schedule","first_capture"]


def test_capture_error_does_not_overwrite_original_scheduler_error(
        setup,monkeypatch):
    project,plan,seen=setup
    def bad(**kw):raise ValueError("original-research-failure")
    def bad_capture(*a,**kw):raise ValueError("corrupt-first-score")
    monkeypatch.setattr(local_schedule,"run_scheduled",bad)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        bad_capture)
    with pytest.raises(ValueError,match="original-research-failure") as exc:
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan)])
    assert "corrupt-first-score" in " ".join(getattr(exc.value,"__notes__",[]))


def test_capture_failure_after_scheduler_success_never_claims_scheduled_success(
        setup,monkeypatch,capsys):
    project,plan,seen=setup
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda *a,**kw:(_ for _ in ()).throw(ValueError("tampered-origin")))
    with pytest.raises(ValueError,match="tampered-origin"):
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan)])
    assert not capsys.readouterr().out


def test_generate_plist_refuses_auto_capture_and_installs_nothing(setup,tmp_path):
    project,plan,seen=setup
    plist=tmp_path/"agent.plist"
    with pytest.raises(ValueError,match="not supported"):
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan),
                            "--generate-plist",str(plist)])
    assert not plist.exists()
    assert seen==[]


def test_concurrent_scheduler_skips_capture(setup,monkeypatch):
    project,plan,seen=setup
    monkeypatch.setattr(local_schedule,"run_scheduled",
                        lambda **kw:{"status":"SKIPPED_ALREADY_RUNNING",
                                     "messages_sent":0,"external_api_calls":0})
    with pytest.raises(RuntimeError,match="concurrent"):
        load_script().main(["--project",str(project),
                            "--native-first-capture-plan",str(plan)])
    assert seen==[]


def test_scheduler_two_separate_kr_us_plans_in_single_verified_run(
        setup,monkeypatch,capsys):
    project,plan,seen=setup
    second=plan.with_name("us_plan.json");second.write_text("{}")
    assert load_script().main([
        "--project",str(project),
        "--native-first-capture-plan",str(plan),
        "--native-first-capture-plan",str(second),
    ])==0
    report=json.loads(capsys.readouterr().out)
    assert [k for k,_ in seen]==["scheduled","first_capture","first_capture"]
    assert seen[1][1][0]==plan and seen[2][1][0]==second
    assert report["native_first_capture"]["plan_count"]==2
    assert len(report["native_first_capture"]["cohorts"])==2
    assert report["native_first_capture"]["status"]=="LOCAL_MULTI_NATIVE_CAPTURE_NOT_CERTIFIED"
    assert report["native_first_capture"]["official_leader_promotions"]==0
    assert report["native_first_capture"]["real_future_leader_accuracy_certified"] is False
    assert report["external_api_calls"]==0


def test_duplicate_scheduled_capture_plan_refused_without_fake_success(
        setup,capsys):
    project,plan,seen=setup
    with pytest.raises(ValueError,match="Duplicate first-native capture plan"):
        load_script().main([
            "--project",str(project),
            "--native-first-capture-plan",str(plan),
            "--native-first-capture-plan",str(plan),
        ])
    assert not capsys.readouterr().out
    assert [k for k,_ in seen]==["scheduled","first_capture"]


def test_second_market_capture_error_cannot_claim_first_and_second_both_complete(
        setup,monkeypatch,capsys):
    project,plan,seen=setup
    second=plan.with_name("bad_other_market.json");second.write_text("{}")
    def capture(original,root):
        seen.append(("first_capture",original))
        if original==second:
            raise ValueError("second-market-source-missing")
        return dict(ALLOWED)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",capture)
    with pytest.raises(ValueError,match="second-market-source-missing"):
        load_script().main([
            "--project",str(project),
            "--native-first-capture-plan",str(plan),
            "--native-first-capture-plan",str(second),
        ])
    assert not capsys.readouterr().out
    assert [k for k,_ in seen]==["scheduled","first_capture","first_capture"]
