"""Synthetic offline source-vintage audit tests; never certify historic PIT."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from eraleader.source_vintage import audit_source_vintages
from eraleader.cli import main

CUTOFF="2024-04-04T18:00:00+09:00"

def build(tmp_path,rows=None,**overrides):
    if rows is None:
        rows=[{"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"B1",
               "revision":1,"session":"2024-04-01",
               "available_at":"2024-04-01T16:00:00+09:00"}]
    body="".join(json.dumps(r)+"\n" for r in rows).encode()
    (tmp_path/"synthetic.jsonl").write_bytes(body)
    item={"source_id":"SYN-RAW","vintage_id":"v1","publisher_id":"SYN-PUB",
          "market":"KR","kind":"raw_prices","file":"synthetic.jsonl",
          "sha256":sha256(body).hexdigest(),
          "retrieved_at":"2024-04-02T09:00:00+09:00"}
    item.update(overrides)
    path=tmp_path/"manifest.json"
    path.write_text(json.dumps({"schema_version":"source_vintage_manifest_v1",
                                "sources":[item]}))
    return path

def audit(path):
    return audit_source_vintages(path,decision_at=CUTOFF)

def test_declared_vintage_never_certifies_historic_pit(tmp_path):
    output=audit(build(tmp_path))
    assert output["status"]=="RESEARCH_DECLARED_VINTAGE_NOT_CERTIFIED"
    assert output["file_integrity_checked"] is True
    assert output["rows_potentially_usable_asof"]==1
    assert output["historical_pit_certified"] is False
    assert output["source_timestamp_independently_attested"] is False

def test_backfilled_source_has_zero_eligible_rows(tmp_path):
    output=audit(build(tmp_path,retrieved_at="2026-10-10T14:00:00+09:00"))
    assert output["status"]=="RESEARCH_RETROSPECTIVE_VINTAGE_NOT_PIT"
    assert output["sources"][0]["rows_available_by_decision_claimed"]==1
    assert output["rows_potentially_usable_asof"]==0

def test_future_correction_excluded_from_earlier_snapshot(tmp_path):
    rows=[{"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"B1",
           "revision":i,"session":"2024-04-01","available_at":when}
          for i,when in [(1,"2024-04-01T16:00:00+09:00"),
                         (2,"2024-04-07T16:00:00+09:00")]]
    output=audit(build(tmp_path,rows,retrieved_at="2024-04-08T10:00:00+09:00"))
    assert output["sources"][0]["rows_available_by_decision_claimed"]==1
    assert output["sources"][0]["rows_after_decision_excluded"]==1
    assert output["rows_potentially_usable_asof"]==0

def test_announced_action_may_precede_effective_day(tmp_path):
    rows=[{"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"A1",
           "revision":1,"effective_on":"2024-06-01",
           "known_at":"2024-04-01T09:00:00+09:00"}]
    assert audit(build(tmp_path,rows,kind="actions"))["sources"][0]["rows_total"]==1

@pytest.mark.parametrize("override,reason",[
    ({"sha256":"0"*64},"SHA256 does not match"),
    ({"sha256":"invalid"},"Invalid SHA256"),
    ({"file":"../other.jsonl"},"Unsafe source filename"),
    ({"kind":"nonexistent"},"kind/market"),
    ({"market":"XX"},"kind/market"),
    ({"retrieved_at":"2024-04-02T09:00:00"},"timezone"),
    ({"retrieved_at":"2024-03-30T09:00:00+09:00"},"postdates"),
])
def test_manifest_rejected(tmp_path,override,reason):
    with pytest.raises(ValueError,match=reason):
        audit(build(tmp_path,**override))

@pytest.mark.parametrize("update,reason",[
    ({"source_id":"WRONG"},"differs"),
    ({"available_at":"2024-04-01T16:00:00"},"timezone"),
    ({"session":"INVALID"},"observation date"),
    ({"revision":True},"positive integer"),
    ({"security_id":""},"security_id"),
])
def test_invalid_row_fails_closed(tmp_path,update,reason):
    row={"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"B1",
         "revision":1,"session":"2024-04-01",
         "available_at":"2024-04-01T16:00:00+09:00"}
    row.update(update)
    with pytest.raises(ValueError,match=reason):
        audit(build(tmp_path,[row]))

def test_duplicate_revision_rejected(tmp_path):
    row={"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"B1",
         "revision":1,"session":"2024-04-01",
         "available_at":"2024-04-01T16:00:00+09:00"}
    with pytest.raises(ValueError,match="Repeated source record"):
        audit(build(tmp_path,[row,deepcopy(row)]))

def test_duplicate_source_declaration_rejected(tmp_path):
    path=build(tmp_path)
    meta=json.loads(path.read_text())
    meta["sources"].append(deepcopy(meta["sources"][0]))
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError,match="Duplicate source vintage"):
        audit(path)

def test_changed_file_fails_hash_check(tmp_path):
    path=build(tmp_path)
    source=tmp_path/"synthetic.jsonl"
    source.write_text(source.read_text().replace("SYN-01", "SYN-02"))
    with pytest.raises(ValueError,match="SHA256 does not match"):
        audit(path)

def test_symlink_source_rejected(tmp_path):
    path=build(tmp_path)
    (tmp_path/"alias.jsonl").symlink_to(tmp_path/"synthetic.jsonl")
    meta=json.loads(path.read_text())
    meta["sources"][0]["file"]="alias.jsonl"
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError,match="symlinked"):
        audit(path)

def test_empty_data_and_bad_schema_rejected(tmp_path):
    path=build(tmp_path,rows=[])
    with pytest.raises(ValueError,match="Empty source"):
        audit(path)
    path.write_text("[]")
    with pytest.raises(ValueError,match="schema"):
        audit(path)

def test_cli_writes_only_derived_summary(tmp_path,capsys):
    path=build(tmp_path,retrieved_at="2026-10-10T14:00:00+09:00")
    main(["audit-source-vintage","--manifest",str(path),
          "--decision-at",CUTOFF,"--out",str(tmp_path/"out")])
    response=json.loads(capsys.readouterr().out)
    assert response["retrospective_source_count"]==1
    stored=json.loads(Path(response["path"]).read_text())
    assert stored["historical_pit_certified"] is False
    assert "SYN-01" not in json.dumps(stored)
    assert stored["sources"][0]["rows_total"]==1

def test_multiple_known_revisions_count_one_current_record(tmp_path):
    rows=[{"source_id":"SYN-RAW","security_id":"SYN-01","record_id":"B1",
           "revision":n,"session":"2024-04-01","available_at":when}
          for n,when in [(1,"2024-04-01T16:00:00+09:00"),
                         (2,"2024-04-03T16:00:00+09:00")]]
    out=audit(build(tmp_path,rows,retrieved_at="2024-04-04T09:00:00+09:00"))
    assert out["sources"][0]["rows_available_by_decision_claimed"]==2
    assert out["sources"][0]["superseded_revisions_excluded"]==1
    assert out["rows_potentially_usable_asof"]==1
