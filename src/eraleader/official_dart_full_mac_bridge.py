"""Use existing strict DART full-page collector from Mac owner-only storage.

Original SSD first raw/receipt are verified read-only, then copied exactly
once into a protected Mac internal evidence folder. This supports exFAT's
0700 file-mode mapping without weakening the existing 0600 source verifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat

from .official_three_provider_session_gate import verified_local_capture
from .official_api_capture import credentials
from .official_dart_daily import capture_dart_day, verify_dart_day

DEFAULT_ROOT=Path.home()/"Library"/"Application Support"/"EraLeader"/"dart_full_live"

def _owner_dir(root:Path) -> None:
    if root.is_symlink():
        raise ValueError("DART private root cannot be linked")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if (not root.is_dir() or root.stat().st_uid!=os.geteuid() or
            stat.S_IMODE(root.stat().st_mode)!=0o700):
        raise ValueError("DART Mac evidence root must be owner-only")

def _private_write(destination:Path,contents:bytes)->None:
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
    fd=os.open(destination,flags,0o600)
    with os.fdopen(fd,"wb") as target:
        target.write(contents)
        target.flush()
        os.fsync(target.fileno())
    if stat.S_IMODE(destination.stat().st_mode)!=0o600:
        raise ValueError("Mac evidence file cannot enforce 0600")

def mirror_first_page(original:Path,first_sha:str,private_root:Path,
                      decision_at:datetime)->Path:
    original=Path(original)
    private_root=Path(private_root)
    checked,_=verified_local_capture(
        original,"dart-disclosures",first_sha,decision_at)
    _owner_dir(private_root)
    if original.stat().st_dev==private_root.stat().st_dev:
        raise ValueError("First DART receipt mirror must be on Mac internal distinct filesystem")
    if not original.name.startswith("first_"):
        raise ValueError("Official first-capture ID expected")
    copied=private_root/original.name
    files=("raw_response.json","first_receipt.json")
    if copied.exists():
        if copied.is_symlink() or not copied.is_dir():
            raise ValueError("Existing mirrored first source invalid")
        for name in files:
            check=copied/name
            if (check.is_symlink() or not check.is_file() or
                    stat.S_IMODE(check.stat().st_mode)!=0o600 or
                    check.stat().st_uid!=os.geteuid()):
                raise ValueError("Mirrored original first file invalid")
            source=original/name
            if sha256(check.read_bytes()).digest()!=sha256(source.read_bytes()).digest():
                raise ValueError("DART first mirror differs from original SSD immutable bytes")
    else:
        copied.mkdir(mode=0o700)
        try:
            for name in files:
                _private_write(copied/name,(original/name).read_bytes())
        except BaseException:
            shutil.rmtree(copied)
            raise
    # Existing strict validator must accept the mirror with the IDENTICAL
    # independent first-receipt SHA, no fresh first-received timestamp.
    if sha256((copied/"first_receipt.json").read_bytes()).hexdigest()!=first_sha:
        raise ValueError("DART original independent receipt SHA mismatch")
    verified,_=verified_local_capture(
        original,"dart-disclosures",first_sha,decision_at)
    if checked!=verified:
        raise ValueError("Original first DART receipt changed during mirror")
    return copied

def complete_day_from_ssd(first_folder:Path,first_sha:str, *,
                          private_root:Path=DEFAULT_ROOT,
                          credential_path:Path|None=None,
                          fetch=None,clock=None,max_pages:int=100)->dict:
    root=Path(private_root)
    now=clock or (lambda:datetime.now(timezone.utc))
    mirror=mirror_first_page(first_folder,first_sha,root,now())
    # Avoid spending DART quota if a previously complete and tested result
    # already exists for this immutable first receipt.
    for candidate in sorted(root.glob("dart_full_*/manifest.json")):
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("Invalid prior complete DART manifest")
        try:
            manifest=json.loads(candidate.read_bytes())
        except (UnicodeError,ValueError):
            raise ValueError("Malformed prior DART completion") from None
        if (manifest.get("original_first_capture_id")==mirror.name and
                manifest.get("original_first_receipt_sha256")==first_sha):
            digest=sha256(candidate.read_bytes()).hexdigest()
            validated=verify_dart_day(
                candidate.parent,digest,first_folder=mirror,
                first_sha=first_sha,decision_at=now())
            return {"status":"DART_COMPLETE_REUSED_VERIFIED",
                    "market_day":validated["market_day"],
                    "total_rows":validated["total_rows"],
                    "pages":validated["total_pages"],"captured_new_pages":0,
                    "capture_id":candidate.parent.name,
                    "manifest_sha256":digest,"pit_certified":False}
    path=credential_path
    if path is None:
        path=Path.home()/"Library"/"Application Support"/"EraLeader"/"api-credentials"/"official_api.env"
    result=capture_dart_day(mirror,first_sha,root,
                            creds=credentials(Path(path)),fetch=fetch,
                            clock=now,max_pages=max_pages)
    verified=verify_dart_day(root/result["capture_id"],result["manifest_sha256"],
                             first_folder=mirror,first_sha=first_sha,decision_at=now())
    if (verified["total_rows"]!=result["total_rows"] or
            verified["total_pages"]!=result["pages"]):
        raise ValueError("Final DART page digest/count verification failed")
    verified_local_capture(Path(first_folder),"dart-disclosures",first_sha,now())
    return result
