from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.discovery_metrics import evaluate_early_discovery
from eraleader.cli import main

WHEN = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)

def run(market="KR", asof="2024-09-01T17:00:00+09:00", sec="SYN-A"):
    return {"market": market, "as_of": asof,
            "version": "era-offline-join-0.1", "run_id": "synthetic-001",
            "pit_certified": False, "offline_provenance": ["synthetic_fixture"],
            "company_rows": [
                {"security_id": sec, "market": market, "as_of": asof,
                 "state": "WATCH", "full_score": None,
                 "verified_future_leader_candidate": False,
                 "research_growth_screen_hit": True,
                 "revenue_yoy": 0.6}
            ]}

def test_prospective_research_signal_registration_idempotent_and_immutable(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        assert ledger.record_integrated(run(),clock=WHEN)["new_records"]==1
        again=ledger.record_integrated(run(),clock=datetime(2026,10,11,tzinfo=timezone.utc))
        assert again["new_records"]==0 and again["duplicates"]==1
        export=ledger.first_signals("KR")
        assert export["total_recorded_observations"]==1
        row=export["first_registration_signals"][0]
        assert row["first_seen"]=="2024-09-01"
        assert row["recorded_at"]=="2026-10-10"
        assert row["historical_backfill"] is True
        assert row["pit_certified"] is False
        assert export["official_leader_signals"]==0
    finally:ledger.close()

def test_replayed_backdated_signal_is_not_credited_as_early_discovery(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        ledger.record_integrated(run(),clock=WHEN)
        exported=ledger.first_signals("KR")["first_registration_signals"]
    finally:ledger.close()
    outcomes=[{"security_id":"SYN-A","is_future_leader":True,
               "leader_start_at":"2025-03-01","mature_on":"2025-09-01",
               "outcome_available_at":"2025-09-02"}]
    result=evaluate_early_discovery(exported,outcomes,
                                    evaluated_at="2026-10-10",horizon_days=180)
    assert result["true_early_discoveries"]==0
    assert result["late_or_post_onset"]==1
    assert result["retrospective_unregistered_signals"]==0

def test_later_nonidentical_input_must_not_replace_registered_record(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        ledger.record_integrated(run(),clock=WHEN)
        new=run()
        new["company_rows"][0]["revenue_yoy"]=0.95
        with pytest.raises(ValueError,match="mutation"):
            ledger.record_integrated(new,clock=WHEN)
        assert ledger.first_signals("KR")["total_recorded_observations"]==1
    finally:ledger.close()

def test_multi_signal_conflict_rolls_back_entire_batch(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        ledger.record_integrated(run(),clock=WHEN)
        candidate=run()
        candidate["company_rows"][0]["revenue_yoy"]=9
        second=deepcopy(candidate["company_rows"][0])
        second["security_id"]="SYN-NEW"
        candidate["company_rows"]=[second,candidate["company_rows"][0]]
        with pytest.raises(ValueError,match="mutation"):
            ledger.record_integrated(candidate,clock=WHEN)
        assert ledger.first_signals("KR")["total_recorded_observations"]==1
    finally:ledger.close()

def test_future_and_naive_timestamps_are_forbidden(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        future=run(asof="2027-01-01T17:00:00+09:00")
        with pytest.raises(ValueError,match="future"):
            ledger.record_integrated(future,clock=WHEN)
        with pytest.raises(ValueError,match="timezone"):
            ledger.record_integrated(run(),clock=datetime(2026,10,10))
        missing_zone=run(asof="2024-09-01T17:00:00")
        with pytest.raises(ValueError,match="Timezone"):
            ledger.record_integrated(missing_zone,clock=WHEN)
    finally:ledger.close()

@pytest.mark.parametrize("alter", [
    lambda x: x.update(pit_certified=True),
    lambda x: x["company_rows"][0].update(state="CONFIRMED"),
    lambda x: x["company_rows"][0].update(full_score=100),
    lambda x: x["company_rows"][0].update(verified_future_leader_candidate=True),
])
def test_unverified_research_cannot_forge_certification(tmp_path,alter):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        report=run()
        alter(report)
        with pytest.raises(ValueError,match="Research registry|must remain WATCH"):
            ledger.record_integrated(report,clock=WHEN)
        assert ledger.first_signals("KR")["distinct_companies"]==0
    finally:ledger.close()

def test_no_growth_hit_does_not_create_signal(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        report=run()
        report["company_rows"][0]["research_growth_screen_hit"]=False
        assert ledger.record_integrated(report,clock=WHEN)["screen_hits"]==0
        assert ledger.first_signals("KR")["distinct_companies"]==0
    finally:ledger.close()

def test_market_timezone_daily_registration_boundary(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"x.sqlite")
    try:
        # 2026-10-10 00:30 UTC is October 9 in US/New York.
        clock=datetime(2026,10,10,0,30,tzinfo=timezone.utc)
        ledger.record_integrated(run(market="US",
                                    asof="2024-09-01T16:00:00-04:00"),clock=clock)
        ledger.record_integrated(run(market="KR"),clock=clock)
        assert ledger.first_signals("US")["first_registration_signals"][0]["recorded_at"]=="2026-10-09"
        assert ledger.first_signals("KR")["first_registration_signals"][0]["recorded_at"]=="2026-10-10"
    finally:ledger.close()

def test_cli_integrated_records_actual_time_and_exports(tmp_path,capsys):
    fixture=Path(__file__).parent/"fixtures"/"offline_synthetic.json"
    main(["offline-import","--file",str(fixture),"--out",str(tmp_path)])
    capsys.readouterr()
    argv=["offline-integrated","--market","KR",
          "--as-of","2024-09-01T17:00:00+09:00","--out",str(tmp_path)]
    main(argv)
    first=json.loads(capsys.readouterr().out)
    assert first["new_prospective_research_signals"]==1
    assert first["official_leaders"]==0
    main(argv)
    second=json.loads(capsys.readouterr().out)
    assert second["new_prospective_research_signals"]==0
    main(["prospective-signals","--market","KR","--out",str(tmp_path)])
    summary=json.loads(capsys.readouterr().out)
    assert summary["first_registration_signals"]==1
    exported=json.loads((tmp_path/"prospective_kr_research.json").read_text())
    first=exported["first_registration_signals"][0]
    assert first["first_seen"]=="2024-09-01"
    assert first["recorded_at"]!="2024-09-01"
    assert first["historical_backfill"] is True
    assert exported["certified_performance"] is False

def test_prospective_web_escapes_identity_and_never_claims_official_leaders(tmp_path):
    from eraleader.delivery import render_prospective_dashboard,write_prospective_dashboard
    report={"market":"KR","status":"PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED",
            "distinct_companies":1,"total_recorded_observations":1,
            "official_leader_signals":0,"certified_performance":False,
            "first_registration_signals":[{
                "security_id":"<script>alert(123)</script>",
                "first_seen":"2024-09-01","recorded_at":"2026-10-10",
                "historical_backfill":True,"signal_kind":"UNVERIFIED_GROWTH_SCREEN",
                "status":"PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED",
                "pit_certified":False
            }]}
    html=render_prospective_dashboard(report)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "2024-09-01" in html and "2026-10-10" in html
    assert "확정 대장주 0건" in html and "N/A — 검증 보류" in html
    path=write_prospective_dashboard(report,tmp_path/"site")
    assert path.is_file() and path.name=="prospective_kr.html"
    tampered=deepcopy(report)
    tampered["official_leader_signals"]=1
    with pytest.raises(ValueError):
        render_prospective_dashboard(tampered)
    tampered=deepcopy(report)
    tampered["first_registration_signals"][0]["pit_certified"]=True
    with pytest.raises(ValueError):
        render_prospective_dashboard(tampered)
