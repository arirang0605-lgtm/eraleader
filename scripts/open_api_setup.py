#!/usr/bin/env python3
"""One-time loopback-only API credential setup UI for the EraLeader Mac.

Secrets are entered solely in the Mac's local browser, never in chat, CLI
arguments, HTTP logs, Git, or generated dashboards. The original API
collector is not modified and all permissions are owner-only.
"""
from __future__ import annotations

import argparse
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

NAMES = {
    "krx": "ERALEADER_KRX_AUTH_KEY",
    "dart": "ERALEADER_DART_API_KEY",
    "sec": "ERALEADER_SEC_USER_AGENT",
}
FORM_NAMES = {"krx", "dart", "sec_email", "csrf", "action"}
SECRET_FILE = "official_api.env"
MAX_REQUEST = 4000
KEY_PATTERN = re.compile(r"[A-Za-z0-9]{40}\Z")
CONTACT_PATTERN = re.compile(r"[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\Z")
SEC_PREFIX = "EraLeader Research "


def private_location(project: Path) -> tuple[Path, Path]:
    """Prefer project .secrets, but use Mac internal disk if SSD masks 0600.

    External disks such as exFAT can report *all files* as mode 0700 even
    after fchmod(0600). Do not weaken the existing API collector's 0600
    requirement or pretend that a chmod on such a volume succeeded.
    """
    project = Path(project)
    if not project.is_absolute() or project.is_symlink() or not project.is_dir():
        raise ValueError("Existing absolute nonlinked EraLeader project required")
    private = project / ".secrets"
    if private.is_symlink():
        raise ValueError("Secret directory cannot be a symlink")
    if not private.exists():
        private.mkdir(mode=0o700)
    if (not private.is_dir() or private.stat().st_uid != os.geteuid() or
            stat.S_IMODE(private.stat().st_mode) != 0o700):
        raise ValueError("Secret directory must be owner-only 0700")
    fd, probe = tempfile.mkstemp(prefix=".mode_probe_", dir=private)
    try:
        os.fchmod(fd, 0o600)
        supports_0600 = stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
    finally:
        os.close(fd)
        os.unlink(probe)
    if not supports_0600:
        private = Path.home() / "Library" / "Application Support" / "EraLeader" / "api-credentials"
        if private.parent.is_symlink() or private.is_symlink():
            raise ValueError("Internal secret path cannot be linked")
        private.mkdir(mode=0o700, parents=True, exist_ok=True)
        if private.stat().st_uid == os.geteuid() and private.is_dir():
            # Owner-only authorization is required on the internal volume.
            os.chmod(private, 0o700)
        else:
            raise ValueError("Mac internal private credential directory invalid")
    if (private.is_symlink() or not private.is_dir() or
            private.stat().st_uid != os.geteuid() or
            stat.S_IMODE(private.stat().st_mode) != 0o700):
        raise ValueError("Private credential directory must be 0700")
    return private, private / SECRET_FILE


def existing(project: Path) -> dict:
    private, path = private_location(project)
    if not path.exists() and not path.is_symlink():
        return {}
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_uid != os.geteuid() or
            stat.S_IMODE(path.stat().st_mode) != 0o600 or
            path.stat().st_size > 8192):
        raise ValueError("Existing secrets require owner-only nonlinked 0600 file")
    saved = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Unrecognized saved credential format")
        name, val = line.split("=", 1)
        if name not in NAMES.values() or name in saved or not val:
            raise ValueError("Unknown/duplicated credential field")
        saved[name] = val
    return saved


def contact_hint(project: Path) -> str:
    try:
        p = subprocess.run(
            ["git", "-C", str(project), "config", "user.email"],
            capture_output=True, text=True, timeout=2)
        value = p.stdout.strip()
        if (p.returncode == 0 and CONTACT_PATTERN.fullmatch(value)
                and "noreply" not in value.lower()
                and "example" not in value.lower()):
            return value
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def save_config(project: Path, fields: dict) -> dict:
    """Atomic read-merge-replace; blank inputs never delete existing secrets."""
    if not isinstance(fields, dict) or set(fields) - {"krx", "dart", "sec_email"}:
        raise ValueError("Unknown settings fields")
    private, filename = private_location(project)
    current = existing(project)
    new = current.copy()
    for short in ("krx", "dart"):
        value = fields.get(short, "")
        if not isinstance(value, str):
            raise ValueError("Invalid key format")
        if value:
            if not KEY_PATTERN.fullmatch(value):
                raise ValueError("KRX/DART key must be an exact 40-character approved key")
            new[NAMES[short]] = value
    email = fields.get("sec_email", "")
    if not isinstance(email, str):
        raise ValueError("Invalid SEC contact")
    if email:
        if (len(email) > 130 or not CONTACT_PATTERN.fullmatch(email)
                or "example" in email.lower() or "noreply" in email.lower()):
            raise ValueError("SEC requires a real contact email address")
        new[NAMES["sec"]] = SEC_PREFIX + email
    if not new:
        raise ValueError("No credentials have been supplied")
    raw = "".join(key + "=" + new[key] + "\n"
                  for key in NAMES.values() if key in new).encode("utf-8")
    if len(raw) > 1000 or b"\x00" in raw:
        raise ValueError("Invalid credential content")
    fd, tempname = tempfile.mkstemp(prefix=".api_setup_", dir=private)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tempname, filename)
        # This is all on the external SSD; no raw keys are duplicated elsewhere.
        root_fd = os.open(str(private), os.O_RDONLY)
        try:
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)
    return {name: bool(new.get(value)) for name, value in NAMES.items()}


