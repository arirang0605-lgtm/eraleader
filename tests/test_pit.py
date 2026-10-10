from pathlib import Path
import pytest
from eraleader.pit import LocalStore,utc_iso

def test_future_filing_never_changes_historical_snapshot(tmp_path):
    store=LocalStore(tmp_path/"state.sqlite")
    try:
        assert store.insert_fact("ABC","sales","2025-03-31","2025-05-10T10:00:00+09:00","filing1",1,100)
        d="2025-05-20T16:00:00+09:00"
        before=store.facts_asof(d)
        assert before[("ABC","sales","2025-03-31")]==100
        assert store.insert_fact("ABC","sales","2025-03-31","2025-06-20T10:00:00+09:00","revision1",2,999)
        assert store.facts_asof(d)==before
        later=store.facts_asof("2025-06-22T16:00:00+09:00")
        assert later[("ABC","sales","2025-03-31")]==999
    finally:store.close()

def test_fact_insert_idempotent_and_strict_timezones(tmp_path):
    store=LocalStore(tmp_path/"pit.sqlite")
    try:
        row=("ABC","eps","2024-12-31","2025-03-15T00:00:00Z","f123",1,4)
        assert store.insert_fact(*row)
        assert store.insert_fact(*row) is False
        assert len(store.facts_asof("2025-05-01T00:00:00Z"))==1
        with pytest.raises(ValueError):
            store.insert_fact("ABC","eps","2025-03-31","2025-04-01T00:00:00","f234",1,5)
    finally:store.close()

def test_events_snapshot_idempotent(tmp_path):
    store=LocalStore(tmp_path/"pit.sqlite")
    ev={"event_id":"id-123","security_id":"ABC","kind":"NEW_TECHNICAL_WATCH"}
    try:
        assert store.save_snapshot("r1","KR","2025-01-02",{"rows":[]},[ev])
        assert not store.save_snapshot("r1","KR","2025-01-02",{"rows":[]},[ev])
        assert len(store.events())==1
        assert len(store.events(pending_only=True))==1
        store.mark_dry_run("id-123")
        assert store.events(pending_only=True)==[]
    finally:store.close()

def test_pit_requires_offset():
    assert utc_iso("2025-01-01T09:00:00+09:00")=="2025-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        utc_iso("2025-01-01T09:00:00")
