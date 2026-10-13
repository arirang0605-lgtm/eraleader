"""Read-only replay of a verified daily research carry-forward publication.

The original publisher creates an immutable daily folder. A scheduler may ask
again later that day; return the exact prior result only when *every* source
and output field still matches. Neither a changed cohort nor damaged output
may be hidden by an older snapshot. No broker requests or writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import stat

from .kiwoom_investor_flow import canonical, utc


def _protected_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("FALLBACK_REPLAY_OUTPUT_UNSAFE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 1_000_000):
            raise ValueError("FALLBACK_REPLAY_OUTPUT_UNSAFE")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("FALLBACK_REPLAY_OUTPUT_OVERSIZED")
        return data
    finally:
        os.close(fd)


def verify_existing_publication(*, output: Path, proposed: dict,
                                now: datetime, render,
                                allowed_reasons: frozenset[str]) -> dict:
    """Return stored content, never change bytes, if exactly same source.

    proposed is a fully source-audited new result for today. Only its original
    publication clock and original gap reason may differ from the saved copy.
    """
    if (output.is_symlink() or not output.is_dir()
            or output.stat().st_uid != os.geteuid()
            or stat.S_IMODE(output.stat().st_mode) & 0o077
            or any(p.is_symlink() for p in output.parents)):
        raise ValueError("FALLBACK_REPLAY_OUTPUT_UNSAFE")
    if {p.name for p in output.iterdir()} != {"report.json", "index.html"}:
        raise ValueError("FALLBACK_REPLAY_INCOMPLETE_OR_EXTRA_FILES")
    raw = _protected_bytes(output / "report.json")
    page = _protected_bytes(output / "index.html")
    # The strict read object must not admit duplicate JSON keys or NaN.
    import json

    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("FALLBACK_REPLAY_DUPLICATE_FIELD")
            result[k] = v
        return result

    saved = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda x: (_ for _ in ()).throw(
                           ValueError("FALLBACK_REPLAY_NONFINITE")))
    if type(saved) is not dict or raw != canonical(saved) + b"\n":
        raise ValueError("FALLBACK_REPLAY_NONCANONICAL_JSON")
    if saved.get("reason") not in allowed_reasons:
        raise ValueError("FALLBACK_REPLAY_UNKNOWN_PREVIOUS_REASON")
    try:
        published = utc(saved["published_at_utc"])
        last = utc(saved["source_last_research_decision_at_utc"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("FALLBACK_REPLAY_TIME_INVALID") from None
    if published < last or published > now.astimezone(timezone.utc):
        raise ValueError("FALLBACK_REPLAY_PUBLICATION_TIME_INVALID")
    expected = dict(proposed)
    expected["published_at_utc"] = saved["published_at_utc"]
    expected["reason"] = saved["reason"]
    expected.pop("content_sha256", None)
    expected["content_sha256"] = sha256(canonical(expected)).hexdigest()
    if saved != expected:
        raise ValueError("FALLBACK_REPLAY_SOURCE_CHANGED_NEW_OUTPUT_REQUIRED")
    if page != render(saved).encode("utf-8"):
        raise ValueError("FALLBACK_REPLAY_PAGE_TAMPERED")
    # Resolve all protected paths after validation: do not accept a swapped
    # directory while another actor rewrites its contents.
    if (output.is_symlink() or
            _protected_bytes(output / "report.json") != raw or
            _protected_bytes(output / "index.html") != page):
        raise ValueError("FALLBACK_REPLAY_CHANGED_DURING_VERIFY")
    return saved
