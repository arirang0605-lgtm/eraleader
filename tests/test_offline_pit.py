from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import csv
import json
import pytest

from eraleader.offline_pit import OfflineLedger, normalize, iso_time
from eraleader.offline_features import financial_snapshot, ratio_growth
from eraleader.cli import main

FIXTURE=Path(__file__).parent/"fixtures/offline_synthetic.json"

def test_json_import_is_idempotent_and_asof_state(tmp_path):
    ledger=OfflineLedger(tmp_path/"test.sqlite")
    try:
        counts=ledger.import_file(FIXTURE)
        assert counts["membership"]["inserted"]==3
        assert counts["fundamentals"]["inserted"]==7
        again=ledger.import_file(FIXTURE)
        assert all(value["inserted"]==0 for value in again.values())
        jun=ledger.snapshot("2024-06-15T21:00:00+09:00",market="KR")
        assert set(jun["members"])=={"SYN-A","SYN-B"}
        assert not jun["actions"]
        assert all(r["period_end"]!="2024-06-30" for r in jun["fundamentals"])
        sept=ledger.snapshot("2024-09-01T21:00:00+09:00",market="KR")
        assert set(sept["members"])=={"SYN-A"}
        assert {a["action_type"] for a in sept["actions"]}=={"delist","split"}
        assert sept["exit_security_ids"]==["SYN-B"]
        july=ledger.snapshot("2024-07-22T10:00:00+09:00",market="KR")
        assert not any(a["action_type"]=="split" for a in july["actions"])
        assert any(a["action_type"]=="split" for a in july["announced_future_actions"])
        assert any(r["value"]==160 and r["metric"]=="revenue" for r in sept["fundamentals"])
        assert not any(r["value"]==166 for r in sept["fundamentals"])
        assert sept["quality"]["financial_pit_complete_verified"] is False
        late=ledger.snapshot("2024-10-05T21:00:00+09:00",market="KR")
        assert set(late["members"])=={"SYN-A","SYN-C"}
        assert any(r["value"]==166 and r["metric"]=="revenue" for r in late["fundamentals"])
        assert all(r["source_id"]=="fixture1" for r in late["fundamentals"])
    finally:
        ledger.close()

def test_growing_company_offline_screen_not_leader(tmp_path):
    led=OfflineLedger(tmp_path/"x.sqlite")
    try:
        led.import_file(FIXTURE)
        early=financial_snapshot(led.snapshot("2024-07-01T17:00:00+09:00",market="KR"))
        company=next(x for x in early["companies"] if x["security_id"]=="SYN-A")
        assert company["revenue_yoy"]==0.25
        assert company["industry_revenue_yoy"] is None
        late=financial_snapshot(led.snapshot("2024-09-01T17:00:00+09:00",market="KR"))
        company=next(x for x in late["companies"] if x["security_id"]=="SYN-A")
        assert company["revenue_yoy"]==0.6
        assert company["operating_income_yoy"]==1.0
        assert company["revenue_yoy_acceleration"]==0.35
        assert company["industry_revenue_yoy"]==0.15
        assert company["operating_margin"]==0.125
        assert company["screen_hit_heuristic"] is True
        assert company["leader_state"]=="WATCH"
        assert company["certified_pit"] is False
        assert late["research_screen_count"]==1
        assert late["quality"]["provenances"]==["synthetic_fixture"]
    finally:
        led.close()

def test_future_revision_never_leaks_backwards(tmp_path):
    led=OfflineLedger(tmp_path/"x.sqlite")
    try:
        obj=json.loads(FIXTURE.read_text())
        revisions=[r for r in obj["records"]["fundamentals"] if r["revision"]==2]
        obj["records"]["fundamentals"]=[r for r in obj["records"]["fundamentals"] if r["revision"]==1]
        led.import_rows("membership",obj["records"]["membership"],"synthetic_fixture")
        led.import_rows("fundamentals",obj["records"]["fundamentals"],"synthetic_fixture")
        t="2024-09-01T21:00:00+09:00"
        prev=led.snapshot(t,market="KR")["fundamentals"]
        led.import_rows("fundamentals",revisions,"synthetic_fixture")
        assert led.snapshot(t,market="KR")["fundamentals"]==prev
    finally:
        led.close()

