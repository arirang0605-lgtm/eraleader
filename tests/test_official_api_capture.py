"""Official KRX/DART/SEC adapter tests: ALL transport bytes are mocked."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import os
import stat
import subprocess
import sys

import pytest

from eraleader import official_api_capture as live

PROJ = Path(__file__).resolve().parents[1]
CLI = PROJ / "scripts" / "capture_official_api.py"
KEY = "a" * 40
CREDS = {
    "ERALEADER_KRX_AUTH_KEY": KEY,
    "ERALEADER_DART_API_KEY": "b" * 40,
    "ERALEADER_SEC_USER_AGENT": "EraLeader AcademicResearch contact@example.org",
}
STAMP = datetime(2026, 10, 12, 9, 1, tzinfo=timezone.utc)


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture
def root(tmp_path):
    p = tmp_path / "private"
    p.mkdir(mode=0o700)
    p.chmod(0o700)
    return p


def krow(day="20261009"):
    return {"BAS_DD": day, "ISU_CD": "005930", "ISU_NM": "테스트",
            "TDD_CLSPRC": "60,200", "ACC_TRDVOL": "1000"}


def fake(source, payload, root, *, day=None, cik=None, creds=CREDS):
    observed = []
    def retrieve(url, headers):
        observed.append((url, headers))
        return encoded(payload)
    result = live.capture_official_api(
        source, root, day=day, cik=cik, creds=creds, fetch=retrieve,
        clock=lambda: STAMP)
    return result, observed


@pytest.mark.parametrize("source", ["krx-kospi", "krx-kosdaq"])
def test_krx_real_shape_first_observation_private_and_no_key_leak(root, source):
    result, observed = fake(source, {"OutBlock_1": [krow()]}, root,
                             day="2026-10-09")
    assert result["status"] == "LIVE_OFFICIAL_API_RAW_RECORDED_RESEARCH_ONLY"
    assert result["provider_row_count"] == 1
    assert result["historical_pit_certified"] is False
    assert result["first_local_received_at_utc"] == STAMP.isoformat()
    assert result["external_api_calls"] == 1
    assert result["messages_sent"] == 0
    url, headers = observed[0]
    assert url.startswith("https://data-dbg.krx.co.kr/svc/apis/sto/")
    assert parse_qs(urlparse(url).query) == {"basDd": ["20261009"]}
    assert headers["AUTH_KEY"] == KEY
    cap = root / result["capture_id"]
    receipt, raw = cap / "first_receipt.json", cap / "raw_response.json"
    assert cap.is_dir() and receipt.is_file() and raw.is_file()
    assert stat.S_IMODE(cap.stat().st_mode) == 0o700
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert stat.S_IMODE(raw.stat().st_mode) == 0o600
    assert sha256(receipt.read_bytes()).hexdigest() == result["first_receipt_sha256"]
    assert sha256(raw.read_bytes()).hexdigest() == result["raw_sha256"]
    assert json.loads(raw.read_bytes()) == {"OutBlock_1": [krow()]}
    assert "005930" not in json.dumps(result)
    assert KEY not in json.dumps(result) + receipt.read_text()
    assert json.loads(receipt.read_bytes())["full_historic_universe_pit_certified"] is False


def test_krx_closed_session_produces_no_rows_but_not_history_certification(root):
    result, _ = fake("krx-kospi", {"OutBlock_1": []}, root, day="2026-10-09")
    assert result["provider_row_count"] == 0
    assert result["quality"] == "NO_DAILY_ROWS"
    assert result["historical_pit_certified"] is False


@pytest.mark.parametrize("bad", [
    {"OutBlock_1": [{"BAS_DD": "20261010", "ISU_CD": "005930", "TDD_CLSPRC": "1"}]},
    {"OutBlock_1": [{"BAS_DD": "20261009", "ISU_CD": "005930"}]},
    {"message": "Unauthorized API Call"},
    {"OutBlock_1": {}},
])
def test_invalid_krx_result_fails_without_any_publishing(root, bad):
    with pytest.raises(ValueError):
        fake("krx-kospi", bad, root, day="2026-10-09")
    assert list(root.iterdir()) == []


def test_dart_actual_fields_and_date_not_claimed_first_publication(root):
    payload = {"status": "000", "total_count": "1", "list": [
        {"rcept_dt": "20261009", "rcept_no": "20261009001234",
         "corp_code": "00123456", "report_nm": "사업보고서"}]}
    result, observed = fake("dart-disclosures", payload, root,
                             day="2026-10-09")
    assert result["provider_row_count"] == 1
    url, headers = observed[0]
    params = parse_qs(urlparse(url).query)
    assert urlparse(url).hostname == "opendart.fss.or.kr"
    assert params["crtfc_key"] == [CREDS["ERALEADER_DART_API_KEY"]]
    assert params["bgn_de"] == ["20261009"]
    assert params["end_de"] == ["20261009"]
    assert params["page_count"] == ["100"]
    assert "crtfc_key" not in json.dumps(result)
    assert CREDS["ERALEADER_DART_API_KEY"] not in json.dumps(result)
    assert "corp_code" not in json.dumps(result)
    assert json.loads((root/result["capture_id"]/"first_receipt.json").read_bytes())[
        "publisher_release_time_verified"] is False


@pytest.mark.parametrize("status,rows,quality", [
    ("013", None, "NO_DISCLOSURES_FOR_DAY"),
    ("000", [{"rcept_dt": "20261009", "rcept_no": "20261009001234"}],
     "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY"),
])
def test_dart_no_data_or_incomplete_page_never_claims_complete_universe(
        root, status, rows, quality):
    payload = {"status": status, "total_count": "150" if rows else "0"}
    if rows is not None:
        payload["list"] = rows
    result, _ = fake("dart-disclosures", payload, root, day="2026-10-09")
    assert result["quality"] == quality
    assert result["historical_pit_certified"] is False


@pytest.mark.parametrize("doc", [
    {"status": "010", "message": "Invalid key"},
    {"status": "000", "list": [{"rcept_dt": "20261008",
                               "rcept_no": "20261008000001"}], "total_count": "1"},
    {"status": "013", "list": [{"rcept_dt": "20261009", "rcept_no": "20261009000001"}]},
])
def test_dart_bad_status_or_changed_day_blocks(root, doc):
    with pytest.raises(ValueError):
        fake("dart-disclosures", doc, root, day="2026-10-09")
    assert not list(root.iterdir())


@pytest.mark.parametrize("source,payload,count", [
    ("sec-submissions", {"cik": 320193, "filings": {"recent": {
        "accessionNumber": ["0000320193-26-000100"],
        "acceptanceDateTime": ["2026-10-09T18:30:12.000Z"]}}}, 1),
    ("sec-companyfacts", {"cik": 320193, "facts": {
        "us-gaap": {"Assets": {"units": {"USD": []}}}}}, 1),
])
def test_sec_keyless_but_contact_declaration_and_cik_only(root, source, payload, count):
    result, observed = fake(source, payload, root, cik="320193")
    assert result["provider_row_count"] == count
    url, headers = observed[0]
    assert url.startswith("https://data.sec.gov/")
    assert "CIK0000320193.json" in url
    assert headers["User-Agent"] == CREDS["ERALEADER_SEC_USER_AGENT"]
    assert "AUTH_KEY" not in headers
    assert "contact@example.org" not in json.dumps(result)
    assert result["historical_pit_certified"] is False


@pytest.mark.parametrize("source,day,cik,creds", [
    ("krx-kospi", "2026-10-09", None, {}),
    ("dart-disclosures", "2026-10-09", None, {}),
    ("sec-submissions", None, "320193", {}),
    ("sec-companyfacts", None, "320193",
     {"ERALEADER_SEC_USER_AGENT": "EraLeader no contact"}),
    ("sec-submissions", "2026-10-09", "320193", CREDS),
    ("krx-kospi", "2099-01-01", None, CREDS),
    ("krx-kospi", "2026-10-09", "320193", CREDS),
])
def test_unconfigured_or_bad_request_never_contacts_remote(root, source, day, cik, creds):
    used=[]
    with pytest.raises(ValueError):
        live.capture_official_api(
            source, root, day=day, cik=cik, creds=creds,
            fetch=lambda u,h: used.append(1) or b"{}")
    assert not used and not list(root.iterdir())


def test_password_file_0600_and_unknown_or_duplicate_keys_fail(tmp_path):
    path = tmp_path/"secure.env"
    path.write_text("ERALEADER_KRX_AUTH_KEY=" + KEY + "\n")
    path.chmod(0o600)
    assert live.credentials(path, environ={})["ERALEADER_KRX_AUTH_KEY"] == KEY
    path.chmod(0o644)
    with pytest.raises(ValueError):
        live.credentials(path, environ={})
    path.chmod(0o600)
    path.write_text("ERALEADER_KRX_AUTH_KEY="+KEY+"\nERALEADER_KRX_AUTH_KEY="+KEY+"\n")
    with pytest.raises(ValueError):
        live.credentials(path, environ={})
    path.write_text("UNKNOWN_SECRET="+KEY+"\n")
    with pytest.raises(ValueError):
        live.credentials(path, environ={})


def test_cli_configuration_present_only_checks_header_and_does_not_call_api(tmp_path):
    env={k:v for k,v in os.environ.items() if not k.startswith("ERALEADER_")}
    env["ERALEADER_SEC_USER_AGENT"]=CREDS["ERALEADER_SEC_USER_AGENT"]
    check=subprocess.run(
        [sys.executable,str(CLI),"--project",str(PROJ),
         "--source","sec-companyfacts","--cik","320193","--check-config"],
        capture_output=True,text=True,env=env,timeout=10)
    assert check.returncode==0 and not check.stderr
    report=json.loads(check.stdout)
    assert report["credentials_and_request_preflight_ready"] is True
    assert report["external_api_calls"]==0
    assert report["first_received_data_available"] is False
    assert "contact@example.org" not in check.stdout


def test_http_origin_whitelist_blocks_unexpected_https_and_plaintext():
    for url in ("http://data.sec.gov/submissions/CIK0000320193.json",
                "https://outside.example.org/",
                "https://username:password@data.sec.gov/submissions/CIK0000320193.json"):
        with pytest.raises(ValueError,match="Unapproved official HTTPS origin"):
            live._http_get(url, {"User-Agent":CREDS["ERALEADER_SEC_USER_AGENT"]})


@pytest.mark.parametrize("mutation", ["symlink", "public_mode"])
def test_no_live_raw_capture_in_unsafe_directory(tmp_path, mutation):
    parent=tmp_path/"out"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    if mutation=="symlink":
        alias=tmp_path/"alias"
        alias.symlink_to(parent)
        parent=alias
    else:
        parent.chmod(0o755)
    with pytest.raises(ValueError):
        live.capture_official_api("krx-kospi",parent,day="2026-10-09",creds=CREDS,
                                  fetch=lambda u,h: encoded({"OutBlock_1":[krow()]}))


def test_official_json_duplicate_keys_and_empty_body_rejected(root):
    for b in (b'{"OutBlock_1":[],"OutBlock_1":[]}', b"", b"<html>blocked</html>"):
        with pytest.raises(ValueError):
            live.capture_official_api("krx-kospi", root,
                day="2026-10-09", creds=CREDS, fetch=lambda u,h:b)
        assert not list(root.iterdir())


def test_cli_auto_uses_local_secure_setup_without_exposing_agent(tmp_path):
    saved = (tmp_path / "Library" / "Application Support" /
             "EraLeader" / "api-credentials")
    saved.mkdir(parents=True,mode=0o700)
    saved.chmod(0o700)
    secret = saved / "official_api.env"
    secret.write_text("ERALEADER_SEC_USER_AGENT=EraLeader Research research@lab.org\\n")
    secret.chmod(0o600)
    env = {k:v for k,v in os.environ.items() if not k.startswith("ERALEADER_")}
    env["HOME"] = str(tmp_path)
    call = subprocess.run(
        [sys.executable,str(CLI),"--project",str(PROJ),
         "--source","sec-submissions","--cik","320193","--check-config"],
        capture_output=True,text=True,env=env,timeout=10)
    assert call.returncode == 0
    result = json.loads(call.stdout)
    assert result["credentials_and_request_preflight_ready"] is True
    assert result["first_received_data_available"] is False
    assert result["external_api_calls"] == 0
    assert "research@lab.org" not in call.stdout + call.stderr


def test_cli_check_has_no_network_and_never_displays_secrets(monkeypatch,tmp_path):
    env = {k:v for k,v in os.environ.items() if not k.startswith("ERALEADER_")}
    # The live Mac may have an owner-only setup file. Test an isolated
    # empty HOME instead of reading real credentials from this machine.
    env["HOME"] = str(tmp_path)
    env.pop("KRX_AUTH_KEY",None)
    env.pop("DART_API_KEY",None)
    env.pop("SEC_USER_AGENT",None)
    call = subprocess.run([sys.executable, str(CLI), "--project", str(PROJ),
                           "--source", "krx-kospi",
                           "--market-day", "2026-10-09", "--check-config"],
                          capture_output=True, text=True, env=env, timeout=10)
    assert call.returncode == 2
    parsed = json.loads(call.stdout)
    assert parsed["external_api_calls"] == 0
    assert parsed["first_received_data_available"] is False
    assert parsed["credentials_and_request_preflight_ready"] is False
    assert "http" not in call.stdout and "a"*40 not in call.stdout
