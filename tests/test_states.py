import pytest
from eraleader.states import evaluate_leader_state,replacement_signal

GOOD={"financial_pit":True,"historic_universe_pit":True,
      "corporate_actions_pit":True,"fundamental_growth":True,
      "confirmed_weekly_trend":True}
C={"industry":18,"competitiveness":18,"earnings":23,"momentum":23,"flow":8}

def test_price_only_cannot_promote_even_high_scores():
    data=evaluate_leader_state(C,{"financial_pit":False},continuous_confirmations=3)
    assert data["state"]=="WATCH" and data["total"] is None
    assert data["pit_verified"] is False

def test_verified_candidate_promotion_and_weakening():
    p=evaluate_leader_state(C,GOOD,continuous_confirmations=1)
    assert p["state"]=="POTENTIAL"
    c=evaluate_leader_state(C,GOOD,continuous_confirmations=2)
    assert c["state"]=="CONFIRMED" and c["total"]==90
    down={"industry":10,"competitiveness":11,"earnings":12,"momentum":13,"flow":4}
    w=evaluate_leader_state(down,GOOD,previous="CONFIRMED",continuous_confirmations=4)
    assert w["state"]=="WEAKENING"
    assert evaluate_leader_state(C,{**GOOD,"suspended":True})["state"]=="PAUSED"

def test_delisted_is_not_resurrected():
    assert evaluate_leader_state(C,GOOD,previous="EXITED")["state"]=="EXITED"

def test_replacement_requires_confirmed_history_and_same_industry():
    leader={"industry":"Tech","earnings":16,"momentum":19,
            "security_id":"L","pit_verified":True}
    new={"industry":"Tech","earnings":19,"momentum":22,
            "security_id":"N","pit_verified":True}
    assert replacement_signal(leader,new,repeats=1) is None
    assert replacement_signal(leader,{**new,"pit_verified":False},repeats=3) is None
    assert replacement_signal(leader,new,repeats=2)["kind"]=="REPLACEMENT_SIGNAL"

def test_reject_out_of_range_scores():
    with pytest.raises(ValueError):evaluate_leader_state({**C,"industry":99},GOOD)

def test_invalid_bar_quarantine_is_explicit():
    import pandas as pd
    from eraleader.data import validate_bars
    data=pd.DataFrame([
        {"security_id":"X","session":pd.Timestamp("2025-02-03"),
          "open":0,"high":0,"low":0,"close":100,"volume":0},
        {"security_id":"X","session":pd.Timestamp("2025-02-04"),
          "open":102,"high":100,"low":101,"close":102,"volume":100},
        {"security_id":"X","session":pd.Timestamp("2025-02-05"),
          "open":100,"high":105,"low":98,"close":101,"volume":100}])
    with pytest.raises(ValueError):
        validate_bars(data,pd.Timestamp("2025-02-05").date())
    ok=validate_bars(data,pd.Timestamp("2025-02-05").date(),quarantine=True)
    assert len(ok)==2
    assert ok.attrs["quarantined_rows"]==1
    assert int(ok["is_suspended"].sum())==1
