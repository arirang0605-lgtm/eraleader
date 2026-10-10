"""PIT-aligned feature bridge tests; all data are synthetic research only."""
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import pytest

from eraleader.rank_feature_bridge import build_rank_feature_inputs
from eraleader.discovery import MODEL_VERSION, run_id_for
from eraleader.cli import main
from eraleader.rank_score_pipeline import compute_and_register_rank_scores
from eraleader.prospective import ProspectiveRegistry
from test_peer_normalization import fixture as peer_fixture
from test_ranked_registry import run as watch_run

MODEL = "bridge-input-synthetic-v1"
NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


def fixture(market="KR"):
    offline = peer_fixture(market)
    offline["as_of"] = ("2026-10-09T16:30:00+09:00" if market == "KR"
                        else "2026-10-09T17:00:00-04:00")
    age = (date(2026, 10, 9) - date(2025, 12, 31)).days
    for company in offline["companies"]:
        company["latest_revenue_period"] = "2025-12-31"
        company["financial_period_age_days"] = {
            "revenue":age, "operating_income":age, "industry_revenue":age}
        company["ticker"] = "T" + company["security_id"]
        company["industry_revenue_yoy"] = .30
    rows = [
        {"security_id": "TA", "observed_at": "2026-10-09", "return_6m": .10},
        {"security_id": "TB", "observed_at": "2026-10-09", "return_6m": .20},
        {"security_id": "TC", "observed_at": "2026-10-09", "return_6m": .30},
        {"security_id": "TD", "observed_at": "2026-10-09", "return_6m": .40},
    ]
    price = {
        "source_market": market, "as_of_requested": "2026-10-09",
        "market_last_observation": "2026-10-09",
        "classification_quality": "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
        "model_version": MODEL_VERSION, "shown": len(rows), "rows": rows,
        "quality_flags": {"price_only": True,
                          "historic_membership_verified": False,
                          "price_adjustments_verified": False},
    }
    price["run_id"] = run_id_for(market, "2026-10-09", rows)
    return offline, price


def write(tmp_path, offline, price):
    a, b = tmp_path/"offline.json", tmp_path/"price.json"
    a.write_text(json.dumps(offline, sort_keys=True), encoding="utf-8")
    b.write_text(json.dumps(price, sort_keys=True), encoding="utf-8")
    return a, b


def build(tmp_path, market="KR", mutate=None, clock=NOW):
    offline, price = fixture(market)
    if mutate is not None:
        mutate(offline, price)
    a, b = write(tmp_path, offline, price)
    out = tmp_path/"generated"
    return build_rank_feature_inputs(a, b, out, model_version=MODEL, clock=clock), out, a, b


def docs(folder):
    return {json.loads(path.read_text())["security_id"]: json.loads(path.read_text())
            for path in folder.glob("*.json")}


def test_asof_peer_and_price_join_yields_only_three_eligible_issuers(tmp_path):
    result, folder, a, b = build(tmp_path)
    entries = docs(folder)
    assert set(entries) == {"A", "B", "C"}   # D is sole member of other sector
    assert all(doc["model_version"] == MODEL for doc in entries.values())
    assert all(doc["available_at"] == NOW.isoformat() for doc in entries.values())
    assert entries["B"]["features"] == {
        "revenue_yoy": .20, "operating_income_yoy": .30,
        "industry_revenue_yoy": .30, "momentum_6m": .20}
    assert result["eligible_documents"] == 3 and result["deferred"] == 1
    assert result["official_leader_promotions"] == 0
    manifest = json.loads((folder/"_meta/source_manifest.json").read_text())
    assert manifest["deferred"] == [{"security_id":"D",
                                    "reason":"PIT_PEER_SCREEN_DEFERRED"}]
    assert manifest["offline_source_sha256"] == sha256(a.read_bytes()).hexdigest()
    assert manifest["price_source_sha256"] == sha256(b.read_bytes()).hexdigest()
    for name, digest in manifest["feature_file_sha256"].items():
        assert sha256((folder/name).read_bytes()).hexdigest() == digest
    assert manifest["ticker_to_permanent_issuer_identity_certified"] is False
    assert manifest["financial_source_publication_independently_attested"] is False


