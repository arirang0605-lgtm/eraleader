"""Fail-closed optional provider-PIT check *before* candidate WATCH publication.

Only local research-screen observation is allowed even for an all-matching
claimed pair. Never treat matching user-supplied publisher names or SHA values
as official PIT, independent issuer ID, or leadership certification.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import re

from .frozen_holdout import _stamp
from .issuer_candidate_evidence import audit_candidate_issuer_class
from .exchange_roster_crosscheck import (
    audit_declared_exchange_roster, _read_roster,
    MATCH as EXCHANGE_ROSTER_MATCH,
)
from .provider_dual_source_audit import (
    STATUS_CONSISTENT,_full_receipt_source,_membership_asof,_latest,
    audit_provider_source_pair,ZONES,
)

GATE_WATCH="LOCAL_CANDIDATE_PIT_PAIR_MATCHED_WATCH_RESEARCH_ONLY"
GATE_BLOCK="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"


def audit_candidate_provider_gate(
    ledger_a:Path,bundle_a:str,ledger_b:Path,bundle_b:str, *,
    market:str,decision_at:str,candidate_members:dict,
    candidate_facts:list|None=None,candidate_industry:list|None=None,
    candidate_actions:list|None=None,
    clock:datetime|None=None,
    require_original_pins:bool=False,
    original_sources:tuple[tuple[Path,Path],tuple[Path,Path]]|None=None,
    issuer_lineage_file:Path|None=None,
    exchange_roster_file:Path|None=None,
    exchange_roster_sha256:str|None=None,
) -> dict:
    """Gate a concrete set of then-visible candidate issuer memberships.

    Pair-level consistency alone is insufficient: the *exact* security ID,
    ticker, industry and as-of listing interval must match both source
    membership sets. Missing/bad sources lead to a block, not zero failures.
    """
    if issuer_lineage_file is not None and (not require_original_pins or original_sources is None):
        raise ValueError('Issuer-class candidate gate requires both original first-ingest PINs')
    # The third source must be bound to the very same pinned original A that
    # the provider+issuer candidate gate already accepted, never a parallel
    # self-declared summary that could silently weaken WATCH proof.
    if (exchange_roster_file is None)!=(exchange_roster_sha256 is None):
        raise ValueError("Exchange roster and its raw SHA256 pin are required together")
    if exchange_roster_file is not None:
        if (not require_original_pins or original_sources is None or
                issuer_lineage_file is None):
            raise ValueError("Exchange roster needs strict original first-ingest PINs and issuer-class lineage")
        if (type(exchange_roster_sha256) is not str or
                not re.fullmatch(r"[0-9a-f]{64}",exchange_roster_sha256)):
            raise ValueError("Invalid pinned exchange roster SHA256")
        _,observed_pin=_read_roster(Path(exchange_roster_file))
        if observed_pin!=exchange_roster_sha256:
            raise ValueError("Exchange roster raw SHA256 does not match first-pinned evidence")
    if market not in ZONES:
        raise ValueError("Candidate evidence market must be KR/US")
    if not isinstance(candidate_members,dict):
        raise ValueError("Candidate membership map is required")
    if len(candidate_members)>50000:
        raise ValueError("Oversized candidate membership research batch")
    full_fields=(candidate_facts,candidate_industry,candidate_actions)
    if any(field is not None for field in full_fields) and not all(
        isinstance(field,list) for field in full_fields
    ):
        raise ValueError("All three candidate PIT domains are required together")
    full_check=all(isinstance(field,list) for field in full_fields)
    cutoff=_stamp(decision_at)
    paired=audit_provider_source_pair(
        Path(ledger_a),bundle_a,Path(ledger_b),bundle_b,
        decision_at=cutoff.isoformat(),clock=clock,sample_limit=50,
        require_original_pins=require_original_pins,
        original_sources=original_sources)
    if paired["market"]!=market:
        raise ValueError("Provider pair market differs from candidate market")
    issues=Counter()
    if paired["status"]!=STATUS_CONSISTENT:
        issues.update({"PAIR_"+key:count
                       for key,count in paired["blocker_counts"].items()})
        if not issues:
            issues["PROVIDER_PAIR_NOT_RESEARCH_CORROBORATED"]=1
    eligible=paired["status"]==STATUS_CONSISTENT and not issues
    matching=0
    if not candidate_members:
        issues["NO_CANDIDATES_TO_CORROBORATE"]+=1
    if eligible and candidate_members:
        local_date=cutoff.astimezone(ZONES[market]).date().isoformat()
        source_data=[
            _full_receipt_source(path,digest,cutoff)
            for path,digest in ((ledger_a,bundle_a),(ledger_b,bundle_b))
        ]
        sources=[
            _membership_asof(data["membership"],local_date)
            for data in source_data
        ]
        exited_by_source=[
            {action["security_id"] for action in data["actions"]
             if action["action_type"] in ("delist","merger") and
                action["effective_on"]<=local_date}
            for data in source_data
        ]
        for sec,member in sorted(candidate_members.items()):
            if (not isinstance(sec,str) or not sec or
                    not isinstance(member,dict) or
                    member.get("security_id")!=sec or
                    member.get("market")!=market):
                issues["INVALID_CANDIDATE_MEMBERSHIP_IDENTITY"]+=1
                continue
            ra,rb=(source.get(sec) for source in sources)
            if ra is None and rb is None:
                issues["CANDIDATE_MISSING_FROM_PROVIDER_A_AND_B"]+=1
                continue
            if ra is None:
                issues["CANDIDATE_MISSING_FROM_PROVIDER_A"]+=1
                continue
            if rb is None:
                issues["CANDIDATE_MISSING_FROM_PROVIDER_B"]+=1
                continue
            if any(
                member.get(field)!=ra.get(field) or
                member.get(field)!=rb.get(field)
                for field in ("ticker","industry_id","valid_from","valid_to")
            ):
                issues["CANDIDATE_ISSUER_FIELD_MISMATCH"]+=1
                continue
            if any(
                source.get("valid_to") is not None and
                source["valid_to"]<=local_date
                for source in (ra,rb)
            ):
                issues["CANDIDATE_ISSUER_NOT_ACTIVE_AT_DECISION"]+=1
                continue
            # Local membership date interval alone is not enough if an
            # announced delist/merger has already taken effect.
            if any(sec in exited for exited in exited_by_source):
                issues["CANDIDATE_HAS_KNOWN_DELIST_OR_MERGER_EXIT"]+=1
                continue
            matching+=1
        if full_check:
            # Compare the very facts consumed by the existing stage-3/4
            # research join against each source's then-published data.
            # Matching just an issuer's name/ticker would permit a corrupted
            # standalone revenue or action row to produce a false WATCH.
            relevant=set(candidate_members)
            industries={row["industry_id"] for row in candidate_members.values()
                        if isinstance(row,dict) and
                           isinstance(row.get("industry_id"),str)}
            domains=(
                ("FUNDAMENTAL",candidate_facts,"fundamentals",
                 ("security_id","metric","period_end"),relevant),
                ("INDUSTRY",candidate_industry,"industry",
                 ("industry_id","metric","period_end"),industries),
            )
            for label,original,db_kind,columns,scope in domains:
                local=_latest([r for r in original
                               if r.get(columns[0]) in scope],columns)
                feeds=[
                    _latest([r for r in data[db_kind]
                             if r.get(columns[0]) in scope],columns)
                    for data in source_data
                ]
                for key in sorted(set(local)|set(feeds[0])|set(feeds[1])):
                    row=local.get(key)
                    a=feeds[0].get(key)
                    b=feeds[1].get(key)
                    if row is None or a is None or b is None:
                        issues["CANDIDATE_"+label+"_COVERAGE_MISMATCH"]+=1
                    elif row["unit"]!=a["unit"] or row["unit"]!=b["unit"]:
                        issues["CANDIDATE_"+label+"_UNIT_MISMATCH"]+=1
                    elif row["value"]!=a["value"] or row["value"]!=b["value"]:
                        issues["CANDIDATE_"+label+"_VALUE_MISMATCH"]+=1
            # Delisted/exited companies are absent from today's candidate
            # membership, but their corporate actions still determine the
            # historic survivor-free universe. Never skip them here.
            action_scope=(
                relevant |
                {r["security_id"] for r in candidate_actions} |
                {r["security_id"] for data in source_data
                 for r in data["actions"]}
            )
            def actions_by_semantic(rows:list)->dict:
                latest=_latest([r for r in rows
                                if r.get("security_id") in action_scope],
                               ("security_id","action_id"))
                by_key={}
                for r in latest.values():
                    key=(r["security_id"],r["action_type"],r["effective_on"])
                    if key in by_key:
                        issues["CANDIDATE_ACTION_DUPLICATE_SEMANTIC_KEY"]+=1
                    by_key[key]=r
                return by_key
            local_actions=actions_by_semantic(candidate_actions)
            feed_actions=[actions_by_semantic(data["actions"])
                          for data in source_data]
            for key in sorted(set(local_actions)|set(feed_actions[0])|
                              set(feed_actions[1])):
                row=local_actions.get(key)
                a=feed_actions[0].get(key)
                b=feed_actions[1].get(key)
                if (row is None or a is None or b is None or
                        (row.get("ratio"),row.get("cash_amount"))
                        != (a.get("ratio"),a.get("cash_amount")) or
                        (row.get("ratio"),row.get("cash_amount"))
                        != (b.get("ratio"),b.get("cash_amount"))):
                    issues["CANDIDATE_ACTION_SOURCE_MISMATCH"]+=1
    issuer_class=None
    exchange_roster=None
    if issuer_lineage_file is not None and eligible:
        issuer_class=audit_candidate_issuer_class(
            Path(original_sources[0][0]),Path(issuer_lineage_file),
            market=market,decision_at=cutoff.isoformat(),
            candidate_members=candidate_members,clock=clock)
        issues.update({'ISSUER_CLASS_'+key:value
                       for key,value in issuer_class['blocker_counts'].items()})
    if exchange_roster_file is not None and eligible:
        exchange_roster=audit_declared_exchange_roster(
            Path(original_sources[0][0]),Path(issuer_lineage_file),
            Path(exchange_roster_file),decision_at=cutoff.isoformat(),clock=clock)
        if exchange_roster["declared_exchange_roster_sha256"]!=exchange_roster_sha256:
            raise ValueError("Exchange roster first-pinned raw SHA256 revised during audit")
        if exchange_roster["market"]!=market:
            raise ValueError("Exchange roster market differs from candidates")
        if exchange_roster["status"]!=EXCHANGE_ROSTER_MATCH:
            issues.update({"EXCHANGE_ROSTER_"+key:value for key,value in
                           exchange_roster["blocker_counts"].items()})
            if not exchange_roster["blocker_counts"]:
                issues["EXCHANGE_ROSTER_NOT_CORROBORATED"]+=1
    # A pair can change between the comparison and membership reads. Reuse
    # original receipt audit to fail-closed against detected revisions.
    if eligible:
        refreshed=audit_provider_source_pair(
            Path(ledger_a),bundle_a,Path(ledger_b),bundle_b,
            decision_at=cutoff.isoformat(),clock=clock,sample_limit=50,
            require_original_pins=require_original_pins,
            original_sources=original_sources)
        if refreshed!=paired:
            raise RuntimeError("Provider pair revised during candidate PIT gate")
        if issuer_class is not None:
            rechecked=audit_candidate_issuer_class(
                Path(original_sources[0][0]),Path(issuer_lineage_file),
                market=market,decision_at=cutoff.isoformat(),
                candidate_members=candidate_members,clock=clock)
            if rechecked!=issuer_class:
                raise RuntimeError('Issuer class evidence revised before WATCH publication')
        if exchange_roster is not None:
            rechecked_roster=audit_declared_exchange_roster(
                Path(original_sources[0][0]),Path(issuer_lineage_file),
                Path(exchange_roster_file),decision_at=cutoff.isoformat(),clock=clock)
            if rechecked_roster!=exchange_roster:
                raise RuntimeError("Exchange roster evidence revised before WATCH publication")
    if exchange_roster_file is not None:
        _,last_pin=_read_roster(Path(exchange_roster_file))
        if last_pin!=exchange_roster_sha256:
            raise ValueError("Exchange roster SHA256 revised before WATCH publication")
    allowed=bool(eligible and not issues and matching==len(candidate_members))
    provenance={
        "market":market,"decision_at":cutoff.isoformat(),
        "bundle_a":bundle_a,"bundle_b":bundle_b,
        "candidate_ids":sorted(candidate_members),
        "blocker_counts":dict(sorted(issues.items())),
        "matched":matching,
    }
    if require_original_pins:
        provenance["original_pin_pair_sha256"]=paired["original_source_pair_witness_sha256"]
    if issuer_lineage_file is not None:
        provenance['issuer_class_evidence_sha256']=(
            issuer_class['candidate_class_evidence_sha256'] if issuer_class is not None
            else 'PAIR_BLOCKED')
    if exchange_roster_file is not None:
        provenance["exchange_roster_raw_sha256"]=exchange_roster_sha256
        provenance["exchange_roster_audit_sha256"]=(
            exchange_roster["research_three_way_evidence_sha256"] if exchange_roster
            else "PAIR_BLOCKED")
    canonical=json.dumps(provenance,ensure_ascii=False,sort_keys=True,
                         separators=(",",":"),allow_nan=False)
    return {
        "status":GATE_WATCH if allowed else GATE_BLOCK,
        "market":market,"decision_at_utc":cutoff.isoformat(),
        "source_pair_status":paired["status"],
        "source_pair_bundle_sha256_a":bundle_a,
        "source_pair_bundle_sha256_b":bundle_b,
        "original_first_ingest_pins_locally_consistent":
            paired["original_first_ingest_pins_locally_consistent"],
        "source_pair_original_pin_sha256":
            paired["original_source_pair_witness_sha256"],
        "require_original_first_ingest_pins":require_original_pins,
        "issuer_class_bridge_required":issuer_lineage_file is not None,
        "issuer_class_bridge_status":(
            issuer_class['status'] if issuer_class is not None else
            ('NOT_EVALUATED_PAIR_BLOCKED' if issuer_lineage_file is not None else None)),
        "issuer_class_evidence_sha256":(
            issuer_class['candidate_class_evidence_sha256'] if issuer_class else None),
        "issuer_class_matched_candidates":(
            issuer_class['candidate_class_match_count'] if issuer_class else 0),
        "source_pair_digest_sha256":sha256(canonical.encode()).hexdigest(),
        "candidate_issuer_count":len(candidate_members),
        "locally_correlated_candidate_issuer_count":matching,
        "research_watch_allowed":allowed,
        "source_consistency_only":True,
        "source_pair_consistency_only":True,
        "local_claim_domains_checked":(
            ["membership","actions","fundamentals","industry"]
            if full_check else ["membership"]
        ),
        "blocker_counts":dict(sorted(issues.items())),
        "blocker_count":sum(issues.values()),
        "publisher_independently_authenticated":False,
        "legal_issuer_identity_independently_verified":False,
        "historic_membership_pit_certified":False,
        "official_candidate_promotion_allowed":False,
        "leader_accuracy_certified":False,
        "official_leader_promotions":0,
        **({
            "exchange_roster_required":True,
            "exchange_roster_sha256":exchange_roster_sha256,
            "exchange_roster_status":(
                exchange_roster["status"] if exchange_roster is not None
                else "NOT_EVALUATED_PAIR_BLOCKED"),
            "exchange_roster_evidence_sha256":(
                exchange_roster["research_three_way_evidence_sha256"]
                if exchange_roster is not None else None),
            "exchange_roster_locally_matched_classes":(
                exchange_roster["locally_matched_full_scope_classes"]
                if exchange_roster is not None else 0),
            "exchange_roster_historical_pit_certified":False,
        } if exchange_roster_file is not None else {}),
        "warning":(
            "A matched pair of claimed source identifiers is not official PIT "
            "proof. Local research WATCH may be generated only for exactly "
            "corroborated same-market issuer memberships; never a promoted "
            "leader, validated actual alpha, or trading recommendation."
        ),
    }
