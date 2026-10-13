#!/usr/bin/env python3
"""ER-NC-08 safe opt-in: pinned derived research → separate local static bundle."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from eraleader.news_catalyst_adapter import _unique
from eraleader.news_theme_delivery import write_research_bundle


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="NEWS OFF by default; static research-only output")
    p.add_argument("--news-enabled", action="store_true")
    p.add_argument("--derived-research-json", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--new-output-root", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.news_enabled:
        print(json.dumps({"status": "NEWS_OFF_NO_WRITE", "files_created": 0}))
        return 0
    try:
        if not args.derived_research_json or not args.new_output_root:
            raise ValueError("Derived research input/output required")
        source = args.derived_research_json
        if (not source.is_absolute() or source.is_symlink() or
                any(parent.is_symlink() for parent in source.parents) or
                not source.is_file()):
            raise ValueError("Read-only ordinary absolute research input required")
        size = source.stat().st_size
        if not 0 < size <= 2_000_000:
            raise ValueError("Bounded derived research input required")
        raw = source.read_bytes()
        digest = sha256(raw).hexdigest()
        if (type(args.expected_sha256) is not str or
                re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256) is None or
                digest != args.expected_sha256):
            raise ValueError("Independently pinned derived input SHA mismatch")
        report = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ValueError("Nonfinite derived JSON")))
        paths = write_research_bundle(report, args.new_output_root, enabled=True)
        print(json.dumps({
            "status": "RESEARCH_ONLY_WRITTEN",
            "input_sha256": digest,
            "files_present": len(paths),
            "files": [str(p.relative_to(args.new_output_root)) for p in paths],
            "messages_sent": 0,
            "trades_executed": 0,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        # Never echo local private paths, source contents, tokens or article data.
        print("ER_NC08_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
