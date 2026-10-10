from copy import deepcopy
import json

import pytest

from eraleader.delist_cash import reconstruct_cash_delisting
from eraleader.cli import main

SEC="SYN-CASH-EXIT"
SIGNAL="2024-04-01T16:00:00+09:00"
EVALUATED="2024-05-01T17:00:00+09:00"


def bars():
    return [
        {"security_id":SEC,"session":d,"close":p,"tradable":True,
         "available_at":d+"T15:40:00+09:00"}
        for d,p in [("2024-04-01",100),("2024-04-02",50),("2024-04-03",50)]
    ]


def split():
    return [{"security_id":SEC,"action_id":"SPLIT-1","action_type":"split",
             "effective_on":"2024-04-02",
             "known_at":"2024-03-25T09:00:00+09:00","ratio":2}]


def settlement(**changes):
    body={
        "security_id":SEC,"source_id":"SYNTHETIC_PROVIDER_NOT_CERTIFIED",
        "event_id":"SYN-CASH-EXIT-1","action_type":"cash_delist",
        "last_trading_on":"2024-04-03","effective_on":"2024-04-04",
        "cash_per_share":55,"currency":"KRW",
        "provenance":"synthetic_fixture",
        "announced_at":"2024-03-25T09:00:00+09:00",
        "paid_at":"2024-04-15T10:00:00+09:00",
        "available_at":"2024-04-16T09:00:00+09:00",
        "cash_payment_confirmed":True,
    }
    body.update(changes)
    return body


def calc(raw=None,actions=None,terms=None,**extra):
    return reconstruct_cash_delisting(
        raw if raw is not None else bars(),
        actions if actions is not None else split(),
        terms if terms is not None else settlement(),
        security_id=SEC,market="KR",decision_at=SIGNAL,
        evaluated_at=EVALUATED,**extra)


def test_cash_exit_after_two_to_one_split_is_not_false_fifty_percent_loss():
    r=calc()
    assert r["return_to_last_tradable_close"]==0
    assert r["cash_exit_total_return"]==0.1
    assert r["raw_last_tradable_close"]==50
    assert r["cash_per_final_share"]==55
    assert r["pit_certified"] is False
    assert r["settlement_source_independently_verified"] is False


def test_cash_exit_dividend_reinvested_factor_and_final_share_convention():
    raw=bars()
    raw[-1]["close"]=49
    acts=split()+[{"security_id":SEC,"action_id":"DIV-1","action_type":"dividend",
                   "effective_on":"2024-04-03",
                   "known_at":"2024-03-26T09:00:00+09:00","cash_amount":1}]
    r=calc(raw,acts)
    assert r["return_to_last_tradable_close"]==0
    assert r["cash_exit_total_return"]==round(55/49-1,12)


def test_missing_settlement_never_invents_a_payout():
    r=reconstruct_cash_delisting(
        bars(),split(),None,security_id=SEC,market="KR",
        decision_at=SIGNAL,evaluated_at=EVALUATED)
    assert r["status"]=="CENSORED_MISSING_CASH_SETTLEMENT"
    assert r["cash_exit_total_return"] is None


@pytest.mark.parametrize("changes",[
    {"cash_payment_confirmed":False},
    {"paid_at":"2024-06-15T10:00:00+09:00",
     "available_at":"2024-06-16T09:00:00+09:00"},
    {"available_at":"2024-06-16T09:00:00+09:00"},
])
def test_not_confirmed_or_not_available_by_evaluation_is_censored(changes):
    result=calc(terms=settlement(**changes))
    assert result["status"]=="CENSORED_CASH_PAYMENT_NOT_KNOWN_BY_EVALUATION"
    assert result["cash_exit_total_return"] is None


