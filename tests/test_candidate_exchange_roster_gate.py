"""2_2/2_5/4_1: strict third exchange-wide roster inside the REAL WATCH gate.

All KRX/DART/SEC-like sources are synthetic, self-declared evidence.
Matching declared files never authenticates official market PIT or performance.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.cli import main
from eraleader.offline_pit import OfflineLedger
from eraleader.provider_candidate_gate import audit_candidate_provider_gate
from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.issuer_lineage import ZONES
from test_candidate_issuer_class_gate import inputs
from test_provider_pair_original_pin_gate import orig, options, DECISION, AUDIT, NOW

ASOF=datetime.fromisoformat(DECISION)


def build(tmp_path, market="KR"):
    pair,lineage,members=inputs(tmp_path,market)
    document=json.loads(lineage.read_text())
    day=ASOF.astimezone(ZONES[market]).date().isoformat()
    roster={
        "schema_version":"eraleader.declared_exchange_roster.v1",
        "market":market,
        "source_id":"THIRD_COMPLETE_EXCHANGE_ROSTER",
        "publisher_id_claimed":"CLAIMED_EXCHANGE_THIRD_VENDOR",
        "scope_id":"ALL_LISTED_EQUITY_CLASSES",
        "complete_scope_claimed":True,
        "session_day":day,
        "published_at":(ASOF-timedelta(minutes=5)).isoformat(),
        "retrieved_at":(ASOF-timedelta(minutes=2)).isoformat(),
        "security_classes":[{
            "security_id":r["security_id"],"ticker":r["ticker"],
            "valid_from":r["valid_from"],"valid_to":r["valid_to"],
        } for r in document["identities"]],
    }
    original=tmp_path/"original_full_exchange_roster.json"
    original.write_text(json.dumps(roster,sort_keys=True))
    return pair,lineage,members,original


def sha(file):
    return sha256(Path(file).read_bytes()).hexdigest()


def strict(pair,lineage,members,roster,market="KR",*,clock=AUDIT,pin=None):
    return audit_candidate_provider_gate(
        pair[0][0],pair[0][1],pair[1][0],pair[1][1],
        market=market,decision_at=DECISION,candidate_members=members,
        require_original_pins=True,original_sources=orig(pair),
        issuer_lineage_file=lineage,exchange_roster_file=roster,
        exchange_roster_sha256=sha(roster) if pin is None else pin,
        clock=clock,
    )


def update(file,fn):
    value=json.loads(file.read_text())
    fn(value)
    file.write_text(json.dumps(value,sort_keys=True))


def cli_flags(pair,lineage,roster):
    return [
        *options(pair),
        "--require-provider-issuer-class-lineage",
        "--provider-issuer-lineage",str(lineage),
        "--require-provider-exchange-roster",
        "--provider-exchange-roster",str(roster),
        "--provider-exchange-roster-sha256",sha(roster),
    ]


@pytest.mark.parametrize("market",["KR","US"])
def test_original_first_pins_plus_third_complete_class_roster_enables_research_only(tmp_path,market):
    pair,lineage,members,roster=build(tmp_path,market)
    sources=[p for side in pair for p in (side[0],side[2],side[3])]
    sources.extend([lineage,roster])
    before={str(p):sha(p) for p in sources}
    result=strict(pair,lineage,members,roster,market)
    assert result["status"]=="LOCAL_CANDIDATE_PIT_PAIR_MATCHED_WATCH_RESEARCH_ONLY"
    assert result["research_watch_allowed"] is True
    assert result["exchange_roster_required"] is True
    assert result["exchange_roster_status"]=="LOCAL_THREE_DECLARED_SOURCES_COMPLETE_SCOPE_MATCH_NOT_CERTIFIED"
    assert result["exchange_roster_sha256"]==sha(roster)
    assert len(result["exchange_roster_evidence_sha256"])==64
    assert result["exchange_roster_locally_matched_classes"]==1
    assert result["require_original_first_ingest_pins"] is True
    assert result["historic_membership_pit_certified"] is False
    assert result["official_leader_promotions"]==0
    assert result["official_candidate_promotion_allowed"] is False
    assert str(roster) not in json.dumps(result)
    assert list(members)[0] not in json.dumps(result)
    assert before=={str(p):sha(p) for p in sources}


@pytest.mark.parametrize("market",["KR","US"])
def test_full_roster_hidden_extra_class_blocks_actual_candidate_not_just_roster_standalone(tmp_path,market):
    pair,lineage,members,roster=build(tmp_path,market)
    extra=("KR:CORP99999999:ISSUE:UNREPORTED" if market=="KR"
           else "US:CIK9999999999:CLASS:UNREPORTED")
    update(roster,lambda d:d["security_classes"].append({
        "security_id":extra,"ticker":"888888" if market=="KR" else "ZXY",
        "valid_from":"2020-01-01","valid_to":None,
    }))
    result=strict(pair,lineage,members,roster,market)
    assert result["research_watch_allowed"] is False
    assert result["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert result["blocker_counts"]["EXCHANGE_ROSTER_EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE"]==1
    assert result["official_leader_promotions"]==0


@pytest.mark.parametrize("mutation,expected",[
    (lambda d:d["security_classes"][0].update(ticker="999999"),"EXCHANGE_CLASS_TICKER_CONFLICT"),
    (lambda d:d["security_classes"][0].update(valid_from="2010-01-01"),"EXCHANGE_CLASS_LISTING_INTERVAL_CONFLICT"),
    (lambda d:d.update(complete_scope_claimed=False),"ROSTER_NOT_CLAIMED_COMPLETE_EXCHANGE_SCOPE"),
    (lambda d:d.update(retrieved_at=(ASOF+timedelta(minutes=5)).isoformat()),"ROSTER_NOT_RETRIEVED_BY_DECISION"),
    (lambda d:d.update(publisher_id_claimed="CLAIMED_PUBLISHER_A"),"NOT_THREE_DISTINCT_CLAIMED_PUBLISHERS"),
])
def test_roster_discrepancy_late_vintage_and_same_publisher_blocks_watch(tmp_path,mutation,expected):
    pair,lineage,members,roster=build(tmp_path)
    update(roster,mutation)
    result=strict(pair,lineage,members,roster)
    assert result["research_watch_allowed"] is False
    assert result["exchange_roster_locally_matched_classes"]==0
    assert result["blocker_counts"]["EXCHANGE_ROSTER_"+expected]>=1
    assert result["historic_membership_pit_certified"] is False


def test_wrong_original_raw_sha_refuses_before_watch_even_for_locally_matching_roster(tmp_path):
    pair,lineage,members,roster=build(tmp_path)
    before=roster.read_bytes()
    with pytest.raises(ValueError,match="roster.*SHA|SHA.*roster"):
        strict(pair,lineage,members,roster,pin="f"*64)
    assert roster.read_bytes()==before


@pytest.mark.parametrize("bad",["missing_pin","missing_roster","no_lineage","no_first_pin","bad_sha"])
def test_incomplete_third_roster_gate_cannot_downgrade_to_weak_pair(tmp_path,bad):
    pair,lineage,members,roster=build(tmp_path)
    params={
        "market":"KR","decision_at":DECISION,"candidate_members":members,"clock":AUDIT,
        "require_original_pins":True,"original_sources":orig(pair),
        "issuer_lineage_file":lineage,"exchange_roster_file":roster,
        "exchange_roster_sha256":sha(roster),
    }
    if bad=="missing_pin":params["exchange_roster_sha256"]=None
    elif bad=="missing_roster":params["exchange_roster_file"]=None
    elif bad=="no_lineage":params["issuer_lineage_file"]=None
    elif bad=="no_first_pin":
        params["require_original_pins"]=False
        params["original_sources"]=None
    else:params["exchange_roster_sha256"]="not_a_sha"
    with pytest.raises(ValueError,match="roster|first-ingest|SHA|lineage"):
        audit_candidate_provider_gate(
            pair[0][0],pair[0][1],pair[1][0],pair[1][1],**params)


def test_roster_same_content_reserialized_but_re_pinned_changes_provenance_digest(tmp_path):
    pair,lineage,members,roster=build(tmp_path)
    first=strict(pair,lineage,members,roster)
    roster.write_bytes(roster.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="SHA"):
        strict(pair,lineage,members,roster,pin=first["exchange_roster_sha256"])
    second=strict(pair,lineage,members,roster)
    assert second["research_watch_allowed"] is True
    assert first["source_pair_digest_sha256"]!=second["source_pair_digest_sha256"]
    assert first["exchange_roster_sha256"]!=second["exchange_roster_sha256"]


def test_roster_mutation_during_multiple_checks_halts_watch_issuance(tmp_path,monkeypatch):
    import eraleader.provider_candidate_gate as mod
    pair,lineage,members,roster=build(tmp_path)
    initial=mod.audit_declared_exchange_roster
    calls=[0]
    def switch(*args,**kwargs):
        report=initial(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            roster.write_bytes(roster.read_bytes()+b" ")
        return report
    monkeypatch.setattr(mod,"audit_declared_exchange_roster",switch)
    with pytest.raises((ValueError,RuntimeError),match="roster|SHA|changed|revised"):
        strict(pair,lineage,members,roster)
    assert calls[0] in (1,2)


@pytest.mark.parametrize("extra",[
    ["--require-provider-exchange-roster"],
    ["--provider-exchange-roster","missing.json"],
    ["--provider-exchange-roster-sha256","a"*64],
    ["--require-provider-exchange-roster","--provider-exchange-roster","missing.json"],
    ["--require-provider-exchange-roster","--provider-exchange-roster-sha256","a"*64],
])
def test_cli_missing_strict_roster_flags_rejected_before_source_file_created(tmp_path,capsys,extra):
    dest=tmp_path/"empty"
    dest.mkdir()
    with pytest.raises(SystemExit) as exc:
        main(["offline-integrated","--market","KR","--as-of",DECISION,
              "--out",str(dest),*extra])
    assert exc.value.code==2
    assert "exchange roster" in capsys.readouterr().err.lower()
    assert not (dest/"offline.sqlite").exists()
    assert not (dest/"runs").exists()
    assert not (dest/"prospective.sqlite").exists()


def test_cli_exact_whole_market_gate_before_successful_first_watch_and_run(tmp_path,capsys):
    pair,lineage,members,roster=build(tmp_path)
    dest=tmp_path/"out"
    dest.mkdir()
    import_provider_bundle(pair[0][3],dest/"offline.sqlite",clock=NOW)
    before=sha(dest/"offline.sqlite")
    main(["offline-integrated","--market","KR","--as-of",DECISION,
          "--out",str(dest),*cli_flags(pair,lineage,roster)])
    summary=json.loads(capsys.readouterr().out)
    assert summary["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert summary["new_prospective_research_signals"]==1
    assert summary["official_leaders"]==0
    detail=json.loads((dest/"provider_candidate_gate_research.json").read_text())
    assert detail["exchange_roster_required"] is True
    assert detail["exchange_roster_status"]=="LOCAL_THREE_DECLARED_SOURCES_COMPLETE_SCOPE_MATCH_NOT_CERTIFIED"
    assert detail["research_watch_allowed"] is True
    assert detail["official_candidate_promotion_allowed"] is False
    with sqlite3.connect(dest/"prospective.sqlite") as db:
        assert db.execute("SELECT count(*) FROM prospective_signals").fetchone()[0]==1
    assert sha(dest/"offline.sqlite")==before


def test_cli_extra_off_roster_class_blocks_without_watch_or_run(tmp_path,capsys):
    pair,lineage,members,roster=build(tmp_path)
    update(roster,lambda d:d["security_classes"].append({
        "security_id":"KR:CORP99999999:ISSUE:FAKE",
        "ticker":"999999","valid_from":"2020-01-01","valid_to":None,
    }))
    dest=tmp_path/"out"
    dest.mkdir()
    import_provider_bundle(pair[0][3],dest/"offline.sqlite",clock=NOW)
    previous=sha(dest/"offline.sqlite")
    main(["offline-integrated","--market","KR","--as-of",DECISION,
          "--out",str(dest),*cli_flags(pair,lineage,roster)])
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert response["new_prospective_research_signals"]==0
    assert response["blocker_counts"]["EXCHANGE_ROSTER_EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE"]==1
    assert not (dest/"prospective.sqlite").exists()
    assert not (dest/"runs").exists()
    assert sha(dest/"offline.sqlite")==previous


def test_cli_bad_roster_sha_never_writes_gate_or_watch(tmp_path,capsys):
    pair,lineage,members,roster=build(tmp_path)
    dest=tmp_path/"out";dest.mkdir()
    import_provider_bundle(pair[0][3],dest/"offline.sqlite",clock=NOW)
    flags=cli_flags(pair,lineage,roster)
    flags[flags.index("--provider-exchange-roster-sha256")+1]="0"*64
    with pytest.raises(SystemExit) as exc:
        main(["offline-integrated","--market","KR","--as-of",DECISION,
              "--out",str(dest),*flags])
    assert exc.value.code==2
    assert "SHA" in capsys.readouterr().err
    assert not (dest/"prospective.sqlite").exists()
    assert not (dest/"provider_candidate_gate_research.json").exists()


def test_cli_quality_page_explains_exchange_missing_class_without_issuing_watch(
    tmp_path,capsys,
):
    pair,lineage,members,roster=build(tmp_path)
    update(roster,lambda d:d["security_classes"].append({
        "security_id":"KR:CORP99999999:ISSUE:EXTRA",
        "ticker":"999999","valid_from":"2018-01-01","valid_to":None,
    }))
    dest=tmp_path/"out";dest.mkdir()
    import_provider_bundle(pair[0][3],dest/"offline.sqlite",clock=NOW)
    main(["offline-integrated","--market","KR","--as-of",DECISION,
          "--out",str(dest),*cli_flags(pair,lineage,roster),
          "--show-provider-gate-quality"])
    response=json.loads(capsys.readouterr().out)
    assert response["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert response["new_prospective_research_signals"]==0
    page=Path(response["provider_quality_dashboard"])
    assert page.is_file()
    html=page.read_text()
    assert "EXCHANGE_ROSTER_EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE" in html
    assert "공식" in html
    assert "EXTRA" not in html
    assert not (dest/"prospective.sqlite").exists()
    assert not (dest/"runs").exists()


def test_original_unflagged_watch_gate_keeps_exact_legacy_public_contract(tmp_path):
    pair,lineage,members,roster=build(tmp_path)
    legacy=audit_candidate_provider_gate(
        pair[0][0],pair[0][1],pair[1][0],pair[1][1],
        market="KR",decision_at=DECISION,candidate_members=members,
        require_original_pins=True,original_sources=orig(pair),
        issuer_lineage_file=lineage,clock=AUDIT)
    assert legacy["research_watch_allowed"] is True
    assert "exchange_roster_required" not in legacy
    assert "exchange_roster_sha256" not in legacy
    strict_result=strict(pair,lineage,members,roster)
    assert strict_result["research_watch_allowed"] is True
    assert strict_result["source_pair_digest_sha256"]!=legacy["source_pair_digest_sha256"]
