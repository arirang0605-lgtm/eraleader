"""ER-NC-05 existing prospective WATCH 2+2 sidecar lineage tests."""
from copy import deepcopy
from datetime import datetime,timezone
import pytest

from eraleader.news_rotation_context import correlate_watch_rotation
from eraleader.theme_pit_catalog import ThemePITCatalog
from eraleader.news_catalyst_adapter import NewsCatalystEvents
from test_watch_rotation import planted, MODEL, EVAL, CLOCK, audit
from test_news_catalyst_adapter import event, seal

ASOF="2026-10-09T00:00:00Z"


def catalog(first_known="2026-09-01T00:00:00Z",broken=False):
    members=[]
    for sec in ("INC","NEW"):
        members.append({
            "member_issuer_id":"issuer."+sec,
            "member_security_id":sec,
            "member_first_known_at":first_known if sec=="NEW" else "2026-09-01T00:00:00Z",
            "member_effective_from":"2026-09-01T00:00:00Z",
            "member_effective_to":None,
            "evidence_ids":["synthetic.source.member."+sec],
            "relationship_type":"DIRECT_CONTRACT"})
    data={"theme_id":"theme.SEMICON","theme_name":"Semiconductors",
          "taxonomy_version":"semicon-pit-v1","aliases":[],
          "parent_industry_id":"industry.SEMICON",
          "created_at":"2026-09-01T00:00:00Z",
          "available_at":"2026-10-01T00:00:00Z",
          "reclassified_at":None,"members":members if not broken else members[:1]}
    return ThemePITCatalog([data]).snapshot(ASOF)


def ep(as_of="2026-10-01T10:00:00Z"):
    return {"theme_id":"theme.SEMICON", "episode_id":"E_FIRST",
            "state":"RISING","as_of":as_of,
            "source_sha256":"a"*64,
            "research_only":True,"official_leaders":0}


def news(available="2026-10-02T12:30:00Z"):
    record=event(
        published="2026-10-02T11:00:00Z",
        first="2026-10-02T12:00:00Z",
        available=available,
        issuer="NEW")
    # Verification+first benefit must be no later than its version available_at.
    record["theme_hints"]=["theme.SEMICON"]
    seal(record)
    events=NewsCatalystEvents([record],source_sha256="f"*64,
                              source_name="fixture.json")
    return events.snapshot(ASOF)


def correlate(tmp_path,**kwargs):
    path=planted(tmp_path)
    params={
        "ledger":path,"market":"KR","model_version":MODEL,
        "evaluated_at":EVAL,"clock":CLOCK,
        "theme_pit_snapshot":catalog(),
        "theme_episode_history":[ep()],
        "news_snapshot":news(),
    }
    params.update(kwargs)
    return correlate_watch_rotation(**params)


def test_real_existing_prospective_2x2_gate_and_theme_news_link(tmp_path):
    result=correlate(tmp_path)
    assert result["rotation_hypothesis_count"]==1
    assert result["source_rotation_audit_count"]==1
    h=result["hypotheses"][0]
    assert (h["incumbent_security_id"],h["challenger_security_id"])==("INC","NEW")
    assert h["theme_id"]=="theme.SEMICON"
    assert h["episode_id"]=="E_FIRST"
    assert h["news_evidence"][0]["catalyst_state"]=="CONFIRMED"
    assert h["status"]=="RESEARCH_ROTATION_HYPOTHESIS"
    assert h["official_leader_replacements"]==0
    assert h["prospective_performance_verified"] is False
    assert h["maturity_due_at"] is None


def test_replay_deterministic_sha_without_writing_original_prospective_db(tmp_path):
    path=planted(tmp_path)
    args=dict(ledger=path,market="KR",model_version=MODEL,
              evaluated_at=EVAL,clock=CLOCK,theme_pit_snapshot=catalog(),
              theme_episode_history=[ep()],news_snapshot=news())
    original=path.read_bytes()
    first=correlate_watch_rotation(**args)
    second=correlate_watch_rotation(**args)
    assert first==second and path.read_bytes()==original


def test_missing_news_still_retains_rotation_research_hypothesis(tmp_path):
    result=correlate(tmp_path,news_snapshot=None)
    assert result["rotation_hypothesis_count"]==1
    assert result["hypotheses"][0]["news_evidence"]==[]


def test_missing_theme_pit_member_refuses_news_based_leader_replacement(tmp_path):
    result=correlate(tmp_path,theme_pit_snapshot=catalog(broken=True))
    assert result["rotation_hypothesis_count"]==0
    assert result["unresolved_theme_class_pairs"]==1


def test_later_discovered_beneficiary_not_retrospectively_credited(tmp_path):
    result=correlate(tmp_path,news_snapshot=news(available="2026-10-07T12:30:00Z"))
    assert result["rotation_hypothesis_count"]==1
    assert result["hypotheses"][0]["news_evidence"]==[]
    assert result["post_candidate_news_not_credited"]>=1


def test_future_known_theme_class_membership_is_excluded(tmp_path):
    r=correlate(tmp_path,theme_pit_snapshot=catalog(first_known="2026-10-06T13:00:00Z"))
    assert r["rotation_hypothesis_count"]==0


def test_episode_from_after_first_candidate_cannot_be_backdated(tmp_path):
    r=correlate(tmp_path,theme_episode_history=[ep(as_of="2026-10-06T09:00:00Z")])
    assert r["rotation_hypothesis_count"]==1
    assert r["hypotheses"][0]["episode_id"] is None


def test_future_episode_asof_fails_closed(tmp_path):
    with pytest.raises(ValueError,match="Future theme episode"):
        correlate(tmp_path,theme_episode_history=[ep(as_of="2026-10-12T10:00:00Z")])


def test_future_news_vintage_must_not_affect_historical_screen(tmp_path):
    report=news()
    report["as_of"]="2026-10-20T10:00:00Z"
    with pytest.raises(ValueError,match="News vintage"):
        correlate(tmp_path,news_snapshot=report)


def test_news_unverified_is_not_a_verified_beneficiary(tmp_path):
    r=news()
    r["events"][0]["evidence_status"]="OBSERVED_UNVERIFIED"
    result=correlate(tmp_path,news_snapshot=r)
    assert result["hypotheses"][0]["news_evidence"]==[]


def test_theme_dormant_not_auto_confirm_or_demote(tmp_path):
    dormant=ep()
    dormant["state"]="DORMANT"
    result=correlate(tmp_path,theme_episode_history=[dormant])
    h=result["hypotheses"][0]
    assert h["theme_state_at_first_watch"]=="DORMANT"
    assert h["status"]=="RESEARCH_ROTATION_HYPOTHESIS"
    assert h["official_leader_replacements"]==0


def test_cannot_upgrade_fake_certified_rotation_report(tmp_path):
    snapshot=catalog()
    snapshot["official_leaders"]=1
    with pytest.raises(ValueError,match="Uncertified theme"):
        correlate(tmp_path,theme_pit_snapshot=snapshot)


def test_legacy_rotation_result_stays_research_only(tmp_path):
    path=planted(tmp_path)
    legacy=audit(path)
    assert legacy["status"]=="RESEARCH_PEER_WATCH_ROTATION_NOT_CERTIFIED"
    assert legacy["official_leader_replacements"]==0
