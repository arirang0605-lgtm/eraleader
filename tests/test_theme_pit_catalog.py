"""ER-NC-03 theme vintage, issuer/share-class PIT, aliases and news hint safety."""
from copy import deepcopy
import pytest

from eraleader.theme_pit_catalog import ThemePITCatalog


def member(*, issuer="issuer.KR.A", security="class.KR.A.1",
           first="2026-01-02T09:00:00+09:00", start="2026-01-01T00:00:00+09:00",
           end=None, relationship="DIRECT_CONTRACT", ticker="AAAAAA"):
    return {"member_issuer_id":issuer,"member_security_id":security,
            "member_first_known_at":first,"member_effective_from":start,
            "member_effective_to":end,
            "evidence_ids":["doc.secure.1"] if relationship=="DIRECT_CONTRACT" else [],
            "relationship_type":relationship,"display_ticker":ticker}


def version(*, tax="2026.v1", asof="2026-01-02T12:00:00+09:00",
            members=None, aliases=None, industry="INDUSTRY.A"):
    return {"theme_id":"theme.ROBOTICS","theme_name":"Robotics",
            "taxonomy_version":tax,
            "parent_industry_id":industry,
            "created_at":"2026-01-01T09:00:00+09:00",
            "available_at":asof,"reclassified_at":None,
            "aliases":aliases if aliases is not None else
                 [{"name":"Robots","first_known_at":"2026-01-02T09:00:00+09:00"}],
            "members":members if members is not None else [member()]}


def test_observed_theme_and_security_is_research_only():
    snap=ThemePITCatalog([version()]).snapshot("2026-01-03T12:00:00+09:00")
    t=snap["themes"]["theme.ROBOTICS"]
    assert t["member_count"]==1 and t["members"][0]["member_security_id"]=="class.KR.A.1"
    assert snap["official_leaders"]==0
    assert snap["historic_exchange_universe_pit_verified"] is False


def test_theme_not_created_yet_invisible():
    c=ThemePITCatalog([version()])
    assert c.snapshot("2025-12-31T17:00:00+09:00")["themes"]=={}


def test_later_member_first_known_not_backfilled():
    future=member(issuer="issuer.KR.B",security="class.KR.B",
                  first="2026-02-01T09:00:00+09:00",
                  start="2026-01-15T00:00:00+09:00")
    c=ThemePITCatalog([version(members=[member(),future])])
    before=c.snapshot("2026-01-20T11:00:00+09:00")
    after=c.snapshot("2026-02-02T11:00:00+09:00")
    assert before["themes"]["theme.ROBOTICS"]["member_count"]==1
    assert after["themes"]["theme.ROBOTICS"]["member_count"]==2


def test_ticker_rename_preserves_immutable_security_class():
    old=version()
    renamed=version(tax="2026.v2",asof="2026-02-20T12:00:00+09:00",
                    members=[member(ticker="BBBBBB")])
    c=ThemePITCatalog([old,renamed])
    past=c.snapshot("2026-01-15T11:00:00+09:00")["themes"]["theme.ROBOTICS"]["members"][0]
    next_=c.snapshot("2026-03-01T11:00:00+09:00")["themes"]["theme.ROBOTICS"]["members"][0]
    assert past["display_ticker"]=="AAAAAA"
    assert next_["display_ticker"]=="BBBBBB"
    assert past["member_security_id"]==next_["member_security_id"]


def test_two_share_classes_not_merged_by_common_issuer():
    a=member()
    b=member(security="class.KR.A.2",ticker="AAAABB")
    members=ThemePITCatalog([version(members=[a,b])]).snapshot("2026-01-03T12:00:00+09:00")
    assert members["themes"]["theme.ROBOTICS"]["member_count"]==2
    assert len({x["member_security_id"] for x in members["themes"]["theme.ROBOTICS"]["members"]})==2


def test_reclassification_does_not_modify_old_industry():
    a=version()
    b=version(tax="2026.v2",asof="2026-05-02T12:00:00+09:00",industry="INDUSTRY.B")
    b["reclassified_at"]="2026-05-02T09:00:00+09:00"
    c=ThemePITCatalog([a,b])
    assert c.snapshot("2026-01-10T12:00:00+09:00")["themes"]["theme.ROBOTICS"]["parent_industry_id"]=="INDUSTRY.A"
    assert c.snapshot("2026-05-03T12:00:00+09:00")["themes"]["theme.ROBOTICS"]["parent_industry_id"]=="INDUSTRY.B"


