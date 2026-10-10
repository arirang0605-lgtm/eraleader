"""Research-only local 4-factor score computation; synthetic fixtures only."""
from datetime import datetime, timezone, timedelta
import json
import sqlite3
import pytest

from eraleader.rank_score_pipeline import (
    compute_research_score, compute_and_register_rank_scores, HEURISTIC_VERSION,
)
from eraleader.prospective import ProspectiveRegistry
from eraleader.cli import main
from test_rank_score_ledger import setup as make_existing, WRITE, STAMP, MODEL
from test_ranked_registry import run

FACTORS_A={"revenue_yoy":.5,"operating_income_yoy":.75,
           "industry_revenue_yoy":.3,"momentum_6m":.6}
FACTORS_B={"revenue_yoy":.25,"operating_income_yoy":.375,
           "industry_revenue_yoy":.15,"momentum_6m":.3}


def bundle(tmp_path,market="KR"):
    b=make_existing(tmp_path,market=market)
    for sec,factors in zip(("A","B"),(FACTORS_A,FACTORS_B)):
        file=b[2]/f"{sec}.json"
        doc=json.loads(file.read_text())
        doc["features"]=factors
        file.write_text(json.dumps(doc,sort_keys=True))
    return b


def update(b,sec,fn):
    f=b[2]/f"{sec}.json"
    doc=json.loads(f.read_text())
    fn(doc)
    f.write_text(json.dumps(doc,sort_keys=True,allow_nan=True))


def score(b,at=WRITE,market="KR"):
    return compute_and_register_rank_scores(
        b[2],b[1],b[4],market=market,model_version=MODEL,clock=at)


def test_fixed_formula_equal_weights_clips_and_never_reuses_missing_factor():
    assert compute_research_score(FACTORS_A)==100
    assert compute_research_score(FACTORS_B)==50
    assert compute_research_score({k:0.0 for k in FACTORS_A})==0
    assert compute_research_score({k:-1 for k in FACTORS_A})==0
    assert HEURISTIC_VERSION.endswith(".v1")


def test_computed_scores_link_to_original_watch_and_actual_first_write(tmp_path):
    b=bundle(tmp_path)
    originals={f.name:f.read_bytes() for f in b[2].glob("*.json")}
    result=score(b)
    assert result["locally_computed_this_run"]==2
    assert result["new_score_records"]==2
    assert result["independent_score_computation_attested"] is False
    assert result["real_future_leader_skill_certified"] is False
    assert result["official_leader_promotions"]==0
    with sqlite3.connect(b[4]) as db:
        rows=[json.loads(x[0]) for x in db.execute("SELECT payload FROM rank_score_events")]
    assert {(r["security_id"],r["score"]) for r in rows}=={("A",100.0),("B",50.0)}
    assert all(r["score_recorded_at_utc"]==WRITE.isoformat() for r in rows)
    assert all(r["watch_registered_at_utc"]==STAMP.isoformat() for r in rows)
    assert originals=={f.name:f.read_bytes() for f in b[2].glob("*.json")}
    assert list(b[2].glob("*.tmp"))==[]


def test_same_inputs_are_idempotent_without_rewriting_first_timestamp(tmp_path):
    b=bundle(tmp_path)
    assert score(b)["new_score_records"]==2
    later=score(b,at=WRITE+timedelta(minutes=10))
    assert later["new_score_records"]==0
    assert later["duplicate_score_records"]==2
    with sqlite3.connect(b[4]) as db:
        assert {json.loads(x[0])["score_recorded_at_utc"] for x in
                db.execute("SELECT payload FROM rank_score_events")}=={WRITE.isoformat()}


@pytest.mark.parametrize("factor,bad",[
    ("momentum_6m",None),
    ("revenue_yoy",True),
    ("industry_revenue_yoy","0.4"),
    ("operating_income_yoy",float("nan")),
    ("momentum_6m",float("inf")),
])
def test_missing_boolean_nonfinite_or_string_factor_fails_closed(tmp_path,factor,bad):
    b=bundle(tmp_path)
    update(b,"B",lambda d:d["features"].__setitem__(factor,bad))
    with pytest.raises(ValueError,match="Invalid"):
        score(b)
    assert not b[4].exists()


