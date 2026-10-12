"""6_5 opt-in encrypted copy of first native original ZIP, on a separate filesystem.

Uses OpenSSL CMS AuthEnvelopedData: AES-256-GCM and RSA-OAEP only.
No market API, live delivery or direct investment signal. Plaintext is never
copied to the secondary vault. Restore requires private key + original SHA
witness and ALWAYS uses a new, otherwise nonexistent private destination.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import fcntl
import os
import re
import shutil
import stat
import subprocess
import tempfile

from .native_evidence_archive import (
    _bytes, _parse, _slot, verify_native_evidence_archive,
    restore_native_evidence_archive,
)
from .native_first_capture import read_capture_plan
from .native_sha_witness import (
    validate_witness_destination, verify_native_sha_witness,
    _read as _read_witness, _witness_paths, SCHEMA as WITNESS_SCHEMA,
    GUARD_SCHEMA as WITNESS_GUARD_SCHEMA,
)

SCHEMA = "eraleader.encrypted_first_native_backup.v1"
GUARD_SCHEMA = "eraleader.encrypted_first_native_guard.v1"
SCHEME = "CMS-AES-256-GCM-RSA-OAEP"
SLOT = re.compile(r"(kr|us)_[0-9a-f]{24}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_ZIP = 250 * 1024 * 1024
MAX_CMS = MAX_ZIP + 1024 * 1024


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _file_sha(path: Path, limit: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Missing or linked original/backup file")
    if not 0 < path.stat().st_size <= limit:
        raise ValueError("Oversized or empty original/backup file")
    digest = sha256()
    count = 0
    with open(path, "rb") as inp:
        while True:
            block = inp.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > limit:
                raise ValueError("Archive grew beyond allowed maximum during SHA check")
            digest.update(block)
    if count != path.stat().st_size:
        raise ValueError("Archive changed during SHA check")
    return digest.hexdigest(), count


def _now(clock):
    value = clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Encrypted backup requires timezone-aware local clock")
    return value.astimezone(timezone.utc)


def _safe_private_root(path: Path, *, must_exist: bool) -> Path:
    root = Path(path)
    if not root.is_absolute() or ".." in root.parts or len(root.parts) < 3:
        raise ValueError("Absolute private external path required")
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise ValueError("Linked private backup path")
    if root.exists():
        if not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise ValueError("Private backup/witness root must be directory mode 0700")
    elif must_exist:
        raise ValueError("Missing original private backup/witness root")
    return root


def _paths(vault_root: Path, slot: str):
    if not isinstance(slot, str) or SLOT.fullmatch(slot) is None:
        raise ValueError("Invalid first-native market/model slot")
    root = _safe_private_root(vault_root, must_exist=False)
    cipher = root / ("native_" + slot + ".cms")
    first = root / ("native_" + slot + "_first.json")
    guard = root / ("native_" + slot + "_guard.json")
    lock = root / (".native_" + slot + ".lock")
    for path in (cipher, first, guard, lock):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Linked or invalid encrypted backup artifact")
    return root, cipher, first, guard, lock


def _new(path: Path, content: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(content)
        out.flush()
        os.fsync(out.fileno())


def _read_json(path: Path, limit: int):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Missing or corrupted first encrypted backup receipt")
    raw = path.read_bytes()
    obj = _parse(raw)
    if type(obj) is not dict or _bytes(obj) != raw:
        raise ValueError("Noncanonical encrypted backup receipt")
    return obj, raw


def _external_first(root: Path, slot: str, *, archive_sha=None, expected_sha=None):
    root = _safe_private_root(root, must_exist=True)
    first, guard, lock = _witness_paths(root, slot)
    if not lock.is_file():
        raise ValueError("Missing external first native SHA witness lock")
    fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent original SHA witness writer") from exc
        try:
            value, raw = _read_witness(first, 4096)
            anchor, _ = _read_witness(guard, 2048)
            valid = (set(anchor) == {
                "schema_version", "slot", "first_witness_sha256",
                "nonce_sha256", "independent_timestamp_attested",
            } and anchor["schema_version"] == WITNESS_GUARD_SCHEMA and
                anchor["slot"] == slot and anchor["first_witness_sha256"] == _sha(raw) and
                type(value) is dict and value.get("schema_version") == WITNESS_SCHEMA and
                value.get("slot") == slot and value.get("market") == slot[:2].upper() and
                type(value.get("nonce")) is str and
                re.fullmatch(r"[a-f0-9]{32}", value["nonce"]) is not None and
                anchor["nonce_sha256"] == _sha(value["nonce"].encode()) and
                anchor["independent_timestamp_attested"] is False and
                value.get("independent_timestamp_attested") is False and
                value.get("independent_market_pit_certified") is False and
                type(value.get("official_leader_promotions")) is int and
                value["official_leader_promotions"] == 0 and
                type(value.get("archive_sha256")) is str and
                DIGEST.fullmatch(value["archive_sha256"]) is not None)
            if not valid:
                raise ValueError("Separate first SHA witness/guard mismatch")
            if archive_sha is not None and value["archive_sha256"] != archive_sha:
                raise ValueError("Original ZIP SHA differs from separate first anchor")
            if expected_sha is not None and _sha(raw) != expected_sha:
                raise ValueError("Replaced original separate first SHA witness")
            return {"witness_sha256": _sha(raw), "archive_sha256": value["archive_sha256"],
                    "market": value["market"], "plan_sha256": value["plan_sha256"]}
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _openssl(args: list[str]):
    exe = shutil.which("openssl")
    if not exe:
        raise RuntimeError("OpenSSL executable unavailable; encryption not attempted")
    process = subprocess.run([exe, "cms", *args], stdin=subprocess.DEVNULL,
                             capture_output=True, check=False)
    if process.returncode != 0:
        # stderr often includes PRIVATE filenames, so never surface it.
        raise ValueError("OpenSSL authenticated CMS encryption/decryption failed")
    return process


def _cert(path: Path, *, require_current: bool = True):
    """Validate the exact original X509, without expiring old decrypt rights.

    Only NEW encryption requires an unexpired certificate. Previously created
    CMS ciphertext remains recoverable with its pinned original certificate
    and correct private key even after certificate expiration.
    """
    path = Path(path)
    sha, size = _file_sha(path, 64 * 1024)
    args = (["-checkend", "0"] if require_current else ["-dates"])
    result = subprocess.run([shutil.which("openssl") or "openssl",
                             "x509", "-in", str(path), "-noout", *args],
                            capture_output=True, stdin=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        raise ValueError("Invalid/expired public encryption certificate")
    return sha


def _private_key(path: Path):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or not stat.S_ISREG(file.stat().st_mode):
        raise ValueError("Missing or linked private restore key")
    if (stat.S_IMODE(file.stat().st_mode) & 0o077 or
            file.stat().st_uid != os.geteuid() or file.stat().st_size > 64 * 1024):
        raise ValueError("Private restore key must be owner-only mode 0600")
    return file


def _verified(root: Path, slot: str, witness_root: Path, cert: Path):
    root, cipher, first, guard, lock = _paths(root, slot)
    if not lock.is_file() or lock.is_symlink():
        raise ValueError("Missing original encrypted vault lock")
    fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Encrypted backup writer is active") from exc
        try:
            return _verified_unlocked(cipher, first, guard, slot, witness_root, cert)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _verified_unlocked(cipher, first, guard, slot, witness_root, cert):
    data, raw = _read_json(first, 4096)
    seal, _ = _read_json(guard, 2048)
    required = {
        "schema_version", "scheme", "slot", "market", "archive_sha256",
        "original_witness_sha256", "encrypted_sha256", "encrypted_bytes",
        "certificate_sha256", "created_at_utc", "nonce",
        "independent_timestamp_attested", "independent_market_pit_certified",
        "official_leader_promotions",
    }
    if (set(data) != required or data["schema_version"] != SCHEMA or
            data["scheme"] != SCHEME or data["slot"] != slot or
            data["market"] != slot[:2].upper() or
            any(type(data[k]) is not str or DIGEST.fullmatch(data[k]) is None for k in
                ("archive_sha256", "original_witness_sha256",
                 "encrypted_sha256", "certificate_sha256")) or
            type(data["encrypted_bytes"]) is not int or
            not 0 < data["encrypted_bytes"] <= MAX_CMS or
            type(data["nonce"]) is not str or
            re.fullmatch(r"[a-f0-9]{32}", data["nonce"]) is None or
            data["independent_timestamp_attested"] is not False or
            data["independent_market_pit_certified"] is not False or
            type(data["official_leader_promotions"]) is not int or
            data["official_leader_promotions"] != 0):
        raise ValueError("Corrupt immutable encrypted ZIP receipt")
    when = datetime.fromisoformat(data["created_at_utc"])
    if when.tzinfo is None or when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("Invalid backup local UTC clock")
    if (set(seal) != {"schema_version", "slot", "receipt_sha256", "nonce_sha256"} or
            seal["schema_version"] != GUARD_SCHEMA or seal["slot"] != slot or
            seal["receipt_sha256"] != _sha(raw) or
            seal["nonce_sha256"] != _sha(data["nonce"].encode())):
        raise ValueError("Original encrypted backup guard mismatch")
    actual, length = _file_sha(cipher, MAX_CMS)
    if actual != data["encrypted_sha256"] or length != data["encrypted_bytes"]:
        raise ValueError("Encrypted native vault ciphertext SHA mismatch")
    anchor = _external_first(witness_root, slot,
                             archive_sha=data["archive_sha256"],
                             expected_sha=data["original_witness_sha256"])
    if anchor["witness_sha256"] != data["original_witness_sha256"]:
        raise ValueError("Original independent first SHA witness no longer matches backup")
    # Historic ciphertext must NOT become unrecoverable at X509 expiration.
    # Pin identical certificate BYTES; OpenSSL CMS/GCM authenticates plaintext.
    if _cert(cert, require_current=False) != data["certificate_sha256"]:
        raise ValueError("Different encryption certificate from first backup")
    return data


def _result(data, status, *, created=False):
    return {
        "status": status, "market": data["market"], "slot": data["slot"],
        "archive_sha256": data["archive_sha256"],
        "encrypted_sha256": data["encrypted_sha256"],
        "ciphertext_verified": True,
        "authenticated_plaintext_verified": False,
        "first_backup_created": created,
        "independent_timestamp_attested": False,
        "independent_market_pit_certified": False,
        "real_future_leader_accuracy_certified": False,
        "official_leader_promotions": 0, "messages_sent": 0,
        "external_api_calls": 0,
    }


def backup_encrypted_native_original(
    project: Path, plan_file: Path, capture_root: Path, witness_root: Path,
    vault_root: Path, cert: Path, *, clock=None,
):
    """Copy already-verified first native ZIP as AES-GCM ciphertext, never raw."""
    now = _now(clock)
    project = Path(project).absolute()
    vault_root = validate_witness_destination(project, vault_root)
    witness_root = validate_witness_destination(project, witness_root)
    if (vault_root == witness_root or vault_root in witness_root.parents or
            witness_root in vault_root.parents):
        raise ValueError("Encrypted vault and first SHA witness roots must be distinct")
    cert_sha = _cert(cert, require_current=False)
    plan, _, _ = read_capture_plan(Path(plan_file))
    slot = _slot(plan)
    local = verify_native_sha_witness(project, plan_file, capture_root, witness_root, clock=now)
    if (local.get("status") != "SEPARATE_VOLUME_NATIVE_SHA_VERIFIED_NOT_ATTESTED" or
            local.get("source_archive_verified") is not True or
            local.get("separate_device_checked") is not True):
        raise ValueError("Cannot copy native source without original cross-volume SHA")
    expected_sha = local["archive_sha256"]
    root, cipher, first, guard, lock = _paths(vault_root, slot)
    if not any(p.exists() or p.is_symlink() for p in (cipher, first, guard, lock)):
        # New issuance must require a current certificate BEFORE first lock.
        _cert(cert, require_current=True)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    validate_witness_destination(project, root)
    previous_lock = lock.exists()
    artifacts = (cipher, first, guard)
    if any(path.exists() for path in artifacts) and not all(path.exists() for path in artifacts):
        raise ValueError("Partial encrypted first backup must not be reissued")
    if any(path.exists() for path in artifacts) and not previous_lock:
        raise ValueError("Missing immutable encrypted first backup lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "rb+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent encrypted first-native backup") from exc
        try:
            if all(path.is_file() for path in artifacts):
                existing = _verified_unlocked(cipher, first, guard, slot,
                                              witness_root, cert)
                if existing["archive_sha256"] != expected_sha:
                    raise ValueError("First original ZIP SHA changed after backup")
                return _result(existing, "EXISTING_ENCRYPTED_NATIVE_BACKUP_VERIFIED", created=False)
            if previous_lock or any(path.exists() for path in artifacts):
                raise ValueError("Missing or partially published encrypted original backup")
            source = project / "output" / "native_first_private_archives" / ("native_" + slot + ".zip")
            if _file_sha(source, MAX_ZIP)[0] != expected_sha:
                raise ValueError("Original private ZIP differs from witnessed first SHA")
            with TemporaryDirectory(prefix=".first-native-encrypt-", dir=root) as tmp:
                intermediate = Path(tmp) / "ciphertext.cms"
                _openssl(["-encrypt", "-aes-256-gcm", "-binary",
                          "-in", str(source), "-out", str(intermediate),
                          "-outform", "DER", "-recip", str(cert),
                          "-keyopt", "rsa_padding_mode:oaep"])
                ciphertext_sha, length = _file_sha(intermediate, MAX_CMS)
                if (_file_sha(source, MAX_ZIP)[0] != expected_sha or
                        verify_native_sha_witness(project, plan_file, capture_root,
                                                  witness_root, clock=now)["archive_sha256"]
                        != expected_sha):
                    raise ValueError("Source changed during encrypted archive copy")
                # Source/archive SHA must be locked to the ORIGINAL first witness.
                witness = _external_first(witness_root, slot, archive_sha=expected_sha)
                with open(intermediate, "rb") as inp:
                    fd_out = os.open(cipher, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                     getattr(os, "O_NOFOLLOW", 0), 0o600)
                    with os.fdopen(fd_out, "wb") as output:
                        shutil.copyfileobj(inp, output, 1024*1024)
                        output.flush()
                        os.fsync(output.fileno())
                if _file_sha(cipher, MAX_CMS) != (ciphertext_sha, length):
                    raise ValueError("Encrypted ciphertext changed during publication")
                stamp = {
                    "schema_version": SCHEMA, "scheme": SCHEME, "slot": slot,
                    "market": plan["market"], "archive_sha256": expected_sha,
                    "original_witness_sha256": witness["witness_sha256"],
                    "encrypted_sha256": ciphertext_sha, "encrypted_bytes": length,
                    "certificate_sha256": cert_sha, "created_at_utc": now.isoformat(),
                    "nonce": os.urandom(16).hex(),
                    "independent_timestamp_attested": False,
                    "independent_market_pit_certified": False,
                    "official_leader_promotions": 0,
                }
                raw = _bytes(stamp)
                seal = {"schema_version": GUARD_SCHEMA, "slot": slot,
                        "receipt_sha256": _sha(raw),
                        "nonce_sha256": _sha(stamp["nonce"].encode())}
                _new(first, raw)
                _new(guard, _bytes(seal))
            _verified_unlocked(cipher, first, guard, slot, witness_root, cert)
            return _result(stamp, "FIRST_ENCRYPTED_NATIVE_BACKUP_CREATED", created=True)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def verify_encrypted_native_original(vault_root, slot, witness_root, cert):
    """Read-only SHA and original first witness audit; no private key required."""
    data = _verified(vault_root, slot, witness_root, cert)
    return _result(data, "ENCRYPTED_NATIVE_BACKUP_SHA_VERIFIED_NOT_DECRYPTED")


def restore_encrypted_native_original(
    vault_root, slot, witness_root, cert, key, target, *, project=None,
):
    """Decrypt+AES-GCM authenticate+replay frozen WATCH at a NEW private path."""
    _private_key(key)
    root = _safe_private_root(Path(vault_root), must_exist=True)
    target = Path(target)
    if not target.is_absolute() or ".." in target.parts or target.exists() or target.is_symlink():
        raise FileExistsError("Encrypted recovery requires an absolute NEW destination")
    if target.parent.is_symlink():
        raise ValueError("Linked encrypted recovery destination")
    if project is not None:
        original = Path(project).absolute()
        if target == original or original in target.parents and (
                target.relative_to(original).parts[0] != "output"):
            raise ValueError("Never restore over original EraLeader project sources")
    # Both private-key and authenticated CMS correctness are checked BEFORE publishing.
    data = _verified(root, slot, witness_root, cert)
    cipher = root / ("native_" + slot + ".cms")
    # A new private directory is essential; no plaintext persists after failure.
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with TemporaryDirectory(prefix=".encrypted-native-recovery-", dir=target.parent) as temp:
        plain = Path(temp) / "original.zip"
        _openssl(["-decrypt", "-binary", "-inform", "DER",
                  "-in", str(cipher), "-out", str(plain),
                  "-recip", str(cert), "-inkey", str(key)])
        if _file_sha(plain, MAX_ZIP)[0] != data["archive_sha256"]:
            raise ValueError("Authenticated recovered archive contradicts first SHA")
        # The existing replay engine validates the original WATCH/score/features,
        # original census chain, label lock, and every ZIP inventory SHA.
        temporary_restore = Path(temp) / "replayed_original"
        result = restore_native_evidence_archive(
            plain, temporary_restore, expected_sha256=data["archive_sha256"], project=project)
        if result.get("messages_sent") != 0 or result.get("external_api_calls") != 0:
            raise RuntimeError("Restored original native evidence attempted delivery")
        if (_verified(root, slot, witness_root, cert)["encrypted_sha256"] !=
                data["encrypted_sha256"]):
            raise ValueError("Encrypted archive changed during recovery")
        if target.exists() or target.is_symlink():
            raise FileExistsError("Refusing to replace an existing recovery destination")
        os.rename(temporary_restore, target)
    return {
        "status": "ENCRYPTED_NATIVE_FIRST_ORIGINAL_RESTORED_NOT_PIT_CERTIFIED",
        "market": data["market"], "slot": slot,
        "archive_sha256": data["archive_sha256"],
        "authenticated_plaintext_verified": True,
        "first_original_watch_replayed": result.get("offline_original_score_provenance_verified") is True,
        "registered_index_chain_verified": result.get("registered_index_chain_verified") is True,
        "independent_timestamp_attested": False,
        "independent_market_pit_certified": False,
        "real_future_leader_accuracy_certified": False,
        "official_leader_promotions": 0, "messages_sent": 0, "external_api_calls": 0,
    }
