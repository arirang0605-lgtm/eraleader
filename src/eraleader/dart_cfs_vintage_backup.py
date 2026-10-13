"""Encrypted, cross-volume, first-known DART CFS SQLite recovery snapshot.

Only a consistent SQLite online-backup copy is encrypted, not the live file.
Reuses the existing OpenSSL CMS AES-256-GCM / RSA-OAEP primitives; no network.
Backups on SSD + Mac are two ciphertext copies, not independent key escrow.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import uuid

from .native_encrypted_vault import _openssl, _cert, _private_key
from .official_dart_vintage_registry import DartCFSVintageRegistry

SCHEMA = "eraleader.dart_cfs_vintage_cross_volume_backup.v1"
SCHEME = "CMS-AES-256-GCM-RSA-OAEP"
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
SLOT = re.compile(r"cfs_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{12}\Z")
FILES = {"vintage.cms", "receipt.json", "complete.json"}
MAX_SOURCE = 32 * 1024 * 1024
MAX_CIPHER = MAX_SOURCE + 1024 * 1024


def _bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(blob: bytes) -> str:
    return sha256(blob).hexdigest()


def _file_sha(path: Path, limit: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Backup expects a regular nonlinked file")
    if path.stat().st_size > limit or path.stat().st_size <= 0:
        raise ValueError("Backup file size out of bounds")
    h=sha256()
    length=0
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024*1024), b""):
            length += len(part)
            if length > limit:
                raise ValueError("Backup file exceeded size limit during read")
            h.update(part)
    return h.hexdigest(), length


def _check_root(folder: Path, *, writable: bool = False) -> Path:
    p=Path(folder)
    if (not p.is_absolute() or ".." in p.parts or p.is_symlink() or
            not p.is_dir() or any(a.is_symlink() for a in p.parents) or
            p.stat().st_uid != os.geteuid() or
            stat.S_IMODE(p.stat().st_mode)&0o077):
        raise ValueError("Owner-only absolute nonlinked backup root required")
    if writable and not os.access(p, os.W_OK):
        raise ValueError("Backup destination cannot be written")
    return p


def _new_file(path: Path, data: bytes) -> None:
    fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0), 0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _now(clock: datetime | None) -> tuple[datetime, bool]:
    if clock is None:
        return datetime.now(timezone.utc), False
    if not isinstance(clock,datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("Backup clock requires timezone")
    return clock.astimezone(timezone.utc), True


def _inspect(path: Path) -> dict:
    """Open the actual SQLite with no writes and recheck the existing chain."""
    p=Path(path)
    if (p.is_symlink() or not p.is_file() or p.stat().st_uid != os.geteuid() or
            stat.S_IMODE(p.stat().st_mode)&0o077):
        raise ValueError("Original SQLite must be private and ordinary")
    digest,length=_file_sha(p,MAX_SOURCE)
    with sqlite3.connect(p.as_uri()+"?mode=ro",uri=True) as db:
        row=db.execute("PRAGMA integrity_check").fetchone()
        if row != ("ok",):
            raise ValueError("Original SQLite integrity_check failed")
    with DartCFSVintageRegistry(p,read_only=True) as db:
        status=db.checksum()
    if (status["records"] < 1 or status["records"] > 100000 or
            not HEX64.fullmatch(status["tail_chain_sha256"])):
        raise ValueError("Empty/invalid original DART first-received chain")
    return {"db_sha256":digest, "db_bytes":length,
            "events":status["records"], "tail_chain_sha256":status["tail_chain_sha256"]}


def create_recovery_keypair(folder: Path) -> dict:
    """One-time local RSA3072 recovery identity. Never overwrite or print key."""
    dest=Path(folder)
    if (not dest.is_absolute() or ".." in dest.parts or dest.is_symlink() or
            any(a.is_symlink() for a in dest.parents) or dest.exists()):
        raise ValueError("Recovery key directory must be a NEW absolute path")
    if not dest.parent.is_dir() or stat.S_IMODE(dest.parent.stat().st_mode)&0o077:
        raise ValueError("Recovery key parent must already be private")
    dest.mkdir(mode=0o700)
    key=dest/"recovery_private.pem"
    cert=dest/"recovery_public.crt"
    try:
        binary=shutil.which("openssl")
        if not binary:
            raise ValueError("Existing OpenSSL prerequisite unavailable")
        result=subprocess.run(
            [binary,"req","-x509","-newkey","rsa:3072","-noenc",
             "-keyout",str(key),"-out",str(cert),"-days","3650",
             "-subj","/CN=EraLeader Local DART CFS Recovery"],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,timeout=45,check=False)
        if result.returncode:
            raise ValueError("Owner-only RSA encryption key setup failed")
        os.chmod(key,0o600)
        os.chmod(cert,0o600)
        fingerprint=_cert(cert,require_current=True)
        _private_key(key)
        return {"status":"LOCAL_RSA_3072_RECOVERY_KEYS_CREATED",
                "public_certificate_sha256":fingerprint,
                "private_key_escrow_independent_volume_verified":False}
    except BaseException:
        # Only files created inside this freshly exclusive owner-only folder.
        shutil.rmtree(dest)
        raise


def _snapshot_sqlite(source: Path, target: Path) -> None:
    source=_check_source(source)
    if target.exists() or target.is_symlink():
        raise ValueError("Fresh isolated SQLite staging required")
    src=sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=30)
    original_umask=os.umask(0o077)
    try:
        dest=sqlite3.connect(str(target),timeout=30)
        try:
            src.backup(dest,pages=100)
            dest.commit()
        finally:
            dest.close()
    finally:
        os.umask(original_umask)
        src.close()
    os.chmod(target,0o600)


def _check_source(path: Path) -> Path:
    p=Path(path)
    if (not p.is_absolute() or p.is_symlink() or not p.is_file() or
            any(parent.is_symlink() for parent in p.parents)):
        raise ValueError("Private original SQLite path must not be linked")
    _inspect(p)
    return p


def _read_seal(folder: Path, certificate: Path) -> tuple[dict,bytes,str]:
    folder=_check_root(folder)
    if {p.name for p in folder.iterdir()} != FILES:
        raise ValueError("Incomplete encrypted CFS snapshot")
    receipt=folder/"receipt.json"
    complete=folder/"complete.json"
    cms=folder/"vintage.cms"
    if (any(p.is_symlink() for p in (receipt,complete,cms)) or
            any(stat.S_IMODE(p.stat().st_mode)&0o077 for p in (receipt,complete,cms))):
        raise ValueError("Encrypted backup cannot include linked/public originals")
    r=receipt.read_bytes()
    if len(r)>5000:
        raise ValueError("Oversized encrypted recovery receipt")
    manifest=json.loads(r)
    seal=json.loads(complete.read_bytes())
    keys={"schema","scheme","slot","created_at_utc","source_db_sha256",
          "snapshot_db_sha256","snapshot_db_bytes","events",
          "tail_chain_sha256","ciphertext_sha256","ciphertext_bytes",
          "recipient_certificate_sha256","clock_simulated",
          "historic_publication_pit_certified","independent_key_escrow_verified"}
    if (type(manifest) is not dict or set(manifest)!=keys or
            manifest["schema"]!=SCHEMA or manifest["scheme"]!=SCHEME or
            not SLOT.fullmatch(str(manifest["slot"])) or
            type(manifest["events"]) is not int or manifest["events"]<1 or
            type(manifest["clock_simulated"]) is not bool or
            manifest["historic_publication_pit_certified"] is not False or
            manifest["independent_key_escrow_verified"] is not False or
            type(manifest["snapshot_db_bytes"]) is not int or
            type(manifest["ciphertext_bytes"]) is not int or
            not 0<manifest["snapshot_db_bytes"]<=MAX_SOURCE or
            not 0<manifest["ciphertext_bytes"]<=MAX_CIPHER or
            any(not HEX64.fullmatch(str(manifest[k])) for k in (
                "source_db_sha256","snapshot_db_sha256","tail_chain_sha256",
                "ciphertext_sha256","recipient_certificate_sha256"))):
        raise ValueError("Recovery receipt SHA contract invalid")
    if (type(seal) is not dict or set(seal)!={"receipt_sha256","ciphertext_sha256"} or
            seal["receipt_sha256"]!=_sha(r) or
            seal["ciphertext_sha256"]!=manifest["ciphertext_sha256"] or
            manifest["recipient_certificate_sha256"]!=_cert(certificate,require_current=False)):
        raise ValueError("Encrypted first evidence receipt/recipient mismatch")
    if _file_sha(cms,MAX_CIPHER)!=(manifest["ciphertext_sha256"],manifest["ciphertext_bytes"]):
        raise ValueError("Encrypted recovery ciphertext changed")
    if folder.name!=manifest["slot"]:
        raise ValueError("Encrypted snapshot slot path mismatch")
    return manifest,r,seal["receipt_sha256"]


def verify_recovery_copies(ssd_snapshot: Path, mac_snapshot: Path,
                           recipient_cert: Path, *,
                           require_independent_devices: bool = True) -> dict:
    first,one,receipt_sha=_read_seal(ssd_snapshot,recipient_cert)
    second,two,other_receipt=_read_seal(mac_snapshot,recipient_cert)
    if (first!=second or one!=two or other_receipt!=receipt_sha or
            _file_sha(Path(ssd_snapshot)/"vintage.cms",MAX_CIPHER) !=
            _file_sha(Path(mac_snapshot)/"vintage.cms",MAX_CIPHER)):
        raise ValueError("SSD and Mac encrypted copies disagree")
    if (require_independent_devices and
            Path(ssd_snapshot).stat().st_dev==Path(mac_snapshot).stat().st_dev):
        raise ValueError("Two encrypted copies must live on independent devices")
    return {"status":"TWO_ENCRYPTED_CFS_COPIES_SHA_MATCHED",
            "slot":first["slot"],"snapshot_db_sha256":first["snapshot_db_sha256"],
            "encrypted_sha256":first["ciphertext_sha256"],
            "receipt_sha256":receipt_sha,
            "events":first["events"],
            "tail_chain_sha256":first["tail_chain_sha256"],
            "crypto":"AES-256-GCM/RSA-OAEP",
            "authenticated_recovery_tested":False,
            "separate_storage_device_verified":require_independent_devices,
            "private_key_offline_escrow_verified":False,
            "historic_publication_pit_certified":False}


def backup_vintage_ledger(source: Path, ssd_root: Path, mac_root: Path,
                          recipient_cert: Path, *,
                          clock: datetime | None = None,
                          require_independent_devices: bool = True) -> dict:
    src=_check_source(source)
    ssd=_check_root(ssd_root,writable=True)
    mac=_check_root(mac_root,writable=True)
    if ssd==mac or (require_independent_devices and ssd.stat().st_dev==mac.stat().st_dev):
        raise ValueError("SSD backup and Mac backup must be physically separate")
    if (src==ssd or src==mac or ssd in src.parents or mac in src.parents):
        raise ValueError("Cannot use live source DB inside backup root")
    cert_sha=_cert(recipient_cert,require_current=True)
    moment,simulated=_now(clock)
    source_before=_inspect(src)
    slot=f"cfs_{moment:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:12]}"
    paths=[ssd/slot,mac/slot]
    if any(p.exists() or p.is_symlink() for p in paths):
        raise FileExistsError("New incremental snapshot slot already exists")
    # Only private Mac staging ever contains an unencrypted online backup.
    with TemporaryDirectory(prefix=".cfs_encrypt_staging_",dir=mac) as temp:
        stage=Path(temp)
        plain=stage/"online_backup.sqlite"
        encrypted=stage/"ciphertext.cms"
        _snapshot_sqlite(src,plain)
        checked=_inspect(plain)
        if (source_before["events"]!=checked["events"] or
                source_before["tail_chain_sha256"]!=checked["tail_chain_sha256"] or
                _inspect(src)["tail_chain_sha256"]!=checked["tail_chain_sha256"]):
            raise ValueError("Live source registration changed during online backup")
        _openssl(["-encrypt","-aes-256-gcm","-binary",
                  "-in",str(plain),"-out",str(encrypted),
                  "-outform","DER","-recip",str(recipient_cert),
                  "-keyopt","rsa_padding_mode:oaep"])
        cipher_sha,cipher_bytes=_file_sha(encrypted,MAX_CIPHER)
        receipt={
            "schema":SCHEMA,"scheme":SCHEME,"slot":slot,
            "created_at_utc":moment.isoformat(),
            "source_db_sha256":source_before["db_sha256"],
            "snapshot_db_sha256":checked["db_sha256"],
            "snapshot_db_bytes":checked["db_bytes"],
            "events":checked["events"],
            "tail_chain_sha256":checked["tail_chain_sha256"],
            "ciphertext_sha256":cipher_sha,"ciphertext_bytes":cipher_bytes,
            "recipient_certificate_sha256":cert_sha,
            "clock_simulated":simulated,
            "historic_publication_pit_certified":False,
            "independent_key_escrow_verified":False,
        }
        r=_bytes(receipt)
        complete=_bytes({"receipt_sha256":_sha(r),"ciphertext_sha256":cipher_sha})
        for folder in paths:
            folder.mkdir(mode=0o700)
            _new_file(folder/"vintage.cms",encrypted.read_bytes())
            _new_file(folder/"receipt.json",r)
            # Complete marker LAST: interrupted publication must fail closed.
            _new_file(folder/"complete.json",complete)
        result=verify_recovery_copies(paths[0],paths[1],recipient_cert,
                     require_independent_devices=require_independent_devices)
    return result


def _verify_first_known_replay(path: Path) -> int:
    """Recompute first registration boundaries on isolated restored SQLite."""
    checked=0
    with DartCFSVintageRegistry(path,read_only=True) as db:
        items=db._audit()
        grouped={}
        for row in items:
            grouped.setdefault(row["identity"],[]).append(row)
        for identity,history in grouped.items():
            segments=identity.split("|")
            if len(segments)!=6 or segments[0]!="KR" or segments[4:]!=["11011","CFS"]:
                raise ValueError("Restored vintage includes unexpected identity")
            _,stock,corp,year,*_=segments
            start=min(datetime.fromisoformat(r["registered_at_utc"]) for r in history)
            end=max(datetime.fromisoformat(r["registered_at_utc"]) for r in history)
            before=db.review_as_of(
                decision_at=(start-timedelta(microseconds=1)).isoformat(),
                stock_code=stock,corp_code=corp,fiscal_year=int(year))
            after=db.review_as_of(
                decision_at=end.isoformat(),stock_code=stock,
                corp_code=corp,fiscal_year=int(year))
            if (before["registered_vintages_available"]!=0 or
                    after["registered_vintages_available"]!=len(history)):
                raise ValueError("Restored vintage cannot reproduce initial first-known time")
            checked+=len(history)
    return checked


def verify_authenticated_recovery(ssd_snapshot: Path, mac_snapshot: Path,
                                  cert: Path, private_key: Path, scratch_root: Path,
                                  *, require_independent_devices: bool=True) -> dict:
    """Decrypt privately in fresh isolated scratch, verify, leave NO raw DB."""
    _private_key(private_key)
    scratch=_check_root(scratch_root,writable=True)
    status=verify_recovery_copies(ssd_snapshot,mac_snapshot,cert,
                                  require_independent_devices=require_independent_devices)
    source_receipt=json.loads((Path(ssd_snapshot)/"receipt.json").read_bytes())
    with TemporaryDirectory(prefix=".cfs_private_restore_",dir=scratch) as tmp:
        restored=Path(tmp)/"isolated_restored.sqlite"
        _openssl(["-decrypt","-binary","-inform","DER",
                  "-in",str(Path(ssd_snapshot)/"vintage.cms"),
                  "-out",str(restored),"-recip",str(cert),"-inkey",str(private_key)])
        os.chmod(restored,0o600)
        actual=_inspect(restored)
        if (actual["db_sha256"]!=source_receipt["snapshot_db_sha256"] or
                actual["db_bytes"]!=source_receipt["snapshot_db_bytes"] or
                actual["events"]!=source_receipt["events"] or
                actual["tail_chain_sha256"]!=source_receipt["tail_chain_sha256"]):
            raise ValueError("Authenticated isolated recovery disagrees with first DB proof")
        replayed=_verify_first_known_replay(restored)
        if replayed!=actual["events"]:
            raise ValueError("Restored prospective first-known event count changed")
    return {**status,"status":"ENCRYPTED_DART_CFS_INDEPENDENT_RESTORE_VERIFIED",
            "authenticated_recovery_tested":True,
            "restored_chain_verified":True,
            "first_known_asof_replay_verified":True,
            "plaintext_retained":False,
            "historic_publication_pit_certified":False}
