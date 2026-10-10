from datetime import date, timedelta
import json
import plistlib
from pathlib import Path
import pytest
from eraleader import local_schedule as mod

@pytest.fixture
def folders(tmp_path):
    return dict(out=tmp_path / "output", control=tmp_path / "control",
                backups=tmp_path / "backups", legacy=tmp_path / "legacy")

def test_stale_cache_skips_without_invoking_batch(folders, monkeypatch):
    monkeypatch.setattr(mod, "execute_local_batch", lambda _: pytest.fail("batch must not run"))
    result = mod.run_scheduled(**folders, today=date(2026, 10, 10),
                               sessions={"KR": date(2026, 10, 2), "US": date(2026, 2, 23)})
    assert result["status"] == "SKIPPED_STALE_CACHE"
    assert not (folders["control"] / "last_verified_batch.json").exists()

def test_verified_backup_checkpoint_and_unchanged_skip(folders, monkeypatch):
    counts = {"batch": 0, "create": 0, "verify": 0}
    def batch(args):
        counts["batch"] += 1
        assert args.kr_as_of == "2026-10-09"
        return {"market_count": 2, "reports_created": 6}
    def backup(out, archive):
        counts["create"] += 1
        assert archive.parent == folders["backups"]
        archive.write_bytes(b"test-archive")
        return {"status": "OK"}
    def verify(archive):
        counts["verify"] += 1
        return {"status": "OK"}
    monkeypatch.setattr(mod, "execute_local_batch", batch)
    monkeypatch.setattr(mod, "create_backup", backup)
    monkeypatch.setattr(mod, "verify_backup", verify)
    sessions = {"KR": date(2026, 10, 9), "US": date(2026, 10, 9)}
    first = mod.run_scheduled(**folders, today=date(2026, 10, 10), sessions=sessions)
    assert first["status"] == "RESEARCH_ONLY_VERIFIED_BACKUP"
    assert first["messages_sent"] == 0 and first["external_api_calls"] == 0
    second = mod.run_scheduled(**folders, today=date(2026, 10, 10), sessions=sessions)
    assert second["status"] == "SKIPPED_UNCHANGED_CACHE"
    assert counts == {"batch": 1, "create": 1, "verify": 2}
    saved = json.loads((folders["control"] / "last_verified_batch.json").read_text())
    assert saved["observations"] == {"KR": "2026-10-09", "US": "2026-10-09"}

def test_failed_backup_does_not_advance_checkpoint_and_retries(folders, monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "execute_local_batch",
                        lambda _: {"market_count": 2, "reports_created": 6})
    monkeypatch.setattr(mod, "create_backup", lambda *a: None)
    def verify(*args):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("corrupt backup")
    monkeypatch.setattr(mod, "verify_backup", verify)
    sessions = {"KR": date(2026, 10, 9), "US": date(2026, 10, 9)}
    with pytest.raises(ValueError, match="corrupt backup"):
        mod.run_scheduled(**folders, today=date(2026, 10, 10), sessions=sessions)
    assert not (folders["control"] / "last_verified_batch.json").exists()
    assert mod.run_scheduled(**folders, today=date(2026, 10, 10),
                             sessions=sessions)["status"] == "RESEARCH_ONLY_VERIFIED_BACKUP"

@pytest.mark.parametrize("sessions", [
    {"KR": date(2026, 10, 11), "US": date(2026, 10, 9)},
    {"KR": date(2026, 10, 9)},
])
def test_invalid_cache_dates_fail_closed(folders, sessions):
    with pytest.raises(ValueError):
        mod.run_scheduled(**folders, today=date(2026, 10, 10), sessions=sessions)

def test_stale_override_is_explicitly_research_only(folders, monkeypatch):
    monkeypatch.setattr(mod, "execute_local_batch",
                        lambda _: {"market_count": 2, "reports_created": 6})
    monkeypatch.setattr(mod, "create_backup", lambda *args: None)
    monkeypatch.setattr(mod, "verify_backup", lambda *args: None)
    result = mod.run_scheduled(**folders, today=date(2026, 10, 10),
                               sessions={"KR": date(2026, 10, 2), "US": date(2026, 2, 23)},
                               allow_stale_research=True)
    assert result["used_stale_override"] is True
    assert result["messages_sent"] == 0

