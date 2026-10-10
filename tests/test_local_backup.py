import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import pytest

from eraleader.local_backup import create_backup, verify_backup, restore_backup

def workspace(tmp_path):
    output=tmp_path/"output"
    output.mkdir()
    conn=sqlite3.connect(output/"state.sqlite")
    conn.execute("CREATE TABLE test_events(id TEXT PRIMARY KEY,value INTEGER)")
    conn.execute("INSERT INTO test_events VALUES('first',100)")
    conn.commit()
    conn.close()
    (output/"site").mkdir()
    (output/"site"/"kr.html").write_text("<h1>Research ONLY</h1>")
    (output/"reports").mkdir()
    (output/"reports"/"daily.md").write_text("# Offline Daily")
    (output/"runs").mkdir()
    (output/"runs"/"run.json").write_text('{"status":"WATCH"}')
    (output/".env").write_text("NEVER_ARCHIVE=secret")
    (output/"raw_secret.json").write_text('{"private_api_key":"SECRET"}')
    return output

def test_local_backup_consistent_and_restore_atomic(tmp_path):
    output=workspace(tmp_path)
    archive=tmp_path/"backups"/"sample.zip"
    saved=create_backup(output,archive)
    assert saved["status"]=="LOCAL_BACKUP_CREATED"
    checked=verify_backup(archive)
    assert checked["file_count"]==4
    restored=tmp_path/"fresh"
    result=restore_backup(archive,restored)
    assert result["status"]=="LOCAL_BACKUP_RESTORED"
    assert (restored/"site"/"kr.html").read_text()=="<h1>Research ONLY</h1>"
    conn=sqlite3.connect(restored/"state.sqlite")
    try:
        assert conn.execute("SELECT value FROM test_events WHERE id='first'").fetchone()==(100,)
    finally:conn.close()
    assert not (restored/".env").exists()
    assert not (restored/"raw_secret.json").exists()
    with pytest.raises(FileExistsError,match="already exists"):
        restore_backup(archive,restored)
    with pytest.raises(FileExistsError,match="already exists"):
        create_backup(output,archive)

def test_backup_checks_sha_before_restore(tmp_path):
    output=workspace(tmp_path)
    archive=tmp_path/"archive.zip"
    create_backup(output,archive)
    with ZipFile(archive) as original:
        values={name:original.read(name) for name in original.namelist()}
    values["site/kr.html"]=b"<h1>tampered</h1>"
    with ZipFile(archive,"w",ZIP_DEFLATED) as dest:
        for name,raw in values.items():dest.writestr(name,raw)
    with pytest.raises(ValueError,match="hash mismatch"):
        verify_backup(archive)
    with pytest.raises(ValueError,match="hash mismatch"):
        restore_backup(archive,tmp_path/"should_not_exist")
    assert not (tmp_path/"should_not_exist").exists()

def test_backup_refuses_path_traversal_and_unknown_files(tmp_path):
    output=workspace(tmp_path)
    archive=tmp_path/"archive.zip"
    create_backup(output,archive)
    with ZipFile(archive,"a") as z:
        z.writestr("../outside.txt","malicious")
    with pytest.raises(ValueError,match="Unsafe archive"):
        verify_backup(archive)

def test_no_artifact_to_backup_and_symlink_denied(tmp_path):
    empty=tmp_path/"empty"
    empty.mkdir()
    with pytest.raises(ValueError,match="No verified"):
        create_backup(empty,tmp_path/"none.zip")
    output=workspace(tmp_path)
    (output/"site"/"link.html").symlink_to(tmp_path/"outside.txt")
    with pytest.raises(ValueError,match="Unsafe source"):
        create_backup(output,tmp_path/"unsafe.zip")

