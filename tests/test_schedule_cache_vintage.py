"""Local scheduled source-revision fingerprint regression tests.

All files under tmp_path are synthetic. The real T5DATA market vault is
read-only and its original contents are not included in Git.
"""
from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from eraleader import local_schedule as schedule


SESSIONS = {"KR":date(2026,10,9),"US":date(2026,10,9)}
TODAY=date(2026,10,10)


@pytest.fixture
def input_tree(tmp_path):
    legacy=tmp_path/"readonly_fixture"
    kr=legacy/"datasets/external_validation/marcap/data"
    kr.mkdir(parents=True)
    us=legacy/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT"
    us.mkdir(parents=True)
    pd.DataFrame({"Date":[pd.Timestamp("2025-10-09")],
                  "Close":[100.0]}).to_parquet(kr/"marcap-2025.parquet",index=False)
    pd.DataFrame({"Date":[pd.Timestamp("2026-10-09")],
                  "Close":[100.0]}).to_parquet(kr/"marcap-2026.parquet",index=False)
    pd.DataFrame({"ts":[pd.Timestamp("2026-10-09")],
                  "close":[100.0]}).to_parquet(us/"bars.parquet",index=False)
    return {"legacy":legacy,"out":tmp_path/"output",
            "control":tmp_path/"control","backups":tmp_path/"backups"}


def mock_batch(monkeypatch, calls, func=None):
    def batch(_):
        calls.append("batch")
        if func is not None:
            func()
        return {"market_count":2,"reports_created":6}
    def create(_,target):
        target.write_bytes(b"fake verified zip for mock test")
    def verify(path):
        if path.read_bytes()!=b"fake verified zip for mock test":
            raise ValueError("Damaged archive")
    monkeypatch.setattr(schedule,"execute_local_batch",batch)
    monkeypatch.setattr(schedule,"create_backup",create)
    monkeypatch.setattr(schedule,"verify_backup",verify)


def test_fingerprint_includes_prior_kr_year_from_actual_550_day_window(input_tree):
    root=input_tree["legacy"]
    locations=schedule.active_cache_files(root,kr_as_of=SESSIONS["KR"])
    assert set(locations)=={"KR-2025","KR-2026","US"}
    digest=schedule.latest_cache_fingerprints(root,kr_as_of=SESSIONS["KR"])
    assert set(digest)==set(locations)
    assert all(len(hash_value)==64 for hash_value in digest.values())
    assert schedule.latest_cached_sessions(root)==SESSIONS


