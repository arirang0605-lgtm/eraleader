from datetime import date
import pytest
from eraleader.corporate_returns import reconstruct_total_return

SIGNAL="2024-04-01T16:00:00+09:00"
EVAL="2024-04-10T16:00:00+09:00"
SEC="SYN-SPLIT"

def bar(session, close, *, tradable=True):
    return {"security_id":SEC,"session":session,"close":close,
            "available_at":session+"T15:40:00+09:00","tradable":tradable}

def event(action_id, kind, day, **kwargs):
    return {
        "security_id":SEC,"action_id":action_id,"action_type":kind,
        "effective_on":day,"known_at":"2024-03-29T09:00:00+09:00",**kwargs}

def calc(bars, actions, **kw):
    return reconstruct_total_return(
        bars, actions, decision_at=SIGNAL, evaluated_at=EVAL,
        security_id=SEC, market="KR", price_basis="raw_unadjusted", **kw)

def test_split_half_price_does_not_create_false_fifty_percent_loss():
    bars=[bar("2024-04-01",100),bar("2024-04-02",50)]
    act=[event("s1","split","2024-04-02",ratio=2)]
    result=calc(bars,act)
    assert result["total_return"]==0
    assert result["actions_applied"]==1
    assert result["pit_certified"] is False
    assert result["factor_path"][0]["corporate_action_on_session"]

def test_split_and_cash_dividend_on_same_ex_date():
    # Two old shares become four; 0.5 cash per post-split share.
    bars=[bar("2024-04-01",100),bar("2024-04-02",50)]
    acts=[event("s1","split","2024-04-02",ratio=2),
          event("d1","dividend","2024-04-02",cash_amount=0.5)]
    result=calc(bars,acts)
    assert result["total_return"]==0.01
    assert result["actions_applied"]==1
    assert result["factor_path"][0]["period_return"]==0.01

def test_split_and_subsequent_dividend_compound_independently():
    bars=[bar("2024-04-01",100),bar("2024-04-02",50),bar("2024-04-03",49)]
    acts=[event("s1","split","2024-04-02",ratio=2),
          event("d1","dividend","2024-04-03",cash_amount=1)]
    assert calc(bars,acts)["total_return"]==0

def test_raw_price_basis_required_to_avoid_double_count():
    with pytest.raises(ValueError,match="raw_unadjusted"):
        reconstruct_total_return(
            [bar("2024-04-01",100),bar("2024-04-02",100)],
            [event("s1","split","2024-04-02",ratio=2)],
            decision_at=SIGNAL,evaluated_at=EVAL,
            security_id=SEC,market="KR",price_basis="adjusted")

def test_delisting_without_proceeds_is_blocked_not_zeroed():
    with pytest.raises(ValueError,match="Unsupported corporate action"):
        calc([bar("2024-04-01",100),bar("2024-04-02",10)],
             [event("del1","delist","2024-04-02")])

def test_halted_observation_is_not_a_tradable_return():
    with pytest.raises(ValueError,match="tradability"):
        calc([bar("2024-04-01",100),
              bar("2024-04-02",100,tradable=False)],[])

def test_unknown_action_and_missing_session_are_blocked():
    bars=[bar("2024-04-01",100),bar("2024-04-03",50)]
    with pytest.raises(ValueError,match="absent"):
        calc(bars,[event("s1","split","2024-04-02",ratio=2)])
    with pytest.raises(ValueError,match="Unsupported"):
        calc(bars,[event("x1","spin_off","2024-04-03")])

def test_future_action_correction_cannot_enter_earlier_evaluation():
    bars=[bar("2024-04-01",100),bar("2024-04-02",50)]
    announced=event("s1","split","2024-04-02",ratio=2)
    announced["known_at"]="2024-10-01T09:00:00+09:00"
    with pytest.raises(ValueError,match="Future-known"):
        calc(bars,[announced])

