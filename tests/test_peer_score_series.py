"""Synthetic append-only market-local peer score history and rotation corroboration."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.peer_score_series import (
    record_peer_score_series, audit_peer_score_advantage, STATUS, AUDIT_STATUS,
)
from eraleader.rank_score_pipeline import compute_research_score
from test_watch_progression import snapshot, MODEL

ROOT = datetime(2026,10,1,1,tzinfo=timezone.utc)  # KR 10:00
EVALUATED = "2026-10-06T10:00:00+09:00"
NOW = datetime(2026,10,11,tzinfo=timezone.utc)


def values(score: float) -> dict:
    """Each factor as a proportional fixed-target proxy of wanted score."""
    t=score/100
    return {
        "revenue_yoy":round(.5*t,9),
        "operating_income_yoy":round(.75*t,9),
        "industry_revenue_yoy":round(.30*t,9),
        "momentum_6m":round(.60*t,9),
    }


def screen(reg,day,sec,hit,*,minute=0,sector="SEMICON",market="KR",moment=None):
    t = moment if moment is not None else ROOT+timedelta(days=day,minutes=minute)
    obj=snapshot(t,security=sec,hit=hit,market=market)
    obj["company_rows"][0]["industry_id"]=sector
    return reg.record_integrated(obj,clock=t),t


def doc(root,day,sec,score,at,*,market="KR",model=MODEL):
    folder=root/at.astimezone(
        __import__("zoneinfo").ZoneInfo("Asia/Seoul" if market=="KR"
                                        else "America/New_York")
    ).date().isoformat()
    folder.mkdir(parents=True,exist_ok=True)
    source=folder/(sec+".json")
    blob={
        "schema":"eraleader.rank_feature_document.v1",
        "market":market,"model_version":model,"security_id":sec,
        "available_at":(at-timedelta(minutes=1)).isoformat(),
        "features":values(score),
    }
    source.write_text(json.dumps(blob,sort_keys=True))
    return source


def setup(tmp_path,*,second_advantage=72,late_second=False):
    root=tmp_path/"feature_source"
    root.mkdir()
    watch=tmp_path/"prospective.sqlite"
    score_db=tmp_path/"peer_scores.sqlite"
    reg=ProspectiveRegistry(watch)
    try:
        screen(reg,0,"INC",True)
        screen(reg,1,"INC",True)
        for day,inc,cont in [(2,40,65),(3,38,second_advantage)]:
            _,a=screen(reg,day,"INC",False)
            if not (late_second and day==3):
                _,b=screen(reg,day,"NEW",True,minute=5)
            else:
                b=None
            doc(root,day,"INC",inc,a+timedelta(minutes=9))
            if b is not None:
                doc(root,day,"NEW",cont,a+timedelta(minutes=9))
            record_peer_score_series(score_db,watch,root,market="KR",
                       model_version=MODEL,clock=a+timedelta(minutes=10))
    finally:reg.close()
    return watch,score_db,root


def compare(bundle,**kwargs):
    watch,series,files=bundle
    return audit_peer_score_advantage(watch,series,files,market="KR",
                model_version=MODEL,evaluated_at=EVALUATED,clock=NOW,**kwargs)


def test_two_contemporaneous_score_advantages_not_a_leader_promotion(tmp_path):
    bundle=setup(tmp_path)
    result=compare(bundle)
    assert result["status"]==AUDIT_STATUS
    assert result["rotation_hypothesis_count"]==1
    assert result["locally_two_session_score_correlated"]==1
    assert result["uncorroborated_rotation_hypotheses"]==0
    row=result["hypothesis_sample"][0]
    assert row["incumbent_security_id"]=="INC"
    assert row["contender_security_id"]=="NEW"
    assert row["locally_score_correlated"] is True
    assert len(row["last_two_paired_market_days"])==2
    assert min(row["last_two_contender_minus_incumbent_scores"]) >= 5
    assert result["official_leader_replacements"]==0
    assert result["issuer_industry_pit_certified"] is False
    assert result["real_leader_replacement_certified"] is False


def test_latest_weak_advantage_not_cherry_picked_as_two_strong(tmp_path):
    b=setup(tmp_path,second_advantage=40)
    report=compare(b)
    assert report["rotation_hypothesis_count"]==1
    assert report["locally_two_session_score_correlated"]==0
    assert report["uncorroborated_rotation_hypotheses"]==1
    assert "RECENT_TWO_PEER_SCORE_ADVANTAGES_INSUFFICIENT" in report["hypothesis_sample"][0]["issues"]


def test_one_paired_session_remains_uncorroborated(tmp_path):
    b=setup(tmp_path,late_second=True)
    report=compare(b)
    assert report["rotation_hypothesis_count"]==0
    assert report["locally_two_session_score_correlated"]==0


def test_existing_first_rank_score_ledger_is_unmodified_or_recreated(tmp_path):
    b=setup(tmp_path)
    watch,score,files=b
    assert not (tmp_path/"rank_scores.sqlite").exists()
    with sqlite3.connect(score) as db:
        rows=db.execute("SELECT security_id, observed_at_utc, payload FROM peer_score_observations").fetchall()
    assert len(rows)==4
    assert {r[0] for r in rows}=={"INC","NEW"}
    assert len({r[1] for r in rows})==4
    assert all(json.loads(r[2])["computation_provenance"]["kind"]=="LOCAL_FIXED_FOUR_FACTOR" for r in rows)


def test_replay_same_screen_does_not_replace_original_score_timestamp(tmp_path):
    b=setup(tmp_path)
    watch,db,files=b
    with sqlite3.connect(db) as conn:
        old=conn.execute("SELECT payload FROM peer_score_observations WHERE security_id='INC' ORDER BY observed_at_utc DESC LIMIT 1").fetchone()[0]
    # Same local session and original features, 30 minutes after screen.
    time=ROOT+timedelta(days=3,minutes=30)
    again=record_peer_score_series(db,watch,files,market="KR",model_version=MODEL,clock=time)
    assert again["new_score_events"]==0
    assert again["unchanged_score_events"]==2
    with sqlite3.connect(db) as conn:
        new=conn.execute("SELECT payload FROM peer_score_observations WHERE security_id='INC' ORDER BY observed_at_utc DESC LIMIT 1").fetchone()[0]
    assert new==old


def test_later_revision_same_screen_is_rejected_without_mutation(tmp_path):
    b=setup(tmp_path)
    watch,db,files=b
    path=files/"2026-10-04"/"INC.json"
    original=path.read_text()
    docdata=json.loads(original)
    docdata["features"]=values(85)
    path.write_text(json.dumps(docdata,sort_keys=True))
    with pytest.raises(ValueError,match="rewritten|revised"):
        record_peer_score_series(db,watch,files,market="KR",model_version=MODEL,
                                 clock=ROOT+timedelta(days=3,minutes=30))
    # Original evidence remains present in SQLite even though source was tampered.
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM peer_score_observations").fetchone()[0]==4
    with pytest.raises(ValueError,match="revised"):
        compare(b)


def test_missing_or_changed_archived_source_blocks_audit(tmp_path):
    b=setup(tmp_path)
    path=b[2]/"2026-10-03"/"NEW.json"
    path.unlink()
    with pytest.raises(ValueError,match="Missing|symlinked"):
        compare(b)


def test_future_feature_available_at_cannot_enter_score_now(tmp_path):
    b=setup(tmp_path)
    data=b[2]/"2026-10-04"/"INC.json"
    obj=json.loads(data.read_text())
    obj["available_at"]="2026-10-05T10:00:00+09:00"
    data.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="Future feature"):
        record_peer_score_series(b[1],b[0],b[2],market="KR",model_version=MODEL,
            clock=ROOT+timedelta(days=3,minutes=30))


def test_history_source_bad_hash_even_when_sqlite_hash_recomputed(tmp_path):
    b=setup(tmp_path)
    con=sqlite3.connect(b[1])
    try:
        row=con.execute("SELECT payload FROM peer_score_observations LIMIT 1").fetchone()[0]
        modified=json.loads(row)
        modified["score"]=99.
        encoded=json.dumps(modified,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        con.execute("UPDATE peer_score_observations SET payload=?,evidence_hash=? WHERE payload=?",
                    (encoded,sha256(encoded.encode()).hexdigest(),row))
        con.commit()
    finally:con.close()
    with pytest.raises(ValueError,match="revised"):
        compare(b)


def test_asof_before_second_score_is_not_retroactively_corroborated(tmp_path):
    b=setup(tmp_path)
    r=audit_peer_score_advantage(b[0],b[1],b[2],market="KR",model_version=MODEL,
        evaluated_at="2026-10-03T17:00:00+09:00",clock=NOW)
    assert r["locally_two_session_score_correlated"]==0


def test_future_cutoff_cannot_be_scored(tmp_path):
    b=setup(tmp_path)
    with pytest.raises(ValueError,match="Future"):
        audit_peer_score_advantage(b[0],b[1],b[2],market="KR",model_version=MODEL,
              evaluated_at="2030-01-01T00:00:00Z",clock=NOW)


def test_missing_explicit_watch_screen_cannot_create_a_daily_score(tmp_path):
    b=setup(tmp_path)
    row=b[2]/"2026-10-04"/"NEW.json"
    # Score must be traceable to a contemporary recorded WATCH event.
    with sqlite3.connect(b[0]) as db:
        db.execute("""DELETE FROM research_screen_observations
                      WHERE security_id='NEW' AND observed_as_of LIKE '2026-10-04%'""")
        db.commit()
    with pytest.raises(ValueError,match="Exactly one current"):
        record_peer_score_series(b[1],b[0],b[2],market="KR",model_version=MODEL,
                                 clock=ROOT+timedelta(days=3,minutes=20))


def test_atomic_score_batch_when_one_feature_document_is_invalid(tmp_path):
    b=setup(tmp_path)
    db=b[1]
    with sqlite3.connect(db) as conn:
        existing=conn.execute("SELECT count(*) FROM peer_score_observations").fetchone()[0]
    newday=ROOT+timedelta(days=4)
    watch=ProspectiveRegistry(b[0])
    try:
        screen(watch,4,"INC",False)
        screen(watch,4,"NEW",True,minute=5)
    finally:watch.close()
    doc(b[2],4,"INC",35,newday+timedelta(minutes=9))
    other=doc(b[2],4,"NEW",70,newday+timedelta(minutes=9))
    raw=json.loads(other.read_text())
    raw["features"]["outcome_next_week"]=1.
    other.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match="four observed|Exactly four"):
        record_peer_score_series(db,b[0],b[2],market="KR",model_version=MODEL,
                                 clock=newday+timedelta(minutes=10))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM peer_score_observations").fetchone()[0]==existing


def test_missing_archived_feature_day_or_unsafe_link_is_rejected(tmp_path):
    b=setup(tmp_path)
    archive=b[2]/"2026-10-04"
    moved=b[2]/"moved_original"
    archive.rename(moved)
    archive.symlink_to(moved)
    with pytest.raises(ValueError,match="symlinked"):
        compare(b)


def test_score_row_tamper_without_updating_checksum_is_rejected(tmp_path):
    b=setup(tmp_path)
    with sqlite3.connect(b[1]) as db:
        db.execute("UPDATE peer_score_observations SET payload='{}' WHERE rowid=(SELECT min(rowid) FROM peer_score_observations)")
        db.commit()
    with pytest.raises(ValueError,match="canonical|checksum|formula"):
        compare(b)


def test_missing_score_ledger_is_not_auto_created_by_auditor(tmp_path):
    b=setup(tmp_path)
    absent=tmp_path/"other.sqlite"
    with pytest.raises(ValueError,match="Missing"):
        audit_peer_score_advantage(b[0],absent,b[2],market="KR",
              model_version=MODEL,evaluated_at=EVALUATED,clock=NOW)
    assert not absent.exists()


def test_score_session_clock_naive_rejected_before_sqlite_creation(tmp_path):
    b=setup(tmp_path)
    candidate=tmp_path/"naive.sqlite"
    with pytest.raises(ValueError,match="timezone"):
        record_peer_score_series(candidate,b[0],b[2],market="KR",
            model_version=MODEL,clock=datetime(2026,10,5))
    assert not candidate.exists()


def test_cli_asof_score_audit_and_safe_derived_archive(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    b=setup(tmp_path)
    args=[
        "audit-peer-score-rotation", "--watch-ledger",str(b[0]),
        "--score-history",str(b[1]),"--feature-root",str(b[2]),
        "--market","KR","--model-version",MODEL,"--evaluated-at",EVALUATED,
        "--out",str(tmp_path/"derived")
    ]
    main(args)
    printed=json.loads(capsys.readouterr().out)
    assert printed["locally_two_session_score_correlated"]==1
    path=tmp_path/"derived"/"peer_score_rotation_kr_research.json"
    saved=json.loads(path.read_text())
    assert saved["official_leader_replacements"]==0
    assert "features" not in json.dumps(saved)
    archive=tmp_path/"derived_only.zip"
    meta=create_backup(tmp_path/"derived",archive)
    assert meta["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert z.namelist()==["peer_score_rotation_kr_research.json","MANIFEST.json"]
    restore_backup(archive,tmp_path/"recovered")
    assert (tmp_path/"recovered"/"peer_score_rotation_kr_research.json").read_bytes()==path.read_bytes()


def test_local_backup_reliably_snapshots_peer_score_sqlite_but_not_feature_documents(tmp_path):
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    b=setup(tmp_path)
    archive=tmp_path/"peer_history_backup.zip"
    summary=create_backup(tmp_path,archive)
    assert summary["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipfile:
        assert sorted(zipfile.namelist())==sorted([
            "prospective.sqlite","peer_scores.sqlite","MANIFEST.json"])
        assert "feature_source" not in "\n".join(zipfile.namelist())
    restored=tmp_path/"history_restored"
    restore_backup(archive,restored)
    with sqlite3.connect(restored/"peer_scores.sqlite") as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0]=="ok"
        assert conn.execute("SELECT count(*) FROM peer_score_observations").fetchone()[0]==4


def test_default_runtime_cli_refuses_historical_score_backfill(tmp_path):
    from eraleader.cli import main
    b=setup(tmp_path)
    target=tmp_path/"new_history.sqlite"
    with pytest.raises(SystemExit) as err:
        main(["record-peer-scores","--watch-ledger",str(b[0]),
             "--score-history",str(target),"--feature-root",str(b[2]),
             "--market","KR","--model-version",MODEL])
    assert err.value.code==2
    assert not target.exists()


def test_score_writer_accepts_explicit_current_watch_and_computed_features(tmp_path,capsys):
    from eraleader.cli import main
    from zoneinfo import ZoneInfo
    now=datetime.now(timezone.utc)
    zone=ZoneInfo("Asia/Seoul")
    sec="LIVE_Synthetic"
    db=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        body=snapshot(now-timedelta(minutes=4),security=sec,hit=True)
        body["company_rows"][0]["industry_id"]="SEMICON"
        db.record_integrated(body,clock=now-timedelta(minutes=3))
    finally:db.close()
    docs=tmp_path/"files"
    docs.mkdir()
    doc(docs,0,sec,66,now-timedelta(minutes=1))
    # doc helper uses a timezone-aware first arg; current date is from "at".
    main(["record-peer-scores","--watch-ledger",str(tmp_path/"prospective.sqlite"),
          "--score-history",str(tmp_path/"peer_scores.sqlite"),
          "--feature-root",str(docs),"--market","KR","--model-version",MODEL])
    printed=json.loads(capsys.readouterr().out)
    assert printed["new_score_events"]==1
    assert printed["real_leader_prediction_certified"] is False
    assert printed["official_leader_replacements"]==0


def test_us_new_york_dst_two_consecutive_pair_sessions(tmp_path):
    """Mar 6 EST to Mar 9 EDT must be treated as local sessions, not UTC dates."""
    from zoneinfo import ZoneInfo
    root=tmp_path/"us_features"
    root.mkdir()
    watch_path=tmp_path/"watch_us.sqlite"
    series_path=tmp_path/"peer_us.sqlite"
    ledger=ProspectiveRegistry(watch_path)
    stamps=[
        ("2026-03-05T16:00:00-05:00",True),
        ("2026-03-06T16:00:00-05:00",True),
        ("2026-03-09T16:00:00-04:00",False),
        ("2026-03-10T16:00:00-04:00",False),
    ]
    try:
        for i,(string,hit) in enumerate(stamps):
            at=datetime.fromisoformat(string)
            screen(ledger,i,"US-INC",hit,market="US",moment=at)
            if not hit:
                later=at+timedelta(minutes=5)
                screen(ledger,i,"US-NEW",True,market="US",moment=later)
                doc(root,i,"US-INC",45 if i==2 else 35,
                    at+timedelta(minutes=9),market="US")
                doc(root,i,"US-NEW",70 if i==2 else 80,
                    at+timedelta(minutes=9),market="US")
                record_peer_score_series(series_path,watch_path,root,
                    market="US",model_version=MODEL,clock=at+timedelta(minutes=10))
    finally:ledger.close()
    report=audit_peer_score_advantage(
        watch_path,series_path,root,market="US",model_version=MODEL,
        evaluated_at="2026-03-12T17:00:00-04:00",clock=NOW)
    assert report["rotation_hypothesis_count"]==1
    assert report["locally_two_session_score_correlated"]==1
    assert report["hypothesis_sample"][0]["last_two_paired_market_days"]==[
        "2026-03-09","2026-03-10"]
    assert report["official_leader_replacements"]==0


def test_old_screen_late_registration_cannot_masquerade_as_score_observed_that_day(tmp_path):
    b=setup(tmp_path)
    expected=tmp_path/"do_not_create.sqlite"
    with pytest.raises(ValueError,match="Exactly one current"):
        record_peer_score_series(expected,b[0],b[2],market="KR",
            model_version=MODEL,clock=ROOT+timedelta(days=3,hours=4))
    assert not expected.exists()


def test_duplicate_feature_keys_are_rejected_before_registering_sqlite(tmp_path):
    b=setup(tmp_path)
    source=b[2]/"2026-10-04"/"INC.json"
    raw=source.read_text()
    source.write_text(raw[:-1]+',"security_id":"INC"}')
    dest=tmp_path/"not_saved.sqlite"
    with pytest.raises(ValueError,match="Invalid prospective feature JSON"):
        record_peer_score_series(dest,b[0],b[2],market="KR",
            model_version=MODEL,clock=ROOT+timedelta(days=3,minutes=20))
    assert not dest.exists()


def test_only_same_market_and_model_scores_can_correlate(tmp_path):
    b=setup(tmp_path)
    r=audit_peer_score_advantage(
        b[0],b[1],b[2],market="US",model_version=MODEL,
        evaluated_at=EVALUATED,clock=NOW)
    assert r["rotation_hypothesis_count"]==0
    assert r["locally_two_session_score_correlated"]==0
    r=audit_peer_score_advantage(
        b[0],b[1],b[2],market="KR",model_version="FORGED_VERSION",
        evaluated_at=EVALUATED,clock=NOW)
    assert r["locally_two_session_score_correlated"]==0


def test_source_feature_file_is_not_copied_into_derived_cli_output(tmp_path,capsys):
    from eraleader.cli import main
    b=setup(tmp_path)
    out=tmp_path/"report"
    main(["audit-peer-score-rotation","--watch-ledger",str(b[0]),
          "--score-history",str(b[1]),"--feature-root",str(b[2]),
          "--market","KR","--model-version",MODEL,
          "--evaluated-at",EVALUATED,"--out",str(out)])
    capsys.readouterr()
    tree=list(out.rglob("*"))
    assert sum(p.is_file() for p in tree)==1
    report=json.loads((out/"peer_score_rotation_kr_research.json").read_text())
    assert report["rank_scores_independently_authenticated"] is False
    assert report["official_leader_replacements"]==0
