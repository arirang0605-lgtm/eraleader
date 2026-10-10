from datetime import datetime
import json
import pytest
from eraleader.offline_pit import OfflineLedger
from eraleader.research import integrated_snapshot
from eraleader.cli import main

def fixture_snapshot(tmp_path,when="2024-09-01T17:00:00+09:00"):
    led=OfflineLedger(tmp_path/"offline.sqlite")
    led.import_file(__import__("pathlib").Path(__file__).parent/"fixtures/offline_synthetic.json")
    snap=led.snapshot(when,market="KR")
    led.close()
    return snap

def synthetic_price(date_string="2024-09-01",market="KR"):
    return {"source_market":market,"as_of_requested":date_string,
       "market_last_observation":"2024-08-30","run_id":"synthetic-price-v1",
       "rows":[{"security_id":"111111","observed_at":"2024-08-30",
                "return_6m":0.4,"price_strength_25":22.5}]}

def test_join_preserves_independent_data_domains(tmp_path):
    offline=fixture_snapshot(tmp_path)
    result=integrated_snapshot(offline,synthetic_price(),"2024-09-01T17:00:00+09:00")
    assert result["company_count"]==1
    assert result["research_growth_screen_count"]==1
    assert result["confirmed_leaders"]==0 and result["potential_leaders"]==0
    row=result["company_rows"][0]
    assert row["revenue_yoy"]==0.6 and row["momentum_6m"]==0.4
    assert row["state"]=="WATCH" and row["full_score"] is None
    assert "TICKER_JOIN_IDENTITY_UNVERIFIED" in row["quality_flags"]
    assert result==integrated_snapshot(offline,synthetic_price(),"2024-09-01T17:00:00+09:00")

def test_cross_market_future_and_stale_price_rejected(tmp_path):
    offline=fixture_snapshot(tmp_path)
    asof="2024-09-01T17:00:00+09:00"
    with pytest.raises(ValueError,match="Cross-market"):
        integrated_snapshot(offline,synthetic_price(market="US"),asof)
    with pytest.raises(ValueError,match="decision date"):
        integrated_snapshot(offline,synthetic_price(date_string="2024-09-04"),asof)
    stale=synthetic_price()
    stale["market_last_observation"]="2024-08-01"
    with pytest.raises(ValueError,match="too stale"):
        integrated_snapshot(offline,stale,asof)
    with pytest.raises(ValueError,match="cutoff"):
        integrated_snapshot(offline,synthetic_price(),"2024-09-02T17:00:00+09:00")

def test_no_price_does_not_fabricate_momentum(tmp_path):
    offline=fixture_snapshot(tmp_path)
    result=integrated_snapshot(offline,None,"2024-09-01T17:00:00+09:00")
    row=result["company_rows"][0]
    assert row["momentum_6m"] is None
    assert "NO_PRICE_OBSERVATION_ASOF" in row["quality_flags"]
    assert row["state"]=="WATCH"

def test_integrated_cli_immutable_result(tmp_path,capsys):
    base=__import__("pathlib").Path(__file__).parent/"fixtures/offline_synthetic.json"
    main(["offline-import","--file",str(base),"--out",str(tmp_path)])
    capsys.readouterr()
    at="2024-09-01T17:00:00+09:00"
    for _ in range(2):
        main(["offline-integrated","--as-of",at,"--out",str(tmp_path)])
        result=json.loads(capsys.readouterr().out)
        assert result["official_leaders"]==0
        assert result["pit_certified"] is False
        assert __import__("pathlib").Path(result["path"]).exists()
    assert len(list((tmp_path/"runs").glob("joined_*")))==1

def test_integrated_dashboard_labels_synthetic_and_escapes(tmp_path):
    from eraleader.delivery import render_integrated_dashboard,write_integrated_dashboard
    snap=fixture_snapshot(tmp_path)
    joined=integrated_snapshot(snap,None,"2024-09-01T17:00:00+09:00")
    joined["company_rows"][0]["ticker"]="<script>bad</script>"
    content=render_integrated_dashboard(joined)
    assert "<script>" not in content and "&lt;script&gt;" in content
    assert "미검증" in content and "0 — 검증 보류" in content
    path=write_integrated_dashboard(joined,tmp_path/"site")
    assert path.name=="research_kr.html" and path.is_file()
    from copy import deepcopy
    untrusted=deepcopy(joined)
    untrusted["confirmed_leaders"]=1
    with pytest.raises(ValueError):
        render_integrated_dashboard(untrusted)

def test_price_rows_cannot_hide_future_bar_behind_stale_header(tmp_path):
    offline=fixture_snapshot(tmp_path)
    header=synthetic_price()
    header["rows"][0]["observed_at"]="2024-09-20"
    with pytest.raises(ValueError,match="Future price row"):
        integrated_snapshot(offline,header,"2024-09-01T17:00:00+09:00")
    header=synthetic_price()
    header["rows"].append(dict(header["rows"][0]))
    with pytest.raises(ValueError,match="Duplicate price"):
        integrated_snapshot(offline,header,"2024-09-01T17:00:00+09:00")