def test_atomic_json_file_conflict_rolls_back_all_kinds(tmp_path):
    led=OfflineLedger(tmp_path/"x.sqlite")
    try:
        led.import_file(FIXTURE)
        obj=json.loads(FIXTURE.read_text())
        obj["records"]["membership"]=[{
          **obj["records"]["membership"][0],
          "security_id":"SYN-D","ticker":"444444"
        }]
        obj["records"]["fundamentals"]=[{
          **obj["records"]["fundamentals"][0],"value":1234
        }]
        obj["records"]["actions"]=[]
        obj["records"]["industry"]=[]
        path=tmp_path/"bad.json"
        path.write_text(json.dumps(obj))
        with pytest.raises(ValueError,match="Conflicting revision"):
            led.import_file(path)
        assert "SYN-D" not in led.snapshot("2024-10-20T16:00:00+09:00",market="KR")["members"]
    finally:
        led.close()

@pytest.mark.parametrize("kind,row,expected",[
 ("membership",{"market":"KR","known_at":"2024-03-01T10:00:00"},
  "Missing source_id"),
 ("fundamentals",{"security_id":"S","metric":"revenue","period_end":"2023-12-31",
   "available_at":"2024-01-01T12:00:00","unit":"KRW","value":1,
   "source_id":"x","revision":1},"timezone"),
 ("actions",{"source_id":"x","revision":1,"security_id":"S","action_id":"a",
   "action_type":"split","effective_on":"2024-01-01","known_at":"2023-12-01T00:00:00Z",
   "ratio":0},"Split"),
])
def test_bad_records_fail_closed(kind,row,expected):
    with pytest.raises(ValueError,match=expected):
        normalize(kind,row)

def test_csv_import_requires_explicit_source_kind(tmp_path):
    row=json.loads(FIXTURE.read_text())["records"]["membership"][0]
    p=tmp_path/"members.csv"
    with p.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=row.keys())
        writer.writeheader();writer.writerow(row)
    led=OfflineLedger(tmp_path/"x.sqlite")
    try:
        with pytest.raises(ValueError,match="requires explicit"):
            led.import_file(p)
        assert led.import_file(p,kind="membership",provenance="user_supplied")["membership"]["inserted"]==1
    finally:
        led.close()

def test_cli_offline_import_and_features(tmp_path,capsys):
    args=["offline-import","--file",str(FIXTURE),"--out",str(tmp_path)]
    main(args)
    assert "OFFLINE_IMPORT_DONE" in capsys.readouterr().out
    main(args)
    assert '"inserted": 0' in capsys.readouterr().out
    main(["offline-features","--market","KR",
          "--as-of","2024-09-01T17:00:00+09:00","--out",str(tmp_path)])
    printed=capsys.readouterr().out
    assert "RESEARCH_ONLY" in printed
    report=json.loads((tmp_path/"offline_kr_features.json").read_text())
    assert report["research_screen_count"]==1
    assert all(r["leader_state"]=="WATCH" for r in report["companies"])
    assert report["quality"]["financial_pit_complete_verified"] is False

def test_no_fabricated_yoy_for_negative_baseline():
    assert ratio_growth(20,0) is None
    assert ratio_growth(20,-5) is None


