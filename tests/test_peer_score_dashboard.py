"""Research-only peer-score rotation dashboard and derived-only release tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from threading import Thread
import json
import urllib.request

import pytest

from eraleader.delivery import (
    render_peer_score_rotation_dashboard,
    write_peer_score_rotation_dashboard,
)
from eraleader.peer_score_series import audit_peer_score_advantage
from eraleader.cli import main
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_peer_score_series import setup, compare, MODEL, EVALUATED, NOW


def report(tmp_path, *, second_advantage=72):
    return compare(setup(tmp_path,second_advantage=second_advantage))


def test_html_shows_two_observed_market_dates_and_actual_local_score_differences(tmp_path):
    r=report(tmp_path)
    page=render_peer_score_rotation_dashboard(r)
    assert "점수 기반 교체 후보" in page
    assert "INC" in page and "NEW" in page and "SEMICON" in page
    assert "2026-10-03" in page and "2026-10-04" in page
    assert "+25" in page and "+34" in page
    assert "확정 대장주 0건" in page
    assert "연구용" in page
    assert "PIT 미인증" in page
    assert r["hypothesis_sample"][0]["last_two_paired_score_event_hashes"][0]["incumbent_event_sha256"][:12] in page
    assert "revenue_yoy" not in page
    assert "feature_source" not in page


def test_insufficient_recent_scores_shown_as_unverified_not_replacement(tmp_path):
    r=report(tmp_path,second_advantage=40)
    page=render_peer_score_rotation_dashboard(r)
    assert r["locally_two_session_score_correlated"]==0
    assert "점수 근거 미충족" in page
    assert "RECENT_TWO_PEER_SCORE_ADVANTAGES_INSUFFICIENT" in page
    assert "공식 교체 0건" in page


def test_zero_real_prospective_data_renders_explicit_na_not_predicted_failures(tmp_path):
    b=setup(tmp_path)
    r=audit_peer_score_advantage(
        b[0],b[1],b[2],market="US",model_version=MODEL,
        evaluated_at=EVALUATED,clock=NOW)
    assert r["rotation_hypothesis_count"]==0
    page=render_peer_score_rotation_dashboard(r)
    assert "관측된 교체 가설 없음" in page
    assert "미검증" in page
    assert "확정 대장주 0건" in page


@pytest.mark.parametrize("field,value", [
    ("market", "GB"), ("status", "OFFICIALLY_VERIFIED"),
    ("official_leader_replacements",1),
    ("rank_scores_independently_authenticated",True),
    ("issuer_industry_pit_certified",True),
    ("real_leader_replacement_certified",True),
])
def test_false_certification_and_wrong_market_cannot_render(tmp_path,field,value):
    r=report(tmp_path)
    r[field]=value
    with pytest.raises(ValueError,match="research|certif|official|market"):
        render_peer_score_rotation_dashboard(r)


@pytest.mark.parametrize("field,value", [
    ("locally_two_session_score_correlated",2),
    ("uncorroborated_rotation_hypotheses",1),
    ("rotation_hypothesis_count",0),
    ("score_history_events_available_by_cutoff",999),
])
def test_inconsistent_aggregate_counts_are_rejected(tmp_path,field,value):
    r=report(tmp_path)
    r[field]=value
    with pytest.raises(ValueError,match="count|inconsistent|score"):
        render_peer_score_rotation_dashboard(r)


def test_html_escape_peers_industry_model_and_issue_strings(tmp_path):
    r=report(tmp_path,second_advantage=40)
    row=r["hypothesis_sample"][0]
    attack='<img src=x onerror="alert(3)">'
    r["model_version"]=attack
    row["industry_id"]=attack
    row["incumbent_security_id"]=attack
    row["issues"]=[attack]
    page=render_peer_score_rotation_dashboard(r)
    assert attack not in page
    assert "&lt;img" in page
    assert "&quot;alert(3)&quot;" in page


@pytest.mark.parametrize("mutate", [
    lambda r: r["hypothesis_sample"][0].update(locally_score_correlated=True,issues=["UNRESOLVED_PROVENANCE"]),
    lambda r: r["hypothesis_sample"][0].update(
        last_two_contender_minus_incumbent_scores=[1.0,2.0]),
    lambda r: r["hypothesis_sample"][0].update(
        last_two_paired_score_event_hashes=[{"incumbent_event_sha256":"fake",
                                              "contender_event_sha256":"0"*64}]),
    lambda r: r["hypothesis_sample"][0].update(
        last_two_paired_market_days=["2026-10-04","2026-10-03"]),
])
def test_forged_individual_score_evidence_is_blocked(tmp_path,mutate):
    r=report(tmp_path)
    mutate(r)
    with pytest.raises(ValueError,match="evidence|score|hypothesis|sample"):
        render_peer_score_rotation_dashboard(r)


def test_cli_writes_sanitized_derived_html_and_backup_restores_only_reports(tmp_path,capsys):
    b=setup(tmp_path)
    before=sha256(b[0].read_bytes()).hexdigest(),sha256(b[1].read_bytes()).hexdigest()
    result_dir=tmp_path/"derived"
    args=[
        "audit-peer-score-rotation", "--watch-ledger",str(b[0]),
        "--score-history",str(b[1]),"--feature-root",str(b[2]),
        "--market","KR","--model-version",MODEL,
        "--evaluated-at",EVALUATED,"--out",str(result_dir)
    ]
    main(args)
    output=json.loads(capsys.readouterr().out)
    report_file=result_dir/"peer_score_rotation_kr_research.json"
    html_file=result_dir/"site"/"peer_score_rotation_kr.html"
    assert output["dashboard"]==str(html_file)
    assert report_file.is_file() and html_file.is_file()
    assert output["official_leader_replacements"]==0
    assert "확정 대장주 0건" in html_file.read_text()
    after=sha256(b[0].read_bytes()).hexdigest(),sha256(b[1].read_bytes()).hexdigest()
    assert before==after
    archive=tmp_path/"derived_peer_score_rotation.zip"
    backup=create_backup(result_dir,archive)
    assert backup["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with __import__("zipfile").ZipFile(archive) as zipfile:
        assert sorted(zipfile.namelist())==sorted([
            "peer_score_rotation_kr_research.json",
            "site/peer_score_rotation_kr.html", "MANIFEST.json",
        ])
        assert "prospective.sqlite" not in zipfile.namelist()
        assert "peer_scores.sqlite" not in zipfile.namelist()
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert (restored/"site"/"peer_score_rotation_kr.html").read_bytes()==html_file.read_bytes()
    assert (restored/"peer_score_rotation_kr_research.json").read_bytes()==report_file.read_bytes()


def test_generated_dashboard_local_http_200(tmp_path):
    r=report(tmp_path)
    site=tmp_path/"site"
    target=write_peer_score_rotation_dashboard(r,site)
    assert target.name=="peer_score_rotation_kr.html"
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self,*args):
            pass
    handler=partial(QuietHandler,directory=str(site))
    httpd=ThreadingHTTPServer(("127.0.0.1",0),handler)
    worker=Thread(target=httpd.serve_forever,daemon=True)
    worker.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}/{target.name}",timeout=5) as response:
            assert response.status==200
            assert b"EraLeader" in response.read()
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=5)

def test_score_pair_witness_contains_two_original_security_scores(tmp_path):
    r=report(tmp_path)
    row=r["hypothesis_sample"][0]
    assert row["last_two_paired_scores"]==[
        {"market_day":"2026-10-03","incumbent_score":40.0,"contender_score":65.0},
        {"market_day":"2026-10-04","incumbent_score":38.0,"contender_score":72.0},
    ]
    html=render_peer_score_rotation_dashboard(r)
    assert "40.00" in html and "65.00" in html
    assert "38.00" in html and "72.00" in html


def test_forged_absolute_score_pair_disagrees_with_source_difference(tmp_path):
    r=report(tmp_path)
    item=r["hypothesis_sample"][0]["last_two_paired_scores"][0]
    item["incumbent_score"]=99.0
    with pytest.raises(ValueError,match="mismatch|score|evidence"):
        render_peer_score_rotation_dashboard(r)


def test_forged_absolute_score_pair_with_mismatched_date_is_refused(tmp_path):
    r=report(tmp_path)
    r["hypothesis_sample"][0]["last_two_paired_scores"][0]["market_day"]="2026-10-02"
    with pytest.raises(ValueError,match="score|market|evidence"):
        render_peer_score_rotation_dashboard(r)
