"""End-to-end CLI replay of a fixed synthetic walk-forward protocol."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from eraleader.cli import main
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_walkforward_replay import dataset, WINDOWS, MODEL, LABEL_ID


def setup_inputs(tmp_path):
    snapshots, outcomes = dataset()
    data = tmp_path/"inputs"
    data.mkdir()
    for name, payload in (("snapshots",snapshots),("outcomes",outcomes),
                          ("windows",WINDOWS)):
        (data/f"{name}.json").write_text(json.dumps(payload))
    command = ["replay-walkforward",
               "--snapshots",str(data/"snapshots.json"),
               "--outcomes",str(data/"outcomes.json"),
               "--windows",str(data/"windows.json"),
               "--model-version",MODEL,
               "--label-definition-id",LABEL_ID,
               "--embargo-days","7","--out",str(tmp_path/"output")]
    return command


def test_replayed_cli_never_emits_holdout_labels(tmp_path,capsys):
    command=setup_inputs(tmp_path)
    main(command)
    printout=json.loads(capsys.readouterr().out)
    assert printout["fold_count"]==2
    assert printout["unique_test_candidate_count"]==3
    assert printout["test_outcome_labels_revealed"] is False
    assert printout["historic_universe_pit_certified"] is False
    report=json.loads((tmp_path/"output"/"repeated_walkforward_research.json").read_text())
    assert report["test_outcome_labels_revealed"] is False
    assert report["historic_universe_pit_certified"] is False
    assert [x["test_candidate_count"] for x in report["folds"]]==[2,1]
    assert all("target" not in json.dumps(f["test_candidates"])
               for f in report["folds"])
    assert all("is_future_leader" not in json.dumps(f)
               for f in report["folds"])
    assert all("training_samples_sha256" in f for f in report["folds"])


def test_cli_rejects_mutated_protocol_without_silent_output(tmp_path,capsys):
    command=setup_inputs(tmp_path)
    wrong=command.copy()
    i=wrong.index("--label-definition-id")
    wrong[i+1]="after-the-fact-label-definition"
    with pytest.raises(SystemExit) as result:
        main(wrong)
    assert result.value.code==2
    assert not (tmp_path/"output"/"repeated_walkforward_research.json").exists()


def test_derived_replay_report_only_is_backed_up_without_labels(tmp_path,capsys):
    command=setup_inputs(tmp_path)
    main(command)
    capsys.readouterr()
    out=tmp_path/"output"
    (out/"raw_future_outcomes.json").write_text('{"private_token":"DO_NOT_EXPORT"}')
    archive=tmp_path/"safe_replay.zip"
    saved=create_backup(out,archive)
    assert saved["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipped:
        assert zipped.namelist()==["repeated_walkforward_research.json","MANIFEST.json"]
    target=tmp_path/"restored"
    restore_backup(archive,target)
    r=json.loads((target/"repeated_walkforward_research.json").read_text())
    assert r["test_outcome_labels_revealed"] is False
    assert r["model_was_pre_registered_attested"] is False
    assert not (target/"raw_future_outcomes.json").exists()
