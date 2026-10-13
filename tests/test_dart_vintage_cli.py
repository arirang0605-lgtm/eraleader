"""ER-NC local CFS vintage CLI: real pinned private originals only."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from test_dart_vintage_registry import fx, capture

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/run_dart_cfs_vintage.py"


def run(*args):
    env=dict(os.environ)
    env["PYTHONPATH"]=str(ROOT/"src")
    return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],
                          env=env,cwd=ROOT,capture_output=True,text=True,
                          timeout=30)


def test_register_asof_and_checksum_run_without_broker_or_vendor_call(fx):
    original=capture(fx)
    args=("register","--db",fx["db"],"--first-capture",original[0],
          "--first-sha256",original[1],"--directory",fx["directory"][0],
          "--directory-sha256",fx["directory"][1])
    first=run(*args)
    assert first.returncode==0,first.stderr
    receipt=json.loads(first.stdout)
    assert receipt["status"]=="PROSPECTIVE_VINTAGE_RESEARCH_RECORDED"
    assert receipt["simulated"] is False
    again=run(*args)
    assert again.returncode==0,again.stderr
    assert json.loads(again.stdout)["status"]=="ORIGINAL_ALREADY_REGISTERED"
    head=run("checksum","--db",fx["db"])
    assert head.returncode==0
    assert json.loads(head.stdout)["records"]==1
    checkpoint=run(
        "as-of","--db",fx["db"],"--stock-code","005930",
        "--corp-code","00126380","--fiscal-year","2025",
        "--decision-at",datetime.now(timezone.utc).isoformat()
    )
    assert checkpoint.returncode==0,checkpoint.stderr
    checked=json.loads(checkpoint.stdout)
    assert checked["registered_vintages_available"]==1
    assert checked["status"]=="SINGLE_LOCAL_VINTAGE_HISTORIC_PUBLICATION_UNKNOWN"
    assert checked["prospective_early_discovery_certified"] is False
    assert checked["leader_score_100"] is None


def test_wrong_first_pin_refuses_creating_false_source_rows(fx):
    original=capture(fx)
    bad=run("register","--db",fx["db"],
            "--first-capture",original[0],"--first-sha256","0"*64,
            "--directory",fx["directory"][0],
            "--directory-sha256",fx["directory"][1])
    assert bad.returncode==2
    assert bad.stdout==""
    assert "DART_VINTAGE_RESEARCH_BLOCKED" in bad.stderr
    assert str(original[0]) not in bad.stderr


def test_asof_nonexistent_sqlite_does_not_create_file(fx):
    check=run("as-of","--db",fx["db"],
              "--stock-code","005930","--corp-code","00126380",
              "--fiscal-year","2025",
              "--decision-at",datetime.now(timezone.utc).isoformat())
    assert check.returncode==2
    assert not fx["db"].exists()


def test_cli_rejects_invalid_revision_claims_and_unknown_years(fx):
    original=capture(fx)
    register=run("register","--db",fx["db"],
                 "--first-capture",original[0],
                 "--first-sha256",original[1],
                 "--directory",fx["directory"][0],
                 "--directory-sha256",fx["directory"][1])
    assert register.returncode==0
    invalid=run("as-of","--db",fx["db"],
              "--stock-code","005930","--corp-code","00126380",
              "--fiscal-year","2025",
              "--decision-at","2020-10-13T08:30:00")
    assert invalid.returncode==2
    old=run("as-of","--db",fx["db"],
              "--stock-code","005930","--corp-code","00126380",
              "--fiscal-year","2020",
              "--decision-at",datetime.now(timezone.utc).isoformat())
    assert old.returncode==0
    assert json.loads(old.stdout)["status"]=="NO_PIT_VINTAGE_AS_OF"
