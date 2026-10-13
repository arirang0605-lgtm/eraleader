"""Build a pinned KR price+CFS+industry cohort without changing original WATCH.

Only existing, independently recorded local first-received originals may be
joined; the complete pair is published as a fresh research-only directory.
No broker access, automatic ranking, backdating or network requests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import re
import tempfile

from .official_kiwoom_daily_bridge import _inspect_cohort, _inspect_official
from .official_dart_multi_company import SCHEMA as CFS_SCHEMA
from .official_industry_peer_screen import COHORT as INDUSTRY_SCHEMA
from scripts.publish_kiwoom_flow_overlay import read
from scripts.publish_basic_company_screen import publish_basic_company_screen
from scripts.publish_dart_industry_peers import publish as publish_industry

CODE = re.compile(r"[0-9]{6}\Z")


def _input(path: Path) -> dict:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or any(p.is_symlink() for p in path.parents)
            or path.stat().st_uid != os.geteuid()):
        raise ValueError("UNSAFE_COHORT_INPUT")
    obj = read(path)
    if type(obj) is not dict:
        raise ValueError("INVALID_COHORT_INPUT")
    return obj


def _nested(path: Path, ancestor: Path) -> bool:
    return path == ancestor or ancestor in path.parents


def publish(*, official_out: Path, financial_manifest: Path,
            industry_manifest: Path, private_root: Path,
            new_output: Path, codes: list[str],
            clock: datetime | None = None) -> dict:
    """Compose existing publishers and atomically expose the verified result.

    The official source day is the *observed market session*, not the date of
    prospective first receipt. Publication never changes either timestamp.
    """
    paths = (official_out, financial_manifest, industry_manifest,
             private_root, new_output)
    if any(not isinstance(p, Path) or not p.is_absolute() or
           p.is_symlink() for p in paths):
        raise ValueError("ABSOLUTE_UNLINKED_PATHS_REQUIRED")
    if (not official_out.is_dir() or not private_root.is_dir()
            or any(p.is_symlink() for p in private_root.parents)
            or private_root.stat().st_uid != os.geteuid()
            or not new_output.parent.is_dir()
            or any(p.is_symlink() for p in new_output.parents)
            or new_output.exists() or new_output.is_symlink()
            or _nested(new_output, official_out)
            or _nested(new_output, private_root)):
        raise ValueError("UNSAFE_OR_EXISTING_COHORT_DESTINATION")
    if (type(codes) is not list or not 1 <= len(codes) <= 5
            or len(set(codes)) != len(codes)
            or any(type(x) is not str or not CODE.fullmatch(x)
                   for x in codes)):
        raise ValueError("INVALID_SELECTED_COHORT")
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("AWARE_RESEARCH_TIME_REQUIRED")
    now = now.astimezone(timezone.utc)
    original_file = official_out / "official_api_pit_research.json"
    original = _input(original_file)
    financial = _input(financial_manifest)
    industry = _input(industry_manifest)
    day = original.get("api_observation_day")
    if (type(day) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) is None
            or financial.get("schema") != CFS_SCHEMA
            or financial.get("research_only") is not True
            or (financial.get("official_market") or {}).get("market_session") != day
            or industry.get("schema") != INDUSTRY_SCHEMA
            or industry.get("current_classification_only") is not True
            or industry.get("historic_industry_pit_certified") is not False):
        raise ValueError("CFS_INDUSTRY_OFFICIAL_SESSION_CONTRACT_MISMATCH")
    expected = _inspect_official(official_out, day, now)
    if expected is None:
        raise ValueError("OFFICIAL_SESSION_ORIGINAL_REQUIRED")
    witness = {
        p: sha256(p.read_bytes()).hexdigest()
        for p in (original_file, financial_manifest, industry_manifest)
    }
    # A private scratch parent and fresh nested output keep partially created
    # HTML, reports and SQLite invisible if any later verification fails.
    with tempfile.TemporaryDirectory(prefix=".cohort_inflight_",
                                     dir=new_output.parent) as scratch:
        stage = Path(scratch) / "cohort"
        published = publish_basic_company_screen(
            official_source=original_file, financial_manifest=financial_manifest,
            private_root=private_root, new_output=stage, clock=now)
        if published.get("market_session") != day:
            raise ValueError("PUBLISHED_CANDIDATE_SESSION_MISMATCH")
        peers = publish_industry(
            candidate_file=stage / "basic_candidates_kr.json",
            industry_manifest=industry_manifest,
            official_evidence=stage / "official_api_pit_research.json",
            private_root=private_root, existing_site=stage / "site")
        if peers.get("market_session") != day:
            raise ValueError("PUBLISHED_INDUSTRY_SESSION_MISMATCH")
        # Industry research is stamped only AFTER its last original is read.
        # A clock captured before the (possibly lengthy) price/CFS pass cannot
        # judge that newly published peer report as evidence from the future.
        final_decision = datetime.now(timezone.utc) if clock is None else now
        if _inspect_cohort(stage, day, final_decision, expected, codes) is None:
            raise ValueError("SAME_SESSION_COHORT_NOT_VERIFIED")
        if any(sha256(p.read_bytes()).hexdigest() != pin
               for p, pin in witness.items()):
            raise ValueError("ORIGINAL_EVIDENCE_CHANGED_DURING_PUBLICATION")
        if new_output.exists() or new_output.is_symlink():
            raise FileExistsError("COHORT_DESTINATION_APPEARED")
        os.rename(stage, new_output)
    return {
        "status": "SAME_SESSION_KR_CFS_INDUSTRY_RESEARCH_PUBLISHED",
        "market_session": day,
        "financial_companies": published["annual_cfs_research_companies"],
        "industry_companies": peers["companies"],
        "selected_stock_count": len(codes),
        "candidate_sha256": read(new_output / "basic_candidates_kr.json")["content_sha256"],
        "industry_sha256": read(new_output / "industry_peers_kr.json")["content_sha256"],
        "historical_pit_certified": False,
        "investment_ranking_available": False,
        "orders_enabled": False,
        "broker_network_calls": 0,
    }