def test_missing_price_not_invented_as_zero(tmp_path):
    def miss(offline, price):
        price["rows"] = price["rows"][:2]
        price["shown"] = 2
        price["run_id"] = run_id_for("KR", "2026-10-09", price["rows"])
    result, folder, _, _ = build(tmp_path, mutate=miss)
    assert set(docs(folder)) == {"A", "B"}
    manifest = json.loads((folder/"_meta/source_manifest.json").read_text())
    assert any(x["security_id"]=="C" and x["reason"]=="NO_PRICE_MOMENTUM_ASOF"
               for x in manifest["deferred"])


def test_too_few_asof_peers_produces_zero_score_inputs(tmp_path):
    result, folder, _, _ = build(tmp_path, mutate=lambda offline, _: offline[
        "companies"][2].__setitem__("screen_evaluated", False))
    assert result["eligible_documents"] == 0
    assert docs(folder) == {}
    assert (folder/"_meta/source_manifest.json").is_file()


def test_us_market_local_cutoff_and_daylight_saving(tmp_path):
    result, folder, _, _ = build(tmp_path, "US")
    assert result["market"] == "US"
    assert set(docs(folder)) == {"A", "B", "C"}


@pytest.mark.parametrize("mutation,reason", [
    (lambda off, px: px.__setitem__("source_market","US"), "market"),
    (lambda off, px: px.__setitem__("as_of_requested","2025-04-02"), "PIT cutoff"),
    (lambda off, px: px.__setitem__("run_id","fake"), "fingerprint"),
    (lambda off, px: px.__setitem__("classification_quality","CERTIFIED"), "model mismatch"),
    (lambda off, px: px["quality_flags"].__setitem__("price_only",False), "quality"),
    (lambda off, px: off["companies"][1].__setitem__("ticker","TA"), "Ambiguous ticker"),
    (lambda off, px: off["companies"][0].__setitem__("revenue_yoy",None),
        None),
])
def test_invalid_identity_mismatched_price_and_missing_fundamentals_defer_or_reject(
        tmp_path, mutation, reason):
    off, px = fixture()
    mutation(off, px)
    a, b = write(tmp_path, off, px)
    target = tmp_path/"generated"
    if reason is None:
        receipt = build_rank_feature_inputs(a,b,target,model_version=MODEL,clock=NOW)
        assert receipt["eligible_documents"] == 0
    else:
        with pytest.raises(ValueError,match=reason):
            build_rank_feature_inputs(a,b,target,model_version=MODEL,clock=NOW)
        assert not target.exists()


def test_unavailable_today_close_is_rejected_for_us_market(tmp_path):
    off, px = fixture("US")
    off["as_of"] = "2026-10-09T15:45:00-04:00"
    a, b = write(tmp_path,off,px)
    with pytest.raises(ValueError,match="before market close"):
        build_rank_feature_inputs(a,b,tmp_path/"generated",model_version=MODEL,clock=NOW)


def test_stale_header_or_future_price_row_rejected_without_outputs(tmp_path):
    off, px = fixture()
    px["market_last_observation"] = "2026-09-15"
    a, b = write(tmp_path, off, px)
    with pytest.raises(ValueError,match="Future/stale"):
        build_rank_feature_inputs(a,b,tmp_path/"stale",model_version=MODEL,clock=NOW)
    assert not (tmp_path/"stale").exists()

    px = fixture()[1]
    px["rows"][0]["observed_at"] = "2026-10-10"
    px["run_id"] = run_id_for("KR","2026-10-09",px["rows"])
    b.write_text(json.dumps(px))
    with pytest.raises(ValueError,match="Price row observation"):
        build_rank_feature_inputs(a,b,tmp_path/"future",model_version=MODEL,clock=NOW)
    assert not (tmp_path/"future").exists()