def test_sqlite_backup_excludes_uncommitted_wal_data(tmp_path):
    output=workspace(tmp_path)
    database=output/"state.sqlite"
    conn=sqlite3.connect(database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN")
    conn.execute("INSERT INTO test_events VALUES('uncommitted',999)")
    archive=tmp_path/"backup.zip"
    try:
        create_backup(output,archive)
    finally:
        conn.rollback();conn.close()
    restore_backup(archive,tmp_path/"recovered")
    restored=sqlite3.connect(tmp_path/"recovered"/"state.sqlite")
    try:
        assert restored.execute("SELECT COUNT(*) FROM test_events").fetchone()[0]==1
        assert restored.execute("PRAGMA quick_check").fetchone()[0]=="ok"
    finally:restored.close()


def test_backup_cli_create_verify_restore(tmp_path,capsys):
    import json
    from eraleader.cli import main
    output=workspace(tmp_path)
    archive=tmp_path/"archive.zip"
    main(["backup-local","--out",str(output),"--archive",str(archive)])
    written=json.loads(capsys.readouterr().out)
    assert written["status"]=="LOCAL_BACKUP_CREATED"
    main(["verify-backup","--archive",str(archive)])
    verified=json.loads(capsys.readouterr().out)
    assert verified["status"]=="LOCAL_BACKUP_VERIFIED"
    target=tmp_path/"restore_via_cli"
    main(["restore-backup","--archive",str(archive),"--target",str(target)])
    recovered=json.loads(capsys.readouterr().out)
    assert recovered["status"]=="LOCAL_BACKUP_RESTORED"
    assert (target/"state.sqlite").is_file()

def test_prospective_registry_survives_verified_backup_restore(tmp_path):
    from datetime import datetime, timezone
    from eraleader.prospective import ProspectiveRegistry
    output=workspace(tmp_path)
    registry=ProspectiveRegistry(output/"prospective.sqlite")
    sample={"market":"KR","as_of":"2024-09-01T17:00:00+09:00",
            "run_id":"test-run-v1","version":"era-offline-join-0.1",
            "pit_certified":False,"offline_provenance":["synthetic_fixture"],
            "company_rows":[{"security_id":"SYN-1","market":"KR",
                 "as_of":"2024-09-01T17:00:00+09:00","state":"WATCH",
                 "full_score":None,"verified_future_leader_candidate":False,
                 "research_growth_screen_hit":True}]}
    try:
        registry.record_integrated(sample,clock=datetime(2026,10,10,tzinfo=timezone.utc))
    finally:
        registry.close()
    archive=tmp_path/"prospective_backup.zip"
    created=create_backup(output,archive)
    assert created["file_count"]==5
    with ZipFile(archive) as z:
        assert "prospective.sqlite" in z.namelist()
        assert "raw_secret.json" not in z.namelist()
        assert ".env" not in z.namelist()
    verify_backup(archive)
    recovered=tmp_path/"restored_with_prospective"
    restore_backup(archive,recovered)
    restored_ledger=ProspectiveRegistry(recovered/"prospective.sqlite")
    try:
        records=restored_ledger.first_signals("KR")["first_registration_signals"]
        assert len(records)==1
        assert records[0]["first_seen"]=="2024-09-01"
        assert records[0]["recorded_at"]=="2026-10-10"
        assert records[0]["status"]=="PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED"
    finally:
        restored_ledger.close()

def test_total_return_audit_json_is_allowlisted_without_raw_payload(tmp_path):
    output=tmp_path/"audit"
    output.mkdir()
    report={"status":"RESEARCH_RETURN_SERIES_DISAGREE",
            "historic_price_actions_pit_certified":False,
            "exception_samples":[{"session":"2024-04-03","deviation_bps":200}]}
    (output/"total_return_crosscheck_research.json").write_text(json.dumps(report))
    (output/"raw_source_dump.json").write_text('{"api_key":"DO_NOT_COPY"}')
    archive=tmp_path/"audit.zip"
    create_backup(output,archive)
    assert verify_backup(archive)["file_count"]==1
    with ZipFile(archive) as reader:
        assert reader.namelist()==["total_return_crosscheck_research.json","MANIFEST.json"]
    restored=tmp_path/"restored_audit"
    restore_backup(archive,restored)
    assert json.loads((restored/"total_return_crosscheck_research.json").read_text())==report
    assert not (restored/"raw_source_dump.json").exists()

def test_continuity_derived_outputs_are_backed_up_without_original_prices(tmp_path):
    from eraleader.local_backup import create_backup, verify_backup, restore_backup
    from zipfile import ZipFile
    output=tmp_path/"research"
    output.mkdir()
    for market in ("kr","us"):
        (output/f"continuity_{market}_research.json").write_text(
            json.dumps({"status":"LOCAL_OBSERVATION_CONTINUITY_NOT_PIT_CERTIFIED",
                        "market":market.upper(),"historic_universe_pit_certified":False}))
    (output/"raw_price_dump.json").write_text('{"private_key":"NEVER_BACKUP"}')
    archive=tmp_path/"continuity.zip"
    result=create_backup(output,archive)
    assert result["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert set(z.namelist())=={
            "continuity_kr_research.json","continuity_us_research.json","MANIFEST.json"}
    target=tmp_path/"restored"
    restore_backup(archive,target)
    assert not (target/"raw_price_dump.json").exists()
    for market in ("kr","us"):
        assert json.loads((target/f"continuity_{market}_research.json").read_text())[
            "historic_universe_pit_certified"] is False

def test_calendar_derived_audit_is_backed_up_but_not_original_reference(tmp_path):
    from eraleader.local_backup import create_backup, verify_backup, restore_backup
    from zipfile import ZipFile
    output=tmp_path/"calendar_derived"
    output.mkdir()
    expected={"status":"LOCAL_CALENDAR_COMPARISON_NOT_PIT_CERTIFIED",
              "calendar_independently_attested":False,
              "calendar_pit_certified":False}
    for market in ("kr","us"):
        (output/f"calendar_{market}_research.json").write_text(json.dumps(expected))
    (output/"calendar_reference_raw.json").write_text('{"private_token":"DO_NOT_COPY"}')
    archive=tmp_path/"calendar_derived.zip"
    result=create_backup(output,archive)
    assert result["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipped:
        assert set(zipped.namelist())=={
            "calendar_kr_research.json","calendar_us_research.json","MANIFEST.json"}
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert not (restored/"calendar_reference_raw.json").exists()
    assert json.loads((restored/"calendar_kr_research.json").read_text())==expected

def test_derived_cash_delisting_report_is_backed_up_not_raw_payout_document(tmp_path):
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    root=tmp_path/"cash_research"
    root.mkdir()
    result={"status":"LOCAL_CASH_DELISTING_RESEARCH_ONLY",
            "cash_exit_total_return":0.10,"pit_certified":False}
    (root/"cash_delisting_research.json").write_text(json.dumps(result))
    (root/"settlement_original_private.json").write_text('{"api_key":"NO_UPLOAD"}')
    target=tmp_path/"cash_backup.zip"
    assert create_backup(root,target)["file_count"]==1
    assert verify_backup(target)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(target) as reader:
        assert reader.namelist()==["cash_delisting_research.json","MANIFEST.json"]
    recovered=tmp_path/"new_recovery"
    restore_backup(target,recovered)
    assert json.loads((recovered/"cash_delisting_research.json").read_text())==result
    assert not (recovered/"settlement_original_private.json").exists()
