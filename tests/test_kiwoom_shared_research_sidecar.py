"""Bounded shared Kiwoom demo → EraLeader append-only sidecar (never scores)."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader.kiwoom_investor_flow import canonical
from eraleader.kiwoom_shared_research_sidecar import make_sidecar, publish, render
from test_kiwoom_investor_flow import fixtures

CLOCK = datetime(2026, 10, 13, 11, tzinfo=timezone.utc)


def source(day="20261008"):
    obj = {
        "schema": "sharedbroker.selected_security_flow_research.v1",
        "project": "eraleader", "market": "KR", "stock_code": "005930",
        "market_session": day, "mode": "demo",
        "source": "KIWOOM_KA10059", "units": "shares",
        "decision_at_utc": "2026-10-13T10:00:00+00:00",
        "first_gateway_received_at_utc": "2026-10-13T09:58:00+00:00",
        "observed_sessions": 100, "page_count": 1,
        "provider_history_complete": False, "recent_window_only": True,
        "page_sha256_witnesses": [{
            "gateway_first_received_at_utc": "2026-10-13T09:58:00+00:00",
            "source_payload_sha256": "a" * 64,
        }],
        "foreign_net_5_sessions": 125, "institution_net_5_sessions": -12,
        "foreign_net_20_sessions": 370, "institution_net_20_sessions": -80,
        "research_quality": "UNVERIFIED_20_OBSERVED_SESSIONS",
        "historical_pit_certified": False,
        "whole_market_foreign_flow_equivalent": False,
        "can_fill_coreastock_macro_foreign_flow_20d": False,
        "can_unlock_new_risk": False, "orders_enabled": False, "trade_signal": None,
        "data_limitations": (),
    }
    obj["content_sha256"] = sha256(canonical(obj)).hexdigest()
    return obj


class Fake:
    project = "eraleader"

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def selected_flow_research(self, **options):
        self.calls.append(options)
        return deepcopy(self.payload)


def seeded(tmp_path):
    basic, peer = fixtures()
    base = tmp_path / "site"
    base.mkdir()
    (base / "index.html").write_text(
        "<!doctype html><html><body><h1>ORIGINAL WATCH UNMODIFIED</h1></body></html>",
        encoding="utf-8",
    )
    one = tmp_path / "candidates.json"
    two = tmp_path / "industry.json"
    one.write_bytes(canonical(basic))
    two.write_bytes(canonical(peer))
    return basic, peer, one, two, base


def test_published_demo_real_one_page_shape_and_immutable_ledger(tmp_path):
    _, _, one, two, site = seeded(tmp_path)
    fake = Fake(source())
    out = publish(client=fake, stock_code="005930", market_day="20261008",
                  candidates=one, industries=two, site=site, now=CLOCK)
    assert fake.calls == [{
        "stock_code": "005930", "day": "20261008", "mode": "demo",
        "max_pages": 1, "recent_sessions": 20,
    }]
    assert out["sessions_match"] is True
    assert out["official_leaders"] == 0 and out["orders"] == 0
    assert out["score_changed"] is False
    path = site / out["page"]
    html = path.read_text()
    assert "125" in html and "370" in html and "-80" in html
    assert "모의투자" in html and "원화" in html
    assert "ORIGINAL WATCH UNMODIFIED" in (site / "index.html").read_text()
    assert out["page"] in (site / "index.html").read_text()
    evidence = json.loads((path.parent / "report.json").read_text())
    assert evidence["historical_pit_certified"] is False
    assert evidence["source_recent_window_only"] is True
    assert evidence["orders_enabled"] is False
    assert evidence["source_sha256"] == fake.payload["content_sha256"]
    assert evidence["research_status"] == "SAME_SESSION_RESEARCH_ONLY_NOT_PIT_CERTIFIED"
    with pytest.raises(FileExistsError):
        publish(client=fake, stock_code="005930", market_day="20261008",
                candidates=one, industries=two, site=site, now=CLOCK)


def test_later_demo_session_is_never_joined_to_old_baseline():
    a, b = fixtures()
    result = make_sidecar(a, b, source("20261013"), stock_code="005930",
                          market_day="20261013", clock=CLOCK)
    assert result["sessions_match"] is False
    assert result["research_status"] == "DIFFERENT_SESSION_NOT_JOINED"
    assert result["score_changed"] is False
    assert result["investment_ranking_available"] is False


@pytest.mark.parametrize("field,value", [
    ("mode", "real"),
    ("stock_code", "000660"),
    ("orders_enabled", True),
    ("historical_pit_certified", True),
    ("can_unlock_new_risk", True),
    ("units", "KRW"),
    ("project", "coreastock"),
    ("decision_at_utc", "2026-10-14T00:00:00+00:00"),
    ("page_count", 2),
    ("recent_window_only", False),
    ("provider_history_complete", True),
    ("foreign_net_20_sessions", 1.5),
])
def test_rebound_security_time_pit_or_units_rejected(field, value):
    a, b = fixtures()
    sample = source()
    sample[field] = value
    sample["content_sha256"] = sha256(canonical({
        k: v for k, v in sample.items() if k != "content_sha256"
    })).hexdigest()
    with pytest.raises(ValueError):
        make_sidecar(a, b, sample, stock_code="005930",
                     market_day="20261008", clock=CLOCK)


def test_sha_tamper_rejected_and_unknown_security_cannot_be_added():
    a, b = fixtures()
    bad = source()
    bad["foreign_net_20_sessions"] = 9999
    with pytest.raises(ValueError, match="SHA"):
        make_sidecar(a, b, bad, stock_code="005930",
                     market_day="20261008", clock=CLOCK)
    with pytest.raises(ValueError, match="cohort"):
        make_sidecar(a, b, source(), stock_code="123456",
                     market_day="20261008", clock=CLOCK)


def test_no_partial_publish_if_linking_fails(tmp_path, monkeypatch):
    _, _, one, two, site = seeded(tmp_path)
    old = (site / "index.html").read_bytes()
    from scripts import publish_kiwoom_flow_overlay
    def fail(*_args):
        raise RuntimeError("simulated link failure")
    monkeypatch.setattr(publish_kiwoom_flow_overlay, "_swap", fail)
    with pytest.raises(RuntimeError):
        publish(client=Fake(source()), stock_code="005930", market_day="20261008",
                candidates=one, industries=two, site=site, now=CLOCK)
    assert (site / "index.html").read_bytes() == old
    assert len(list(site.iterdir())) == 1


def test_render_refuses_tampered_promotion():
    a, b = fixtures()
    report = make_sidecar(a, b, source(), stock_code="005930",
                          market_day="20261008", clock=CLOCK)
    report["official_leaders"] = 1
    with pytest.raises(ValueError):
        render(report)


def test_cli_demo_publication_with_shared_client_stub(tmp_path, monkeypatch, capsys):
    import shared_broker_api.client as broker_client
    from scripts.publish_shared_kiwoom_flow import main
    _, _, one, two, site = seeded(tmp_path)
    payload = source()

    class Stub(Fake):
        def __init__(self, project):
            assert project == "eraleader"
            super().__init__(payload)

        def status(self):
            return {"configured": {"demo": True, "real": False},
                    "orders_enabled": False}

    monkeypatch.setattr(broker_client, "ReadOnlyClient", Stub)
    args = ["--code", "005930", "--day", "20261008",
            "--candidate-json", str(one), "--industry-json", str(two),
            "--site", str(site)]
    assert main(args) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["orders"] == 0 and response["score_changed"] is False

    class Wrong(Stub):
        def status(self):
            return {"configured": {"demo": True, "real": True},
                    "orders_enabled": True}

    monkeypatch.setattr(broker_client, "ReadOnlyClient", Wrong)
    assert main(args) == 2
    captured = capsys.readouterr()
    assert "SHARED_KIWOOM_DEMO_SIDECAR_BLOCKED" in captured.err
    assert "secret" not in captured.err.lower()


def test_cli_symlink_site_not_silently_resolved(tmp_path, monkeypatch, capsys):
    import shared_broker_api.client as broker_client
    from scripts.publish_shared_kiwoom_flow import main
    _, _, one, two, site = seeded(tmp_path)
    shortcut = tmp_path / "shortcut"
    shortcut.symlink_to(site, target_is_directory=True)

    class Stub(Fake):
        def __init__(self, project):
            super().__init__(source())

        def status(self):
            return {"configured": {"demo": True}, "orders_enabled": False}

    monkeypatch.setattr(broker_client, "ReadOnlyClient", Stub)
    args = ["--code", "005930", "--day", "20261008",
            "--candidate-json", str(one), "--industry-json", str(two),
            "--site", str(shortcut)]
    assert main(args) == 2
    assert not any(p.name.startswith("kiwoom_shared_") for p in site.iterdir())
