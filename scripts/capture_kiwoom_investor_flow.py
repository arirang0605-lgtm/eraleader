#!/usr/bin/env python3
"""Read-only selected Kiwoom ka10059: share-quantity net flows, NO ORDERS.

Example: --check-config
Actual: --codes 005930,000660 --day YYYYMMDD --out /absolute/private/new/dir
All actual credentials/OAuth are owned by the shared local broker service.
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
from eraleader.kiwoom_investor_flow import (
    canonical, day, fetch_ka10059, verify_flow,
)


def _new(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def capture(*, codes: list[str], market_day: str, out: Path,
            token: str, fetch=fetch_ka10059,
            environment_mode: str = "demo", post=None) -> dict:
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
    if not token or type(token) is not str or not callable(post):
        raise ValueError("Shared broker read-only transport required; no direct OAuth fallback")
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
    shared_src = Path("/Volumes/T5DATA/SharedBrokerAPI/src")
    gateway = None
    reachable = False
    ready = False
    if shared_src.is_dir():
        try:
            sys.path.insert(0, str(shared_src))
            from shared_broker_api.client import ReadOnlyClient, eraleader_compatible_post
            gateway = ReadOnlyClient("eraleader")
            status = gateway.status()
            if status.get("orders_enabled") is not False:
                raise ValueError("Shared broker must be read-only")
            ready = status["configured"][args.profile] is True
            reachable = True
        except (OSError, ValueError, KeyError, TypeError, ImportError):
            ready = False
            gateway = None
    if args.check_config:
        print(json.dumps({"provider":"kiwoom", "profile":args.profile,
                          "credentials_configured":ready,
                          "gateway_reachable":reachable,
                          "transport":"SharedBrokerAPI/UNIX_SOCKET",
                          "network_calls":0,"orders_enabled":False}, sort_keys=True))
        return 0
    if not ready or gateway is None or not args.codes or not args.day or args.out is None:
        print("KIWOOM_READ_ONLY_BLOCKED: GATEWAY_OR_ARGUMENTS_UNAVAILABLE",
              file=sys.stderr)
        return 2
    post = eraleader_compatible_post(gateway, args.profile)
    try:
        result = capture(
            codes=args.codes.split(","), market_day=args.day, out=args.out,
            token="INTERNAL_LOCAL_GATEWAY_NO_PROVIDER_TOKEN",
            environment_mode=args.profile, post=post)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("KIWOOM_READ_ONLY_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
