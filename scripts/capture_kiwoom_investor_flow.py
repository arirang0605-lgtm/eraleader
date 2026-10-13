#!/usr/bin/env python3
"""Read-only selected Kiwoom ka10059: share-quantity net flows, NO ORDERS.

Example: --check-config
Actual: --codes 005930,000660 --day YYYYMMDD --out /absolute/private/new/dir
Credentials only from process environment: ERALEADER_KIWOOM_ACCESS_TOKEN or
ERALEADER_KIWOOM_APP_KEY + ERALEADER_KIWOOM_APP_SECRET.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eraleader.kiwoom_profile_settings import read_profiles, public_status
from eraleader.kiwoom_investor_flow import (
    canonical, day, access_token, fetch_ka10059, verify_flow, https_post,
)


def _new(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def capture(*, codes: list[str], market_day: str, out: Path,
            token: str | None = None, appkey: str | None = None,
            secretkey: str | None = None, fetch=fetch_ka10059,
            environment_mode: str = "demo", post=https_post) -> dict:
    day(market_day)
    if environment_mode not in ("demo","real"):
        raise ValueError("Explicit demo or real profile required")
    if (not codes or len(codes) > 20 or len(set(codes)) != len(codes) or
            any(re.fullmatch(r"[0-9]{6}", code) is None for code in codes)):
        raise ValueError("Only 1..20 unique KR security ids")
    out = Path(out)
    if (not out.is_absolute() or out.exists() or out.is_symlink()
            or not out.parent.is_dir() or out.parent.is_symlink()):
        raise ValueError("Output must be new nonlinked local private path")
    if not token:
        token = access_token(appkey=appkey or "", secretkey=secretkey or "", post=post)
    # Prepare privately; never publish a partially captured cohort.
    scratch = Path(tempfile.mkdtemp(prefix=".kiwoom_flow_", dir=out.parent))
    os.chmod(scratch, 0o700)
    try:
        receipts = []
        for code in codes:
            report = fetch(code=code, as_of=market_day, token=token,
                           environment_mode=environment_mode, post=post)
            from datetime import datetime, timezone
            verify_flow(report, decision_at=datetime.now(timezone.utc))
            payload = canonical(report) + b"\n"
            filename = code + ".json"
            _new(scratch / filename, payload)
            receipts.append({
                "security_id": code,
                "filename": filename,
                "sha256": sha256(payload).hexdigest(),
                "rows": report["observed_rows"],
                "status": report["completeness"],
            })
        manifest = {
            "schema": "eraleader.kiwoom_selected_flow_capture_manifest.v1",
            "requested_day": market_day, "provider": "KIWOOM_REST_KA10059",
            "unit": "shares", "environment_mode": environment_mode,
            "files": receipts, "companies": len(receipts),
            "first_receipt_local_only": True,
            "historic_market_pit_certified": False, "trading_enabled": False,
        }
        manifest["content_sha256"] = sha256(canonical(manifest)).hexdigest()
        _new(scratch / "manifest.json", canonical(manifest) + b"\n")
        os.rename(scratch, out)
        return {
            "status": "CAPTURED_KIWOOM_READ_ONLY_RESEARCH",
            "companies": len(receipts), "tr": "ka10059",
            "market_day": market_day, "official_investment_ranking": False,
            "manifest_sha256": manifest["content_sha256"],
        }
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--profile", choices=("demo","real"), default="demo")
    parser.add_argument("--codes", help="comma-separated selected KR 6-digit codes")
    parser.add_argument("--day")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        profiles = read_profiles()
        profile = profiles[args.profile]
        appkey = profile.get("appkey") or ""
        secret = profile.get("secretkey") or ""
    except (ValueError,OSError,KeyError):
        print("KIWOOM_PROFILE_PRIVATE_STORAGE_UNAVAILABLE", file=sys.stderr)
        return 2
    # Profile-scoped process vars are never borrowed from the other environment.
    label = args.profile.upper()
    appkey = os.getenv(f"ERALEADER_KIWOOM_{label}_APP_KEY") or appkey
    secret = os.getenv(f"ERALEADER_KIWOOM_{label}_APP_SECRET") or secret
    token = os.getenv(f"ERALEADER_KIWOOM_{label}_ACCESS_TOKEN")
    ready = bool(token or (appkey and secret))
    if args.check_config:
        print(json.dumps({"provider":"kiwoom", "profile":args.profile,
                          "credentials_configured":ready, "tr":"ka10059",
                          "network_calls":0,"orders_enabled":False}, sort_keys=True))
        return 0
    if not ready or not args.codes or not args.day or args.out is None:
        print("KIWOOM_READ_ONLY_BLOCKED: CONFIG_OR_ARGUMENTS_MISSING", file=sys.stderr)
        return 2
    post=lambda path,body,headers: https_post(path,body,headers,mode=args.profile)
    try:
        result = capture(
            codes=args.codes.split(","), market_day=args.day, out=args.out,
            token=token, appkey=appkey, secretkey=secret,
            environment_mode=args.profile, post=post)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("KIWOOM_READ_ONLY_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