def render(project: Path, *, token: str, notice: str = "", success=False) -> bytes:
    configured = existing(project)
    hint = contact_hint(project)
    ua = configured.get(NAMES["sec"], "")
    if ua.startswith(SEC_PREFIX):
        hint = ua.removeprefix(SEC_PREFIX)
    fields = [
        ("krx", "KRX API 인증키", "한국거래소 Open API에서 발급받은 40자리 AUTH_KEY"),
        ("dart", "DART API 인증키 (선택)", "OpenDART 40자리 인증키. 비워두면 기존 키 유지"),
    ]
    rows = []
    for name, title, description in fields:
        present = bool(configured.get(NAMES[name]))
        rows.append(f"""<label for="{name}">{escape(title)}
            <span class="saved">{'● 저장됨' if present else '○ 미등록'}</span></label>
            <input id="{name}" name="{name}" type="password" autocomplete="new-password"
                   placeholder="{'등록된 키 유지 (변경하려면 새 키 입력)' if present else '40자리 API 인증키 입력'}"
                   inputmode="text" minlength="0" maxlength="40">
            <p class="help">{escape(description)}</p>""")
    sec_present = bool(ua)
    message = (f'<div class="notice {"ok" if success else "err"}">{escape(notice)}</div>'
               if notice else "")
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader — API 연결 설정</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0c1018;color:#e9edf6;font:15px -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}}
main{{max-width:620px;margin:6vh auto;padding:16px}}
.top{{font-size:12px;letter-spacing:.15em;color:#73c8b5;font-weight:700;margin-bottom:11px}}
h1{{font-size:26px;letter-spacing:-.04em;margin:0 0 9px}}.sub{{color:#a4b1c5;line-height:1.65;margin:0 0 27px}}
section{{padding:27px 24px;background:#171d28;border:1px solid #2c3646;border-radius:14px}}
label{{display:block;font-weight:650;margin:19px 0 8px}}label:first-child{{margin-top:0}}
.saved{{float:right;color:#8796a9;font-size:12px;font-weight:500}}
input{{width:100%;border-radius:9px;background:#0d131d;border:1px solid #36445a;
color:#e9edf6;font-size:15px;padding:13px 14px;outline:none}}
input:focus{{border-color:#65c9b8;box-shadow:0 0 0 3px #65c9b81c}}
.help{{color:#91a0b7;font-size:12px;margin:6px 0 12px;line-height:1.5}}
button{{display:block;background:#4cb4a5;border:none;color:#081713;font-weight:700;
font-size:16px;border-radius:9px;padding:14px;width:100%;cursor:pointer;margin-top:26px}}
.note{{font-size:12px;color:#9eb0c7;line-height:1.8;margin-top:17px}}
.notice{{padding:12px 14px;border-radius:8px;margin-bottom:16px;line-height:1.6}}
.notice.ok{{border:1px solid #438d77;color:#c3f2e5}}
.notice.err{{border:1px solid #915458;color:#ffd3d6}}
footer{{font-size:12px;color:#8090a6;line-height:1.7;margin-top:20px}}
</style></head><body><main><div class="top">ERALEADER · LOCAL CONFIGURATION</div>
<h1>시장 데이터 API 연결</h1>
<p class="sub">이 창은 맥북의 <strong>127.0.0.1</strong>에서만 실행됩니다.
입력한 키는 ChatGPT나 GitHub로 전송되지 않으며 Mac 사용자 전용 <strong>보호 저장소(600/700 권한)</strong>에만 보관됩니다.</p>
{message}<section><form action="/save" method="post" autocomplete="off">
<input type="hidden" name="csrf" value="{escape(token)}">
{''.join(rows)}
<label for="sec_email">SEC 무료 API 연락용 이메일 (선택)
<span class="saved">{'● 설정됨' if sec_present else '○ 미등록'}</span></label>
<input id="sec_email" name="sec_email" type="email" autocomplete="email"
       value="{escape(hint,quote=True)}" placeholder="contact@your-domain.com" maxlength="130">
<p class="help">SEC는 API 키가 없습니다. 연락 가능한 이메일을 User-Agent에 사용합니다.</p>
<button name="action" value="save" type="submit">API 설정 안전하게 저장</button>
<p class="note">✓ 키를 이미 등록했다면 입력칸을 비워도 기존 키가 유지됩니다.<br>
✓ 저장 시 파일 권한 600, 폴더 권한 700을 적용합니다.<br>
✓ 실제 시장 데이터 수신 테스트는 설정 저장 이후 별도로 검증합니다.</p>
</form></section>
<footer>외부 인터넷 접근을 허용하는 서비스가 아닙니다. 접속은 이 맥북에서만 가능하며,
설정 파일은 EraLeader Git에서 제외됩니다.</footer>
</main></body></html>"""
    return html.encode("utf-8")


class UI(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, project: Path, port: int = 8768):
        super().__init__(("127.0.0.1", port), Handler)
        self.project = project
        self.token = secrets.token_urlsafe(36)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # Including on HTTP failures, NEVER log URL or POST data.
        return

    def _valid_host(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _same_loopback_origin(self) -> bool:
        # Safari/embedded browser forms may supply 'Origin: null' for an
        # opaque-origin document or 'localhost' for the loopback alias.
        # Both still require a literal 127.0.0.1 Host AND the unpredictable
        # same-page CSRF token in the POST body before any key can be saved.
        origin = self.headers.get("Origin")
        if origin is None or origin == "null":
            return True
        try:
            parsed = urlsplit(origin)
            return (parsed.scheme == "http" and
                    parsed.hostname in {"127.0.0.1", "localhost"} and
                    parsed.port == self.server.server_port and
                    not parsed.username and not parsed.password and
                    not parsed.path and not parsed.query and not parsed.fragment)
        except ValueError:
            return False

    def _send(self, status: int, body: bytes, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._valid_host() or urlsplit(self.path).path != "/":
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        try:
            body = render(self.server.project, token=self.server.token)
        except (OSError, ValueError):
            return self._send(500, b"Local credential storage unavailable",
                              "text/plain; charset=utf-8")
        self._send(200, body)

    def do_POST(self):
        if (not self._valid_host() or self.path != "/save" or
                not self._same_loopback_origin()):
            return self._send(403, "보안 확인 실패: 입력창을 새로 열어주세요.".encode("utf-8"),
                              "text/plain; charset=utf-8")
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self._send(415, b"Wrong form encoding", "text/plain; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, b"Invalid form size", "text/plain; charset=utf-8")
        if not 0 < length <= MAX_REQUEST:
            return self._send(413, b"Form too large", "text/plain; charset=utf-8")
        try:
            raw = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(raw, keep_blank_values=True, strict_parsing=True,
                              max_num_fields=8)
            required = FORM_NAMES - {"action"}
            # Submitting via Enter or some webviews may omit the clicked
            # button field. CSRF and every actual credential field are still
            # mandatory; never accept duplicate or additional parameters.
            if (not required.issubset(fields) or
                    set(fields) - FORM_NAMES or
                    any(len(v) != 1 for v in fields.values()) or
                    fields["csrf"][0] != self.server.token or
                    (fields.get("action", ["save"])[0] != "save")):
                return self._send(
                    403, "보안 확인이 만료되었습니다. 입력창을 새로고침 후 다시 입력하세요.".encode("utf-8"),
                    "text/plain; charset=utf-8")
            save_config(self.server.project,
                        {key: fields[key][0] for key in ("krx","dart","sec_email")})
            # New token prevents replay and keeps the user on the same page.
            self.server.token = secrets.token_urlsafe(36)
            body = render(self.server.project, token=self.server.token,
                          notice="안전하게 저장했습니다. API 키는 브라우저에 다시 표시하지 않습니다.",
                          success=True)
            self._send(200, body)
        except (ValueError, OSError, UnicodeError):
            # No secret values or paths in HTTP response or logs.
            body = render(self.server.project, token=self.server.token,
                          notice="저장하지 못했습니다. 40자리 키/연락 이메일/보관 권한을 확인하세요.")
            self._send(400, body)


def main(argv=None):
    parser = argparse.ArgumentParser(description="EraLeader local API setup window")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    private_location(args.project)
    server = UI(args.project, args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print("ERALEADER_LOCAL_API_WINDOW=" + url, flush=True)
    if not args.no_browser:
        subprocess.Popen(["open", url], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    # Expire the temporary secret-entry listener after 45 minutes.
    watchdog = threading.Timer(2700, server.shutdown)
    watchdog.daemon = True
    watchdog.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        watchdog.cancel()
        server.server_close()


if __name__ == "__main__":
    main()
