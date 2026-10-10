"""Reject stale fiscal/sector evidence before future WATCH registration.

Fixture and observed times are synthetic; this is not a stock-alpha test.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from eraleader.offline_pit import OfflineLedger
from eraleader.offline_features import financial_snapshot, MAX_RESEARCH_FISCAL_AGE_DAYS
from eraleader.research import integrated_snapshot
from eraleader.prospective import ProspectiveRegistry
from eraleader.watch_progression import audit_watch_progression

FIXTURE=Path(__file__).parent/"fixtures"/"offline_synthetic.json"


def snapshot(tmp_path, when):
    ledger=OfflineLedger(tmp_path/"offline.sqlite")
    try:
        ledger.import_file(FIXTURE)
        return ledger.snapshot(when,market="KR")
    finally: ledger.close()


def company(result, sid="SYN-A"):
    return next(row for row in result["companies"] if row["security_id"]==sid)


def test_recent_fundamentals_and_sector_can_still_form_research_screen(tmp_path):
    research=financial_snapshot(snapshot(tmp_path,"2024-09-01T17:00:00+09:00"))
    row=company(research)
    assert row["screen_evaluated"] is True
    assert row["screen_hit_heuristic"] is True
    assert row["financial_period_age_days"]["revenue"] == 63
    assert row["financial_period_age_days"]["industry_revenue"] == 63
    assert research["research_screen_count"]==1
    assert research["research_screens_deferred"]==0
    assert research["max_research_fiscal_age_days"]==450


def test_stale_2024_statements_cannot_issue_2026_growth_hit(tmp_path):
    asof="2026-10-10T17:00:00+09:00"
    offline=snapshot(tmp_path,asof)
    research=financial_snapshot(offline)
    row=company(research)
    assert row["revenue_yoy"] > 0.20  # descriptive historical data preserved, including known later revisions
    assert row["screen_hit_heuristic"] is False
    assert row["screen_evaluated"] is False
    assert "STALE_REVENUE_PERIOD" in row["quality_flags"]
    assert "STALE_INDUSTRY_REVENUE_PERIOD" in row["quality_flags"]
    assert research["research_screen_count"]==0
    joined=integrated_snapshot(offline,None,asof)
    out=next(x for x in joined["company_rows"] if x["security_id"]=="SYN-A")
    assert out["research_growth_screen_hit"] is False
    assert out["research_screen_evaluated"] is False
    assert joined["research_screen_deferred_count"]>=1
    assert joined["confirmed_leaders"]==0


def test_fiscal_freshness_window_boundary(tmp_path):
    # Latest fiscal observation in fixture: 2024-06-30.
    reference=date(2024,6,30)
    for age in (MAX_RESEARCH_FISCAL_AGE_DAYS,MAX_RESEARCH_FISCAL_AGE_DAYS+1):
        day=reference+timedelta(days=age)
        report=financial_snapshot(snapshot(tmp_path,day.isoformat()+"T17:00:00+09:00"))
        row=company(report)
        assert row["financial_period_age_days"]["revenue"]==age
        assert row["screen_evaluated"] is (age <= MAX_RESEARCH_FISCAL_AGE_DAYS)
        assert row["screen_hit_heuristic"] is (age <= MAX_RESEARCH_FISCAL_AGE_DAYS)


def test_an_missing_or_stale_factor_is_not_an_explicit_negative(tmp_path):
    fresh="2024-09-01T17:00:00+09:00"
    stale="2026-10-10T17:00:00+09:00"
    fresh_result=integrated_snapshot(snapshot(tmp_path,fresh),None,fresh)
    stale_result=integrated_snapshot(snapshot(tmp_path,stale),None,stale)
    reg=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        registered=reg.record_integrated(
            fresh_result,clock=datetime(2026,10,10,8,tzinfo=timezone.utc))
        assert registered["screen_hits"]==1
        skipped=reg.record_integrated(
            stale_result,clock=datetime(2026,10,10,9,tzinfo=timezone.utc))
        assert skipped["screen_hits"]==0
        assert skipped["new_research_observations"]==0
        assert reg.first_signals("KR")["total_recorded_observations"]==1
    finally:reg.close()
    trace=audit_watch_progression(tmp_path/"prospective.sqlite",
         market="KR",model_version=fresh_result["version"])
    assert trace["transition_counts"]["SCREEN_WEAKENED"]==0
    assert trace["excluded_retrospective_observations"]==1
    assert trace["official_state_promotions"]==0


def test_deferred_positive_or_malformed_flag_rejected(tmp_path):
    at="2024-09-01T17:00:00+09:00"
    src=integrated_snapshot(snapshot(tmp_path,at),None,at)
    reg=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        row=next(x for x in src["company_rows"] if x["security_id"]=="SYN-A")
        row["research_screen_evaluated"]=False
        with pytest.raises(ValueError,match="Deferred screen"):
            reg.record_integrated(src,clock=datetime(2026,10,10,tzinfo=timezone.utc))
        assert reg.first_signals("KR")["total_recorded_observations"]==0
        row["research_screen_evaluated"]="no"
        with pytest.raises(ValueError,match="must be boolean"):
            reg.record_integrated(src,clock=datetime(2026,10,10,tzinfo=timezone.utc))
    finally:reg.close()


def test_future_fiscal_period_fails_even_before_screen(tmp_path):
    data=snapshot(tmp_path,"2024-09-01T17:00:00+09:00")
    data["as_of"]="2023-03-01T08:00:00+00:00"
    with pytest.raises(ValueError,match="Future fiscal period"):
        financial_snapshot(data)


def test_misaligned_profit_quarter_does_not_become_current_growth_signal(tmp_path):
    offline=snapshot(tmp_path,"2024-09-01T17:00:00+09:00")
    profit=[row for row in offline["fundamentals"] if
            row["security_id"]=="SYN-A" and row["metric"]=="operating_income"]
    assert profit
    old_unit=profit[0]["unit"]
    offline["fundamentals"]=[row for row in offline["fundamentals"] if
             not (row["security_id"]=="SYN-A" and row["metric"]=="operating_income")]
    # Both profit numbers support a nominal +100% YoY, but the profit
    # quarter (March) differs from the latest revenue quarter (June).
    for period,value in (("2023-03-31",10),("2024-03-31",20)):
        offline["fundamentals"].append({
            **profit[0],"period_end":period,"value":value,
            "unit":old_unit})
    report=financial_snapshot(offline)
    row=company(report)
    assert row["revenue_yoy"] > 0.20
    assert row["operating_income_yoy"]==1.0
    assert row["fundamental_periods_aligned"] is False
    assert row["screen_evaluated"] is False
    assert row["screen_hit_heuristic"] is False
    assert "FUNDAMENTAL_REPORT_PERIOD_MISMATCH" in row["quality_flags"]


def test_full_cli_never_registers_old_statements_as_current_watch(tmp_path,capsys):
    import json
    from eraleader.cli import main
    main(["offline-import","--file",str(FIXTURE),"--out",str(tmp_path)])
    capsys.readouterr()
    recent_clock="2026-10-10T17:00:00+09:00"
    main(["offline-features","--market","KR","--as-of",recent_clock,
          "--out",str(tmp_path)])
    feature=json.loads(capsys.readouterr().out)
    assert feature["heuristic_screen_hits"]==0
    main(["offline-integrated","--market","KR","--as-of",recent_clock,
          "--out",str(tmp_path)])
    combined=json.loads(capsys.readouterr().out)
    assert combined["growth_screen_hits"]==0
    assert combined["new_prospective_research_signals"]==0
    assert combined["official_leaders"]==0
    ledger=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        assert ledger.first_signals("KR")["total_recorded_observations"]==0
    finally: ledger.close()
    path=Path(combined["path"])
    report=json.loads(path.read_text())
    assert report["research_screen_deferred_count"]>=1
    assert any("STALE_REVENUE_PERIOD" in row["quality_flags"]
               for row in report["company_rows"])


def test_stale_fiscal_warning_surfaces_in_local_research_web(tmp_path):
    from eraleader.delivery import render_integrated_dashboard
    asof="2026-10-10T17:00:00+09:00"
    joined=integrated_snapshot(snapshot(tmp_path,asof),None,asof)
    html=render_integrated_dashboard(joined)
    assert "근거 부족으로 스크리닝 보류" in html
    assert "STALE_REVENUE_PERIOD" in html
    assert "STALE_INDUSTRY_REVENUE_PERIOD" in html
    assert "0 — 검증 보류" in html


def test_cli_returns_deferred_count_for_stale_source(tmp_path,capsys):
    import json
    from eraleader.cli import main
    main(["offline-import","--file",str(FIXTURE),"--out",str(tmp_path)])
    capsys.readouterr()
    at="2026-10-10T17:00:00+09:00"
    main(["offline-features","--market","KR","--as-of",at,"--out",str(tmp_path)])
    feature=json.loads(capsys.readouterr().out)
    assert feature["heuristic_screen_hits"]==0
    assert feature["deferred_research_screens"]>=1
    main(["offline-integrated","--market","KR","--as-of",at,"--out",str(tmp_path)])
    joined=json.loads(capsys.readouterr().out)
    assert joined["growth_screen_hits"]==0
    assert joined["deferred_research_screens"]>=1
    assert joined["pit_certified"] is False