def test_alias_is_not_a_backdated_name():
    a=version()
    b=version(tax="2026.v2",asof="2026-03-01T12:00:00+09:00",
              aliases=[{"name":"Humanoids","first_known_at":"2026-03-01T09:00:00+09:00"}])
    c=ThemePITCatalog([a,b])
    assert c.resolve_hint("Humanoids","2026-01-20T12:00:00+09:00")["status"]=="NO_PIT_THEME_MATCH"
    assert c.resolve_hint("Humanoids","2026-03-02T12:00:00+09:00")["status"]=="UNVERIFIED_THEME_HINT"


def test_unknown_news_hint_is_never_membership():
    c=ThemePITCatalog([version()])
    before=c.snapshot("2026-01-03T12:00:00+09:00")
    result=c.resolve_hint("New AI Robotics","2026-01-03T12:00:00+09:00")
    after=c.snapshot("2026-01-03T12:00:00+09:00")
    assert result["auto_membership_changes"]==0
    assert result["status"]=="NO_PIT_THEME_MATCH"
    assert before==after


def test_delisted_security_excluded_at_effective_end_but_past_visible():
    expired=member(end="2026-01-20T10:00:00+09:00")
    c=ThemePITCatalog([version(members=[expired])])
    assert c.snapshot("2026-01-10T12:00:00+09:00")["themes"]["theme.ROBOTICS"]["member_count"]==1
    assert c.snapshot("2026-02-10T12:00:00+09:00")["themes"]["theme.ROBOTICS"]["member_count"]==0


def test_co_mentioned_unverified_not_promoted_to_membership():
    weak=member(relationship="CO_MENTION")
    c=ThemePITCatalog([version(members=[weak])])
    snap=c.snapshot("2026-01-03T12:00:00+09:00")
    assert snap["themes"]["theme.ROBOTICS"]["member_count"]==0
    assert snap["mapping_quality_report"]["unverified_relationship_count"]==1


def test_missing_permanent_security_class_is_quality_issue_not_auto_ticker_join():
    unknown=member(security=None)
    c=ThemePITCatalog([version(members=[unknown])])
    report=c.snapshot("2026-01-10T12:00:00+09:00")
    assert report["mapping_quality_report"]["missing_permanent_class_id"]==1
    assert report["themes"]["theme.ROBOTICS"]["members"]==[]


def test_duplicate_theme_taxonomy_vintage_rejected():
    with pytest.raises(ValueError,match="collision"):
        ThemePITCatalog([version(),version()])


def test_duplicate_member_identity_rejected():
    a=member()
    with pytest.raises(ValueError,match="duplicate membership"):
        ThemePITCatalog([version(members=[a,deepcopy(a)])])


def test_verified_direct_contract_without_document_rejected():
    bad=member();bad["evidence_ids"]=[]
    with pytest.raises(ValueError,match="without source"):
        ThemePITCatalog([version(members=[bad])])


def test_history_does_not_accept_renamed_created_at():
    old=version()
    newer=version(tax="2026.v2",asof="2026-05-03T12:00:00+09:00")
    newer["created_at"]="2025-12-15T09:00:00+09:00"
    with pytest.raises(ValueError,match="immutable"):
        ThemePITCatalog([old,newer])


def test_later_alias_cannot_be_embedded_in_older_catalog_vintage():
    old=version(aliases=[{"name":"FutureName","first_known_at":"2026-09-01T09:00:00+09:00"}])
    with pytest.raises(ValueError,match="first known"):
        ThemePITCatalog([old])


def test_duplicate_alias_banned():
    with pytest.raises(ValueError,match="duplicate alias"):
        ThemePITCatalog([version(aliases=[
            {"name":"Robots","first_known_at":"2026-01-02T09:00:00+09:00"},
            {"name":"Robots","first_known_at":"2026-01-02T10:00:00+09:00"}])])
