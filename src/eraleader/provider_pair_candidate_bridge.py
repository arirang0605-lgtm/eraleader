"""Bridge a *previously published, independently pinned* PIT source pair into
the existing local candidate WATCH research gate; never official certification.

The caller must supply the original SHA acquired at atomic first publication.
No raw source paths or ticker/issuer data are exported in candidate summaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .provider_pair_asof_seal import (
    READY, _receipt, audit_atomic_provider_pair_asof,
)


@dataclass(frozen=True)
class PinnedCandidatePair:
    market: str
    first_sha256: str
    pair: tuple[Path, str, Path, str]
    originals: tuple[tuple[Path, Path], tuple[Path, Path]]


def resolve_atomic_candidate_pair(
    root: Path, independent_first_sha256: str, *, market: str,
    decision_at: str, clock: datetime | None = None,
) -> PinnedCandidatePair:
    """Fail before any downstream candidate/quality/history write."""
    report = audit_atomic_provider_pair_asof(
        root, independent_first_sha256, decision_at=decision_at, clock=clock)
    if (report["status"] != READY or report["market"] != market or
            report["eligible_for_local_candidate_watch_research_only"] is not True or
            report["official_pit_certified"] is not False):
        raise ValueError("Atomic first-pinned provider pair not usable for local WATCH research")
    private_root, first, _, staged = _receipt(root, independent_first_sha256)
    if first["market"] != market or report["first_pair_receipt_sha256"] != independent_first_sha256:
        raise ValueError("Atomic first-pinned provider pair identity changed")
    a, b = private_root / "source_a", private_root / "source_b"
    originals = (
        (staged[0], a / "normalized" / "manifest.json"),
        (staged[1], b / "normalized" / "manifest.json"),
    )
    return PinnedCandidatePair(
        market=market,
        first_sha256=independent_first_sha256,
        pair=(a / "offline.sqlite", first["normalized_manifest_sha256"][0],
              b / "offline.sqlite", first["normalized_manifest_sha256"][1]),
        originals=originals,
    )


def guard_atomic_pair_derived_output(
    pinned: PinnedCandidatePair, root: Path, out_dir: Path,
) -> None:
    """Never let derived WATCH writes overlap the immutable originals."""
    derived = Path(out_dir).resolve()
    protected = (
        Path(root).resolve(),
        pinned.originals[0][0].parent.resolve(),
        pinned.originals[1][0].parent.resolve(),
    )
    if any(derived == origin or derived in origin.parents or
           origin in derived.parents for origin in protected):
        raise ValueError("Derived WATCH output overlaps immutable paired original evidence")


def assert_atomic_candidate_pair_unchanged(
    pinned: PinnedCandidatePair, root: Path, *,
    decision_at: str, clock: datetime | None = None,
) -> None:
    """Re-audit the entire original evidence after candidate corroboration,
    before publishing any gate, prospective signal, or history artifact.
    """
    fresh = resolve_atomic_candidate_pair(
        root, pinned.first_sha256, market=pinned.market,
        decision_at=decision_at, clock=clock)
    if fresh != pinned:
        raise ValueError("Atomic paired PIT source changed during candidate evaluation")
