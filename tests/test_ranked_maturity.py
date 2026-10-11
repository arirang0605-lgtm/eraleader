"""5_3/5_5/6_2: Native Top-K maturity inventory. All inputs synthetic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from threading import Thread
from zoneinfo import ZoneInfo
import json
import sqlite3
import urllib.request

import pytest

from eraleader.ranked_maturity import audit_ranked_maturity
from eraleader.delivery import (
    render_ranked_maturity_dashboard, write_ranked_maturity_dashboard,
)
from eraleader.ranked_discovery import _frozen, _digest, _canonical
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from eraleader.cli import main

from test_native_topk_freeze import fixture, freeze, LABEL, NOW, MODEL
from test_rank_score_ledger import WRITE

UTC=timezone.utc
MAX=NOW+timedelta(days=300)


def setup(tmp_path,market="KR",k=1):
    b,rule,out=fixture(tmp_path,market=market)
    if k==1:
        freeze(b,rule,out,market=market)
    else:
        from eraleader.native_topk_freeze import freeze_native_topk
        freeze_native_topk(b[4],b[1],b[2],rule,out,
                           market=market,model_version=MODEL,
                           label_definition_id=LABEL,
                           horizon_days=180,k=k,clock=NOW)
    return b,rule,out


def evaluate(files, at=NOW, *, clock=MAX, sample_limit=100):
    b,rule,out=files
    return audit_ranked_maturity(
        out,rule,b[4],b[1],b[2],
        as_of=at.isoformat(),clock=clock,sample_limit=sample_limit)


def deadline(market,files):
    frozen=_frozen(files[2])
    z=ZoneInfo("Asia/Seoul" if market=="KR" else "America/New_York")
    local=datetime.fromisoformat(frozen["snapshot_at_utc"]).astimezone(z)
    return (local+timedelta(days=180)).astimezone(UTC)


@pytest.mark.parametrize("market",["KR","US"])
def test_frozen_native_cohort_pending_with_no_future_labels(tmp_path,market):
    files=setup(tmp_path,market)
    before={str(p):sha256(p.read_bytes()).hexdigest()
            for p in (files[0][1],files[0][4],files[2],files[1])}
    result=evaluate(files)
    assert result["status"]=="LOCAL_RANKED_MATURITY_INVENTORY_NOT_CERTIFIED"
    assert result["market"]==market
    assert result["selected_top_k_count"]==1
    assert result["full_horizon_pending_count"]==1
    assert result["full_horizon_elapsed_count"]==0
    assert result["awaiting_mature_outcome_evidence_count"]==0
    assert result["next_horizon_end_utc"]==deadline(market,files).isoformat()
    assert result["local_native_provenance_rechecked"] is True
    assert result["frozen_first_score_count"]==2
    assert result["predeclared_rule_sha256_verified"] is True
    assert result["retrospective_freeze"] is False
    assert result["known_positive_leaders"] is None
    assert result["known_failures"] is None
    assert result["precision_at_k"] is None
    assert result["recall_at_k"] is None
    assert result["official_leader_promotions"]==0
    assert result["actual_future_leader_skill_certified"] is False
    assert result["outcome_labels_read"] is False
    assert result["selected_candidate_sample"][0]["status"]=="HORIZON_PENDING"
    assert {str(p):sha256(Path(p).read_bytes()).hexdigest()
            for p in before}==before


@pytest.mark.parametrize("market",["KR","US"])
def test_exact_market_clock_horizon_including_us_dst(tmp_path,market):
    files=setup(tmp_path,market=market)
    end=deadline(market,files)
    before=evaluate(files,at=end-timedelta(microseconds=1))
    on=evaluate(files,at=end)
    assert before["full_horizon_pending_count"]==1
    assert before["full_horizon_elapsed_count"]==0
    assert before["selected_candidate_sample"][0]["status"]=="HORIZON_PENDING"
    assert on["full_horizon_pending_count"]==0
    assert on["full_horizon_elapsed_count"]==1
    assert on["awaiting_mature_outcome_evidence_count"]==1
    assert on["selected_candidate_sample"][0]["status"]=="HORIZON_ELAPSED_OUTCOME_UNKNOWN"
    assert on["precision_at_k"] is None
    assert on["source_document_outcome_corroborated"] is False
    assert on["next_horizon_end_utc"] is None


def test_missing_labels_cannot_be_interpreted_as_negative(tmp_path):
    files=setup(tmp_path,k=2)
    report=evaluate(files,at=deadline("KR",files)+timedelta(days=20))
    assert report["full_horizon_elapsed_count"]==2
    assert report["awaiting_mature_outcome_evidence_count"]==2
    assert report["known_failures"] is None
    assert report["precision_at_k"] is None
    assert report["selected_top_k_count"]==2
    assert report["selected_candidate_sample"][0]["rank"]==1
    assert report["selected_candidate_sample"][1]["rank"]==2


def test_sample_limit_never_reduces_denominator(tmp_path):
    files=setup(tmp_path,k=2)
    result=evaluate(files,sample_limit=1)
    assert len(result["selected_candidate_sample"])==1
    assert result["selected_top_k_count"]==2
    assert result["sample_truncated"] is True
    assert result["full_horizon_pending_count"]==2


def test_malformed_or_missing_predeclared_label_rule_blocked(tmp_path):
    files=setup(tmp_path)
    files[1].write_text('{"post_hoc_rewrite":true}')
    with pytest.raises(ValueError,match="rule|label|predeclared|SHA"):
        evaluate(files)


def test_missing_score_original_or_tampered_feature_blocked(tmp_path):
    files=setup(tmp_path)
    feature=files[0][2]/"A.json"
    feature.write_text('{"future_new":true}')
    with pytest.raises(ValueError,match="formula|feature|native|score|Source"):
        evaluate(files)


def test_missing_original_watch_proof_blocks_maturity(tmp_path):
    files=setup(tmp_path)
    with sqlite3.connect(files[0][1]) as db:
        db.execute("DELETE FROM prospective_signals WHERE security_id='A'")
    with pytest.raises(ValueError,match="WATCH|watch|native|formula|source"):
        evaluate(files)


def test_rehashed_numeric_score_modified_without_formula_blocked(tmp_path):
    files=setup(tmp_path)
    with sqlite3.connect(files[0][4]) as db:
        text=db.execute("SELECT payload FROM rank_score_events WHERE security_id='B'").fetchone()[0]
        obj=json.loads(text)
        obj["score"]=80.0
        serialized=_canonical(obj).decode()
        db.execute("UPDATE rank_score_events SET payload=?,evidence_hash=? WHERE security_id='B'",
                   (serialized,sha256(serialized.encode()).hexdigest()))
    with pytest.raises(ValueError,match="formula|native|hash|score|source|witness"):
        evaluate(files)


def test_rehashed_cohort_binding_digest_wrong_rejected(tmp_path):
    files=setup(tmp_path)
    obj=json.loads(files[2].read_text())
    obj["native_cohort_binding"]["watch_score_evidence_sha256"]="0"*64
    obj["content_sha256"]=_digest({k:v for k,v in obj.items() if k!="content_sha256"})
    files[2].write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="cohort|witness|hash"):
        evaluate(files)


def test_legacy_rank_without_native_cohort_blocked(tmp_path):
    files=setup(tmp_path)
    obj=json.loads(files[2].read_text())
    obj.pop("native_cohort_binding")
    obj["content_sha256"]=_digest({k:v for k,v in obj.items() if k!="content_sha256"})
    files[2].write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="native|cohort"):
        evaluate(files)


def test_retrospective_seal_cannot_claim_future_prediction(tmp_path):
    files=setup(tmp_path)
    obj=json.loads(files[2].read_text())
    snap=datetime.fromisoformat(obj["snapshot_at_utc"])
    obj["frozen_at_utc"]=(snap+timedelta(hours=4)).isoformat()
    obj["retrospective_freeze"]=True
    obj["content_sha256"]=_digest({k:v for k,v in obj.items() if k!="content_sha256"})
    files[2].write_text(json.dumps(obj))
    future=evaluate(files,at=deadline("KR",files)+timedelta(days=1))
    assert future["retrospective_freeze"] is True
    assert future["prospective_maturity_eligible"] is False
    assert future["selected_candidate_sample"][0]["status"]=="RETROSPECTIVE_SEAL_NOT_A_PREDICTION"
    assert future["precision_at_k"] is None


def test_asof_future_and_before_actual_seal_rejected(tmp_path):
    files=setup(tmp_path)
    with pytest.raises(ValueError,match="future|clock"):
        evaluate(files,at=MAX+timedelta(seconds=1))
    with pytest.raises(ValueError,match="seal|freeze|before"):
        evaluate(files,at=NOW-timedelta(seconds=1))


def test_html_injection_cannot_claim_leader_or_execute(tmp_path):
    files=setup(tmp_path)
    report=evaluate(files)
    report["selected_candidate_sample"][0]["security_id"]='<script>alert("x")</script>'
    html=render_ranked_maturity_dashboard(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "N/A" in html
    assert "확정 대장주 0" in html


@pytest.mark.parametrize("field,value",[
    ("official_leader_promotions",1),
    ("actual_future_leader_skill_certified",True),
    ("precision_at_k",0.5),
    ("source_document_outcome_corroborated",True),
    ("known_failures",0),
])
def test_html_refuses_false_certification_or_metrics(tmp_path,field,value):
    files=setup(tmp_path)
    report=evaluate(files)
    report[field]=value
    with pytest.raises(ValueError,match="leader|certif|performance|outcome|status"):
        render_ranked_maturity_dashboard(report)


def test_html_rejects_inconsistent_elapsed_counts(tmp_path):
    files=setup(tmp_path)
    report=evaluate(files)
    report["full_horizon_elapsed_count"]=2
    with pytest.raises(ValueError,match="count|maturity|inconsistent"):
        render_ranked_maturity_dashboard(report)


def test_cli_json_html_http_backup_and_restore_are_derived_only(tmp_path,capsys):
    files=setup(tmp_path)
    target=tmp_path/"derived"
    main(["report-ranked-maturity","--freeze",str(files[2]),
          "--definition-file",str(files[1]),
          "--score-ledger",str(files[0][4]),
          "--watch-ledger",str(files[0][1]),
          "--features-dir",str(files[0][2]),
          "--as-of",NOW.isoformat(),"--out",str(target)])
    result=json.loads(capsys.readouterr().out)
    assert result["official_leader_promotions"]==0
    assert result["full_horizon_pending_count"]==1
    html=target/"site"/"ranked_maturity_kr.html"
    report_file=target/"ranked_maturity_kr_research.json"
    assert html.is_file() and report_file.is_file()
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(SimpleHTTPRequestHandler,
                                                    directory=str(target/"site")))
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/ranked_maturity_kr.html",timeout=5
        ) as response:
            assert response.status==200
            assert "미검증" in response.read().decode()
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()
    backup=tmp_path/"derived.zip"
    assert create_backup(target,backup)["file_count"]==2
    assert verify_backup(backup)["status"]=="LOCAL_BACKUP_VERIFIED"
    with __import__("zipfile").ZipFile(backup) as archive:
        contents=archive.namelist()
        assert "ranked_maturity_kr_research.json" in contents
        assert "site/ranked_maturity_kr.html" in contents
        assert all(not name.endswith(".sqlite") for name in contents)
    restored=tmp_path/"restored"
    restore_backup(backup,restored)
    assert (restored/"ranked_maturity_kr_research.json").read_bytes()==report_file.read_bytes()
    assert (restored/"site"/html.name).read_bytes()==html.read_bytes()


def test_feature_file_replaced_during_maturity_audit_cannot_publish(tmp_path,monkeypatch):
    import eraleader.ranked_maturity as module
    files=setup(tmp_path)
    real=module._verify_native_original_witnesses
    calls=[0]
    def change_after_first_witness(*args,**kwargs):
        real(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            (files[0][2]/"A.json").write_text('{"replaced_during_report":true}')
    monkeypatch.setattr(module,"_verify_native_original_witnesses",change_after_first_witness)
    with pytest.raises(ValueError,match="feature|formula|source|revised"):
        evaluate(files)
    assert calls[0]>=1


def test_original_rank_snapshot_replaced_during_audit_cannot_publish(tmp_path,monkeypatch):
    import eraleader.ranked_maturity as module
    files=setup(tmp_path)
    real=module._verify_native_original_witnesses
    calls=[0]
    def replace_after_first(*args,**kwargs):
        real(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            original=json.loads(files[2].read_text())
            original["model_version"]="MALICIOUS_REHASHED_MODEL"
            original["content_sha256"]=_digest({
                k:v for k,v in original.items() if k!="content_sha256"
            })
            files[2].write_text(json.dumps(original))
    monkeypatch.setattr(module,"_verify_native_original_witnesses",replace_after_first)
    with pytest.raises(ValueError,match="snapshot|revised|frozen|source"):
        evaluate(files)
    assert calls[0]>=1
