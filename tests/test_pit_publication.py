"""Durable on-disk publication boundary for opt-in PIT research batches.

Fully synthetic fixture and injected filesystem failures; no investment
outcomes, broker operations, network, or official source PIT evidence.
"""
import json
from pathlib import Path
import pytest
from eraleader.cli import main
from eraleader.pit_publication import verify_pit_publication, POINTER
from test_batch_pit_integration import src, optin


def publish(root, capsys):
    main(optin(root))
    return json.loads(capsys.readouterr().out)


def test_published_two_market_generation_and_source_isolation(src,capsys):
    before=(src/"offline.sqlite").read_bytes()
    reported=publish(src,capsys)
    assert reported["status"]=="PUBLISHED_OFFLINE_PIT_RESEARCH_ONLY"
    assert reported["official_leaders"]==0 and reported["pit_certified"] is False
    active=verify_pit_publication(src)
    assert active["status"]=="VERIFIED_LOCAL_RESEARCH_PUBLICATION"
    manifest=json.loads(Path(active["manifest"]).read_text())
    assert manifest["explicit_offline_pit_research"] is True
    assert [m["market"] for m in manifest["markets"]]==["KR","US"]
    assert all(Path(m["dashboard"]).is_file() for m in manifest["markets"])
    assert all(Path(m["pit_research"]["research_dashboard"]).is_file()
               for m in manifest["markets"])
    assert all(m["pit_research"]["pit_certified"] is False for m in manifest["markets"])
    assert not (src/"state.sqlite").exists()
    assert not (src/"prospective.sqlite").exists()
    assert not (src/"batch_manifest.json").exists()
    assert before==(src/"offline.sqlite").read_bytes()
    assert active["artifact_count"]>10


def test_repeat_publishes_new_version_and_keeps_first_immutable(src,capsys):
    first=publish(src,capsys)
    original=verify_pit_publication(src)
    original_bytes=Path(original["manifest"]).read_bytes()
    next_report=publish(src,capsys)
    new=verify_pit_publication(src)
    assert new["generation_id"] != original["generation_id"]
    assert new["manifest"] != original["manifest"]
    assert Path(original["manifest"]).read_bytes()==original_bytes
    next_manifest=json.loads(Path(new["manifest"]).read_text())
    assert all(m["pit_research"]["new_watch_research_signals"]==0
               for m in next_manifest["markets"])
    assert next_report["official_leaders"]==0


def test_second_market_runtime_failure_keeps_old_version_only(src,capsys,monkeypatch):
    publish(src,capsys)
    previous=verify_pit_publication(src)
    pointer=(src/POINTER).read_bytes()
    from eraleader import batch
    original=batch.execute_integrated
    calls=[]
    def break_after_kr(args):
        calls.append(args.market)
        if args.market=="US":
            raise ValueError("SYNTHETIC_CRASH_DURING_US_PERSISTENCE")
        return original(args)
    monkeypatch.setattr(batch,"execute_integrated",break_after_kr)
    with pytest.raises(SystemExit) as err:
        main(optin(src))
    assert err.value.code==2
    assert calls==["KR","US"]
    assert (src/POINTER).read_bytes()==pointer
    assert verify_pit_publication(src)["generation_id"]==previous["generation_id"]
    assert not list((src/".pit_staging").iterdir())


def test_failed_first_generation_has_no_published_outputs(src,monkeypatch):
    from eraleader import batch
    original=batch.execute_integrated
    def fail_on_us(args):
        if args.market=="US":
            raise ValueError("SYNTHETIC_US_PERSISTENCE_FAILED")
        return original(args)
    monkeypatch.setattr(batch,"execute_integrated",fail_on_us)
    with pytest.raises(SystemExit) as error:
        main(optin(src))
    assert error.value.code==2
    assert verify_pit_publication(src) is None
    assert not (src/"state.sqlite").exists()
    assert not (src/"batch_manifest.json").exists()
    assert not list((src/".pit_staging").iterdir())


