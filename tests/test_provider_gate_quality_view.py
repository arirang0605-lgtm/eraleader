"""6_2: opt-in honest local provider/source quality web view; no live delivery."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen
import json
import sqlite3

import pytest

from eraleader.cli import main
from eraleader.local_backup import create_backup, restore_backup, verify_backup
from eraleader.offline_pit import OfflineLedger
from eraleader.provider_candidate_gate import audit_candidate_provider_gate
from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.provider_gate_quality_view import (
    render_provider_gate_quality, write_provider_gate_quality,
)
from test_issuer_class_bridge import fixture
from test_provider_pair_original_pin_gate import (
    AUDIT, DECISION, NOW, case, options, orig,
)
from test_provider_candidate_gate import args as legacy_args, setup_case


def case_with_lineage(tmp_path, market="KR"):
    pair = case(tmp_path / "provider", market=market)
    _, lineage = fixture(tmp_path / "identity", market=market)
    db = OfflineLedger.open_readonly(pair[0][0])
    try:
        members = db.snapshot(DECISION, market=market)["members"]
    finally:
        db.close()
    gate = audit_candidate_provider_gate(
        pair[0][0], pair[0][1], pair[1][0], pair[1][1],
        market=market, decision_at=DECISION, candidate_members=members,
        require_original_pins=True, original_sources=orig(pair),
        issuer_lineage_file=lineage, clock=AUDIT,
    )
    return pair, lineage, gate


@pytest.mark.parametrize("market", ["KR", "US"])
def test_page_shows_three_separate_local_evidence_states_never_official(tmp_path, market):
    pair, lineage, gate = case_with_lineage(tmp_path, market)
    html = render_provider_gate_quality(gate)
    assert "<!doctype html>" in html
    assert "원천 검증" in html
    assert "최초 원본 SHA" in html
    assert "법인" in html and "주식클래스" in html
    assert "연구용 WATCH" in html
    assert "미인증" in html
    assert "공식 확정 대장주" in html and "0" in html
    assert gate["source_pair_digest_sha256"] in html
    assert "CIK0000012345" not in html
    assert "CORP00001234" not in html
    assert str(lineage) not in html
    assert str(pair[0][0]) not in html
    assert "SYNTHETIC_DOC_NOT_OFFICIAL" not in html
    assert "실전 적중률 N/A" in html
    assert '<script' not in html


def test_legacy_pair_can_view_but_pin_and_class_display_not_requested(tmp_path):
    pair, _, gate = case_with_lineage(tmp_path)
    weak = audit_candidate_provider_gate(
        pair[0][0], pair[0][1], pair[1][0], pair[1][1],
        market="KR", decision_at=DECISION,
        candidate_members=OfflineLedger.open_readonly(pair[0][0]).snapshot(
            DECISION, market="KR"
        )["members"],
        clock=AUDIT,
    )
    html = render_provider_gate_quality(weak)
    assert weak["research_watch_allowed"]
    assert html.count("미요청") >= 2
    assert "공식 확정 대장주" in html
    assert "공급자 원본 증명 완료" not in html


def test_issuer_class_mismatch_is_blocked_with_count_and_reason(tmp_path):
    _, lineage, gate = case_with_lineage(tmp_path)
    bad = deepcopy(gate)
    bad["status"] = "BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    bad["research_watch_allowed"] = False
    bad["blocker_counts"] = {"ISSUER_CLASS_SECURITY_CLASS_TICKER_CONFLICT": 1}
    bad["blocker_count"] = 1
    bad["issuer_class_bridge_status"] = "BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    bad["issuer_class_matched_candidates"] = 0
    html = render_provider_gate_quality(bad)
    assert "보류" in html
    assert "ISSUER_CLASS_SECURITY_CLASS_TICKER_CONFLICT" in html
    assert "1" in html
    assert "연구용 WATCH 허용" not in html
    assert str(lineage) not in html


@pytest.mark.parametrize("field,value", [
    ("publisher_independently_authenticated", True),
    ("legal_issuer_identity_independently_verified", True),
    ("historic_membership_pit_certified", True),
    ("official_candidate_promotion_allowed", True),
    ("leader_accuracy_certified", True),
    ("official_leader_promotions", 1),
    ("source_consistency_only", False),
    ("source_pair_consistency_only", False),
    ("official_leader_promotions", False),
    ("leader_accuracy_certified", 0),
])
def test_fake_certification_flags_are_rejected(tmp_path, field, value):
    _, _, gate = case_with_lineage(tmp_path)
    forged = {**gate, field: value}
    with pytest.raises(ValueError):
        render_provider_gate_quality(forged)


@pytest.mark.parametrize("field,value", [
    ("candidate_issuer_count", -1),
    ("locally_correlated_candidate_issuer_count", 999),
    ("issuer_class_matched_candidates", 999),
    ("blocker_count", 1),
    ("blocker_counts", {"<script>alert(1)</script>": 1}),
    ("blocker_counts", {"PAIR_FAKE": -1}),
    ("source_pair_digest_sha256", "broken"),
    ("issuer_class_evidence_sha256", "not-a-sha"),
    ("source_pair_bundle_sha256_a", "unsafe"),
    ("source_pair_status", "APPROVED_BY_KRX"),
    ("issuer_class_bridge_status", "OFFICIAL_CERTIFIED"),
    ("status", "CERTIFIED"),
    ("research_watch_allowed", False),
    ("original_first_ingest_pins_locally_consistent", False),
    ("require_original_first_ingest_pins", False),
])
def test_malformed_or_contradictory_quality_report_fails_closed(tmp_path, field, value):
    _, _, gate = case_with_lineage(tmp_path)
    with pytest.raises(ValueError):
        render_provider_gate_quality({**gate, field: value})


def test_quality_html_atomic_writer_refuses_symlinks_and_invalid_reports(tmp_path):
    _, _, gate = case_with_lineage(tmp_path)
    site = tmp_path / "site"
    doc = write_provider_gate_quality(gate, site)
    assert doc.name == "provider_quality_kr.html"
    assert doc.is_file()
    before = doc.read_bytes()
    forged = {**gate, "publisher_independently_authenticated": True}
    with pytest.raises(ValueError):
        write_provider_gate_quality(forged, site)
    assert doc.read_bytes() == before
    redirected = tmp_path / "redirected"
    redirected.write_text("DO_NOT_OVERWRITE")
    doc.unlink()
    doc.symlink_to(redirected)
    with pytest.raises(ValueError, match="symlink|Unsafe"):
        write_provider_gate_quality(gate, site)
    assert redirected.read_text() == "DO_NOT_OVERWRITE"


def test_quality_page_in_approved_derived_only_backup_and_http(tmp_path):
    _, _, gate = case_with_lineage(tmp_path)
    derived = tmp_path / "derived"
    page = write_provider_gate_quality(gate, derived / "site")
    blob = page.read_bytes()
    archive = tmp_path / "safe.zip"
    result = create_backup(derived, archive)
    assert result["file_count"] == 1
    assert verify_backup(archive)["status"] == "LOCAL_BACKUP_VERIFIED"
    restore_backup(archive, tmp_path / "restored")
    assert (tmp_path / "restored" / "site" / page.name).read_bytes() == blob
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(
        *args, directory=str(derived / "site"), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    try:
        thread.start()
        with urlopen(f"http://127.0.0.1:{server.server_port}/{page.name}", timeout=4) as r:
            assert r.status == 200 and r.read() == blob
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_missing_pair_with_quality_flag_rejected_before_artifacts(tmp_path, capsys):
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as error:
        main(["offline-integrated", "--market", "KR", "--as-of", DECISION,
              "--out", str(out), "--show-provider-gate-quality"])
    assert error.value.code == 2
    assert "quality" in capsys.readouterr().err.lower()
    assert not out.exists()


@pytest.mark.parametrize("market", ("KR", "US"))
def test_cli_opt_in_strict_gate_creates_website_and_link_only_when_requested(
    tmp_path, capsys, market,
):
    pair, lineage, gate = case_with_lineage(tmp_path, market)
    out = tmp_path / "out"
    out.mkdir()
    import_provider_bundle(pair[0][3], out / "offline.sqlite", clock=NOW)
    originals = [p for side in pair for p in (side[0], side[2], side[3])]
    originals += [lineage, out / "offline.sqlite"]
    before = {str(p): sha256(p.read_bytes()).hexdigest() for p in originals}
    main(["offline-integrated", "--market", market, "--as-of", DECISION,
          "--out", str(out), *options(pair),
          "--require-provider-issuer-class-lineage",
          "--provider-issuer-lineage", str(lineage),
          "--show-provider-gate-quality"])
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert response["new_prospective_research_signals"] == 1
    assert response["official_leaders"] == 0
    page = out / "site" / f"provider_quality_{market.lower()}.html"
    assert response["provider_quality_dashboard"] == str(page)
    assert page.is_file()
    research = (out / "site" / f"research_{market.lower()}.html").read_text()
    assert f"provider_quality_{market.lower()}.html" in research
    assert "원천 검증" in page.read_text()
    assert before == {str(p): sha256(p.read_bytes()).hexdigest() for p in originals}


def test_cli_blocked_pair_creates_only_quality_page_no_watch_or_research(tmp_path, capsys):
    out, pair = setup_case(tmp_path, change_b=lambda m: update_action_ratio(m))
    main([*legacy_args(out, pair), "--show-provider-gate-quality"])
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    page = out / "site" / "provider_quality_kr.html"
    assert page.is_file()
    assert "PAIR_SPLIT_RATIO_CONFLICT" in page.read_text()
    assert response["provider_quality_dashboard"] == str(page)
    assert not (out / "prospective.sqlite").exists()
    assert not (out / "state_history.sqlite").exists()
    assert not (out / "site" / "research_kr.html").exists()
    assert not (out / "runs").exists()


def update_action_ratio(manifest):
    from test_provider_dual_source_audit import edit_stream
    edit_stream(manifest, "actions", lambda rows: rows[0].update(ratio=4))


def test_without_new_opt_in_no_new_quality_page_or_legacy_link(tmp_path, capsys):
    out, pair = setup_case(tmp_path)
    main(legacy_args(out, pair))
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert "provider_quality_dashboard" not in result
    assert not (out / "site" / "provider_quality_kr.html").exists()
    assert "provider_quality_kr.html" not in (
        out / "site" / "research_kr.html").read_text()


def test_twice_issued_same_quality_page_reflects_current_blocker(tmp_path):
    _, _, gate = case_with_lineage(tmp_path)
    site = tmp_path / "site"
    path = write_provider_gate_quality(gate, site)
    good = path.read_bytes()
    blocked = deepcopy(gate)
    blocked.update(
        status="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH",
        research_watch_allowed=False,
        blocker_counts={"ISSUER_CLASS_CANDIDATE_CLASS_NOT_IN_PINNED_SOURCE": 1},
        blocker_count=1,
        issuer_class_matched_candidates=0,
    )
    write_provider_gate_quality(blocked, site)
    assert path.read_bytes() != good
    assert "보류" in path.read_text()
    assert "연구용 WATCH 허용" not in path.read_text()
