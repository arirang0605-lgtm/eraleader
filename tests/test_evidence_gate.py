from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from eraleader.cli import main
from eraleader.evidence_gate import evaluate_local_evidence, REPORTS

DECISION="2026-10-02T17:00:00+09:00"
DECISION_UTC="2026-10-02T08:00:00+00:00"


def valid_reports(market="KR"):
    base = {
        "source_vintage": {
            "status":"RESEARCH_DECLARED_VINTAGE_NOT_CERTIFIED",
            "decision_at":DECISION_UTC,
            "historical_pit_certified":False,
            "source_timestamp_independently_attested":False,
            "sources":[{
                "market":market,"kind":kind,"sha256_verified":True,
                "retrospective_backfill":False,"retrieved_by_decision_claimed":True
            } for kind in ("membership","actions","fundamentals","industry",
                           "raw_prices","total_return_index")]
        },
        "issuer_lineage": {
            "status":"RESEARCH_ISSUER_IDENTITY_AUDIT_NOT_CERTIFIED",
            "market":market,"decision_at":DECISION_UTC,
            "historic_membership_pit_certified":False,
            "permanent_identity_independently_verified":False,
            "retrospective_retrieval":False,
            "active_ticker_conflict_count":0,"observed_tickers_unmatched_count":0,
            "corporate_events_with_unknown_parent_count":0,
            "corporate_events_with_missing_successor_count":0,
            "cash_exit_events_without_verified_proceeds_count":0,
        },
        "exchange_calendar": {
            "status":"LOCAL_CALENDAR_COMPARISON_NOT_PIT_CERTIFIED",
            "market":market,"cutoff":"2026-10-02",
            "calendar_pit_certified":False,
            "calendar_independently_attested":False,
            "calendar_retrospectively_retrieved":False,
            "calendar_complete_claimed":True,
            "reference_only_missing_market_periods":0,
            "feed_only_unexpected_periods":0,
        },
        "price_continuity": {
            "status":"LOCAL_OBSERVATION_CONTINUITY_NOT_PIT_CERTIFIED",
            "market":market,"as_of_requested":"2026-10-02",
            "observation_cadence":"daily" if market=="KR" else "weekly",
            "historic_universe_pit_certified":False,
            "exchange_calendar_completeness_verified":False,
            "internal_gap_event_count":0,
            "right_boundary_last_observations":0,
        },
        "membership_price": {
            "status":"PIT_MEMBERSHIP_OBSERVATION_AUDIT_NOT_CERTIFIED",
            "market":market,"requested_as_of":"2026-10-02",
            "historic_membership_pit_certified":False,
            "price_availability_pit_certified":False,
            "synthetic_or_uncertified_input":False,
            "member_without_price_count":0,"price_without_member_count":0,
            "observed_exited_count":0,
        },
    }
    return base


def write_bundle(tmp_path, data=None, market="KR"):
    inputs = data if data is not None else valid_reports(market)
    root=tmp_path/"existing_reports"
    root.mkdir(exist_ok=True)
    for domain, payload in inputs.items():
        name=REPORTS[domain].format(market=market.lower())
        (root/name).write_text(json.dumps(payload,sort_keys=True))
    return root


def audit(root,market="KR"):
    return evaluate_local_evidence(root, market=market,decision_at=DECISION)


def test_missing_everything_is_blocked_not_zero_filled(tmp_path):
    root=tmp_path/"existing"
    root.mkdir()
    result=audit(root)
    assert result["status"]=="BLOCKED_MISSING_OR_UNRESOLVED_PIT_EVIDENCE"
    assert result["present_domains"]==0
    assert result["blocker_count"]==5
    assert result["official_promotion_allowed"] is False
    assert result["official_leader_count"]==0
    assert all(item["sha256"] is None for item in result["evidence"])


def test_all_reported_local_checks_do_not_auto_certify_pit(tmp_path):
    result=audit(write_bundle(tmp_path))
    assert result["present_domains"]==5
    assert result["research_diagnostics_complete"] is True
    assert result["status"]=="LOCAL_AUDIT_DIAGNOSTICS_COMPLETE_NOT_PIT_CERTIFIED"
    assert result["blocker_count"]==0
    assert all(len(item["sha256"])==64 for item in result["evidence"])
    assert result["official_promotion_allowed"] is False
    assert result["historical_pit_certified"] is False
    assert result["model_accuracy_certified"] is False