def test_atomic_pointer_replace_failure_preserves_last_healthy_generation(src,capsys,monkeypatch):
    publish(src,capsys)
    previous=verify_pit_publication(src)
    prior_pointer=(src/POINTER).read_bytes()
    from eraleader import pit_publication
    original=pit_publication.os.replace
    def fail_pointer(src_path,dst_path):
        if Path(dst_path).name==POINTER:
            raise OSError("SYNTHETIC_POINTER_ATOMIC_REPLACE_FAILED")
        return original(src_path,dst_path)
    monkeypatch.setattr(pit_publication.os,"replace",fail_pointer)
    with pytest.raises(SystemExit) as error:
        main(optin(src))
    assert error.value.code==2
    monkeypatch.setattr(pit_publication.os,"replace",original)
    assert (src/POINTER).read_bytes()==prior_pointer
    assert verify_pit_publication(src)["generation_id"]==previous["generation_id"]
    # A fully written generation without a committed pointer is an orphan,
    # never current and must not be reported as latest by consumers.
    assert len(list((src/"pit_generations").iterdir()))==2
    assert not list((src/".pit_staging").iterdir())
    publish(src,capsys)
    assert verify_pit_publication(src)["generation_id"]!=previous["generation_id"]


def test_corrupt_current_artifact_fails_closed_before_next_run(src,capsys):
    publish(src,capsys)
    active=verify_pit_publication(src)
    report=Path(active["generation"])/"reports"
    item=next(report.rglob("*.md"))
    item.write_text(item.read_text()+"\nTAMPERED\n")
    with pytest.raises(ValueError,match="artifacts changed"):
        verify_pit_publication(src)
    pointer=(src/POINTER).read_bytes()
    with pytest.raises(SystemExit) as error:
        main(optin(src))
    assert error.value.code==2
    assert (src/POINTER).read_bytes()==pointer


def test_symlinked_generation_or_pointer_never_becomes_current(src,capsys,tmp_path):
    publish(src,capsys)
    pointer=src/POINTER
    backup=src/"pointer.bak"
    pointer.rename(backup)
    pointer.symlink_to(backup)
    with pytest.raises(ValueError,match="Unsafe PIT publication pointer"):
        verify_pit_publication(src)
    pointer.unlink()
    backup.rename(pointer)
    prior=verify_pit_publication(src)
    folder=Path(prior["generation"])
    saved=folder.with_name(folder.name+"-renamed")
    folder.rename(saved)
    folder.symlink_to(saved)
    with pytest.raises(ValueError,match="missing or unsafe"):
        verify_pit_publication(src)


def test_orphan_directories_are_not_live_published_generations(tmp_path):
    from eraleader.pit_publication import verify_pit_publication
    folder=tmp_path/"pit_generations"/("1"*32)
    folder.mkdir(parents=True)
    (folder/"batch_manifest.json").write_text('{"status":"INCOMPLETE"}')
    assert verify_pit_publication(tmp_path) is None


def test_cli_verifies_only_published_generation(src,capsys):
    main(["verify-pit-publication","--out",str(src)])
    empty=json.loads(capsys.readouterr().out)
    assert empty["status"]=="NO_PUBLISHED_PIT_RESEARCH_GENERATION"
    publish(src,capsys)
    main(["verify-pit-publication","--out",str(src)])
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="VERIFIED_LOCAL_RESEARCH_PUBLICATION"
    assert Path(result["manifest"]).is_file()
    assert result["official_leaders"]==0 and result["pit_certified"] is False


def test_false_official_receipt_or_pointer_rejected(src,capsys):
    publish(src,capsys)
    pointer=src/POINTER
    source=json.loads(pointer.read_text())
    source["official_leaders"]=1
    pointer.write_text(json.dumps(source))
    with pytest.raises(ValueError,match="falsely certified"):
        verify_pit_publication(src)


def test_publication_root_symlink_rejected(src,tmp_path):
    alias=tmp_path/"alias"
    alias.symlink_to(src,target_is_directory=True)
    from argparse import Namespace
    from eraleader.pit_publication import execute_published_pit_batch
    def unexpected(_):
        pytest.fail("Must not execute inside symlinked output directory")
    with pytest.raises(ValueError,match="Unsafe PIT output"):
        execute_published_pit_batch(Namespace(out=str(alias)),unexpected)
