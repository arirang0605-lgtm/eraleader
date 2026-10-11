"""5_3/5_5 native first-WATCH-score gate for prospective top-K census.

Synthetic KR/US fixture only. Tests NEVER certify a real market issuer.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import sqlite3

import pytest

from eraleader.native_census_gate import (
    SCHEMA, register_native_census, audit_native_census,
)
from eraleader.ranked_discovery import _digest
from test_native_topk_freeze import fixture as make_native, freeze, NOW


def prepare(root: Path, *, market="KR"):
    root.mkdir(parents=True, exist_ok=True)
    b, rule, frozen = make_native(root, market=market)
    freeze(b, rule, frozen, market=market)
    source = root / "census_input.json"
    source.write_text(json.dumps([{
        "frozen": frozen.name, "definition": rule.name,
        "outcomes": "future_outcomes.json", "receipts": "future_receipts.json",
    }]))
    item = {
        "frozen_sha256": sha256(frozen.read_bytes()).hexdigest(),
        "score_ledger": str(b[4].absolute()),
        "watch_ledger": str(b[1].absolute()),
        "features_dir": str(b[2].absolute()),
    }
    return b, rule, frozen, source, item


def config(dest: Path, items: list[dict]) -> Path:
    dest.write_text(json.dumps({"schema_version": SCHEMA, "cohorts": items}, sort_keys=True))
    return dest


def register(source, registry, conf, name="census_native.json"):
    return register_native_census(
        source, registry, name, native_config=conf,
        clock=NOW+timedelta(minutes=2),
    )


def audit(registry, conf):
    return audit_native_census(
        registry, native_config=conf,
        evaluated_at=(NOW+timedelta(minutes=3)).isoformat(),
        clock=NOW+timedelta(minutes=4),
    )


def test_first_native_prospective_registration_and_all_registered_audit(tmp_path):
    b, rule, frozen, source, item = prepare(tmp_path/"original")
    conf = config(tmp_path/"native_provenance.json", [item])
    registry = tmp_path/"indexed_registry"
    originals = {str(p):sha256(p.read_bytes()).hexdigest() for p in (
        b[1],b[4],frozen,rule,b[2]/"A.json",b[2]/"B.json")}
    created=register(source,registry,conf)
    assert created["status"] == "LOCAL_NATIVE_FIRST_WRITE_CENSUS_REGISTERED_NOT_PIT_CERTIFIED"
    assert created["local_native_score_provenance_complete"] is True
    assert created["fully_native_bound_cohorts"]==1
    assert created["native_frozen_selected_count"]==1
    assert created["complete_positive_watch_first_scores"]==2
    assert created["receipt_index_entries"]==1
    result=audit(registry,conf)
    assert result["status"]=="LOCAL_ALL_NATIVE_PROSPECTIVE_COHORTS_AUDITED_NOT_CERTIFIED"
    assert result["frozen_selected_denominator"]==1
    assert result["unknown_or_censored"]==1
    assert result["complete_positive_watch_first_scores"]==2
    assert result["first_write_receipts_verified"] is True
    assert result["official_leader_promotions"]==0
    assert result["issuer_source_pit_independently_verified"] is False
    assert result["real_precision_at_k"] is None
    assert result["external_api_calls"]==0
    assert originals=={str(p):sha256(p.read_bytes()).hexdigest() for p in (
        b[1],b[4],frozen,rule,b[2]/"A.json",b[2]/"B.json")}


def test_ordinary_rank_without_native_binding_is_refused_before_first_registration(tmp_path):
    b, rule, frozen, source, item = prepare(tmp_path/"original")
    body=json.loads(frozen.read_text())
    del body["native_cohort_binding"]
    body["content_sha256"]=_digest({k:v for k,v in body.items() if k!="content_sha256"})
    frozen.write_text(json.dumps(body,sort_keys=True))
    item["frozen_sha256"]=sha256(frozen.read_bytes()).hexdigest()
    conf=config(tmp_path/"sources.json",[item])
    registry=tmp_path/"registry"
    with pytest.raises(ValueError,match="binding|native|score"):
        register(source,registry,conf)
    assert not (registry/"census_native.json").exists()


@pytest.mark.parametrize("mode",["missing","extra","wrong_sha","duplicate_sha"])
def test_original_native_source_config_must_cover_exactly_the_cohorts(tmp_path,mode):
    *_, source, item=prepare(tmp_path/"original")
    if mode=="missing": rows=[]
    elif mode=="extra": rows=[item,{**item,"frozen_sha256":"f"*64}]
    elif mode=="wrong_sha": rows=[{**item,"frozen_sha256":"f"*64}]
    else: rows=[item,item]
    conf=config(tmp_path/"sources.json",rows)
    with pytest.raises(ValueError,match="source|config|cohort|SHA|Duplicate|invalid|exact|native"):
        register(source,tmp_path/"registry",conf)
    assert not (tmp_path/"registry"/"census_native.json").exists()


def test_changed_original_feature_byte_prevents_first_registration(tmp_path):
    b, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    p=b[2]/"A.json"
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError,match="feature|formula|source|provenance"):
        register(source,tmp_path/"registry",conf)
    assert not (tmp_path/"registry"/"census_native.json").exists()


def test_post_registration_feature_revision_blocks_native_evaluation(tmp_path):
    b, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    registry=tmp_path/"registry"
    register(source,registry,conf)
    p=b[2]/"B.json"
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError,match="feature|formula|source|provenance"):
        audit(registry,conf)
    assert (registry/"census_native.json").exists()


def test_deleted_score_witness_after_registration_blocks_evaluation(tmp_path):
    b, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    registry=tmp_path/"registry"
    register(source,registry,conf)
    with sqlite3.connect(b[4]) as db:
        db.execute("DELETE FROM rank_score_events WHERE security_id='A'")
    with pytest.raises(ValueError,match="score|native|source|coverage"):
        audit(registry,conf)


def test_missing_watch_ledger_blocks_first_write(tmp_path):
    b, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    b[1].unlink()
    with pytest.raises(ValueError,match="WATCH|ledger|Missing"):
        register(source,tmp_path/"registry",conf)


def test_invalid_config_and_symlink_refused(tmp_path):
    *_, source, item=prepare(tmp_path/"original")
    original=config(tmp_path/"config.json",[item])
    linked=tmp_path/"linked.json"
    linked.symlink_to(original)
    with pytest.raises(ValueError,match="unsafe|source configuration"):
        register(source,tmp_path/"registry",linked)
    original.write_text('{"schema_version":"x","schema_version":"x","cohorts":[]}')
    with pytest.raises(ValueError,match="Duplicate|JSON|config"):
        register(source,tmp_path/"registry",original)


def test_untrusted_remote_source_path_refused_not_fetched(tmp_path):
    *_, source, item=prepare(tmp_path/"original")
    item["features_dir"]="https://untrusted.example.org/features"
    conf=config(tmp_path/"config.json",[item])
    with pytest.raises(ValueError,match="absolute safe local"):
        register(source,tmp_path/"registry",conf)


def test_multi_market_all_registered_native_audit_requires_both_config_rows(tmp_path):
    kr=prepare(tmp_path/"kr",market="KR")
    us=prepare(tmp_path/"us",market="US")
    registry=tmp_path/"registry"
    register(kr[3],registry,config(tmp_path/"kr.json",[kr[4]]),"census_kr.json")
    register(us[3],registry,config(tmp_path/"us.json",[us[4]]),"census_us.json")
    with pytest.raises(ValueError,match="EXACTLY|all|cohort"):
        audit(registry,config(tmp_path/"missing_us.json",[kr[4]]))
    both=config(tmp_path/"both.json",[kr[4],us[4]])
    report=audit(registry,both)
    assert report["registered_cohort_count"]==2
    assert report["registered_market_cohort_counts"]=={"KR":1,"US":1}
    assert report["frozen_selected_denominator"]==2
    assert report["unknown_or_censored"]==2
    assert report["fully_native_bound_cohorts"]==2
    assert report["complete_positive_watch_first_scores"]==4


def test_recomputed_registry_sha_still_cannot_fake_native_provenance(tmp_path):
    b, _, frozen, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    registry=tmp_path/"registry"
    register(source,registry,conf)
    original=frozen.read_bytes()
    # A locally re-hashed frozen file must fail the strict registry/index digest.
    body=json.loads(original)
    body["model_version"]="UNVERIFIED_ALTERNATIVE"
    body["content_sha256"]=_digest({k:v for k,v in body.items() if k!="content_sha256"})
    frozen.write_text(json.dumps(body,sort_keys=True))
    with pytest.raises(ValueError,match="SHA|mismatch|source|native|no longer matches"):
        audit(registry,conf)


def test_cli_native_option_requires_index_and_keeps_legacy_mode(tmp_path,monkeypatch,capsys):
    *_, source, item=prepare(tmp_path/"original")
    config_path=config(tmp_path/"paths.json",[item])
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_census.py"
    spec=importlib.util.spec_from_file_location("native_census_cli",script)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registry=tmp_path/"registry"
    with pytest.raises(ValueError,match="receipt-index"):
        module.main(["register","--spec",str(source),"--registry-dir",str(registry),
                     "--name","census_native.json",
                     "--native-evidence-config",str(config_path)])
    from eraleader import native_census_gate as gate
    original_register=gate.register_native_census
    monkeypatch.setattr(gate,"register_native_census",lambda *a,**kw:
                        original_register(*a,**dict(kw,clock=NOW+timedelta(minutes=2))))
    assert module.main(["register","--spec",str(source),"--registry-dir",str(registry),
                        "--name","census_native.json","--receipt-index",
                        "--native-evidence-config",str(config_path)])==0
    original_audit=gate.audit_native_census
    monkeypatch.setattr(gate,"audit_native_census",lambda *a,**kw:
                        original_audit(*a,**dict(kw,clock=NOW+timedelta(minutes=4))))
    output=tmp_path/"derived"
    assert module.main(["audit","--registry-dir",str(registry),
                        "--evaluated-at",(NOW+timedelta(minutes=3)).isoformat(),
                        "--out",str(output),"--receipt-index",
                        "--native-evidence-config",str(config_path)])==0
    report=json.loads((output/"prospective_census_research.json").read_text())
    assert report["local_native_score_provenance_complete"] is True
    assert report["real_precision_at_k"] is None
    assert report["official_leader_promotions"]==0
    assert "UNVERIFIED_ALTERNATIVE" not in capsys.readouterr().out


def test_mutation_mid_native_source_audit_fails_closed(tmp_path,monkeypatch):
    b, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"config.json",[item])
    root=tmp_path/"registry"
    register(source,root,conf)
    from eraleader import native_census_gate as mod
    original=mod._preflight
    calls=[0]
    def manipulated(*args,**kwargs):
        report=original(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            p=b[2]/"A.json"
            p.write_bytes(p.read_bytes()+b" ")
        return report
    monkeypatch.setattr(mod,"_preflight",manipulated)
    with pytest.raises(ValueError,match="feature|source|formula|provenance"):
        audit(root,conf)


def test_native_strict_marker_prevents_downgrade_in_cli(tmp_path):
    _, _, _, source, item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    root=tmp_path/"registry"
    register(source,root,conf)
    from eraleader.native_census_gate import native_gate_marker, NATIVE_MARKER
    assert json.loads(native_gate_marker(root).read_text())==NATIVE_MARKER
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_census.py"
    spec=importlib.util.spec_from_file_location("native_census_no_downgrade",script)
    cli=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    with pytest.raises(ValueError,match="native-evidence-config|downgrade"):
        cli.main(["audit","--registry-dir",str(root),
                  "--evaluated-at",(NOW+timedelta(minutes=3)).isoformat(),
                  "--receipt-index","--out",str(tmp_path/"weak_result")])
    assert not (tmp_path/"weak_result"/"prospective_census_research.json").exists()


def test_existing_indexed_non_native_registry_cannot_upgrade_later(tmp_path):
    from eraleader.prospective_census_seal import indexed_register_census
    _,_,_,source,item=prepare(tmp_path/"original")
    root=tmp_path/"registry"
    indexed_register_census(source,root,"census_first.json",
                            clock=NOW+timedelta(minutes=1))
    conf=config(tmp_path/"sources.json",[item])
    with pytest.raises(ValueError,match="retroactively|unpinned"):
        register_native_census(source,root,"census_native.json",
                               native_config=conf,clock=NOW+timedelta(minutes=2))
    assert not (root/"census_native.json").exists()


@pytest.mark.parametrize("mutation",["missing","changed","linked"])
def test_native_mode_requirement_deleted_or_tampered_fails_closed(tmp_path,mutation):
    _,_,_,source,item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    root=tmp_path/"registry"
    register(source,root,conf)
    from eraleader.native_census_gate import native_gate_marker
    marker=native_gate_marker(root)
    if mutation=="missing":
        marker.unlink()
    elif mutation=="changed":
        marker.write_bytes(marker.read_bytes()+b" ")
    else:
        original=tmp_path/"marker-original.json"
        original.write_bytes(marker.read_bytes())
        marker.unlink()
        marker.symlink_to(original)
    with pytest.raises(ValueError,match="native|Missing|linked|requirement"):
        audit(root,conf)


def test_orphan_strict_mode_marker_after_registration_crash_cannot_downgrade(tmp_path,monkeypatch):
    _,_,_,source,item=prepare(tmp_path/"original")
    conf=config(tmp_path/"sources.json",[item])
    root=tmp_path/"registry"
    from eraleader import native_census_gate as gate
    def failed(*args,**kwargs):
        raise RuntimeError("simulated first receipt crash")
    monkeypatch.setattr(gate,"indexed_register_census",failed)
    with pytest.raises(RuntimeError,match="simulated"):
        register(source,root,conf)
    from eraleader.native_census_gate import native_gate_marker
    assert native_gate_marker(root).is_file()
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_census.py"
    spec=importlib.util.spec_from_file_location("native_census_crash_guard",script)
    cli=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    with pytest.raises(ValueError,match="native-evidence-config"):
        cli.main(["register","--spec",str(source),"--registry-dir",str(root),
                  "--name","census_fallback.json"])
    assert not (root/"census_fallback.json").exists()
