"""PIT source SQLite integrity: corrupted/revised source must never become WATCH evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.offline_pit import OfflineLedger, normalize

FIXTURE=Path(__file__).parent/"fixtures/offline_synthetic.json"
ASOF="2024-09-01T21:00:00+09:00"


def ledger(tmp_path):
    path=tmp_path/"offline.sqlite"
    writer=OfflineLedger(path)
    try:writer.import_file(FIXTURE)
    finally:writer.close()
    return path


def snapshot(path,at=ASOF):
    obj=OfflineLedger.open_readonly(path)
    try:return obj.snapshot(at,market="KR")
    finally:obj.close()


def modify(path,*,kind="membership",edit,rehash=False):
    with sqlite3.connect(path) as conn:
        key,payload=conn.execute(
            "SELECT record_key,payload FROM offline_records WHERE kind=? LIMIT 1",(kind,)
        ).fetchone()
        row=json.loads(payload)
        if edit.__code__.co_argcount==1:
            updated=edit(row)
            if updated is None: updated=row
        else:
            raise AssertionError("Expected one item edit")
        blob=json.dumps(updated,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        fingerprint=sha256(blob.encode()).hexdigest() if rehash else sha256(payload.encode()).hexdigest()
        conn.execute(
            "UPDATE offline_records SET payload=?,fingerprint=? WHERE kind=? AND record_key=?",
            (blob,fingerprint,kind,key))
    return key


def test_normalized_source_snapshot_unchanged(tmp_path):
    path=ledger(tmp_path)
    assert "SYN-A" in snapshot(path)["members"]
    assert snapshot(path)["quality"]["historic_membership_pit_verified"] is False


def test_payload_rewritten_without_fingerprint_cannot_supply_pit_snapshot(tmp_path):
    path=ledger(tmp_path)
    modify(path,kind="membership",edit=lambda x:x.update(ticker="ATTACK") or x)
    with pytest.raises(ValueError,match="fingerprint|SHA|integrity"):
        snapshot(path)


def test_rehashing_forged_issuer_identity_does_not_bypass_natural_key(tmp_path):
    path=ledger(tmp_path)
    modify(path,kind="membership",
           edit=lambda x:x.update(security_id="OTHER") or x,rehash=True)
    with pytest.raises(ValueError,match="record_key|identity|natural"):
        snapshot(path)


def test_change_stored_available_at_after_import_fails_timestamp_coherence(tmp_path):
    path=ledger(tmp_path)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE offline_records SET available_at=? WHERE kind='membership'",
                  ("2024-01-01T00:00:00+00:00",))
    with pytest.raises(ValueError,match="availability|timestamp|stored"):
        snapshot(path)


def test_change_source_id_column_but_keep_matching_payload_rejected(tmp_path):
    path=ledger(tmp_path)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE offline_records SET source_id='FORGED'")
    with pytest.raises(ValueError,match="source|identity"):
        snapshot(path)


def test_fake_verification_provenance_value_cannot_certify_source(tmp_path):
    path=ledger(tmp_path)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE offline_records SET provenance='independently_certified'")
    with pytest.raises(ValueError,match="provenance"):
        snapshot(path)


def test_duplicate_json_fields_even_with_rehashed_fingerprint_rejected(tmp_path):
    path=ledger(tmp_path)
    with sqlite3.connect(path) as c:
        key,original=c.execute(
            "SELECT record_key,payload FROM offline_records WHERE kind='membership' LIMIT 1"
        ).fetchone()
        blob=original[:-1]+',"ticker":"DUPLICATE"}'
        c.execute("UPDATE offline_records SET payload=?,fingerprint=? WHERE kind=? AND record_key=?",
                  (blob,sha256(blob.encode()).hexdigest(),"membership",key))
    with pytest.raises(ValueError,match="duplicate|canonical|source|integrity"):
        snapshot(path)


def test_rehashed_revision_does_not_replace_original_immutable_source_version(tmp_path):
    path=ledger(tmp_path)
    modify(path,kind="membership",
           edit=lambda x:x.update(revision=99) or x,rehash=True)
    with pytest.raises(ValueError,match="record_key|revision|natural"):
        snapshot(path)


def test_rehashed_available_at_inside_payload_rejected_if_canonical_invalid(tmp_path):
    path=ledger(tmp_path)
    modify(path,kind="fundamentals",
           edit=lambda x:x.update(available_at="2024-01-01T00:00:00") or x,
           rehash=True)
    with pytest.raises(ValueError,match="timezone|available|timestamp"):
        snapshot(path)


def test_future_revision_not_visible_in_earlier_pit_snapshot(tmp_path):
    path=ledger(tmp_path)
    early=snapshot(path,"2024-09-01T21:00:00+09:00")
    assert "SYN-A" in early["members"]
    modify(path,kind="fundamentals",edit=lambda x:x.update(value=3e9) or x)
    # Full cutoff sees any earlier or future dated rows? This test only
    # establishes that an already-known tampered row fails even for earlier cutoffs.
    with pytest.raises(ValueError,match="fingerprint|integrity"):
        snapshot(path,"2024-09-01T21:00:00+09:00")


@pytest.mark.parametrize("revision", [True, 1.5, "1.5", 0, -1])
def test_invalid_import_revision_cannot_be_truncated_to_valid_integer(revision):
    row=json.loads(FIXTURE.read_text())["records"]["membership"][0]
    row["revision"]=revision
    with pytest.raises(ValueError,match="Revision|revision"):
        normalize("membership",row)


def test_readonly_query_does_not_update_pit_source_db(tmp_path):
    path=ledger(tmp_path)
    before=sha256(path.read_bytes()).hexdigest()
    result=snapshot(path)
    assert result["quality"]["historic_membership_pit_verified"] is False
    after=sha256(path.read_bytes()).hexdigest()
    assert before==after
    view=OfflineLedger.open_readonly(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            view.db.execute("DELETE FROM offline_records")
    finally:view.close()
