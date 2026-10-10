from pathlib import Path
import pytest
from eraleader.state_history import StateHistory

QUAL={"financial_pit":True,"historic_universe_pit":True,
      "corporate_actions_pit":True,"fundamental_growth":True,
      "confirmed_weekly_trend":True}
HIGH={"industry":18,"competitiveness":18,"earnings":23,"momentum":23,"flow":8}
LOW={"industry":9,"competitiveness":10,"earnings":10,"momentum":12,"flow":5}

def item(sec="A",components=None,evidence=None):
    return {"security_id":sec,"components":components or HIGH,
            "evidence":evidence or QUAL}

def test_state_history_early_candidate_confirmation_weakening(tmp_path):
    h=StateHistory(tmp_path/"state.sqlite")
    try:
        first=h.record("KR","2024-05-01",[item()])
        assert first["new_state_events"][0]["state"]=="POTENTIAL"
        second=h.record("KR","2024-05-08",[item()])
        assert second["new_state_events"][0]["state"]=="CONFIRMED"
        third=h.record("KR","2024-05-15",[item(components=LOW)])
        assert third["new_state_events"][0]["state"]=="WEAKENING"
        assert [x["state"] for x in h.history("KR","A")]==[
            "POTENTIAL","CONFIRMED","WEAKENING"]
        assert all(x["first_candidate_at"]=="2024-05-01" for x in h.history("KR","A"))
        assert h.record("KR","2024-05-15",[item(components=LOW)])["new_state_events"]==[]
    finally:h.close()

def test_missing_source_pit_never_promotes(tmp_path):
    h=StateHistory(tmp_path/"x.sqlite")
    try:
        r=h.record("KR","2024-05-01",[item(evidence={"financial_pit":True})])
        assert r["new_state_events"]==[]
        assert h.history("KR","A")[0]["state"]=="WATCH"
        assert h.history("KR","A")[0]["score"] is None
    finally:h.close()

def test_existing_state_is_immutable_and_nonretroactive(tmp_path):
    h=StateHistory(tmp_path/"x.sqlite")
    try:
        h.record("KR","2024-05-08",[item()])
        with pytest.raises(ValueError,match="mutation"):
            h.record("KR","2024-05-08",[item(components=LOW)])
        with pytest.raises(ValueError,match="Out-of-order"):
            h.record("KR","2024-05-01",[item()])
        assert len(h.history("KR","A"))==1
    finally:h.close()

def test_atomic_write_rolls_back_on_conflicting_second_security(tmp_path):
    h=StateHistory(tmp_path/"x.sqlite")
    try:
        h.record("KR","2024-05-01",[item(sec="B")])
        with pytest.raises(ValueError,match="mutation"):
            h.record("KR","2024-05-01",[item(sec="A"),item(sec="B",components=LOW)])
        assert h.history("KR","A")==[]
        assert len(h.history("KR","B"))==1
    finally:h.close()

def test_verified_leader_goes_paused_when_pit_sources_disappear(tmp_path):
    h=StateHistory(tmp_path/"x.sqlite")
    try:
        h.record("KR","2024-05-01",[item()])
        h.record("KR","2024-05-08",[item()])
        poor={"security_id":"A","components":{},
              "evidence":{"financial_pit":False}}
        summary=h.record("KR","2024-05-15",[poor])
        assert summary["new_state_events"][0]["state"]=="PAUSED"
        assert h.history("KR","A")[-1]["score"] is None
    finally:h.close()