def test_launchd_weekday_local_plist_generation(tmp_path):
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    (project / "scripts" / "run_local_scheduled.py").touch()
    target = tmp_path / "agent.plist"
    bootstrap = tmp_path / "offline-launcher.sh"
    mod.write_launch_agent(target, python=Path("/usr/bin/python3"), project=project,
                           bootstrap_path=bootstrap)
    content = plistlib.loads(target.read_bytes())
    assert content["Label"] == "org.eraleader.offline-research"
    assert [x["Weekday"] for x in content["StartCalendarInterval"]] == [2,3,4,5,6]
    assert all(x["Hour"] == 18 and x["Minute"] == 10 for x in content["StartCalendarInterval"])
    assert content["ProgramArguments"] == ["/bin/sh",str(bootstrap)]
    assert content["StartInterval"] == 3600
    assert bootstrap.read_text().startswith("#!/bin/sh")
    assert "--project" in bootstrap.read_text()
    assert bootstrap.stat().st_mode & 0o777 == 0o700
    assert content["RunAtLoad"] is True
    with pytest.raises(ValueError):
        mod.write_launch_agent(target, python=Path("/usr/bin/python3"),
                               project=project, hour=25)

def test_deleted_or_corrupt_backup_forces_retry(folders, monkeypatch):
    sessions = {"KR": date(2026,10,9), "US": date(2026,10,9)}
    called = {"batch":0}
    def batch(_):
        called["batch"] += 1
        return {"market_count":2,"reports_created":6}
    def make_backup(_,archive):
        archive.write_bytes(b"valid")
    def verify(archive):
        if archive.read_bytes() != b"valid":
            raise ValueError("archive corrupted")
    monkeypatch.setattr(mod,"execute_local_batch",batch)
    monkeypatch.setattr(mod,"create_backup",make_backup)
    monkeypatch.setattr(mod,"verify_backup",verify)
    first=mod.run_scheduled(**folders,today=date(2026,10,10),sessions=sessions)
    assert called["batch"]==1
    assert mod.run_scheduled(**folders,today=date(2026,10,10),sessions=sessions)["status"]=="SKIPPED_UNCHANGED_CACHE"
    assert called["batch"]==1
    Path(first["archive"]).unlink()
    second=mod.run_scheduled(**folders,today=date(2026,10,10),sessions=sessions)
    assert called["batch"]==2 and second["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    Path(second["archive"]).write_bytes(b"corrupted")
    third=mod.run_scheduled(**folders,today=date(2026,10,10),sessions=sessions)
    assert called["batch"]==3 and third["status"]=="RESEARCH_ONLY_VERIFIED_BACKUP"
    assert Path(third["archive"]).read_bytes()==b"valid"

def test_home_bootstrap_survives_missing_and_restored_external_cache(tmp_path,monkeypatch):
    import subprocess,sys
    project=tmp_path/"Removable SSD"/"era leader"
    script=project/"scripts"/"run_local_scheduled.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('LOCAL_RESEARCH_ENTRYPOINT_REACHED')")
    cache=tmp_path/"not-yet-mounted-cache"
    monkeypatch.setattr(mod,"LEGACY_DEFAULT",cache)
    launcher=tmp_path/"home"/"offline-launcher.sh"
    mod.write_launch_agent(tmp_path/"agent.plist",project=project,
                           python=Path(sys.executable),bootstrap_path=launcher)
    missing=subprocess.run(["/bin/sh",str(launcher)],capture_output=True,text=True,check=True)
    assert "SKIPPED_EXTERNAL_SSD_UNAVAILABLE" in missing.stdout
    assert "ENTRYPOINT_REACHED" not in missing.stdout
    cache.mkdir()
    restored=subprocess.run(["/bin/sh",str(launcher)],capture_output=True,text=True,check=True)
    assert "LOCAL_RESEARCH_ENTRYPOINT_REACHED" in restored.stdout

def test_bootstrap_target_symlink_is_rejected(tmp_path):
    project=tmp_path/"project"
    (project/"scripts").mkdir(parents=True)
    (project/"scripts"/"run_local_scheduled.py").touch()
    outside=tmp_path/"outside.txt"
    outside.write_text("do not change")
    launcher=tmp_path/"launcher.sh"
    launcher.symlink_to(outside)
    with pytest.raises(ValueError,match="Symlink"):
        mod.write_launch_agent(tmp_path/"agent.plist",project=project,
                               python=Path("/usr/bin/python3"),bootstrap_path=launcher)
    assert outside.read_text()=="do not change"