@pytest.mark.parametrize("bad_key",["future_return","outcome_label","bonus_unverified"])
def test_future_or_unversioned_extra_factor_fails_before_registration(tmp_path,bad_key):
    b=bundle(tmp_path)
    update(b,"B",lambda d:d["features"].__setitem__(bad_key,1))
    with pytest.raises(ValueError,match="Exactly four"):
        score(b)
    assert not b[4].exists()


def test_missing_factor_refuses_invented_zero(tmp_path):
    b=bundle(tmp_path)
    update(b,"A",lambda d:d["features"].pop("momentum_6m"))
    with pytest.raises(ValueError,match="Exactly four"):
        score(b)
    assert not b[4].exists()


def test_future_available_at_is_rejected(tmp_path):
    b=bundle(tmp_path)
    update(b,"B",lambda d:d.__setitem__(
        "available_at",(WRITE+timedelta(seconds=1)).isoformat()))
    with pytest.raises(ValueError,match="Future"):
        score(b)
    assert not b[4].exists()


def test_wrong_market_cannot_borrow_watch_records(tmp_path):
    b=bundle(tmp_path)
    with pytest.raises(ValueError,match="market/model/schema"):
        score(b,market="US")
    assert not b[4].exists()


def test_missing_watch_cannot_invent_prospective_candidate(tmp_path):
    b=bundle(tmp_path)
    with sqlite3.connect(b[1]) as db:
        db.execute("DELETE FROM prospective_signals WHERE security_id='B'")
    with pytest.raises(ValueError,match="No eligible"):
        score(b)
    assert not b[4].exists()


def test_late_first_native_computation_not_backdated(tmp_path):
    b=bundle(tmp_path)
    with pytest.raises(ValueError,match="too late"):
        score(b,at=STAMP+timedelta(hours=2))
    assert not b[4].exists()


def test_recomputed_value_mutation_never_overwrites_first_event(tmp_path):
    b=bundle(tmp_path)
    score(b)
    update(b,"B",lambda d:d["features"].__setitem__("momentum_6m",.6))
    with pytest.raises(ValueError,match="mutation rejected"):
        score(b,at=WRITE+timedelta(minutes=1))
    with sqlite3.connect(b[4]) as db:
        old=json.loads(db.execute(
            "SELECT payload FROM rank_score_events WHERE security_id='B'").fetchone()[0])
    assert old["score"]==50.0


def test_feature_symlink_rejected_and_no_first_event(tmp_path):
    b=bundle(tmp_path)
    f=b[2]/"B.json"
    f.unlink()
    f.symlink_to(b[2]/"A.json")
    with pytest.raises(ValueError,match="linked"):
        score(b)
    assert not b[4].exists()


def test_us_market_is_supported_with_exchange_local_watch_time(tmp_path):
    b=bundle(tmp_path,market="US")
    result=score(b,market="US")
    assert result["market"]=="US"
    assert result["new_score_records"]==2


def test_cli_uses_actual_os_clock_and_never_exposes_backdate_flag(tmp_path,capsys):
    now=datetime.now(timezone.utc)
    first=now-timedelta(seconds=5)
    market="KR"
    model="new-native-computation-synthetic"
    watch=tmp_path/"watch.sqlite"
    w=ProspectiveRegistry(watch)
    try:
        w.record_integrated(run(["SRC"],market=market,model=model,
                                observed=first.isoformat()),clock=first)
    finally:
        w.close()
    folder=tmp_path/"features"
    folder.mkdir()
    (folder/"src.json").write_text(json.dumps({
        "schema":"eraleader.rank_feature_document.v1",
        "market":market,"model_version":model,"security_id":"SRC",
        "available_at":(first-timedelta(seconds=1)).isoformat(),
        "features":FACTORS_A,
    }))
    score_db=tmp_path/"score.sqlite"
    main(["compute-rank-scores","--market",market,"--model-version",model,
          "--features-dir",str(folder),"--watch-ledger",str(watch),
          "--score-ledger",str(score_db)])
    response=json.loads(capsys.readouterr().out)
    assert response["new_score_records"]==1
    stamp=datetime.fromisoformat(response["score_first_write_clock_utc"])
    assert now<=stamp<=datetime.now(timezone.utc)
    assert response["external_feature_publication_attested"] is False
    assert not list(folder.glob("*.tmp"))
