"""Fail-closed, API-free local scheduled execution for EraLeader research batches.

A scheduled run is not a real-time market signal. Never silently roll forward
a cached market date to today's date.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from zipfile import BadZipFile
from pathlib import Path
import fcntl
import json
import os
import plistlib
import shlex
import sys
import uuid

from .data import LEGACY_DEFAULT
from .batch import execute_local_batch
from .local_backup import create_backup, verify_backup
from .scheduled_watch_bridge import (
    read_watch_schedule_config, audit_watch_schedule_sources,
    publish_watch_schedule_reports,
)
from .scheduled_maturity_bridge import (
    read_maturity_schedule_config, audit_maturity_schedule_sources,
    publish_scheduled_maturity_reports,
)

def active_cache_files(root: Path, *, kr_as_of: date | None = None,
                       lookback_days: int = 550) -> dict[str, Path]:
    """Exact read-only cache paths, including EVERY KR year used by batch."""
    kr_dir = root / "datasets/external_validation/marcap/data"
    years = sorted(kr_dir.glob("marcap-????.parquet"))
    if not years:
        raise FileNotFoundError(f"No KR cache in {kr_dir}")
    us_path = root / "datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    if kr_as_of is None:
        return {"KR": years[-1], "US": us_path}
    start_year = (kr_as_of - timedelta(days=lookback_days)).year
    result = {"US": us_path}
    for year in range(start_year, kr_as_of.year + 1):
        result[f"KR-{year}"] = kr_dir / f"marcap-{year}.parquet"
    return result

def latest_cache_fingerprints(root: Path, *, kr_as_of: date) -> dict[str, str]:
    """Hash actual source bytes, not mtime, file size or most-recent session.

    Detect corrected/historically restated cached files without exporting raw
    market data. Never follow symlinks or silently accept missing/empty files.
    """
    answer = {}
    for market, path in active_cache_files(root, kr_as_of=kr_as_of).items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"Untrusted/missing {market} source cache file")
        digest = sha256()
        with path.open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk)
        answer[market] = digest.hexdigest()
    return answer

def latest_cached_sessions(root: Path) -> dict[str, date]:
    """Inspect actual cache timestamps, not file modification times."""
    import pandas as pd
    sources = active_cache_files(root)
    kr = pd.read_parquet(sources["KR"], columns=["Date"])["Date"]
    us = pd.read_parquet(sources["US"], columns=["ts"])["ts"]
    if kr.empty or us.empty:
        raise ValueError("Cached market session column is empty")
    return {"KR": pd.to_datetime(kr).max().date(),
            "US": pd.to_datetime(us).max().date()}

def run_scheduled(*, legacy: Path = LEGACY_DEFAULT, out: Path,
                  control: Path, backups: Path, today: date | None = None,
                  max_age_days: int = 10, allow_stale_research: bool = False,
                  sessions: dict[str, date] | None = None,
                  input_fingerprints: dict[str, str] | None = None,
                  watch_research_config: Path | None = None,
                  watch_max_age_days: int = 7) -> dict:
    """Run at most once per cache vintage, retry on failure, verify backup.

    All paths are local. A process lock is held across analysis and backup.
    State is committed only after successful verified backup, allowing retries.
    """
    if max_age_days < 0:
        raise ValueError("max_age_days must be nonnegative")
    now = today or datetime.now().astimezone().date()
    control.mkdir(parents=True, exist_ok=True)
    with (control / "batch.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "SKIPPED_ALREADY_RUNNING"}
        live_files = sessions is None
        seen = sessions if sessions is not None else latest_cached_sessions(legacy)
        if set(seen) != {"KR", "US"} or not all(type(v) is date for v in seen.values()):
            raise ValueError("Both KR and US observed dates are required")
        dates = {k: v.isoformat() for k, v in seen.items()}
        age = {k: (now-v).days for k, v in seen.items()}
        if any(v < 0 for v in age.values()):
            raise ValueError("Cache contains observations later than local date")
        if any(v > max_age_days for v in age.values()) and not allow_stale_research:
            return {"status": "SKIPPED_STALE_CACHE", "observations": dates,
                    "age_days": age, "max_age_days": max_age_days,
                    "no_live_notifications": True}
        # A date-only checkpoint is insufficient: a vendor can correct old
        # closes, splits or bars without changing its latest session date.
        fingerprints = (input_fingerprints if input_fingerprints is not None else
                        latest_cache_fingerprints(legacy, kr_as_of=seen["KR"])
                        if live_files else None)
        if fingerprints is not None and (not fingerprints or
                any(not isinstance(k, str) or not k or
                    not (k == "US" or k == "KR" or k.startswith("KR-"))
                    for k in fingerprints) or
                not any(k.startswith("KR") for k in fingerprints) or
                "US" not in fingerprints or
                any(not isinstance(v, str) or len(v) != 64 or
                    any(c not in "0123456789abcdef" for c in v)
                    for v in fingerprints.values())):
            raise ValueError("KR/US immutable SHA256 source fingerprints required")
        # Entirely optional: existing price-only scheduled research is
        # unchanged without an explicit local WATCH config file.
        watch_sources = watch_preflight = watch_fingerprint = watch_config_digest = None
        if watch_research_config is not None:
            watch_sources = read_watch_schedule_config(Path(watch_research_config))
            watch_config_digest = sha256(Path(watch_research_config).read_bytes()).hexdigest()
            watch_preflight = audit_watch_schedule_sources(
                watch_sources,clock=datetime.now(timezone.utc),
                max_age_days=watch_max_age_days,
            )
            if not watch_preflight["all_markets_recent"]:
                return {
                    "status":"SKIPPED_WATCH_RESEARCH_NOT_CURRENT",
                    "observations":dates,
                    "watch_freshness_status":watch_preflight["watch_freshness_status"],
                    "no_live_notifications":True,
                    "official_leaders_confirmed":0,
                }
            watch_fingerprint = watch_preflight["watch_research_sha256"]
        def check_watch_still_stable():
            if watch_sources is None:
                return
            check = audit_watch_schedule_sources(
                watch_sources,clock=datetime.now(timezone.utc),
                max_age_days=watch_max_age_days,
            )
            if (not check["all_markets_recent"] or
                    check["watch_research_sha256"] != watch_fingerprint or
                    sha256(Path(watch_research_config).read_bytes()).hexdigest()
                        != watch_config_digest):
                raise RuntimeError("WATCH source revised during scheduled run")
        marker = control / "last_verified_batch.json"
        if marker.exists():
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if (previous.get("observations") == dates and
                    previous.get("cache_sha256") == fingerprints and
                    previous.get("watch_research_sha256") == watch_fingerprint and
                    previous.get("watch_research_config_sha256") == watch_config_digest):
                prior_archive = Path(str(previous.get("archive") or ""))
                # A successful analysis without a surviving *verified* backup
                # is not a complete scheduled cycle. Re-run and repair.
                if prior_archive.is_file():
                    try:
                        verify_backup(prior_archive)
                    except (OSError, ValueError):
                        pass
                    else:
                        check_watch_still_stable()
                        return {"status": "SKIPPED_UNCHANGED_CACHE", "observations": dates,
                                "last_archive": str(prior_archive)}
        result = execute_local_batch(Namespace(
            kr_as_of=dates["KR"], us_as_of=dates["US"], days=550, top=20,
            legacy=str(legacy), out=str(out)))
        if result.get("market_count") != 2 or result.get("reports_created") != 6:
            raise RuntimeError("Incomplete KR/US batch")
        # A price-only cache vintage can remain unchanged while the WATCH
        # source changes. Preflight both markets AGAIN before publication.
        check_watch_still_stable()
        watch_pages = None
        if watch_preflight is not None:
            watch_pages=publish_watch_schedule_reports(watch_preflight,Path(out))
            if watch_pages["research_report_pages"]!=14:
                raise RuntimeError("Incomplete KR/US scheduled WATCH reports")
        # A file revision DURING a long analysis may mix two cache vintages.
        # Do not create a trusted checkpoint/backup in that case.
        if live_files and (latest_cached_sessions(legacy) != seen or
                           latest_cache_fingerprints(legacy, kr_as_of=seen["KR"]) != fingerprints):
            raise RuntimeError("Input cache was revised during scheduled analysis")
        backups.mkdir(parents=True, exist_ok=True)
        archive = backups / f"eraleader_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}.zip"
        create_backup(out, archive)
        verify_backup(archive)
        # The source must still be stable after creating/verifying the ZIP.
        check_watch_still_stable()
        # A correction during ZIP creation must not be marked as a stable
        # source vintage either. The archive may remain for investigation,
        # but the successful checkpoint is never advanced.
        if live_files and (latest_cached_sessions(legacy) != seen or
                           latest_cache_fingerprints(legacy, kr_as_of=seen["KR"]) != fingerprints):
            raise RuntimeError("Input cache was revised during scheduled backup")
        record = {
            "status": "RESEARCH_ONLY_VERIFIED_BACKUP",
            "observations": dates, "age_days": age,
            "cache_sha256": fingerprints,
            "source_files_verified_during_run": live_files,
            "run_finished_utc": datetime.now(timezone.utc).isoformat(),
            "archive": str(archive), "dry_run_only": True,
            "watch_research_enabled":watch_research_config is not None,
            "watch_research_config_sha256":watch_config_digest,
            "watch_research_sha256":watch_fingerprint,
            "watch_operating_report_pages":(
                watch_pages["research_report_pages"] if watch_pages else 0),
            "watch_market_run_ids":(
                watch_pages["watch_market_run_ids"] if watch_pages else None),
            "used_stale_override": allow_stale_research and any(v > max_age_days for v in age.values()),
            "external_api_calls": 0, "messages_sent": 0,
        }
        tmp = control / f".verified_{uuid.uuid4().hex}.tmp"
        try:
            tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, marker)
        finally:
            tmp.unlink(missing_ok=True)
        return record

def run_scheduled_watch_only(*, out: Path, control: Path, backups: Path,
                             watch_research_config: Path,
                             watch_max_age_days: int = 7) -> dict:
    """Independent local WATCH research when cached prices are old or absent.

    Reuses the existing scheduler lock but NEVER invokes the price backtest
    batch, price cache, an actual scheduler installation or external messages.
    The WATCH-only checkpoint is distinct from last_verified_batch.json.
    """
    if watch_research_config is None:
        raise ValueError("WATCH-only operation requires explicit local config")
    path=Path(watch_research_config)
    if out.is_symlink() or out.parent.is_symlink():
        raise ValueError("Symlink WATCH-only report target not allowed")
    config=read_watch_schedule_config(path)
    config_hash=sha256(path.read_bytes()).hexdigest()
    control.mkdir(parents=True,exist_ok=True)
    with (control/"batch.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_ALREADY_RUNNING","messages_sent":0}
        first=audit_watch_schedule_sources(
            config,clock=datetime.now(timezone.utc),
            max_age_days=watch_max_age_days,
        )
        if not first["all_markets_recent"]:
            return {
                "status":"SKIPPED_WATCH_RESEARCH_NOT_CURRENT",
                "watch_freshness_status":first["watch_freshness_status"],
                "price_batch_runs":0,
                "messages_sent":0,
                "official_leaders_confirmed":0,
            }
        fingerprints=first["watch_research_sha256"]
        def check_stable():
            read_watch_schedule_config(path)
            if sha256(path.read_bytes()).hexdigest()!=config_hash:
                raise RuntimeError("WATCH-only config revised during scheduled run")
            later=audit_watch_schedule_sources(
                config,clock=datetime.now(timezone.utc),
                max_age_days=watch_max_age_days,
            )
            if (not later["all_markets_recent"] or
                    later["watch_research_sha256"]!=fingerprints):
                raise RuntimeError("WATCH source revised during scheduled run")

        marker=control/"last_verified_watch_only.json"
        if marker.exists():
            previous=json.loads(marker.read_text(encoding="utf-8"))
            if (previous.get("watch_research_config_sha256")==config_hash and
                    previous.get("watch_research_sha256")==fingerprints):
                arch=Path(str(previous.get("archive") or ""))
                if arch.is_file():
                    try:
                        verify_backup(arch)
                    except (ValueError,OSError):
                        pass
                    else:
                        check_stable()
                        return {
                            "status":"SKIPPED_UNCHANGED_WATCH_EVIDENCE",
                            "watch_freshness_status":first["watch_freshness_status"],
                            "last_archive":str(arch),
                            "messages_sent":0,
                            "price_batch_runs":0,
                        }
        check_stable()
        pages=publish_watch_schedule_reports(first,Path(out))
        if pages["research_report_pages"]!=14:
            raise RuntimeError("WATCH-only KR/US research report incomplete")
        check_stable()
        backups.mkdir(parents=True,exist_ok=True)
        archive=backups/f"watch_only_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}.zip"
        create_backup(Path(out),archive)
        verified=verify_backup(archive)
        if verified.get("status")!="LOCAL_BACKUP_VERIFIED":
            raise RuntimeError("WATCH-only source report backup not fully verified")
        check_stable()
        result={
            "status":"WATCH_ONLY_RESEARCH_VERIFIED_BACKUP",
            "run_finished_utc":datetime.now(timezone.utc).isoformat(),
            "watch_research_enabled":True,
            "watch_research_config_sha256":config_hash,
            "watch_research_sha256":fingerprints,
            "watch_market_run_ids":pages["watch_market_run_ids"],
            "watch_operating_report_pages":pages["research_report_pages"],
            "watch_freshness_status":first["watch_freshness_status"],
            "archive":str(archive),
            "price_batch_runs":0,
            "messages_sent":0,
            "external_api_calls":0,
            "official_leaders_confirmed":0,
            "dry_run_only":True,
            "independent_market_pit_certified":False,
            "real_leader_prediction_certified":False,
        }
        temp=control/f".watch_checkpoint_{uuid.uuid4().hex}.tmp"
        try:
            with temp.open("x",encoding="utf-8") as output:
                json.dump(result,output,ensure_ascii=False,sort_keys=True,indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp,marker)
        finally:
            temp.unlink(missing_ok=True)
        return result


def write_launch_agent(path: Path, *, python: Path, project: Path,
                       hour: int = 18, minute: int = 10,
                       bootstrap_path: Path | None = None,
                       watch_research_config: Path | None = None,
                       watch_max_age_days: int = 7,
                       watch_only: bool = False,
                       maturity_only: bool = False,
                       ranked_maturity_config: Path | None = None) -> Path:
    """Generate a user-level launchd definition and SSD-safe home bootstrap.

    Does not install/load the agent. The stable home bootstrap can exit 0
    while a removable SSD is missing, then retry on next launchd interval.
    """
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid local schedule time")
    if type(watch_only) is not bool or (watch_only and watch_research_config is None):
        raise ValueError("WATCH-only launch agent requires explicit research config")
    if (type(maturity_only) is not bool or
        (maturity_only and (watch_only or watch_research_config is not None or
                            ranked_maturity_config is None)) or
        (ranked_maturity_config is not None and not maturity_only)):
        raise ValueError("Maturity-only launch agent requires its own explicit KR/US config")
    script = project / "scripts" / "run_local_scheduled.py"
    if not script.is_file():
        raise FileNotFoundError(script)
    # launchd launches this small durable shell script from the home volume.
    # A missing external volume is not a fatal agent configuration error.
    helper = (Path(bootstrap_path) if bootstrap_path is not None else
              Path.home() / "Library" / "Application Support" / "EraLeader" /
              ("ranked-maturity-launcher.sh" if maturity_only else "offline-launcher.sh"))
    if helper.is_symlink() or helper.parent.is_symlink():
        raise ValueError("Symlink launcher paths are not allowed")
    helper.parent.mkdir(parents=True, exist_ok=True)
    unavailable = "SKIPPED_EXTERNAL_SSD_UNAVAILABLE"
    quoted_script = shlex.quote(str(script))
    quoted_project = shlex.quote(str(project))
    quoted_python = shlex.quote(str(python))
    quoted_cache = shlex.quote(str(LEGACY_DEFAULT))
    watch_options=""
    if watch_research_config is not None:
        watch_path=Path(watch_research_config)
        if not watch_path.is_absolute():
            raise ValueError("Scheduled WATCH config must use an absolute path")
        read_watch_schedule_config(watch_path)
        if type(watch_max_age_days) is not int or not 0<=watch_max_age_days<=365:
            raise ValueError("Invalid WATCH research freshness day limit")
        watch_options=(
            " --watch-research-config "+shlex.quote(str(watch_path))
            +" --watch-max-age-days "+str(watch_max_age_days)
        )
    if maturity_only:
        maturity_path=Path(ranked_maturity_config)
        if not maturity_path.is_absolute():
            raise ValueError("Maturity-only config must be an absolute path")
        read_maturity_schedule_config(maturity_path)
        quoted_maturity=shlex.quote(str(maturity_path))
        ready_gate=f"if [ ! -f {quoted_script} ] || [ ! -f {quoted_maturity} ]; then"
        watch_options=(" --maturity-only --ranked-maturity-config "
                       +quoted_maturity)
    elif watch_only:
        quoted_watch = shlex.quote(str(Path(watch_research_config)))
        ready_gate=f"if [ ! -f {quoted_script} ] || [ ! -f {quoted_watch} ]; then"
        watch_options+=" --watch-only"
    else:
        ready_gate=f"if [ ! -f {quoted_script} ] || [ ! -d {quoted_cache} ]; then"
    bootstrap = chr(10).join([
        "#!/bin/sh",
        ready_gate,
        f"  echo {unavailable}",
        "  exit 0",
        "fi",
        f"exec {quoted_python} {quoted_script} --project {quoted_project}{watch_options}",
        ""
    ])
    temp = helper.with_name(f".{helper.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(bootstrap, encoding="utf-8")
        temp.chmod(0o700)
        os.replace(temp, helper)
    finally:
        temp.unlink(missing_ok=True)
    logs = Path.home() / "Library" / "Logs" / "EraLeader"
    logs.mkdir(parents=True, exist_ok=True)
    document = {
        "Label": ("org.eraleader.ranked-maturity-research" if maturity_only
                  else "org.eraleader.offline-research"),
        "ProgramArguments": ["/bin/sh", str(helper)],
        "StartInterval": 3600,
        "StartCalendarInterval": [{"Weekday": day, "Hour": hour, "Minute": minute}
                                  for day in range(2, 7)],
        "RunAtLoad": True,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(logs / ("ranked_maturity.log" if maturity_only
                                         else "scheduled.log")),
        "StandardErrorPath": str(logs / ("ranked_maturity_error.log" if maturity_only
                                          else "scheduled_error.log")),
        "EnvironmentVariables": {"PYTHONPATH": str(project / "src")},
        "ProcessType": "Background",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(document, sort_keys=True))
    return path


def run_scheduled_maturity_only(
    *, out: Path, control: Path, backups: Path,
    ranked_maturity_config: Path, sample_limit: int = 100,
) -> dict:
    """Opt-in KR+US Top-K maturity briefs, regardless of old price/WATCH age.

    Only local native first-write/frozen evidence is read. Never materialize
    labels, run the normal price batch, install launchd or send notifications.
    The verified checkpoint records the maturity state as well as the market
    day, so a full-horizon transition on that SAME market day is not skipped.
    """
    if ranked_maturity_config is None:
        raise ValueError("Maturity-only scheduling requires an explicit KR/US config")
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Invalid maturity-only sample limit")
    for path in (Path(out),Path(control),Path(backups)):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Linked maturity-only scheduled output forbidden")
    config=Path(ranked_maturity_config)
    pinned=read_maturity_schedule_config(config)
    config_hash=sha256(config.read_bytes()).hexdigest()
    control.mkdir(parents=True,exist_ok=True)
    with (control/"batch.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_ALREADY_RUNNING","messages_sent":0,
                    "price_batch_runs":0}
        first=audit_maturity_schedule_sources(
            pinned,clock=datetime.now(timezone.utc),sample_limit=sample_limit,
        )
        fingerprint=first["maturity_market_fingerprints"]

        def recheck():
            # A mutated config or any original frozen/score/feature/WATCH
            # source invalidates the checkpoint, including while skipping.
            refreshed=read_maturity_schedule_config(config)
            if sha256(config.read_bytes()).hexdigest()!=config_hash or refreshed!=pinned:
                raise RuntimeError("Maturity-only source config revised during scheduled run")
            now=audit_maturity_schedule_sources(
                pinned,clock=datetime.now(timezone.utc),
                sample_limit=sample_limit,
            )
            if now["maturity_market_fingerprints"]!=fingerprint:
                raise RuntimeError("Native Top-K maturity source or deadline state revised during run")

        marker=control/"last_verified_ranked_maturity_only.json"
        if marker.is_symlink():
            raise ValueError("Unsafe linked maturity checkpoint")
        if marker.exists():
            previous=json.loads(marker.read_text(encoding="utf-8"))
            if (previous.get("ranked_maturity_config_sha256")==config_hash and
                previous.get("ranked_maturity_fingerprints")==fingerprint and
                previous.get("sample_limit")==sample_limit):
                old_archive=Path(str(previous.get("archive") or ""))
                if old_archive.is_file():
                    try:
                        verify_backup(old_archive)
                    except (OSError,ValueError,BadZipFile):
                        pass
                    else:
                        # Never claim an unchanged *published* report when
                        # someone deleted the dashboard after the ZIP.
                        expected=[
                            Path(out)/f"ranked_maturity_{m.lower()}_research.json"
                            for m in ("KR","US")
                        ]
                        expected += [
                            Path(out)/"site"/f"ranked_maturity_{m.lower()}.html"
                            for m in ("KR","US")
                        ]
                        expected += [
                            Path(out)/folder/f"ranked_maturity_{period}_{m.lower()}.{ext}"
                            for m in ("KR","US")
                            for period in ("daily","weekly","monthly")
                            for folder,ext in (("site","html"),("reports","md"))
                        ]
                        if all(p.is_file() and not p.is_symlink() for p in expected):
                            recheck()
                            return {
                                "status":"SKIPPED_UNCHANGED_RANKED_MATURITY_EVIDENCE",
                                "last_archive":str(old_archive),
                                "messages_sent":0,"external_api_calls":0,
                                "price_batch_runs":0,
                                "official_leaders_confirmed":0,
                            }
        recheck()
        pages=publish_scheduled_maturity_reports(first,Path(out))
        if pages["ranked_maturity_report_pages"]!=16:
            raise RuntimeError("Incomplete two-market daily/weekly/monthly maturity research briefs")
        recheck()
        backups.mkdir(parents=True,exist_ok=True)
        archive=backups/(
            "ranked_maturity_only_"+datetime.now(timezone.utc).strftime(
                "%Y%m%dT%H%M%S%f")+"_"+uuid.uuid4().hex[:8]+".zip"
        )
        create_backup(Path(out),archive)
        verified=verify_backup(archive)
        if verified.get("status")!="LOCAL_BACKUP_VERIFIED":
            raise RuntimeError("Scheduled maturity derived archive could not be verified")
        recheck()
        result={
            "status":"RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP",
            "run_finished_utc":datetime.now(timezone.utc).isoformat(),
            "ranked_maturity_research_enabled":True,
            "ranked_maturity_config_sha256":config_hash,
            "ranked_maturity_fingerprints":fingerprint,
            "ranked_market_run_ids":pages["ranked_market_run_ids"],
            "ranked_maturity_report_pages":pages["ranked_maturity_report_pages"],
            "sample_limit":sample_limit,
            "archive":str(archive),
            "watch_operating_report_pages":0,
            "price_batch_runs":0,"messages_sent":0,"external_api_calls":0,
            "official_leaders_confirmed":0,
            "independent_market_pit_certified":False,
            "actual_future_leader_skill_certified":False,
            "outcome_labels_read":False,
            "dry_run_only":True,
        }
        scratch=control/f".ranked_maturity_checkpoint_{uuid.uuid4().hex}.tmp"
        try:
            with scratch.open("x",encoding="utf-8") as stream:
                json.dump(result,stream,ensure_ascii=False,sort_keys=True,indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(scratch,marker)
        finally:
            scratch.unlink(missing_ok=True)
        return result