@pytest.mark.parametrize("domain,mutation,expected", [
    ("source_vintage",lambda x:x["sources"].__setitem__(0,{**x["sources"][0],
           "retrospective_backfill":True}),"RETROSPECTIVE_SOURCE_VINTAGE"),
    ("source_vintage",lambda x:x["sources"].pop(),"NO_TOTAL_RETURN_INDEX_SOURCE"),
    ("issuer_lineage",lambda x:x.update(active_ticker_conflict_count=2),"ACTIVE_TICKER_CONFLICT_COUNT"),
    ("issuer_lineage",lambda x:x.update(cash_exit_events_without_verified_proceeds_count=1),"CASH_EXIT_EVENTS_WITHOUT_VERIFIED_PROCEEDS_COUNT"),
    ("issuer_lineage",lambda x:x.update(retrospective_retrieval=True),"RETROSPECTIVE_ISSUER_VINTAGE"),
    ("exchange_calendar",lambda x:x.update(reference_only_missing_market_periods=3),"REFERENCE_ONLY_MISSING_MARKET_PERIODS"),
    ("exchange_calendar",lambda x:x.update(calendar_complete_claimed=False),"EXCHANGE_CALENDAR_NOT_COMPLETE"),
    ("price_continuity",lambda x:x.update(right_boundary_last_observations=1),"RIGHT_BOUNDARY_LAST_OBSERVATIONS"),
    ("price_continuity",lambda x:x.update(observation_cadence="weekly"),"PRICE_CADENCE_MISMATCH"),
    ("membership_price",lambda x:x.update(synthetic_or_uncertified_input=True),"HISTORICAL_MEMBERSHIP_SOURCE_UNCERTIFIED"),
    ("membership_price",lambda x:x.update(price_without_member_count=1),"PRICE_WITHOUT_MEMBER_COUNT"),
])
def test_each_local_evidence_anomaly_blocks_research_readiness(tmp_path,domain,mutation,expected):
    records=valid_reports()
    mutation(records[domain])
    result=audit(write_bundle(tmp_path,records))
    assert result["research_diagnostics_complete"] is False
    assert any(expected in v for v in result["blockers"])
    assert result["official_promotion_allowed"] is False


@pytest.mark.parametrize("domain,field", [
    ("source_vintage","historical_pit_certified"),
    ("issuer_lineage","permanent_identity_independently_verified"),
    ("exchange_calendar","calendar_pit_certified"),
    ("price_continuity","historic_universe_pit_certified"),
    ("membership_price","historic_membership_pit_certified"),
])
def test_certification_flag_spoofing_is_rejected(tmp_path,domain,field):
    records=valid_reports()
    records[domain][field]=True
    with pytest.raises(ValueError,match="Untrusted certified"):
        audit(write_bundle(tmp_path,records))


def test_unexpected_status_cannot_masquerade_as_evidence(tmp_path):
    rows=valid_reports()
    rows["exchange_calendar"]["status"]="OFFICIAL_CERTIFIED"
    with pytest.raises(ValueError,match="Unexpected audit"):
        audit(write_bundle(tmp_path,rows))


def test_wrong_market_and_cutoff_do_not_silently_join(tmp_path):
    rows=valid_reports()
    rows["issuer_lineage"]["market"]="US"
    rows["exchange_calendar"]["cutoff"]="2026-09-30"
    out=audit(write_bundle(tmp_path,rows))
    assert "issuer_lineage:MARKET_MISMATCH" in out["blockers"]
    assert "exchange_calendar:DECISION_MARKET_DAY_MISMATCH" in out["blockers"]


def test_american_weekly_evidence_requires_weekly_cadence(tmp_path):
    rows=valid_reports("US")
    result=audit(write_bundle(tmp_path,rows,market="US"),"US")
    assert result["research_diagnostics_complete"] is True
    assert result["official_promotion_allowed"] is False


def test_symlink_and_oversized_reports_rejected(tmp_path):
    root=write_bundle(tmp_path)
    path=root/REPORTS["exchange_calendar"].format(market="kr")
    path.unlink()
    outside=tmp_path/"wrong_calendar.json"
    outside.write_text("{}")
    path.symlink_to(outside)
    with pytest.raises(ValueError,match="Unsafe symlink"):
        audit(root)
    path.unlink()
    path.write_bytes(b"x"*3_000_001)
    with pytest.raises(ValueError,match="oversized"):
        audit(root)


def test_invalid_timestamp_rejected(tmp_path):
    rows=valid_reports()
    rows["source_vintage"]["decision_at"]="2026-10-02T08:00:00"
    with pytest.raises(ValueError,match="timezone-aware"):
        audit(write_bundle(tmp_path,rows))


