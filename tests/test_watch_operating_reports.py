"""Offline daily/weekly/monthly WATCH operating briefs. Synthetic only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.watch_operating_reports import (
    compile_watch_operating_report, write_watch_operating_reports,
    render_watch_operating_markdown,
)
from test_watch_progression import FIRST, MODEL, snapshot, observe

AT = "2026-10-08T23:50:00+09:00"
CLOCK = datetime(2026,10,11,tzinfo=timezone.utc)


def chain(tmp_path, *, last_negative=False):
    path=tmp_path/"prospective.sqlite"
    store=ProspectiveRegistry(path)
    try:
        observe(store,0,hit=True)
        observe(store,1,hit=True)
        observe(store,2,hit=False)
        observe(store,3,hit=not last_negative)
    finally: store.close()
    return path


def make(ledger,*,asof=AT,**kwargs):
    clock=kwargs.pop("clock",CLOCK)
    return compile_watch_operating_report(
        ledger,market="KR",model_version=MODEL,evaluated_at=asof,
        clock=clock,**kwargs)


def test_daily_weekly_monthly_operational_counts_use_real_registration_cutoffs(tmp_path):
    report=make(chain(tmp_path))
    assert report["official_leader_promotions"]==0
    assert report["pit_certified"] is False
    assert report["real_leader_prediction_certified"] is False
    assert report["source_ledger_rows"]==4
    assert report["eligible_historical_observations"]==4
    d=report["periods"]["daily"]
    w=report["periods"]["weekly"]
    m=report["periods"]["monthly"]
    assert d["window_start_market_day"]=="2026-10-08"
    assert d["observations"]==1
    assert d["transition_counts"]["SCREEN_REENTERED"]==1
    assert d["transition_counts"]["INITIAL_WATCH"]==0
    assert w["window_start_market_day"]=="2026-10-05"
    assert w["observations"]==4
    assert w["transition_counts"]["INITIAL_WATCH"]==1
    assert w["transition_counts"]["WATCH_PERSISTED"]==1
    assert w["transition_counts"]["SCREEN_WEAKENED"]==1
    assert w["transition_counts"]["SCREEN_REENTERED"]==1
    assert m["window_start_market_day"]=="2026-10-01"
    assert m["observations"]==4
    assert report["latest_explicit_positive_watch_ids_sample"]==["SYN-A"]
    assert report["market_universe_coverage_certified"] is False
    assert report["peer_score_rotation"]["status"]=="NOT_REQUESTED"


def test_later_future_observations_do_not_appear_in_older_asof_report(tmp_path):
    path=chain(tmp_path)
    earlier=make(path,asof="2026-10-07T23:50:00+09:00")
    assert earlier["eligible_historical_observations"]==3
    assert earlier["registered_after_cutoff_excluded"]==1
    assert earlier["periods"]["daily"]["transition_counts"]["SCREEN_WEAKENED"]==1
    assert earlier["periods"]["weekly"]["transition_counts"]["SCREEN_REENTERED"]==0
    assert earlier["latest_explicit_positive_watch_ids_sample"]==[]


def test_missing_row_does_not_generate_weakening_or_failure(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        observe(reg,0)
        observe(reg,1,security="SYN-B",hit=False)
        observe(reg,2)
    finally: reg.close()
    r=make(path)
    assert r["periods"]["weekly"]["transition_counts"]["SCREEN_WEAKENED"]==0
    assert r["periods"]["weekly"]["transition_counts"]["PRE_WATCH"]==1
    assert r["periods"]["weekly"]["transition_counts"]["WATCH_PERSISTED"]==1
    assert r["official_leader_promotions"]==0


def test_older_historical_backfill_excluded_not_a_real_first_discovery(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        historical=datetime(2024,5,1,8,tzinfo=timezone.utc)
        reg.record_integrated(snapshot(historical),clock=FIRST)
        observe(reg,1,security="SYN-A",hit=True)
    finally: reg.close()
    r=make(path)
    assert r["retrospective_backfills_excluded"]==1
    assert r["periods"]["weekly"]["transition_counts"]["INITIAL_WATCH"]==1
    assert r["periods"]["weekly"]["observations"]==1


def test_market_local_calendar_week_and_month_do_not_assume_utc_date(tmp_path):
    at=datetime(2026,11,1,0,30,tzinfo=timezone.utc)
    path=tmp_path/"us.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        reg.record_integrated(snapshot(at,market="US"),clock=at)
    finally:reg.close()
    r=compile_watch_operating_report(
        path,market="US",model_version=MODEL,
        evaluated_at="2026-10-31T23:30:00-04:00",
        clock=datetime(2026,11,1,5,tzinfo=timezone.utc))
    assert r["as_of_market_day"]=="2026-10-31"
    assert r["periods"]["monthly"]["window_start_market_day"]=="2026-10-01"
    assert r["periods"]["daily"]["observations"]==1
    assert r["periods"]["weekly"]["window_start_market_day"]=="2026-10-26"


def test_rehashing_payload_with_wrong_permanent_company_id_cannot_forge_reports(tmp_path):
    path=chain(tmp_path)
    with sqlite3.connect(path) as con:
        old=con.execute("SELECT payload FROM research_screen_observations LIMIT 1").fetchone()[0]
        bad=json.loads(old)
        bad["company"]["security_id"]="OTHER"
        encoded=json.dumps(bad,sort_keys=True,ensure_ascii=False,
                           separators=(",",":"),allow_nan=False)
        con.execute("UPDATE research_screen_observations SET payload=?,payload_hash=? WHERE payload=?",
                    (encoded,sha256(encoded.encode()).hexdigest(),old))
    with pytest.raises(ValueError,match="identity|payload"):
        make(path)


def test_missing_corrupt_original_positive_signal_fails_closed(tmp_path):
    path=chain(tmp_path)
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM prospective_signals WHERE signal_id=(SELECT min(signal_id) FROM prospective_signals)")
    with pytest.raises(ValueError,match="WATCH|signal|positive"):
        make(path)


def test_aged_only_observations_are_not_current_leader_alerts(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try: observe(reg,0,hit=True)
    finally:reg.close()
    r=make(path,asof="2026-11-10T17:00:00+09:00",
           clock=datetime(2026,11,11,tzinfo=timezone.utc))
    assert r["data_freshness_status"]=="STALE_RESEARCH_OBSERVATIONS_NOT_CURRENT"
    assert r["latest_explicit_positive_watch_ids_sample"]==["SYN-A"]
    assert r["recent_positive_watch_ids_sample"]==[]
    assert r["latest_evidence_age_market_days"]>7
    assert r["periods"]["daily"]["observations"]==0
    assert r["periods"]["weekly"]["observations"]==0


def test_empty_prospective_ledger_is_na_and_does_not_claim_zero_false_positives(tmp_path):
    path=tmp_path/"prospective.sqlite"
    store=ProspectiveRegistry(path)
    store.close()
    r=make(path)
    assert r["data_freshness_status"]=="NO_PROSPECTIVE_OBSERVATIONS"
    assert r["periods"]["monthly"]["observations"]==0
    assert r["future_accuracy_certified"] is False
    assert r["actual_future_precision"] is None
    assert r["official_leader_promotions"]==0
    assert "실전" in render_watch_operating_markdown(r,"daily")


def test_missing_or_symlink_watch_ledger_is_not_created(tmp_path):
    path=tmp_path/"absent.sqlite"
    with pytest.raises(ValueError,match="ledger|missing|symlink"):
        make(path)
    assert not path.exists()
    original=chain(tmp_path)
    link=tmp_path/"alias.sqlite"
    link.symlink_to(original)
    with pytest.raises(ValueError,match="symlink"):
        make(link)


def test_score_rotation_optional_source_is_never_silently_assumed(tmp_path):
    path=chain(tmp_path)
    with pytest.raises(ValueError,match="both|required"):
        make(path,score_ledger=tmp_path/"missing.sqlite")
    r=make(path)
    assert r["peer_score_rotation"]["status"]=="NOT_REQUESTED"


def test_actual_audited_score_evidence_summary_is_separate_from_watch_events(tmp_path):
    from test_peer_score_series import setup, EVALUATED
    watch,score_db,features=setup(tmp_path)
    report=make(watch,asof=EVALUATED,score_ledger=score_db,feature_root=features)
    assert report["peer_score_rotation"]["status"]=="LOCAL_RESEARCH_CORROBORATION_ONLY"
    assert report["peer_score_rotation"]["rotation_hypotheses"]==1
    assert report["peer_score_rotation"]["two_session_score_correlations"]==1
    assert report["peer_score_rotation"]["official_replacements"]==0
    assert report["peer_score_rotation"]["confidence_independently_verified"] is False


def test_report_rendering_sanitizes_security_names(tmp_path):
    path=tmp_path/"prospective.sqlite"
    obj=snapshot(FIRST,security='<img src=x onerror="alert(1)">')
    reg=ProspectiveRegistry(path)
    try:reg.record_integrated(obj,clock=FIRST)
    finally:reg.close()
    r=make(path)
    from eraleader.watch_operating_reports import render_watch_operating_html
    page=render_watch_operating_html(r,"weekly")
    assert '<img src=x' not in page
    assert "&lt;img" in page
    assert "공식 대장주 0건" in page


def test_project_cli_writes_three_markdown_html_and_one_json_without_mutating_sqlite(tmp_path,capsys):
    from eraleader.cli import main
    path=chain(tmp_path)
    old=sha256(path.read_bytes()).hexdigest()
    out=tmp_path/"derived"
    main(["report-watch-operations","--watch-ledger",str(path),
          "--market","KR","--model-version",MODEL,
          "--evaluated-at",AT,"--out",str(out)])
    output=json.loads(capsys.readouterr().out)
    assert output["official_leader_promotions"]==0
    assert output["research_report_periods"]==3
    files=sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files==sorted([
        "watch_operating_kr_research.json",
        "reports/watch_daily_kr.md","reports/watch_weekly_kr.md",
        "reports/watch_monthly_kr.md",
        "site/watch_daily_kr.html","site/watch_weekly_kr.html",
        "site/watch_monthly_kr.html"])
    assert sha256(path.read_bytes()).hexdigest()==old
    assert "watch_daily_kr.md" in json.dumps(output)
    assert "실전 발굴 성능 미검증" in (out/"reports"/"watch_monthly_kr.md").read_text()


def test_safe_local_backup_restores_derived_reports_not_prospective_sqlite(tmp_path):
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    r=make(chain(tmp_path))
    derived=tmp_path/"derived"
    write_watch_operating_reports(r,derived)
    archive=tmp_path/"derived_report.zip"
    info=create_backup(derived,archive)
    assert info["file_count"]==7
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        names=z.namelist()
        assert "prospective.sqlite" not in names
        assert all("outcome" not in name for name in names)
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    for f in derived.rglob("*"):
        if f.is_file():
            assert (restored/f.relative_to(derived)).read_bytes()==f.read_bytes()


def test_orphan_first_positive_signal_is_not_silently_erased_from_operating_history(tmp_path):
    path=chain(tmp_path)
    with sqlite3.connect(path) as con:
        con.execute("""DELETE FROM research_screen_observations
                       WHERE screen_hit=1 AND observed_as_of LIKE '2026-10-05%'""")
    with pytest.raises(ValueError,match="positive|orphan|complete"):
        make(path)


def test_state_carries_over_from_prior_week_even_when_period_has_one_screen(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    sunday=datetime(2026,10,4,8,tzinfo=timezone.utc)
    monday=datetime(2026,10,5,8,tzinfo=timezone.utc)
    try:
        reg.record_integrated(snapshot(sunday),clock=sunday)
        reg.record_integrated(snapshot(monday),clock=monday)
    finally:reg.close()
    result=make(path,asof="2026-10-05T23:30:00+09:00")
    assert result["periods"]["weekly"]["observations"]==1
    assert result["periods"]["weekly"]["transition_counts"]["WATCH_PERSISTED"]==1
    assert result["periods"]["weekly"]["transition_counts"]["INITIAL_WATCH"]==0


def test_registration_day_controls_reporting_not_past_observation_day(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    prior=FIRST
    recorded=FIRST+timedelta(days=1)
    try:
        reg.record_integrated(snapshot(prior),clock=recorded)
    finally:reg.close()
    result=make(path,asof="2026-10-06T23:30:00+09:00")
    assert result["periods"]["daily"]["observations"]==1
    assert result["periods"]["daily"]["transition_counts"]["INITIAL_WATCH"]==1
    assert result["retrospective_backfills_excluded"]==0


def test_sample_truncation_does_not_understate_transition_aggregate(tmp_path):
    result=make(chain(tmp_path),sample_limit=1)
    weekly=result["periods"]["weekly"]
    assert weekly["observations"]==4
    assert sum(weekly["transition_counts"].values())==4
    assert len(weekly["event_sample"])==1
    assert weekly["event_sample_truncated"] is True


def test_unexpected_future_labels_in_rehashed_watch_input_are_blocked(tmp_path):
    path=chain(tmp_path)
    with sqlite3.connect(path) as con:
        row=con.execute("SELECT payload,security_id,observed_as_of FROM research_screen_observations WHERE screen_hit=0 LIMIT 1").fetchone()
        old,sec,observed=row
        obj=json.loads(old)
        obj["company"]["is_future_leader"]=True
        updated=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        con.execute("""UPDATE research_screen_observations
                       SET payload=?, payload_hash=? WHERE security_id=? AND observed_as_of=?""",
                    (updated,sha256(updated.encode()).hexdigest(),sec,observed))
    with pytest.raises(ValueError,match="Future outcome label"):
        make(path)


def test_operating_dashboard_local_http_200_and_uncertified_labels(tmp_path):
    from functools import partial
    from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen
    r=make(chain(tmp_path))
    out=tmp_path/"site_derived"
    write_watch_operating_reports(r,out)
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(
        ("127.0.0.1",0),partial(Quiet,directory=str((out/"site").resolve())))
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/watch_weekly_kr.html",timeout=5) as response:
            assert response.status==200
            html=response.read().decode()
            assert "공식 대장주 0건" in html
            assert "PIT 미인증" in html
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_research_report_symlink_output_is_rejected(tmp_path):
    r=make(chain(tmp_path))
    out=tmp_path/"out"
    out.mkdir()
    raw=tmp_path/"outside.html"
    raw.write_text("sensitive untouched")
    path=out/"site"
    path.symlink_to(tmp_path)
    with pytest.raises(ValueError,match="linked|Unsafe"):
        write_watch_operating_reports(r,out)
    assert raw.read_text()=="sensitive untouched"


def test_missing_data_does_not_claim_a_false_discovery_precision_zero(tmp_path):
    path=tmp_path/"prospective.sqlite"
    p=ProspectiveRegistry(path)
    p.close()
    report=make(path)
    assert report["actual_future_precision"] is None
    assert report["peer_score_rotation"]["rotation_hypotheses"] is None
    assert report["data_freshness_status"]=="NO_PROSPECTIVE_OBSERVATIONS"
    assert report["recent_positive_watch_count"]==0
    assert report["future_accuracy_certified"] is False


def test_daily_weekly_monthly_files_share_one_source_version_run_id(tmp_path):
    r=make(chain(tmp_path))
    assert len(r["research_run_id"])==20
    assert all(c in "0123456789abcdef" for c in r["research_run_id"])
    root=tmp_path/"derived"
    write_watch_operating_reports(r,root)
    for period in ("daily","weekly","monthly"):
        md=(root/"reports"/f"watch_{period}_kr.md").read_text()
        html=(root/"site"/f"watch_{period}_kr.html").read_text()
        assert r["research_run_id"] in md
        assert r["research_run_id"] in html
    rebuilt=make(tmp_path/"prospective.sqlite")
    assert rebuilt["research_run_id"]==r["research_run_id"]
    older=make(tmp_path/"prospective.sqlite",asof="2026-10-07T23:00:00+09:00")
    assert older["research_run_id"]!=r["research_run_id"]