def test_membership_amendment_closes_open_ended_record(tmp_path):
    led=OfflineLedger(tmp_path/"data.sqlite")
    try:
        base=json.loads(FIXTURE.read_text())["records"]["membership"][0]
        led.import_rows("membership",[base],"synthetic_fixture")
        earlier=led.snapshot("2024-07-31T17:00:00+09:00",market="KR")
        assert "SYN-A" in earlier["members"]
        amended={**base,"revision":2,"valid_to":"2024-07-01",
                 "known_at":"2024-08-10T12:00:00+09:00"}
        led.import_rows("membership",[amended],"synthetic_fixture")
        assert "SYN-A" in led.snapshot("2024-07-31T17:00:00+09:00",market="KR")["members"]
        assert "SYN-A" not in led.snapshot("2024-09-01T17:00:00+09:00",market="KR")["members"]
    finally:led.close()

def test_overlapping_ticker_reuse_is_rejected(tmp_path):
    led=OfflineLedger(tmp_path/"data.sqlite")
    try:
        row=json.loads(FIXTURE.read_text())["records"]["membership"][0]
        conflicting={**row,"security_id":"SYN-Z"}
        led.import_rows("membership",[row,conflicting],"synthetic_fixture")
        with pytest.raises(ValueError,match="Ambiguous overlapping ticker"):
            led.snapshot("2024-05-01T17:00:00+09:00",market="KR")
    finally:led.close()

def test_local_midnight_keeps_exchange_date(tmp_path):
    led=OfflineLedger(tmp_path/"data.sqlite")
    try:
        record={
            "security_id":"MID","ticker":"123456","industry_id":"TECH",
            "market":"KR","valid_from":"2024-09-01","valid_to":None,
            "known_at":"2024-08-31T18:00:00Z","source_id":"test","revision":1}
        led.import_rows("membership",[record],"synthetic_fixture")
        s=led.snapshot("2024-09-01T03:30:00+09:00",market="KR")
        assert s["trading_day"]=="2024-09-01"
        assert "MID" in s["members"]
    finally:led.close()

def test_report_source_is_never_upgraded_to_certified(tmp_path):
    led=OfflineLedger(tmp_path/"data.sqlite")
    try:
        row=json.loads(FIXTURE.read_text())["records"]["membership"][0]
        led.import_rows("membership",[row],"external_public_file")
        report=financial_snapshot(led.snapshot("2024-09-01T17:00:00+09:00",market="KR"))
        assert report["quality"]["financial_pit_complete_verified"] is False
        assert report["companies"][0]["certified_pit"] is False
        assert report["companies"][0]["screen_hit_heuristic"] is False
    finally:led.close()

def test_unknown_empty_json_kind_is_rejected(tmp_path):
    led=OfflineLedger(tmp_path/"x.sqlite")
    try:
        invalid={"schema_version":"eraleader.offline.v1",
                 "provenance":"synthetic_fixture","records":{"unknown_kind":[]}}
        p=tmp_path/"bad.json";p.write_text(json.dumps(invalid))
        with pytest.raises(ValueError):
            led.import_file(p)
    finally:led.close()


def test_separate_asof_research_runs_are_preserved(tmp_path,capsys):
    main(["offline-import","--file",str(FIXTURE),"--out",str(tmp_path)])
    capsys.readouterr()
    paths=[]
    for when in ("2024-07-01T17:00:00+09:00",
                 "2024-09-01T17:00:00+09:00",
                 "2024-10-05T17:00:00+09:00"):
        main(["offline-features","--market","KR","--as-of",when,
              "--out",str(tmp_path)])
        result=json.loads(capsys.readouterr().out)
        paths.append(Path(result["immutable_run"]))
    assert len({str(p) for p in paths})==3
    assert all(p.is_file() for p in paths)
    first=json.loads(paths[0].read_text())
    middle=json.loads(paths[1].read_text())
    last=json.loads(paths[2].read_text())
    assert first["research_screen_count"]==0
    assert middle["research_screen_count"]==1
    assert last["research_screen_count"]==1
    assert first["companies"][0]["revenue_yoy"]==0.25
    assert middle["companies"][0]["revenue_yoy"]==0.6
    assert last["companies"][0]["revenue_yoy"]==0.66
    assert all(r["quality"]["historic_membership_pit_verified"] is False for r in (first,middle,last))
