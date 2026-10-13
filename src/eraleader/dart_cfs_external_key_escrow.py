"""Owner-assisted independent public-key escrow for CFS recovery identity.

The external recipient RSA private key MUST be created and retained separately
from this Mac. This module never generates or silently duplicates it. A new
separate external recipient certificate is required (not the CFS certificate).
No password, private-key bytes, or decrypted key material leave local scratch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import re
import shutil
import stat
import subprocess
import uuid

from .native_encrypted_vault import _cert, _private_key, _openssl
from .dart_cfs_vintage_backup import (
    _check_root, _new_file, _bytes, _sha, _file_sha,
    verify_authenticated_recovery,
)

SCHEMA="eraleader.dart_cfs_external_recovery_escrow.v1"
SCHEME="CMS-AES-256-GCM-RSA-OAEP"
HEX=re.compile(r"[a-f0-9]{64}\Z")
SLOT=re.compile(r"escrow_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{12}\Z")
ARTIFACTS={"recovery_key.cms","receipt.json","complete.json"}
MAX_CMS=128*1024


def _public_spki(cert: Path) -> bytes:
    """Canonical DER SPKI of a validated public X509 certificate."""
    _cert(cert,require_current=False)
    bin=shutil.which("openssl")
    if not bin:
        raise ValueError("OpenSSL unavailable")
    x=subprocess.run([bin,"x509","-in",str(cert),"-pubkey","-noout"],
                     capture_output=True,stdin=subprocess.DEVNULL,timeout=15)
    if x.returncode:
        raise ValueError("Invalid public X509 certificate")
    spki=subprocess.run([bin,"pkey","-pubin","-outform","DER"],
                        input=x.stdout,capture_output=True,timeout=15)
    if spki.returncode or not spki.stdout:
        raise ValueError("Cannot canonicalize X509 public key")
    return spki.stdout


def _key_spki(key: Path) -> bytes:
    """Read only the public component of an owner-only private key."""
    _private_key(key)
    bin=shutil.which("openssl")
    if not bin:
        raise ValueError("OpenSSL unavailable")
    result=subprocess.run([bin,"pkey","-in",str(key),"-pubout",
                           "-outform","DER","-passin","pass:"],
                          capture_output=True,stdin=subprocess.DEVNULL,timeout=15)
    if result.returncode or not result.stdout:
        raise ValueError("Owner-only recovery key is unusable or protected")
    return result.stdout


def _checked_cert_pair(original_cert: Path, external_cert: Path,
                       original_key: Path | None = None,
                       *, require_external_current: bool = False) -> tuple[str,str,str]:
    primary=_public_spki(original_cert)
    independent=_public_spki(external_cert)
    if (primary==independent or
            Path(original_cert).resolve()==Path(external_cert).resolve()):
        raise ValueError("Independent escrow must use a DIFFERENT RSA public key")
    if require_external_current:
        _cert(external_cert,require_current=True)
    if original_key is not None and _key_spki(original_key)!=primary:
        raise ValueError("Live recovery private key does not match encrypted CFS recipient")
    return (_cert(original_cert,require_current=False),
            _cert(external_cert,require_current=False),
            sha256(primary).hexdigest())


def _read_seal(escrow_dir: Path, original_cert: Path,
               external_cert: Path) -> dict:
    path=_check_root(escrow_dir)
    if {p.name for p in path.iterdir()}!=ARTIFACTS:
        raise ValueError("Incomplete external key escrow package")
    if (any(p.is_symlink() or
            stat.S_IMODE(p.stat().st_mode)&0o077 for p in path.iterdir())):
        raise ValueError("External escrow cannot contain linked or public files")
    receipt=path/"receipt.json"
    raw=receipt.read_bytes()
    if len(raw)>8192:
        raise ValueError("Oversized escrow receipt")
    info=json.loads(raw)
    seal=json.loads((path/"complete.json").read_bytes())
    valid={"schema","scheme","slot","created_at_utc",
           "source_recipient_cert_sha256","external_recipient_cert_sha256",
           "source_public_spki_sha256","ciphertext_sha256","ciphertext_bytes",
           "actual_independent_private_key_custody_attested",
           "plain_key_escrowed","original_private_key_retained"}
    original_sha,external_sha,public_sha=_checked_cert_pair(original_cert,external_cert)
    if (type(info) is not dict or set(info)!=valid or
            info["schema"]!=SCHEMA or info["scheme"]!=SCHEME or
            type(info["slot"]) is not str or not SLOT.fullmatch(info["slot"]) or
            info["slot"]!=path.name or
            info["source_recipient_cert_sha256"]!=original_sha or
            info["external_recipient_cert_sha256"]!=external_sha or
            info["source_public_spki_sha256"]!=public_sha or
            type(info["ciphertext_bytes"]) is not int or
            not 0<info["ciphertext_bytes"]<=MAX_CMS or
            info["plain_key_escrowed"] is not False or
            info["original_private_key_retained"] is not True or
            info["actual_independent_private_key_custody_attested"] is not False or
            type(info["ciphertext_sha256"]) is not str or
            not HEX.fullmatch(info["ciphertext_sha256"])):
        raise ValueError("External recovery key escrow receipt/identity invalid")
    if (type(seal) is not dict or
            set(seal)!={"receipt_sha256","ciphertext_sha256"} or
            seal["receipt_sha256"]!=_sha(raw) or
            seal["ciphertext_sha256"]!=info["ciphertext_sha256"]):
        raise ValueError("External escrow receipt SHA seal invalid")
    if _file_sha(path/"recovery_key.cms",MAX_CMS)!=(
            info["ciphertext_sha256"],info["ciphertext_bytes"]):
        raise ValueError("External key escrow ciphertext SHA mismatch")
    return info


def prepare_external_key_escrow(local_key: Path, original_cert: Path,
                                external_cert: Path, destination_root: Path,
                                *, require_independent_device: bool = True,
                                clock: datetime | None = None) -> dict:
    """Protect local recovery key under an OFF-MAC managed external RSA identity.

    External private key is never accepted by this export operation.
    The physically/offline custodied external key is a human responsibility.
    """
    source=Path(local_key)
    _private_key(source)
    orig_sha,recipient_sha,pub_sha=_checked_cert_pair(
        original_cert,external_cert,source,require_external_current=True)
    out=_check_root(destination_root,writable=True)
    if (source==out or out in source.parents or source in out.parents or
            (require_independent_device and source.stat().st_dev==out.stat().st_dev)):
        raise ValueError("Escrow ciphertext must be on a DIFFERENT device from live key")
    if clock is None:
        now=datetime.now(timezone.utc)
    elif not isinstance(clock,datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("Escrow clock must be timezone-aware")
    else:
        now=clock.astimezone(timezone.utc)
    slot=f"escrow_{now:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:12]}"
    target=out/slot
    if target.exists() or target.is_symlink():
        raise FileExistsError("Escrow cannot overwrite a prior recovery package")
    with TemporaryDirectory(prefix=".escrow_encrypt_",dir=out) as stage_str:
        stage=Path(stage_str)
        cms=stage/"recovery_key.cms"
        previous_umask=os.umask(0o077)
        try:
            _openssl(["-encrypt","-aes-256-gcm","-binary","-in",str(source),
                      "-out",str(cms),"-outform","DER",
                      "-recip",str(external_cert),
                      "-keyopt","rsa_padding_mode:oaep"])
        finally:
            os.umask(previous_umask)
        os.chmod(cms,0o600)
        cipher_sha,length=_file_sha(cms,MAX_CMS)
        info={
            "schema":SCHEMA,"scheme":SCHEME,"slot":slot,
            "created_at_utc":now.isoformat(),
            "source_recipient_cert_sha256":orig_sha,
            "external_recipient_cert_sha256":recipient_sha,
            "source_public_spki_sha256":pub_sha,
            "ciphertext_sha256":cipher_sha,"ciphertext_bytes":length,
            "actual_independent_private_key_custody_attested":False,
            "plain_key_escrowed":False,"original_private_key_retained":True,
        }
        receipt=_bytes(info)
        _new_file(stage/"receipt.json",receipt)
        _new_file(stage/"complete.json",_bytes({
            "receipt_sha256":_sha(receipt),"ciphertext_sha256":cipher_sha
        }))
        if target.exists() or target.is_symlink():
            raise FileExistsError("Escrow target unexpectedly exists")
        os.rename(stage,target)
    verified=_read_seal(target,original_cert,external_cert)
    return {
        "status":"EXTERNAL_KEY_ESCROW_ENCRYPTED_NOT_OFFLINE_CUSTODY_CERTIFIED",
        "slot":verified["slot"],
        "ciphertext_sha256":verified["ciphertext_sha256"],
        "external_recipient_certificate_sha256":recipient_sha,
        "original_private_key_retained":True,
        "actual_offline_private_key_custody_verified":False,
        "external_recovery_drill_passed":False,
    }


def verify_external_key_escrow(escrow_dir: Path, original_cert: Path,
                               external_cert: Path) -> dict:
    report=_read_seal(escrow_dir,original_cert,external_cert)
    return {"status":"EXTERNAL_KEY_ESCROW_SHA_VERIFIED_NOT_DECRYPTED",
            "slot":report["slot"],
            "ciphertext_sha256":report["ciphertext_sha256"],
            "actual_offline_private_key_custody_verified":False,
            "external_recovery_drill_passed":False}


def drill_external_key_escrow(escrow_dir: Path, original_cert: Path,
                              external_cert: Path, external_key: Path,
                              ssd_snapshot: Path, mac_snapshot: Path,
                              scratch_root: Path,
                              *, require_independent_device: bool = True) -> dict:
    """Decrypt only inside private scratch, then test recovery with restored key."""
    info=_read_seal(escrow_dir,original_cert,external_cert)
    escrow_private=_private_key(external_key)
    if _key_spki(escrow_private)!=_public_spki(external_cert):
        raise ValueError("Supplied independent recipient private key mismatches cert")
    scratch=_check_root(scratch_root,writable=True)
    if (scratch==Path(escrow_dir) or Path(escrow_dir) in scratch.parents or
            Path(ssd_snapshot) in scratch.parents or
            Path(mac_snapshot) in scratch.parents):
        raise ValueError("Independent recovery scratch cannot overlap protected originals")
    with TemporaryDirectory(prefix=".dart_cfs_external_drill_",dir=scratch) as temp:
        source_key=Path(temp)/"recovered_original_recovery_private.pem"
        previous_umask=os.umask(0o077)
        try:
            _openssl(["-decrypt","-binary","-inform","DER",
                      "-in",str(Path(escrow_dir)/"recovery_key.cms"),
                      "-out",str(source_key),"-recip",str(external_cert),
                      "-inkey",str(escrow_private)])
        finally:
            os.umask(previous_umask)
        os.chmod(source_key,0o600)
        if _key_spki(source_key)!=_public_spki(original_cert):
            raise ValueError("Externally recovered key not linked to existing CFS backup")
        result=verify_authenticated_recovery(
            ssd_snapshot,mac_snapshot,original_cert,source_key,scratch,
            require_independent_devices=require_independent_device)
        if (result.get("authenticated_recovery_tested") is not True or
                result.get("first_known_asof_replay_verified") is not True or
                result.get("plaintext_retained") is not False):
            raise ValueError("External key escrow recovery did not replay CFS source")
    return {
        "status":"EXTERNAL_KEY_ESCROW_AUTHENTICATED_CFS_RESTORE_DRILL_PASS",
        "slot":info["slot"],
        "ciphertext_sha256":info["ciphertext_sha256"],
        "first_known_asof_replay_verified":True,
        "original_backup_authenticated":True,
        "scratch_plaintext_retained":False,
        "actual_offline_private_key_custody_verified":False,
    }
