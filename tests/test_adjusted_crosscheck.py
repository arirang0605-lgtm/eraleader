from copy import deepcopy
import json
from pathlib import Path
import pytest
from eraleader.adjusted_crosscheck import compare_total_return_indexes
from eraleader.cli import main

SAMPLE=Path(__file__).parent/"fixtures"/"corporate_split_dividend_synthetic.json"
SIGNAL="2024-04-01T16:00:00+09:00"
EVAL="2024-04-10T16:00:00+09:00"

def inputs():
    bundle=json.loads(SAMPLE.read_text())
    reference={"source_id":"INDEPENDENT_DECLARED_SYNTHETIC_INDEX",
               "basis":"total_return_reinvested_index",
               "bars":[{"session":r["session"],"index":100.0,
                        "available_at":r["available_at"]} for r in bundle["bars"]]}
    return bundle["bars"],bundle["actions"],reference

def run(bars=None,actions=None,reference=None,**kwargs):
    stored=inputs()
    return compare_total_return_indexes(
        bars if bars is not None else stored[0],
        actions if actions is not None else stored[1],
        reference if reference is not None else stored[2],
        security_id="SYN-SPLIT",market="KR",
        raw_source_id="SYNTHETIC_RAW_PRICE",
        decision_at=SIGNAL,evaluated_at=EVAL,**kwargs)

def test_independent_declared_total_return_index_matches_split_cash_dividend():
    output=run()
    assert output["status"]=="RESEARCH_RETURN_SERIES_MATCH_NOT_CERTIFIED"
    assert output["compared_intervals"]==2
    assert output["intervals_outside_tolerance"]==0
    assert output["maximum_abs_deviation_bps"]==0
    assert output["reconstructed_total_return"]==0
    assert output["reference_total_return"]==0
    assert output["independent_provider_identity_verified"] is False
    assert output["historic_price_actions_pit_certified"] is False

def test_mismatch_reports_exception_not_false_certification():
    bars,actions,ref=inputs()
    ref["bars"][2]["index"]=102
    result=run(bars,actions,ref)
    assert result["status"]=="RESEARCH_RETURN_SERIES_DISAGREE"
    assert result["intervals_outside_tolerance"]==1
    assert result["maximum_abs_deviation_bps"]==200.0
    assert result["exception_samples"][0]["session"]=="2024-04-03"
    assert result["historic_price_actions_pit_certified"] is False

def test_missing_actions_expose_split_disagreement():
    bars,actions,ref=inputs()
    result=run(bars,[],ref)
    assert result["intervals_outside_tolerance"]==2
    assert result["status"]=="RESEARCH_RETURN_SERIES_DISAGREE"

@pytest.mark.parametrize("mutation,error", [
    (lambda r:r.update(source_id="SYNTHETIC_RAW_PRICE"), "distinct"),
    (lambda r:r.update(basis="adjusted_close"), "basis"),
    (lambda r:r["bars"].pop(), "coverage"),
    (lambda r:r["bars"][1].update(session="2024-04-05"), "mismatch"),
    (lambda r:r["bars"][1].update(available_at="2024-04-30T15:40:00+09:00"), "not available"),
    (lambda r:r["bars"][1].update(available_at="2024-04-01T15:40:00+09:00"), "before its observed"),
    (lambda r:r["bars"][0].update(available_at="2024-04-01T18:00:00+09:00"), "not available"),
    (lambda r:r["bars"][1].update(index=float("nan")), "Invalid reference"),
    (lambda r:r["bars"][1].update(available_at="2024-04-02T15:40:00"), "timezone"),
])
def test_bad_reference_index_rejected(mutation,error):
    bars,actions,ref=inputs()
    mutation(ref)
    with pytest.raises(ValueError,match=error):
        run(bars,actions,ref)

def test_reference_cannot_infer_delisting_cash_payoff():
    bars,actions,ref=inputs()
    actions.append({"security_id":"SYN-SPLIT","action_id":"END",
                    "action_type":"delist","effective_on":"2024-04-03",
                    "known_at":"2024-04-03T10:00:00+09:00"})
    with pytest.raises(ValueError,match="Unsupported corporate action"):
        run(bars,actions,ref)

@pytest.mark.parametrize("tolerance",[-1,float("nan"),float("inf"),True,1001])
def test_invalid_tolerance_denied(tolerance):
    with pytest.raises(ValueError,match="Invalid tolerance"):
        run(tolerance_bps=tolerance)

def test_crosscheck_offline_cli_synthetic_json(tmp_path,capsys):
    bundle=json.loads(SAMPLE.read_text())
    _,_,ref=inputs()
    bundle["schema_version"]="total_return_crosscheck_v1"
    bundle["raw_source_id"]="SYNTHETIC_RAW_PRICE"
    bundle["reference"]=ref
    path=tmp_path/"crosscheck.json"
    path.write_text(json.dumps(bundle))
    cmd=["audit-total-return","--file",str(path),
         "--security-id","SYN-SPLIT","--market","KR",
         "--decision-at",SIGNAL,"--evaluated-at",EVAL,
         "--out",str(tmp_path)]
    main(cmd)
    output=json.loads(capsys.readouterr().out)
    assert output["status"]=="RESEARCH_RETURN_SERIES_MATCH_NOT_CERTIFIED"
    assert output["intervals_outside_tolerance"]==0
    stored=json.loads((tmp_path/"total_return_crosscheck_research.json").read_text())
    assert stored["independent_provider_identity_verified"] is False
    assert stored["delisting_settlement_verified"] is False
    bundle["price_basis"]="split_adjusted"
    path.write_text(json.dumps(bundle))
    with pytest.raises(SystemExit) as raised:
        main(cmd)
    assert raised.value.code==2