def test_old_year_revision_with_same_market_latest_date_forces_full_rerun(input_tree,monkeypatch):
    calls=[]
    mock_batch(monkeypatch,calls)
    first=schedule.run_scheduled(**input_tree,today=TODAY)
    assert first["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert first["source_files_verified_during_run"] is True
    assert set(first["cache_sha256"])=={"KR-2025","KR-2026","US"}
    assert schedule.run_scheduled(**input_tree,today=TODAY)["status"]=="SKIPPED_UNCHANGED_CACHE"
    assert calls==["batch"]
    original=schedule.latest_cache_fingerprints(input_tree["legacy"],kr_as_of=SESSIONS["KR"])
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    pd.DataFrame({"Date":[pd.Timestamp("2025-10-09")],
                  "Close":[202.0]}).to_parquet(old,index=False)
    assert schedule.latest_cached_sessions(input_tree["legacy"])==SESSIONS
    modified=schedule.latest_cache_fingerprints(input_tree["legacy"],kr_as_of=SESSIONS["KR"])
    assert modified["KR-2025"]!=original["KR-2025"]
    assert modified["KR-2026"]==original["KR-2026"]
    assert modified["US"]==original["US"]
    rerun=schedule.run_scheduled(**input_tree,today=TODAY)
    assert rerun["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert rerun["cache_sha256"]==modified
    assert calls==["batch","batch"]


def test_unchanged_date_revision_to_us_bars_forces_rerun(input_tree,monkeypatch):
    calls=[]
    mock_batch(monkeypatch,calls)
    first=schedule.run_scheduled(**input_tree,today=TODAY)
    us=input_tree["legacy"]/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    pd.DataFrame({"ts":[pd.Timestamp("2026-10-09")],
                  "close":[999.0]}).to_parquet(us,index=False)
    assert schedule.latest_cached_sessions(input_tree["legacy"])==SESSIONS
    second=schedule.run_scheduled(**input_tree,today=TODAY)
    assert second["cache_sha256"]["US"]!=first["cache_sha256"]["US"]
    assert calls==["batch","batch"]


def test_source_mutation_during_batch_never_marks_verified_checkpoint(input_tree,monkeypatch):
    calls=[]
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    def replace_while_running():
        pd.DataFrame({"Date":[pd.Timestamp("2025-10-09")],
                      "Close":[101.0]}).to_parquet(old,index=False)
    mock_batch(monkeypatch,calls,replace_while_running)
    with pytest.raises(RuntimeError,match="revised during scheduled analysis"):
        schedule.run_scheduled(**input_tree,today=TODAY)
    assert calls==["batch"]
    assert not (input_tree["control"]/"last_verified_batch.json").exists()
    assert not input_tree["backups"].exists()


def test_legacy_date_only_checkpoint_revalidates_one_time(input_tree,monkeypatch):
    calls=[]
    mock_batch(monkeypatch,calls)
    first=schedule.run_scheduled(**input_tree,today=TODAY)
    marker=input_tree["control"]/"last_verified_batch.json"
    item=json.loads(marker.read_text())
    del item["cache_sha256"]
    marker.write_text(json.dumps(item))
    rerun=schedule.run_scheduled(**input_tree,today=TODAY)
    assert rerun["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert rerun["cache_sha256"]==first["cache_sha256"]
    assert calls==["batch","batch"]


def test_missing_prior_kr_year_fails_not_replaced_by_latest_year(input_tree):
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    old.unlink()
    with pytest.raises(ValueError,match="Untrusted/missing"):
        schedule.latest_cache_fingerprints(input_tree["legacy"],kr_as_of=SESSIONS["KR"])


def test_symlink_source_fails_closed(input_tree):
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    real=old.with_name("source_backup.dat")
    old.rename(real)
    old.symlink_to(real)
    with pytest.raises(ValueError,match="Untrusted/missing"):
        schedule.latest_cache_fingerprints(input_tree["legacy"],kr_as_of=SESSIONS["KR"])


def test_stale_cache_rejection_precedes_expensive_fingerprinting(input_tree,monkeypatch):
    monkeypatch.setattr(schedule,"latest_cache_fingerprints",
                        lambda *a,**k: pytest.fail("do not read entire stale cache"))
    result=schedule.run_scheduled(**input_tree,today=date(2026,11,3))
    assert result["status"]=="SKIPPED_STALE_CACHE"
    assert not (input_tree["control"]/"last_verified_batch.json").exists()


def test_cache_mutation_during_backup_never_advances_checkpoint(input_tree,monkeypatch):
    calls=[]
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    mock_batch(monkeypatch,calls)
    def backup(_,archive):
        archive.write_bytes(b"fake verified zip for mock test")
        pd.DataFrame({"Date":[pd.Timestamp("2025-10-09")],
                      "Close":[707.0]}).to_parquet(old,index=False)
    monkeypatch.setattr(schedule,"create_backup",backup)
    with pytest.raises(RuntimeError,match="revised during scheduled backup"):
        schedule.run_scheduled(**input_tree,today=TODAY)
    assert calls==["batch"]
    assert not (input_tree["control"]/"last_verified_batch.json").exists()


def test_fingerprint_rejects_missing_source_file_during_analysis(input_tree,monkeypatch):
    calls=[]
    old=input_tree["legacy"]/"datasets/external_validation/marcap/data/marcap-2025.parquet"
    mock_batch(monkeypatch,calls,old.unlink)
    with pytest.raises(ValueError,match="Untrusted/missing"):
        schedule.run_scheduled(**input_tree,today=TODAY)
    assert not (input_tree["control"]/"last_verified_batch.json").exists()
