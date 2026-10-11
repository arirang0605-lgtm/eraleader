"""6_2/6_5 opted-in local operations + dry-run alert evidence dashboard."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json
import sqlite3
import subprocess
import sys

import pytest
from test_operations_overview import NOW, seed
from eraleader.local_failure_outbox import run_local_failure_outbox
from eraleader.operations_alert_bridge import (
    audit_operations_alert_dashboard,
    render_operations_alert_dashboard,
    publish_operations_alert_dashboard,
)

SOURCE=Path(__file__).resolve().parents[1]


def paths(project):
    root=project/"output"
    return (root/"local_failure_outbox"/"dry_run_alerts.sqlite",
            root/"local_failure_outbox_control"/"verified.json",
            root/"local_failure_outbox"/"dry_run_alerts_research.json",
            root/"local_failure_outbox"/"site"/"index.html")


def fixtures(project):
    seed(project,"price")
    run_local_failure_outbox(project,clock=NOW)


def audit(project,at=NOW):
    return audit_operations_alert_dashboard(project,clock=at)


def alert(report):
    return report["local_failure_outbox"]


def test_unconfigured_alerts_remain_unknown_and_not_false_market_failure(tmp_path):
    item=audit(tmp_path)
    assert alert(item)["evidence_state"]=="OUTBOX_NOT_CONFIGURED"
    assert alert(item)["historical_event_count"] is None
    assert alert(item)["active_local_faults"] is None
    assert item["operations"]["modes"]["watch"]["state"]=="NO_CHECKPOINT"
    assert item["official_leader_promotions"]==0 and item["real_precision_at_k"] is None


def test_verified_event_count_and_status_match_real_sqlite_and_zip(tmp_path):
    fixtures(tmp_path)
    item=audit(tmp_path)
    info=alert(item)
    assert info["evidence_state"]=="VERIFIED_LOCAL_SNAPSHOT"
    assert info["verified_local_backup"] is True
    assert info["matches_current_scheduler"] is True
    assert info["historical_event_count"]==1 and info["active_local_faults"]==1
    assert len(info["recent_events"])==1
    assert info["recent_events"][0]["type"]=="DATA_FAILURE_LOCAL"
    assert item["live_notifications_sent"]==0
    assert item["actual_future_leader_skill_certified"] is False
    html=render_operations_alert_dashboard(item)
    assert "DATA_FAILURE_LOCAL" in html and "N/A" in html
    assert "실제 발송" in html and "공식" in html


def test_last_good_alert_becomes_stale_after_new_scheduler_checkpoint(tmp_path):
    fixtures(tmp_path)
    seed(tmp_path,"watch")
    info=alert(audit(tmp_path))
    assert info["evidence_state"]=="OUTBOX_STALE_VS_SCHEDULER"
    assert info["matches_current_scheduler"] is False
    assert info["verified_local_backup"] is True


@pytest.mark.parametrize("which",["json","html","zip","sqlite","checkpoint"])
def test_outbox_tamper_never_displays_verified_counts(tmp_path,which):
    fixtures(tmp_path)
    db,checkpoint,report,page=paths(tmp_path)
    archive=Path(json.loads(checkpoint.read_text())["archive"])
    if which=="json":
        report.write_bytes(report.read_bytes()+b" ")
    elif which=="html":
        page.write_bytes(page.read_bytes()+b" ")
    elif which=="zip":
        archive.write_bytes(b"bad-zip")
    elif which=="sqlite":
        db.write_bytes(b"bad-sqlite")
    else:
        cp=json.loads(checkpoint.read_text())
        cp["total_events"]=999
        checkpoint.write_text(json.dumps(cp))
    info=alert(audit(tmp_path))
    assert info["evidence_state"]=="OUTBOX_UNVERIFIED"
    assert info["historical_event_count"] is None
    assert info["active_local_faults"] is None
    assert info["verified_local_backup"] is False


@pytest.mark.parametrize("field,value", [
    ("messages_sent",1), ("external_api_calls",1),
    ("official_leaders_confirmed",1),
    ("actual_future_leader_skill_certified",True),
    ("local_artifacts_only",False),
    ("status","LIVE_SENT"),
])
def test_fake_live_or_certified_outbox_checkpoint_rejected(tmp_path,field,value):
    fixtures(tmp_path)
    cp=paths(tmp_path)[1]
    payload=json.loads(cp.read_text())
    payload[field]=value
    cp.write_text(json.dumps(payload))
    assert alert(audit(tmp_path))["evidence_state"]=="OUTBOX_UNVERIFIED"


def test_archive_redirect_to_valid_external_file_is_rejected(tmp_path):
    fixtures(tmp_path)
    cp=paths(tmp_path)[1]
    record=json.loads(cp.read_text())
    archive=Path(record["archive"])
    outside=tmp_path/"valid-other.zip"
    outside.write_bytes(archive.read_bytes())
    record["archive"]=str(outside)
    cp.write_text(json.dumps(record))
    assert alert(audit(tmp_path))["evidence_state"]=="OUTBOX_UNVERIFIED"
    assert outside.is_file()


def test_symlink_report_and_db_are_rejected_without_following(tmp_path):
    fixtures(tmp_path)
    db,checkpoint,report,page=paths(tmp_path)
    outside=tmp_path/"outside-secret"
    outside.write_bytes(b"DO_NOT_READ_OR_CHANGE")
    report.unlink()
    report.symlink_to(outside)
    assert alert(audit(tmp_path))["evidence_state"]=="OUTBOX_UNVERIFIED"
    assert outside.read_bytes()==b"DO_NOT_READ_OR_CHANGE"


def test_archive_snapshot_sqlite_rehashed_but_corrupt_rejected(tmp_path):
    fixtures(tmp_path)
    cp=json.loads(paths(tmp_path)[1].read_text())
    archive=Path(cp["archive"])
    with ZipFile(archive) as z:
        items={name:z.read(name) for name in z.namelist()}
    manifest=json.loads(items["MANIFEST.json"])
    for entry in manifest["files"]:
        if entry["path"]=="dry_run_alerts.sqlite":
            items[entry["path"]]=b"INVALID SQLITE" + b"0"*(entry["bytes"]-14)
            entry["bytes"]=len(items[entry["path"]])
            entry["sha256"]=sha256(items[entry["path"]]).hexdigest()
    manifest["total_input_bytes"]=sum(x["bytes"] for x in manifest["files"])
    items["MANIFEST.json"]=json.dumps(manifest).encode()
    with ZipFile(archive,"w") as z:
        for name,data in items.items():
            z.writestr(name,data)
    assert alert(audit(tmp_path))["evidence_state"]=="OUTBOX_UNVERIFIED"


def test_mid_audit_source_mutation_fails_before_publishing(tmp_path,monkeypatch):
    fixtures(tmp_path)
    from eraleader import operations_alert_bridge as mod
    original=mod.audit_operations_alert_dashboard
    calls=[0]
    def changed(*a,**kw):
        data=original(*a,**kw)
        calls[0]+=1
        if calls[0]==2:
            data["local_failure_outbox"]["historical_event_count"]=777
        return data
    monkeypatch.setattr(mod,"audit_operations_alert_dashboard",changed)
    with pytest.raises(RuntimeError,match="changed"):
        mod.publish_operations_alert_dashboard(tmp_path,clock=NOW)
    assert not (tmp_path/"output"/"operations_alerts"/"site"/"index.html").exists()


def test_publish_writes_separate_sanitized_pages_and_preserves_sources(tmp_path):
    fixtures(tmp_path)
    original_ops=tmp_path/"output"/"operations"/"site"/"index.html"
    original_ops.parent.mkdir(parents=True,exist_ok=True)
    original_ops.write_text("PREEXISTING HOME")
    originals=[*paths(tmp_path),tmp_path/"output"/"scheduler_control"/"last_verified_batch.json"]
    digests={str(p):sha256(p.read_bytes()).hexdigest() for p in originals}
    result=publish_operations_alert_dashboard(tmp_path,clock=NOW)
    assert result["status"]=="LOCAL_OPERATIONS_ALERT_DASHBOARD_RESEARCH_ONLY"
    assert result["published_derived_pages"]==2
    assert result["live_notifications_sent"]==0
    index=tmp_path/"output"/"operations_alerts"/"site"/"index.html"
    assert "DATA_FAILURE_LOCAL" in index.read_text()
    assert json.loads((tmp_path/"output"/"operations_alerts"/"operations_alerts_research.json").read_text())["local_failure_outbox"]["historical_event_count"]==1
    assert original_ops.read_text()=="PREEXISTING HOME"
    assert {str(p):sha256(p.read_bytes()).hexdigest() for p in originals}==digests


def test_cli_opt_in_does_not_change_default_operations_mode(tmp_path):
    fixtures(tmp_path)
    script=SOURCE/"scripts"/"render_local_operations.py"
    normal=subprocess.run([sys.executable,str(script),"--project",str(tmp_path)],
                          capture_output=True,text=True)
    assert normal.returncode==0,normal.stderr
    assert json.loads(normal.stdout)["status"]=="LOCAL_OPERATIONS_OVERVIEW_RESEARCH_ONLY"
    opt=subprocess.run([sys.executable,str(script),"--project",str(tmp_path),"--include-local-outbox"],
                       capture_output=True,text=True)
    assert opt.returncode==0,opt.stderr
    assert json.loads(opt.stdout)["status"]=="LOCAL_OPERATIONS_ALERT_DASHBOARD_RESEARCH_ONLY"
    assert "실전" in (tmp_path/"output"/"operations_alerts"/"site"/"index.html").read_text()


def test_renderer_blocks_forged_success_field(tmp_path):
    fixtures(tmp_path)
    item=audit(tmp_path)
    item["official_leader_promotions"]=1
    with pytest.raises(ValueError,match="live|leader|official|unsafe|certif"):
        render_operations_alert_dashboard(item)
