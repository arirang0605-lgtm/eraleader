"""Local-only credential entry UI and permissions (all dummy keys, no real API)."""
from __future__ import annotations

import contextlib
from http.client import HTTPConnection
from pathlib import Path
import re
import stat
import threading
from urllib.parse import urlencode

import pytest

from scripts.open_api_setup import UI, existing, private_location, save_config

KRX = "A" * 40
DART = "B" * 40


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "eraleader"
    p.mkdir()
    return p


def test_secure_file_600_directory_700_and_blank_never_overwrites(project):
    first = save_config(project, {"krx": KRX, "dart": DART, "sec_email": "user@sample.org"})
    assert first == {"krx": True, "dart": True, "sec": True}
    folder, file = private_location(project)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
    before = file.read_bytes()
    assert KRX.encode() in before
    assert b"ERALEADER_SEC_USER_AGENT=EraLeader Research user@sample.org" in before
    blank = save_config(project, {"krx": "", "dart": "", "sec_email": ""})
    assert blank == first
    assert file.read_bytes() == before


@pytest.mark.parametrize("settings", [
    {"krx": "1234"},
    {"krx": "a" * 41},
    {"dart": "B" * 39},
    {"sec_email": "not-an-email"},
    {"sec_email": "bad@example.com"},
    {"sec_email": "me@noreply.github.com"},
    {"secret_token": "unsupported"},
])
def test_invalid_fields_rejected_without_any_secret_file(project, settings):
    with pytest.raises(ValueError):
        save_config(project, settings)
    assert not (project / ".secrets" / "official_api.env").exists()


@pytest.mark.parametrize("unsafe", ["symlink", "public", "wrong_file_mode"])
def test_reject_unsafe_credential_path(project, tmp_path, unsafe):
    root, filename = private_location(project)
    if unsafe == "symlink":
        root.rmdir()
        root.symlink_to(tmp_path)
    elif unsafe == "public":
        root.chmod(0o755)
    else:
        save_config(project, {"krx": KRX})
        filename.chmod(0o644)
    with pytest.raises(ValueError):
        save_config(project, {"krx": KRX})


@contextlib.contextmanager
def webserver(project):
    server = UI(project, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def call(server, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read().decode()
        return response.status, payload, dict(response.getheaders())
    finally:
        connection.close()


def test_real_loopback_page_saves_keys_without_echoing_them(project):
    with webserver(project) as server:
        status, html, headers = call(server, "GET", "/")
        assert status == 200
        assert "KRX API 인증키" in html
        assert 'type="password"' in html
        assert "DART API 인증키" in html
        assert "SEC 무료 API 연락용 이메일" in html
        assert headers["Cache-Control"] == "no-store, max-age=0"
        assert headers["Content-Security-Policy"].startswith("default-src 'none'")
        csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        values = {"krx": KRX, "dart": DART, "sec_email": "user@sample.org",
                  "csrf": csrf, "action": "save"}
        body = urlencode(values)
        status, returned, headers = call(server, "POST", "/save", body,
                        {"Content-Type": "application/x-www-form-urlencoded",
                         "Origin": f"http://127.0.0.1:{server.server_port}"})
        assert status == 200
        assert "안전하게 저장했습니다" in returned
        assert KRX not in returned and DART not in returned
        assert "user@sample.org" in returned  # only SEC public contact shown to owner
        assert existing(project)["ERALEADER_KRX_AUTH_KEY"] == KRX
        assert "저장됨" in returned
        status, _, _ = call(server, "POST", "/save", body,
                        {"Content-Type": "application/x-www-form-urlencoded",
                         "Origin": f"http://127.0.0.1:{server.server_port}"})
        assert status == 403  # used token cannot be replayed


@pytest.mark.parametrize("submit_mode", ["opaque_origin", "localhost_origin", "enter_without_button"])
def test_browser_origin_and_implicit_submit_still_require_csrf(project, submit_mode):
    with webserver(project) as server:
        status, html, _ = call(server, "GET", "/")
        assert status == 200
        token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        pairs = [("krx", KRX), ("dart", ""), ("sec_email", ""),
                 ("csrf", token), ("action", "save")]
        origin = f"http://127.0.0.1:{server.server_port}"
        if submit_mode == "opaque_origin":
            origin = "null"
        elif submit_mode == "localhost_origin":
            origin = f"http://localhost:{server.server_port}"
        else:
            pairs = [p for p in pairs if p[0] != "action"]
        status, html, _ = call(server, "POST", "/save", urlencode(pairs),
                              {"Content-Type": "application/x-www-form-urlencoded",
                               "Origin": origin})
        assert status == 200
        assert "안전하게 저장했습니다" in html
        assert KRX not in html
        assert existing(project)["ERALEADER_KRX_AUTH_KEY"] == KRX


@pytest.mark.parametrize("attack", ["foreign_origin", "bad_token", "duplicate_field", "bad_host"])
def test_reject_cross_site_or_tampered_post_before_write(project, attack):
    with webserver(project) as server:
        _, html, _ = call(server, "GET", "/")
        token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        pairs = [("krx", KRX), ("dart", ""), ("sec_email", ""),
                 ("csrf", token), ("action", "save")]
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Origin": f"http://127.0.0.1:{server.server_port}"}
        if attack == "foreign_origin":
            headers["Origin"] = "https://attacker.example"
        elif attack == "bad_token":
            pairs[3] = ("csrf", "bad")
        elif attack == "duplicate_field":
            pairs.append(("krx", "Z" * 40))
        else:
            headers["Host"] = "untrusted.example"
        status, _, _ = call(server, "POST", "/save", urlencode(pairs), headers)
        assert status in (403, 404)
        assert not (project / ".secrets" / "official_api.env").exists()
