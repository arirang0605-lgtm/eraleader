"""2_2/2_5: independent claimed legal issuer and stock-class crosscheck.

All provider, SEC/CIK and KRX/corp codes here are SYNTHETIC self-declarations.
Never certify a real permanent security ID or a historical trade.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader.issuer_class_bridge import audit_staged_issuer_class
from eraleader.provider_export_normalizer import _company_id
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_provider_export_normalizer import stage_fixture, rows_for, revise_stream

DECISION = "2026-10-11T14:30:00+09:00"
CLOCK = datetime(2026,10,11,7,tzinfo=timezone.utc)
PUBLISHER = "CLAIMED_SECOND_ISSUER_REGISTRY"


def fixture(tmp_path, market="KR", *, rows=None):
    manifest = stage_fixture(tmp_path/"staged", market=market, rows=rows)
    raw = rows or rows_for(market)
    stage = json.loads(manifest.read_text())
    identities = [{
        "record_id": "ROW_" + str(i),
        "security_id": _company_id(m,market),
        "ticker": m["stock_code"] if market=="KR" else m["ticker"],
        "market": market,
        "source_id": "OTHER_LEGAL_ENTITY_REGISTRY",
        "valid_from": m["listed_on"],
        "valid_to": m["delisted_on"],
        "known_at": m["published_at"],
        "revision": 1,
    } for i,m in enumerate(raw["membership"])]
    reference = {
        "schema_version": "eraleader.issuer_lineage_research.v1",
        "market":market,
        "source_id":"OTHER_LEGAL_ENTITY_REGISTRY",
        "publisher_id_claimed":PUBLISHER,
        "retrieved_at":"2026-10-11T14:05:00+09:00",
        "identities":identities,"events":[],
        "observed_tickers":[],
    }
    file=tmp_path/"issuer_class_lineage.json"
    file.write_text(json.dumps(reference,sort_keys=True))
    return manifest,file


def check(paths,*,decision=DECISION,clock=CLOCK):
    return audit_staged_issuer_class(*paths,decision_at=decision,clock=clock)


@pytest.mark.parametrize("market,required_prefix",[
    ("KR","KR:CORP00001234:ISSUE:ISSUE_A"),
    ("US","US:CIK0000012345:CLASS:CLASS_A"),
])
def test_exact_claimed_issuer_and_security_class_match_never_certifies_pit(
    tmp_path,market,required_prefix
):
    paths=fixture(tmp_path,market)
    before={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    result=check(paths)
    assert result["status"]=="LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert result["market"]==market
    assert result["matched_security_class_count"]==1
    assert result["matched_legal_entity_count"]==1
    assert result["unmatched_or_conflicted_count"]==0
    assert result["legal_issuer_or_class_independently_verified"] is False
    assert result["historical_universe_pit_certified"] is False
    assert result["official_candidate_promotion_allowed"] is False
    assert result["official_leader_promotions"]==0
    assert required_prefix not in json.dumps(result)  # no raw vendor ID in derived
    assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}


def test_two_legal_classes_under_same_us_cik_remain_two_securities(tmp_path):
    raw=rows_for("US")
    cls=deepcopy(raw["membership"][0])
    cls.update(share_class_uid="CLASS_B",ticker="EXA.B",source_document_id="SECOND_CLASS_VINTAGE")
    raw["membership"].append(cls)
    paths=fixture(tmp_path,"US",rows=raw)
    result=check(paths)
    assert result["status"]=="LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert result["matched_security_class_count"]==2
    assert result["matched_legal_entity_count"]==1


def test_ticker_only_join_with_different_class_is_rejected(tmp_path):
    manifest,reference=fixture(tmp_path,"US")
    data=json.loads(reference.read_text())
    data["identities"][0]["security_id"]="US:CIK0000012345:CLASS:DIFFERENT_CLASS"
    reference.write_text(json.dumps(data))
    result=check((manifest,reference))
    assert result["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["matched_security_class_count"]==0
    assert result["blocker_counts"]["TICKER_ONLY_DIFFERENT_SECURITY_CLASS"]>=1


def test_same_ticker_but_different_legal_issuer_is_not_auto_joined(tmp_path):
    manifest,reference=fixture(tmp_path,"KR")
    data=json.loads(reference.read_text())
    data["identities"][0]["security_id"]="KR:CORP99999999:ISSUE:ISSUE_A"
    reference.write_text(json.dumps(data))
    result=check((manifest,reference))
    assert result["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["matched_security_class_count"]==0
    assert result["blocker_counts"]["TICKER_ONLY_DIFFERENT_SECURITY_CLASS"]>=1


def test_same_permanent_class_but_different_ticker_is_blocked(tmp_path):
    manifest,reference=fixture(tmp_path,"KR")
    data=json.loads(reference.read_text())
    data["identities"][0]["ticker"]="999999"
    reference.write_text(json.dumps(data))
    result=check((manifest,reference))
    assert result["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["blocker_counts"]["SECURITY_CLASS_TICKER_CONFLICT"]==1


def test_one_side_only_class_cannot_become_complete_universe(tmp_path):
    manifest,reference=fixture(tmp_path)
    data=json.loads(reference.read_text())
    data["identities"][0]["security_id"]="KR:CORP00005678:ISSUE:ISSUE_A"
    data["identities"][0]["ticker"]="888888"
    reference.write_text(json.dumps(data))
    result=check((manifest,reference))
    assert result["matched_security_class_count"]==0
    assert result["blocker_counts"]["STAGED_ONLY_SECURITY_CLASS"]==1
    assert result["blocker_counts"]["ISSUER_LINEAGE_ONLY_SECURITY_CLASS"]==1


@pytest.mark.parametrize("reason,mutate",[
    ("STAGED_SOURCE_NOT_AVAILABLE_BY_DECISION", lambda stage,reference:
        revise_retrieved(stage,"2026-10-11T15:00:00+09:00")),
    ("ISSUER_LINEAGE_NOT_AVAILABLE_BY_DECISION", lambda stage,reference:
        alter_registry(reference,{"retrieved_at":"2026-10-11T15:00:00+09:00"})),
    ("DUPLICATE_CLAIMED_PUBLISHER", lambda stage,reference:
        alter_registry(reference,{"publisher_id_claimed":"SYNTHETIC_NOT_KRX_NOT_SEC"})),
    ("DUPLICATE_CLAIMED_SOURCE", lambda stage,reference:
        alter_registry(reference,{"source_id":"SYNTHETIC_STAGED_SOURCE"},identity_source=True)),
])
def test_retroactive_or_single_claimed_publisher_never_provides_pit_match(
    tmp_path,reason,mutate
):
    paths=fixture(tmp_path)
    mutate(*paths)
    result=check(paths)
    assert result["status"]=="CENSORED_STAGED_ISSUER_CLASS_SOURCE_NOT_INDEPENDENT_OR_PIT"
    assert result["matched_security_class_count"]==0
    assert result["blocker_counts"][reason]==1
    assert result["historical_universe_pit_certified"] is False


def revise_retrieved(manifest, value):
    data=json.loads(manifest.read_text())
    data["retrieved_at_claimed"]=value
    manifest.write_text(json.dumps(data))


def alter_registry(file,updates,*,identity_source=False):
    data=json.loads(file.read_text())
    data.update(updates)
    if identity_source:
        for item in data["identities"]:
            item["source_id"]=updates["source_id"]
    file.write_text(json.dumps(data))


def test_active_staged_delist_but_open_class_reference_is_blocked(tmp_path):
    paths=fixture(tmp_path)
    revise_stream(paths[0],"actions",lambda rows:rows.append({
        "corp_code":"00001234","issue_uid":"ISSUE_A","source_document_id":"DELIST_NOTICE",
        "revision":1,"published_at":"2026-09-01T12:00:00+09:00",
        "event_uid":"DELIST_1","action_type":"delist",
        "effective_on":"2026-10-01"
    }))
    result=check(paths)
    assert result["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["matched_security_class_count"]==0
    assert result["blocker_counts"]["STAGED_TERMINAL_EXIT_CONFLICT"]>=1


def test_future_announced_delist_keeps_issuer_active_until_effective_day(tmp_path):
    paths=fixture(tmp_path)
    revise_stream(paths[0],"actions",lambda rows:rows.append({
        "corp_code":"00001234","issue_uid":"ISSUE_A","source_document_id":"FUTURE_EXIT",
        "revision":1,"published_at":"2026-10-11T13:00:00+09:00",
        "event_uid":"FUTURE_DELIST_1","action_type":"delist",
        "effective_on":"2026-11-01",
    }))
    result=check(paths)
    assert result["status"]=="LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert result["matched_security_class_count"]==1


def test_late_published_issuer_revision_cannot_backfill_earlier_ticker(tmp_path):
    paths=fixture(tmp_path)
    data=json.loads(paths[1].read_text())
    data["retrieved_at"]="2026-10-11T15:05:00+09:00"
    revision=deepcopy(data["identities"][0])
    revision["revision"]=2
    revision["ticker"]="OTHER"
    revision["known_at"]="2026-10-11T14:50:00+09:00"
    data["identities"].append(revision)
    paths[1].write_text(json.dumps(data))
    result=check(paths)
    assert result["status"]=="CENSORED_STAGED_ISSUER_CLASS_SOURCE_NOT_INDEPENDENT_OR_PIT"
    assert result["matched_security_class_count"]==0


def test_original_issuer_class_source_sha_or_staged_stream_change_mid_audit_fails_closed(
    tmp_path,monkeypatch
):
    import eraleader.issuer_class_bridge as module
    paths=fixture(tmp_path)
    original=module._one_pass
    called=0
    def altered(*args,**kwargs):
        nonlocal called
        result=original(*args,**kwargs)
        called+=1
        if called==1:
            paths[1].write_bytes(paths[1].read_bytes()+b" ")
        return result
    monkeypatch.setattr(module,"_one_pass",altered)
    with pytest.raises(ValueError, match="changed|revised|original|source|SHA"):
        check(paths)


def test_staged_stream_rehashed_wrong_class_identity_is_never_accepted(tmp_path):
    paths=fixture(tmp_path,"US")
    revise_stream(paths[0],"membership",lambda rows:rows[0].update(share_class_uid="CLASS_MISMATCH"))
    result=check(paths)
    assert result["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["matched_security_class_count"]==0


def test_rejected_unsafe_source_symlink_and_duplicate_json_keys(tmp_path):
    manifest,reference=fixture(tmp_path)
    reference.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(ValueError, match="duplicate|Invalid|JSON"):
        check((manifest,reference))
    original=reference.parent/"other.json"
    reference.rename(original)
    reference.symlink_to(original)
    with pytest.raises(ValueError, match="link|unsafe|source"):
        check((manifest,reference))


def test_cli_writes_sanitized_derived_only_zip_and_restores(tmp_path):
    paths=fixture(tmp_path,"KR")
    before={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    out=tmp_path/"derived"
    cli=Path(__file__).resolve().parents[1]/"scripts"/"audit_issuer_class_bridge.py"
    result=subprocess.run([sys.executable,str(cli),
                           "--staged-manifest",str(paths[0]),
                           "--issuer-lineage",str(paths[1]),
                           "--decision-at",DECISION,"--out",str(out)],
                          capture_output=True,text=True,check=False)
    assert result.returncode==0,result.stderr
    report=json.loads((out/"issuer_class_corroboration_research.json").read_text())
    assert report["matched_security_class_count"]==1
    assert report["official_leader_promotions"]==0
    assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    backup=tmp_path/"backup"/"corroboration.zip"
    create_backup(out,backup)
    assert verify_backup(backup)["status"]=="LOCAL_BACKUP_VERIFIED"
    restored=tmp_path/"restored"
    restore_backup(backup,restored)
    assert (restored/"issuer_class_corroboration_research.json").read_bytes()==(
        out/"issuer_class_corroboration_research.json").read_bytes()


def test_closed_historical_ticker_owner_does_not_join_new_issuer(tmp_path):
    stage, reference=fixture(tmp_path,"KR")
    registry=json.loads(reference.read_text())
    old={
        "record_id":"PRIOR_TICKER_OWNER",
        "security_id":"KR:CORP99999999:ISSUE:OLD_CLASS",
        "ticker":"123456", "market":"KR",
        "source_id":registry["source_id"],
        "valid_from":"2020-01-01",
        "valid_to":"2024-01-01",
        "known_at":"2023-01-01T09:00:00+09:00","revision":1,
    }
    registry["identities"].append(old)
    reference.write_text(json.dumps(registry))
    report=check((stage,reference))
    assert report["status"]=="LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert report["matched_security_class_count"]==1
    assert report["matched_legal_entity_count"]==1


def test_same_ticker_two_current_share_classes_cannot_both_be_matched(tmp_path):
    data=rows_for("US")
    other=deepcopy(data["membership"][0])
    other.update(share_class_uid="CLASS_B",
                 source_document_id="SECOND_CLASS_ACTIVE")
    data["membership"].append(other)
    manifest,reference=fixture(tmp_path,"US",rows=data)
    report=check((manifest,reference))
    assert report["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert report["blocker_counts"]["STAGED_ACTIVE_TICKER_COLLISION"]==1
    assert report["blocker_counts"]["ISSUER_LINEAGE_ACTIVE_TICKER_COLLISION"]==1
    assert report["historical_universe_pit_certified"] is False


def test_both_sources_known_delist_effective_never_count_old_class(tmp_path):
    manifest,reference=fixture(tmp_path)
    revise_stream(manifest,"actions",lambda rows:rows.append({
        "corp_code":"00001234","issue_uid":"ISSUE_A",
        "source_document_id":"PAST_DELIST_2026",
        "revision":1,"published_at":"2026-09-01T12:00:00+09:00",
        "event_uid":"DELIST_TERM","action_type":"delist",
        "effective_on":"2026-10-01",
    }))
    registry=json.loads(reference.read_text())
    registry["events"].append({
        "event_id":"ISSUER_EXIT","security_id":registry["identities"][0]["security_id"],
        "action_type":"delist","source_id":registry["source_id"],
        "effective_on":"2026-10-01",
        "known_at":"2026-09-01T12:00:00+09:00",
    })
    reference.write_text(json.dumps(registry))
    report=check((manifest,reference))
    assert report["status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert report["matched_security_class_count"]==0
    assert report["blocker_counts"]["STAGED_TERMINAL_EXIT_CONFLICT"]==1
    assert report["blocker_counts"]["LINEAGE_TERMINAL_EXIT_CONFLICT"]==1


def test_us_market_local_dst_decision_uses_real_utc_cutoff(tmp_path):
    manifest,reference=fixture(tmp_path,"US")
    revise_retrieved(manifest,"2026-03-07T18:00:00-05:00")
    alter_registry(reference,{"retrieved_at":"2026-03-07T18:10:00-05:00"})
    report=check((manifest,reference),decision="2026-03-08T03:15:00-04:00")
    assert report["status"]=="LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert report["matched_security_class_count"]==1


def test_staged_original_jsonl_revision_between_two_reads_fails_closed(tmp_path,monkeypatch):
    import eraleader.issuer_class_bridge as mod
    manifest,reference=fixture(tmp_path)
    orig=mod._one_pass
    n=0
    def altered(*args,**kwargs):
        nonlocal n
        result=orig(*args,**kwargs)
        n+=1
        if n==1:
            raw=manifest.parent/"membership.jsonl"
            raw.write_bytes(raw.read_bytes()+b" ")
        return result
    monkeypatch.setattr(mod,"_one_pass",altered)
    with pytest.raises(ValueError,match="SHA|source|changed|revised"):
        check((manifest,reference))


def test_late_staged_membership_published_after_claimed_retrieval_fails_closed(tmp_path):
    manifest,ref=fixture(tmp_path)
    revise_stream(manifest,"membership",lambda rows:rows[0].update(
        published_at="2026-10-11T15:20:00+09:00"))
    with pytest.raises(ValueError,match="publication|retrieval|source|Staged"):
        check((manifest,ref))