@pytest.mark.parametrize("bad",[-1.0,float("nan"),True,"0.2"])
def test_invalid_momentum_never_reaches_native_score(tmp_path,bad):
    off, px = fixture()
    px["rows"][0]["return_6m"] = bad
    px["run_id"] = run_id_for("KR","2026-10-09",px["rows"])
    a,b = write(tmp_path,off,px)
    with pytest.raises(ValueError,match="Invalid six-month"):
        build_rank_feature_inputs(a,b,tmp_path/"generated",model_version=MODEL,clock=NOW)
    assert not (tmp_path/"generated").exists()


def test_no_future_generation_and_no_existing_or_symlink_overwrite(tmp_path):
    off,px = fixture()
    a,b = write(tmp_path,off,px)
    with pytest.raises(ValueError,match="Future offline"):
        build_rank_feature_inputs(a,b,tmp_path/"notyet",model_version=MODEL,
                                  clock=datetime(2025, 1, 1,tzinfo=timezone.utc))
    target=tmp_path/"generated"
    build_rank_feature_inputs(a,b,target,model_version=MODEL,clock=NOW)
    original = (target/"_meta/source_manifest.json").read_bytes()
    with pytest.raises(FileExistsError,match="already exists"):
        build_rank_feature_inputs(a,b,target,model_version=MODEL,clock=NOW)
    assert original == (target/"_meta/source_manifest.json").read_bytes()
    symlink=tmp_path/"link"
    symlink.symlink_to(a)
    with pytest.raises(ValueError,match="symlinked"):
        build_rank_feature_inputs(symlink,b,tmp_path/"linked",model_version=MODEL,clock=NOW)


def test_generated_feature_inputs_work_with_original_watch_score_ledger(tmp_path):
    generation = NOW - timedelta(seconds=2)
    result, folder, _, _ = build(tmp_path,clock=generation)
    assert result["eligible_documents"] == 3
    watched = tmp_path/"prospective.sqlite"
    registry=ProspectiveRegistry(watched)
    at = NOW-timedelta(seconds=6)
    try:
        registry.record_integrated(watch_run(["A","B","C"],market="KR",model=MODEL,
                                             observed=(at-timedelta(seconds=1)).isoformat()),
                                   clock=at)
    finally:
        registry.close()
    scores=tmp_path/"score.sqlite"
    original={p.name:p.read_bytes() for p in folder.glob("*.json")}
    receipt=compute_and_register_rank_scores(folder,watched,scores,
                                               market="KR",model_version=MODEL,clock=NOW)
    assert receipt["new_score_records"] == 3
    assert receipt["official_leader_promotions"] == 0
    assert original == {p.name:p.read_bytes() for p in folder.glob("*.json")}


def test_cli_creates_safe_input_folder_with_true_now_clock(tmp_path,capsys):
    off,px = fixture()
    a,b=write(tmp_path,off,px)
    before=datetime.now(timezone.utc)
    main(["prepare-rank-features","--offline",str(a),"--price",str(b),
          "--features-dir",str(tmp_path/"cli"),"--model-version",MODEL])
    after=datetime.now(timezone.utc)
    receipt=json.loads(capsys.readouterr().out)
    assert receipt["eligible_documents"]==3
    generated=datetime.fromisoformat(receipt["generated_now_not_backdated"])
    assert before<=generated<=after
    assert generated>datetime.fromisoformat(off["as_of"])
    assert len(docs(tmp_path/"cli"))==3


def test_historic_only_snapshot_is_rejected_for_present_first_score(tmp_path):
    off, px = fixture()
    off["as_of"] = "2026-09-20T16:30:00+09:00"
    age = (date(2026, 9, 20) - date(2025, 12, 31)).days
    for row in off["companies"]:
        row["financial_period_age_days"] = {
            "revenue":age, "operating_income":age, "industry_revenue":age}
    for row in px["rows"]:
        row["observed_at"] = "2026-09-20"
    px["as_of_requested"] = "2026-09-20"
    px["market_last_observation"] = "2026-09-20"
    px["run_id"] = run_id_for("KR", "2026-09-20", px["rows"])
    a,b = write(tmp_path,off,px)
    target=tmp_path/"historical_forbidden"
    with pytest.raises(ValueError,match="Historical research snapshot"):
        build_rank_feature_inputs(a,b,target,model_version=MODEL,clock=NOW)
    assert not target.exists()
