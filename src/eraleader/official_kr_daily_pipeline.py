"""Explicit one-day KRX + complete DART -> research WATCH and reports.

Manual one-shot only. No launch agent, live messaging, trading or certification.
Publication writes are blocked until all official raw captures and daily SHA
checks finish. Prior successful original receipts are never overwritten.
"""
from __future__ import annotations
from datetime import date, datetime, timezone, time
from pathlib import Path
from zoneinfo import ZoneInfo
import os
import shutil
import stat
import tempfile

from .official_api_capture import _root, _settings, capture_official_api
from .official_dart_daily import capture_dart_day
from .official_api_pit_bridge import build_official_price_snapshot, run_official_research


def capture_and_publish_kr_day(*, trading_day: str, capture_root: Path,
                               research_out: Path, creds: dict, top: int=20,
                               days: int=550, legacy_root: Path|None=None,
                               fetch=None, clock=None,
                               dart_directory: tuple[Path,str] | None = None) -> dict:
    """Integrate all three sources atomically at *research publication* level.

    Independently pinned API evidence remains private even when a later stage
    blocks. Returned WATCH/first receipt dates are NEVER trading-day backfills.
    """
    now_fn=clock or (lambda: datetime.now(timezone.utc))
    now=now_fn()
    if now.tzinfo is None:
        raise ValueError("Must use aware real-time clock")
    local=now.astimezone(ZoneInfo("Asia/Seoul"))
    requested=date.fromisoformat(trading_day)
    if requested>local.date() or (local.date()-requested).days>10:
        raise ValueError("KRX/DART trading day outside bounded research freshness")
    if requested==local.date() and local.time()<time(19,0):
        raise ValueError("Current market day not yet closed for complete API research")
    capture_root=_root(Path(capture_root))
    out=Path(research_out)
    if (not out.is_absolute() or out.is_symlink() or ".." in out.parts or
            out.parent.is_symlink() or out.exists()):
        raise ValueError("Research publication must use a new absolute output directory")
    if type(top) is not int or not 1<=top<=100 or type(days) is not int or days<260:
        raise ValueError("Invalid research lookback or top-K cap")
    if legacy_root is not None and not Path(legacy_root).is_dir():
        raise ValueError("Read-only legacy price history unavailable")
    for source in ("krx-kospi","krx-kosdaq","dart-disclosures"):
        _settings(source,day=trading_day,cik=None,creds=creds)
    # Existing official first-capture implementation and its atomic, private
    # folders are reused; interrupted acquisitions can be audited/recovered.
    captures={}
    for source in ("krx-kospi","krx-kosdaq","dart-disclosures"):
        res=capture_official_api(source,capture_root,day=trading_day,
                                 creds=creds,fetch=fetch,clock=now_fn)
        captures[source]=(capture_root/res["capture_id"],
                          res["first_receipt_sha256"])
    d_full=capture_dart_day(*captures["dart-disclosures"],capture_root,
                            creds=creds,fetch=fetch,clock=now_fn)
    full=(capture_root/d_full["capture_id"],d_full["manifest_sha256"],
          *captures["dart-disclosures"])
    decision=now_fn()
    if decision.tzinfo is None or decision < now:
        raise ValueError("Decision timestamp cannot predate captured observations")
    as_of=decision.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    kwargs={} if legacy_root is None else {"legacy_root":Path(legacy_root)}
    snap=build_official_price_snapshot(
        kospi=captures["krx-kospi"],kosdaq=captures["krx-kosdaq"],
        decision_at=decision.isoformat(),as_of=as_of,days=days,top=top,
        auxiliary=(("dart-disclosures",*captures["dart-disclosures"]),),
        dart_complete=full,dart_directory=dart_directory,**kwargs)
    # Run the existing writer inside a private empty sibling directory. A late
    # report/SQLite/HTML exception must not expose a half-created WATCH site.
    # The first-source captures above remain preserved for inspection/retry.
    if not out.parent.is_dir():
        raise ValueError("Research publication parent directory must exist")
    stage = Path(tempfile.mkdtemp(prefix=".official_kr_research_",dir=out.parent))
    try:
        result = run_official_research(snap,stage)
        paths = {}
        for key in ("market_dashboard","dashboard"):
            published = Path(result[key])
            if not published.is_file() or not published.is_relative_to(stage):
                raise ValueError("Research stage returned an invalid dashboard path")
            paths[key] = str(out/published.relative_to(stage))
        # No prior output, even an empty directory, may be overwritten.
        if out.exists() or out.is_symlink():
            raise ValueError("Research output destination appeared during processing")
        os.rename(stage,out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"status":"OFFICIAL_KR_DAY_RESEARCH_ONLY",
            "market_session":trading_day, "as_of_research":as_of,
            "api_observation_rows":result["krx_rows"],
            "dart_disclosure_rows":result["dart_full_rows"],
            "dart_pages":d_full["pages"],
            "watch_rows":result["watch_count"],"reports":result["reports"],
            "alert_dry_run_count":result["alert_dry_run_count"],
            "live_messages":0,"official_leaders":0,"pit_certified":False,
            "market_dashboard":paths["market_dashboard"],
            "audit_dashboard":paths["dashboard"],
            "captured_sources":3+d_full["captured_new_pages"]}
