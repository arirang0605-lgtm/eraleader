"""Loopback-only dashboard for separate Kiwoom demo and real read-only keys.

No order endpoints, no account balances, and no brokerage account passwords.
Credentials are private 0600 on Mac's internal user filesystem, NOT Git or HTML.
"""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
import json
import os
import secrets
import stat
import tempfile

MODES = ("demo", "real")
PROFILE_ENV = {"demo": "https://mockapi.kiwoom.com",
               "real": "https://api.kiwoom.com"}
DEFAULT_STORE = Path.home() / "Library/Application Support/EraLeader/ProviderKeys/kiwoom_profiles.json"
MAX_POST = 12000


def _file_secure(path: Path) -> None:
    details = path.lstat()
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid()
            or stat.S_IMODE(details.st_mode) & 0o077):
        raise ValueError("Kiwoom private credential file unsafe")


def read_profiles(path: Path = DEFAULT_STORE) -> dict:
    if path.is_symlink():
        raise ValueError("Credential file cannot be linked")
    if not path.exists():
        return {"active_mode": "demo", "demo": {}, "real": {}}
    _file_secure(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if (type(value) is not dict or value.get("active_mode") not in MODES
            or any(type(value.get(mode)) is not dict for mode in MODES)):
        raise ValueError("Invalid Kiwoom private profile data")
    return value


def save_profiles(form: dict, path: Path = DEFAULT_STORE) -> dict:
    """Save both profiles independently. Empty fields DO NOT clear old secrets."""
    mode = form.get("active_mode")
    if mode not in MODES:
        raise ValueError("Select demo or real environment")
    value = read_profiles(path)
    for environment in MODES:
        prior = dict(value.get(environment) or {})
        key = form.get(environment + "_appkey", "")
        secret = form.get(environment + "_secret", "")
        label = form.get(environment + "_label", "")
        if type(key) is not str or type(secret) is not str or type(label) is not str:
            raise ValueError("Expected text form entries")
        if len(key) > 512 or len(secret) > 512 or len(label) > 80:
            raise ValueError("Invalid credential field length")
        if bool(key) != bool(secret):
            raise ValueError("Provide both App Key and App Secret to update a profile")
        if key and secret:
            if any(ord(c) < 33 or ord(c) > 126 for c in key + secret):
                raise ValueError("Invalid characters in API credentials")
            prior["appkey"] = key
            prior["secretkey"] = secret
        if label:
            prior["label"] = label
        value[environment] = prior
    if mode == "real" and not (value["real"].get("appkey")
                                and value["real"].get("secretkey")):
        raise ValueError("Real environment must be configured before activating")
    value["active_mode"] = mode
    directory = path.parent
    if directory.is_symlink():
        raise ValueError("Credential directory cannot be linked")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise ValueError("Credential directory owner mismatch")
    os.chmod(directory, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".kiwoom_", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = -1
            json.dump(value, f, ensure_ascii=False, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        if path.exists():
            _file_secure(path)
        os.replace(tmp, path)
    finally:
        if fd >= 0:os.close(fd)
        if os.path.exists(tmp):os.unlink(tmp)
    return value


def public_status(value: dict) -> dict:
    return {
        "active_mode": value["active_mode"],
        "orders_enabled": False,
        "accounts": {
            name: {
                "configured": bool(value[name].get("appkey") and value[name].get("secretkey")),
                "label": value[name].get("label", ""),
                "server": PROFILE_ENV[name],
            } for name in MODES
        },
    }


def render(value: dict, csrf: str, *, feedback: str = "") -> str:
    """Always show both forms; never preload credentials into HTML or logs."""
    state = public_status(value)
    blocks = []
    for name, title in (("demo", "모의투자 계좌"), ("real", "실전투자 계좌 (조회 전용)")):
        row = state["accounts"][name]
        checked = " checked" if state["active_mode"] == name else ""
        configured = "등록 완료" if row["configured"] else "미등록"
        blocks.append(
            f"<fieldset><legend><strong>{title}</strong></legend>"
            f"<p>API 서버: {escape(row['server'])} · 현재 설정: {configured}</p>"
            f"<label><input type='radio' name='active_mode' value='{name}'{checked}> "
            f"기본 조회 환경으로 선택</label><br>"
            f"<label>계좌 구분 별칭 (계좌번호 불필요)"
            f"<input name='{name}_label' maxlength='80' value='{escape(row['label'], quote=True)}'"
            " autocomplete='off'></label><br>"
            f"<label>App Key<input name='{name}_appkey' type='password' maxlength='512'"
            " autocomplete='new-password' placeholder='등록/변경할 때만 입력'></label><br>"
            f"<label>App Secret<input name='{name}_secret' type='password' maxlength='512'"
            " autocomplete='new-password' placeholder='등록/변경할 때만 입력'></label>"
            "</fieldset>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader · 키움증권 API 설정</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:780px;margin:30px auto;"
        "padding:0 16px;line-height:1.7;background:#111923;color:#eee}"
        "fieldset{border:1px solid #5e687c;border-radius:9px;margin:18px 0;padding:20px}"
        "input[type=password],input[name$=_label]{display:block;width:94%;max-width:540px;"
        "padding:10px;margin:7px 0 13px;background:#f7f7f7;color:#000}"
        "button{padding:12px 22px;cursor:pointer}a{color:#90cbff}"
        ".note{padding:15px;background:#293544;border-radius:8px}</style></head><body>"
        "<h1>EraLeader · 키움증권 REST API</h1>"
        "<p class='note'><strong>모의투자/실전투자를 완전히 분리합니다.</strong><br>"
        "기본값은 모의투자이며 키가 등록돼도 매수·매도·계좌조회는 작동하지 않습니다."
        " 기관·외국인 수급 조회만 사용합니다. 인증정보는 Mac 내부 소유자 전용"
        " 파일(0600)에 저장되며 암호화된 키체인 보관이 아닙니다."
        " 실전 키는 별도 암호화 보관이 준비될 때까지 등록하지 않는 것을 권장합니다.</p>"
        + ("<p role='status'>"+escape(feedback)+"</p>" if feedback else "")
        + "<form action='/save' method='post' autocomplete='off'>"
        f"<input type='hidden' name='csrf' value='{escape(csrf, quote=True)}'>"
        + "".join(blocks) + "<button type='submit'>설정 저장 (주문 없음)</button></form>"
        "<p>실전 계좌번호·계좌 비밀번호·공동인증서·OTP는 입력하지 않습니다."
        " App Key/Secret은 모의/실전에서 각자 발급받아야 합니다.</p>"
        "<p>설정 화면은 이 Mac의 <code>127.0.0.1</code>에서만 접속할 수 있습니다.</p>"
        "</body></html>"
    )


def make_handler(store: Path, csrf: str, port: int):
    expected_host = f"127.0.0.1:{port}"
    origin = f"http://{expected_host}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log secret-bearing POSTs.

        def headers_safe(self):
            self.send_header("Cache-Control", "no-store, no-cache")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")

        def respond(self, status: int, html: str):
            data = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html;charset=utf-8")
            self.headers_safe()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            return (self.headers.get("Host") == expected_host and
                    self.client_address[0] == "127.0.0.1")

        def do_GET(self):
            if not self.allowed() or self.path != "/":
                self.respond(404, "Not Found")
                return
            try:
                html = render(read_profiles(store), csrf)
                self.respond(200, html)
            except (ValueError, OSError, KeyError):
                self.respond(500, "Private settings unavailable")

        def do_POST(self):
            if (not self.allowed() or self.path != "/save" or
                    self.headers.get("Origin") != origin or
                    self.headers.get("Content-Type","").split(";")[0].strip() !=
                    "application/x-www-form-urlencoded"):
                self.respond(403, "Forbidden")
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 < size <= MAX_POST:
                    raise ValueError("Invalid form size")
                payload = self.rfile.read(size).decode("utf-8", errors="strict")
                data = parse_qs(payload, keep_blank_values=True, strict_parsing=True)
                if any(len(v) != 1 for v in data.values()):
                    raise ValueError("Duplicate form fields rejected")
                args = {k: v[0] for k,v in data.items()}
                if not secrets.compare_digest(args.pop("csrf",""), csrf):
                    self.respond(403, "Forbidden")
                    return
                known = {"active_mode"} | {
                    f"{mode}_{field}" for mode in MODES for field in
                    ("appkey","secret","label")}
                if set(args) - known:
                    raise ValueError("Unexpected credentials form field")
                value = save_profiles(args, store)
                self.respond(200, render(value, csrf, feedback="설정이 로컬에 저장되었습니다. API 주문 비활성화."))
            except (ValueError, OSError, UnicodeError, KeyError):
                # Do not echo even partial secret-bearing values.
                try:
                    self.respond(400, render(read_profiles(store), csrf,
                                             feedback="저장 실패: 입력값 또는 로컬 권한을 확인하세요."))
                except (OSError, ValueError):
                    self.respond(400, "Private settings unavailable")
    return Handler


def serve(*, port: int = 8782, store: Path = DEFAULT_STORE):
    if type(port) is not int or not 1024 <= port < 65536:
        raise ValueError("Choose a user port above 1023")
    with ThreadingHTTPServer(("127.0.0.1",port),
                             make_handler(store, secrets.token_urlsafe(36), port)) as server:
        server.serve_forever()