def test_duplicate_action_and_session_are_rejected():
    bars=[bar("2024-04-01",100),bar("2024-04-02",50)]
    s=event("s1","split","2024-04-02",ratio=2)
    with pytest.raises(ValueError,match="duplicate"):
        calc(bars,[s,s])
    with pytest.raises(ValueError,match="Duplicate sessions"):
        calc([bars[0],bars[0]],[])

def test_ordered_sessions_and_bounded_historical_prices():
    with pytest.raises(ValueError,match="chronologically"):
        calc([bar("2024-04-02",50),bar("2024-04-01",100)],[])
    with pytest.raises(ValueError,match="Future price"):
        calc([bar("2024-04-01",100),bar("2024-04-11",102)],[])

def test_attestation_is_not_certification():
    result=calc([bar("2024-04-01",100),bar("2024-04-02",101)],
        [],corporate_actions_complete=True,price_sessions_complete=True)
    assert result["coverage_attested_by_input"] is True
    assert result["pit_certified"] is False
    assert result["status"]=="LOCAL_ADJUSTMENT_RESEARCH_ONLY"


def test_preclose_decision_rejects_same_day_close_lookahead():
    start="2024-04-01T03:00:00+09:00"
    end="2024-04-02T16:00:00+09:00"
    with pytest.raises(ValueError,match="not yet available"):
        reconstruct_total_return(
            [bar("2024-04-01",100),bar("2024-04-02",99)],
            [],decision_at=start,evaluated_at=end,
            security_id=SEC,market="KR",price_basis="raw_unadjusted")


def test_cli_accepts_synthetic_json_and_rejects_bad_schema(tmp_path,capsys):
    from eraleader.cli import main
    from pathlib import Path
    import json
    sample=Path(__file__).parent/"fixtures/corporate_split_dividend_synthetic.json"
    command=["corporate-return","--file",str(sample),"--security-id",SEC,
             "--market","KR","--decision-at",SIGNAL,"--evaluated-at",EVAL,
             "--price-basis","raw_unadjusted","--out",str(tmp_path)]
    main(command)
    stdout=json.loads(capsys.readouterr().out)
    assert stdout["status"]=="LOCAL_ADJUSTMENT_RESEARCH_ONLY"
    assert stdout["total_return_research"]==0
    result=json.loads((tmp_path/"corporate_returns_research.json").read_text())
    assert result["pit_certified"] is False
    assert result["actions_applied"]==2
    altered=json.loads(sample.read_text())
    altered["price_basis"]="adjusted"
    bad=tmp_path/"wrong.json"
    bad.write_text(json.dumps(altered))
    with pytest.raises(SystemExit) as error:
        main(command[:2]+[str(bad)]+command[3:])
    assert error.value.code==2


def test_non_boolean_coverage_flag_cannot_false_claim(tmp_path,capsys):
    from eraleader.cli import main
    from pathlib import Path
    import json
    sample=Path(__file__).parent/"fixtures/corporate_split_dividend_synthetic.json"
    altered=json.loads(sample.read_text())
    altered["corporate_actions_complete"]="false"
    bad=tmp_path/"bad_quality.json"
    bad.write_text(json.dumps(altered))
    with pytest.raises(SystemExit) as error:
        main(["corporate-return","--file",str(bad),"--security-id",SEC,
              "--market","KR","--decision-at",SIGNAL,"--evaluated-at",EVAL,
              "--price-basis","raw_unadjusted","--out",str(tmp_path)])
    assert error.value.code==2


def test_unknown_or_future_published_close_is_not_pit_safe():
    bars=[bar("2024-04-01",100),bar("2024-04-02",50)]
    without_availability=[{k:v for k,v in bars[0].items() if k!="available_at"},bars[1]]
    with pytest.raises(ValueError,match="Missing price available_at"):
        calc(without_availability,[])
    too_new=[bars[0],{**bars[1],"available_at":"2024-04-20T15:40:00+09:00"}]
    with pytest.raises(ValueError,match="Future price availability"):
        calc(too_new,[])