@pytest.mark.parametrize("changes,match",[
    ({"cash_per_share":0},"positive"),
    ({"cash_per_share":float("nan")},"positive"),
    ({"cash_per_share":True},"Invalid cash consideration"),
    ({"currency":"USD"},"currency"),
    ({"security_id":"OTHER"},"identity"),
    ({"action_type":"stock_merger"},"Unsupported"),
    ({"cash_payment_confirmed":"true"},"boolean"),
    ({"last_trading_on":"2024-04-02"},"Last observed"),
    ({"effective_on":"2024-04-02"},"precedes last trade"),
    ({"paid_at":"2024-04-03T10:00:00+09:00",
      "available_at":"2024-04-16T09:00:00+09:00"},"chronology"),
    ({"available_at":"2024-04-10T09:00:00+09:00"},"chronology"),
    ({"paid_at":"2024-04-15T10:00:00",
      "available_at":"2024-04-16T09:00:00+09:00"},"Timezone"),
])
def test_unsafe_settlement_contract_is_rejected(changes,match):
    with pytest.raises(ValueError,match=match):
        calc(terms=settlement(**changes))


def test_merger_non_cash_action_never_substitutes_zero_value():
    rights=split()+[{"security_id":SEC,"action_id":"MERGE",
                      "action_type":"merger","effective_on":"2024-04-03",
                      "known_at":"2024-04-01T10:00:00+09:00"}]
    with pytest.raises(ValueError,match="Unsupported corporate action"):
        calc(actions=rights)


def test_missing_post_last_trade_action_not_silently_ignored():
    extra=split()+[{"security_id":SEC,"action_id":"DIV",
                    "action_type":"dividend","effective_on":"2024-04-04",
                    "known_at":"2024-04-01T10:00:00+09:00","cash_amount":1}]
    with pytest.raises(ValueError,match="after last tradable"):
        calc(actions=extra)


def test_pit_price_availability_and_basis_still_checked():
    bad=bars()
    bad[0]["available_at"]="2024-04-01T18:00:00+09:00"
    with pytest.raises(ValueError,match="not yet available"):
        calc(raw=bad)
    with pytest.raises(ValueError,match="Raw unadjusted"):
        calc(price_basis="adjusted")


def test_cli_cash_exit_and_missing_payout(tmp_path,capsys):
    file=tmp_path/"input.json"
    payload={"schema_version":"cash_delist_research_v1",
             "price_basis":"raw_unadjusted",
             "bars":bars(),"actions":split(),"settlement":settlement()}
    file.write_text(json.dumps(payload))
    args=["audit-cash-delist","--file",str(file),"--security-id",SEC,
          "--market","KR","--decision-at",SIGNAL,"--evaluated-at",EVALUATED,
          "--out",str(tmp_path/"derived")]
    main(args)
    out=json.loads(capsys.readouterr().out)
    assert out["cash_exit_total_return"]==0.1
    assert out["pit_certified"] is False
    assert json.loads((tmp_path/"derived"/"cash_delisting_research.json").read_text())[
        "settlement_source_independently_verified"] is False
    payload.pop("settlement")
    file.write_text(json.dumps(payload))
    main(args)
    censored=json.loads(capsys.readouterr().out)
    assert censored["cash_exit_total_return"] is None


def test_us_dollar_cash_exit_with_new_york_local_timestamps():
    sec="SYN-US-CASH"
    raw=[{"security_id":sec,"session":session,"close":amount,
          "tradable":True,"available_at":session+"T16:30:00-04:00"}
         for session,amount in [("2024-04-01",100),("2024-04-02",101)]]
    terms={
        "security_id":sec,"source_id":"SYNTHETIC_US_NOT_CERTIFIED",
        "event_id":"US-CASH-1","action_type":"cash_delist",
        "last_trading_on":"2024-04-02","effective_on":"2024-04-03",
        "cash_per_share":105,"currency":"USD","provenance":"synthetic_fixture",
        "announced_at":"2024-03-25T10:00:00-04:00",
        "paid_at":"2024-04-15T12:00:00-04:00",
        "available_at":"2024-04-16T09:00:00-04:00",
        "cash_payment_confirmed":True,
    }
    out=reconstruct_cash_delisting(
        raw,[],terms,security_id=sec,market="US",
        decision_at="2024-04-01T17:00:00-04:00",
        evaluated_at="2024-05-01T17:00:00-04:00")
    assert out["cash_exit_total_return"]==0.05
    assert out["currency"]=="USD"
    assert out["pit_certified"] is False