def test_cli_creates_only_uncertified_summary(tmp_path,capsys):
    root=write_bundle(tmp_path)
    main(["audit-evidence-gate","--market","KR","--decision-at",DECISION,
          "--input-root",str(root),"--out",str(tmp_path/"derived")])
    result=json.loads(capsys.readouterr().out)
    assert result["present_domains"]==5
    assert result["blocker_count"]==0
    assert result["official_promotion_allowed"] is False
    stored=json.loads(Path(result["path"]).read_text())
    assert len(stored["evidence"])==5
    assert stored["model_accuracy_certified"] is False
    assert "source_id" not in json.dumps(stored)


def test_evidence_gate_derived_json_survives_safe_local_backup(tmp_path,capsys):
    from zipfile import ZipFile
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    root=write_bundle(tmp_path)
    out=tmp_path/"derived"
    main(["audit-evidence-gate","--market","KR","--decision-at",DECISION,
          "--input-root",str(root),"--out",str(out)])
    capsys.readouterr()
    (out/"raw_vendor_payload.json").write_text('{"private_api_key":"NEVER_COPY"}')
    archive=tmp_path/"safe_gate.zip"
    saved=create_backup(out,archive)
    assert saved["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert set(z.namelist())=={
            "evidence_gate_kr_research.json","site/evidence_kr.html","MANIFEST.json"}
    restored=tmp_path/"restored_gate"
    restore_backup(archive,restored)
    saved_report=json.loads((restored/"evidence_gate_kr_research.json").read_text())
    assert saved_report["official_promotion_allowed"] is False
    assert saved_report["historical_pit_certified"] is False
    assert not (restored/"raw_vendor_payload.json").exists()


def test_evidence_dashboard_shows_real_blockers_without_certification(tmp_path):
    from eraleader.delivery import render_evidence_gate_dashboard
    rows=valid_reports()
    rows["issuer_lineage"]["active_ticker_conflict_count"]=1
    result=audit(write_bundle(tmp_path,rows))
    html=render_evidence_gate_dashboard(result)
    assert "대장주 공식 확정: 차단됨" in html
    assert "UNRESOLVED_ACTIVE_TICKER_CONFLICT_COUNT" in html
    assert "0건 · 인증 보류" in html
    assert "투자 추천 또는 확정 후보가 아닙니다" in html


def test_evidence_dashboard_escapes_untrusted_text_and_refuses_promotions(tmp_path):
    from eraleader.delivery import render_evidence_gate_dashboard
    result=audit(write_bundle(tmp_path))
    result["evidence"][0]["domain"]="<script>alert('bad')</script>"
    html=render_evidence_gate_dashboard(result)
    assert "<script>" not in html and "&lt;script&gt;" in html
    spoof=deepcopy(result)
    spoof["official_promotion_allowed"]=True
    with pytest.raises(ValueError,match="cannot render"):
        render_evidence_gate_dashboard(spoof)
    spoof=deepcopy(result)
    spoof["official_leader_count"]=1
    with pytest.raises(ValueError,match="cannot render"):
        render_evidence_gate_dashboard(spoof)


def test_cli_outputs_dashboard_file_as_well_as_machine_report(tmp_path,capsys):
    root=write_bundle(tmp_path)
    out=tmp_path/"research"
    main(["audit-evidence-gate","--market","KR","--decision-at",DECISION,
          "--input-root",str(root),"--out",str(out)])
    result=json.loads(capsys.readouterr().out)
    assert result["dashboard"]==str(out/"site"/"evidence_kr.html")
    html=(out/"site"/"evidence_kr.html").read_text()
    assert "PIT 근거 품질 점검" in html
    assert "공식 확정 대장주" in html
    assert "독립 PIT 인증은 아직" in html or "독립 PIT 인증과 실제 미래" in html
    assert result["official_promotion_allowed"] is False


def test_dashboard_html_is_safe_local_backup_artifact(tmp_path,capsys):
    from zipfile import ZipFile
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    root=write_bundle(tmp_path)
    out=tmp_path/"out"
    main(["audit-evidence-gate","--market","KR","--decision-at",DECISION,
          "--input-root",str(root),"--out",str(out)])
    capsys.readouterr()
    (out/"original_provider_data.csv").write_text("private_api_token,NEVER_ARCHIVE")
    backup=tmp_path/"evidence_web.zip"
    created=create_backup(out,backup)
    assert created["file_count"]==2
    assert verify_backup(backup)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(backup) as z:
        assert set(z.namelist())=={
            "evidence_gate_kr_research.json","site/evidence_kr.html","MANIFEST.json"}
    restored=tmp_path/"safe_restore"
    restore_backup(backup,restored)
    assert "확정 대장주" in (restored/"site"/"evidence_kr.html").read_text()
    assert not (restored/"original_provider_data.csv").exists()
