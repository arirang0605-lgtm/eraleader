"""6_5 opt-in portable *encrypted-only* first-native custody package.

Bundles only verified AES-256-GCM CMS ciphertext, first SHA witness,
immutable receipt/guards/locks, and original PUBLIC X509 certificate.
Never exports the private key, original plaintext ZIP, prices or issuers.

A portable bundle is NOT independently attested, nor necessarily offsite.
Verification/reconstruction REQUIRES an independently retained SHA256 pin.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo, ZIP_STORED, BadZipFile
import os
import re
import shutil
import stat

from .native_encrypted_vault import (
    SLOT, DIGEST, MAX_CMS, _file_sha, _verified, _cert, _paths,
)
from .native_encrypted_vault import _safe_private_root
from .native_sha_witness import validate_witness_destination, _witness_paths
from .native_evidence_archive import _bytes, _parse

SCHEMA = "eraleader.portable_encrypted_first_native_custody.v1"
MANIFEST = "COLD_CUSTODY_MANIFEST.json"
CERT_NAME = "public/original_recipient.crt"
MAX_SLOTS = 16
MAX_SMALL = 64 * 1024
MAX_PACKAGE = (MAX_CMS + 100_000) * MAX_SLOTS + 1_000_000
FILE_MODE = stat.S_IFREG | 0o600


def _hash(raw):
    return sha256(raw).hexdigest()


def _when(clock):
    at = datetime.now(timezone.utc) if clock is None else clock
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Portable backup requires aware local time")
    return at.astimezone(timezone.utc)


def _slot_names(slots):
    if type(slots) not in (list, tuple) or not 1 <= len(slots) <= MAX_SLOTS:
        raise ValueError("Portable encrypted custody requires 1..16 original slots")
    if any(type(slot) is not str or SLOT.fullmatch(slot) is None for slot in slots):
        raise ValueError("Only first-native KR/US hashed model slots may be carried")
    if len(set(slots)) != len(slots):
        raise ValueError("Duplicate encrypted custody model slot")
    return tuple(sorted(slots))


def _member_paths(slot):
    """Exactly seven non-secret members per immutable first-native slot."""
    return {
        f"vault/native_{slot}.cms": ("vault", f"native_{slot}.cms"),
        f"vault/native_{slot}_first.json": ("vault", f"native_{slot}_first.json"),
        f"vault/native_{slot}_guard.json": ("vault", f"native_{slot}_guard.json"),
        f"vault/.native_{slot}.lock": ("vault", f".native_{slot}.lock"),
        f"witness/native_{slot}_first.json": ("witness", f"native_{slot}_first.json"),
        f"witness/native_{slot}_guard.json": ("witness", f"native_{slot}_guard.json"),
        f"witness/.native_{slot}.lock": ("witness", f".native_{slot}.lock"),
    }


def _source_map(vault, witness, cert, slots):
    names = {CERT_NAME: Path(cert)}
    for slot in slots:
        for name,(folder,file) in _member_paths(slot).items():
            names[name] = (vault if folder == "vault" else witness) / file
    return names


def _safe_path(path, *, exists=None):
    raw = Path(path)
    if not raw.is_absolute() or ".." in raw.parts or len(raw.parts) < 4:
        raise ValueError("Absolute nontrivial portable storage location required")
    if any(item.is_symlink() for item in (raw, *raw.parents)):
        raise ValueError("Linked encrypted custody path")
    if exists is True and not raw.is_file():
        raise ValueError("Missing original portable custody package")
    if exists is False and raw.exists():
        raise FileExistsError("Portable original package/target may never be overwritten")
    return raw


def _nearest_existing(path):
    cursor = path
    while not cursor.exists():
        if cursor == cursor.parent:
            raise ValueError("Unable to determine portable output filesystem")
        cursor = cursor.parent
    return cursor


def _distinct_filesystems(project, vault, witness, target):
    device = _nearest_existing(target.parent).stat().st_dev
    original_devices = {project.stat().st_dev,
                        vault.stat().st_dev, witness.stat().st_dev}
    return device not in original_devices


def _file_digest(file, cap, *, allow_empty=False):
    file = _safe_path(file, exists=True)
    if not stat.S_ISREG(file.stat().st_mode):
        raise ValueError("Nonregular native encrypted custody source")
    if file.stat().st_size == 0 and allow_empty:
        return _hash(b""), 0
    return _file_sha(file, cap)


def _members_source(project, slots, vault, witness, cert):
    project = Path(project).absolute()
    vault = validate_witness_destination(project, Path(vault))
    witness = validate_witness_destination(project, Path(witness))
    vault = _safe_private_root(vault, must_exist=True)
    witness = _safe_private_root(witness, must_exist=True)
    if vault == witness or vault in witness.parents or witness in vault.parents:
        raise ValueError("Original first ZIP vault and witness must be independent paths")
    cert = _safe_path(Path(cert), exists=True)
    certificate_digest = _cert(cert, require_current=False)
    source = _source_map(vault, witness, cert, slots)
    seals = {}
    for slot in slots:
        checked = _verified(vault, slot, witness, cert)
        if checked.get("slot") != slot or checked.get("certificate_sha256") != certificate_digest:
            raise ValueError("Original first ciphertext/witness certificate pair not trusted")
        seals[slot] = {
            "market": checked["market"],
            "archive_sha256": checked["archive_sha256"],
            "cipher_sha256": checked["encrypted_sha256"],
            "witness_sha256": checked["original_witness_sha256"],
        }
    return project, vault, witness, cert, source, seals


def _info(name):
    info = ZipInfo(name, date_time=(1980,1,1,0,0,0))
    info.create_system = 3
    info.external_attr = FILE_MODE << 16
    info.compress_type = ZIP_STORED
    return info


def _transfer_member(writer, name, file, limit):
    digest = sha256()
    count = 0
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(file, flags)
    with os.fdopen(fd, "rb") as original:
        st = os.fstat(original.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError("Invalid/oversized custody source")
        with writer.open(_info(name), "w", force_zip64=True) as output:
            while True:
                block = original.read(1024*1024)
                if not block:
                    break
                count += len(block)
                if count > limit:
                    raise ValueError("Source grew past portable custody maximum")
                digest.update(block)
                output.write(block)
        if count != st.st_size:
            raise ValueError("Source altered during first ciphertext copy")
    return {"name": name, "bytes": count, "sha256": digest.hexdigest()}


def _validate_manifest(meta):
    if (type(meta) is not dict or set(meta) != {
            "schema", "created_at_local_utc", "slots", "members",
            "original_first_shas", "no_plaintext_or_private_key",
            "independent_timestamp_attested", "offsite_geography_attested",
        } or meta["schema"] != SCHEMA or
            meta["no_plaintext_or_private_key"] is not True or
            meta["independent_timestamp_attested"] is not False or
            meta["offsite_geography_attested"] is not False):
        raise ValueError("Forged portable native encrypted custody manifest")
    if type(meta["created_at_local_utc"]) is not str:
        raise ValueError("Invalid local creation time of portable custody")
    dt = datetime.fromisoformat(meta["created_at_local_utc"])
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("Invalid local creation time of portable custody")
    slots = _slot_names(meta["slots"])
    if list(slots) != meta["slots"]:
        raise ValueError("Portable encrypted custody slots must be strictly ordered")
    expected = {CERT_NAME}
    for slot in slots:
        expected |= set(_member_paths(slot))
    members = meta["members"]
    if (type(members) is not list or len(members) != len(expected) or
            any(type(x) is not dict or set(x) != {"name","bytes","sha256"} or
                type(x["name"]) is not str for x in members)):
        raise ValueError("Duplicate or incomplete cold-custody members")
    names = [x["name"] for x in members]
    if len(set(names)) != len(names) or set(names) != expected:
        raise ValueError("Unexpected/duplicate first native portable custody member")
    if names != sorted(expected):
        raise ValueError("Noncanonical portable custody file ordering")
    for item in members:
        if (type(item) is not dict or set(item) != {"name","bytes","sha256"} or
                type(item["bytes"]) is not int or item["bytes"] < 0 or
                item["bytes"] > (MAX_CMS if item["name"].endswith(".cms") else MAX_SMALL) or
                type(item["sha256"]) is not str or
                DIGEST.fullmatch(item["sha256"]) is None):
            raise ValueError("Invalid portable member SHA or length")
    pins = meta["original_first_shas"]
    if type(pins) is not dict or set(pins) != set(slots):
        raise ValueError("Incomplete portable native first ZIP SHA pins")
    for slot,value in pins.items():
        if (type(value) is not dict or set(value) != {
                "market","archive_sha256","cipher_sha256","witness_sha256"} or
                value["market"] != slot[:2].upper() or
                any(type(value[k]) is not str or DIGEST.fullmatch(value[k]) is None
                    for k in ("archive_sha256","cipher_sha256","witness_sha256"))):
            raise ValueError("Invalid pinned original first native encrypted proof")
    return slots, members, pins


def _extract_and_check(archive, expected_sha, destination):
    """Verify bundle SHA pin and every member; replay original SHA-only verifiers."""
    actual, _ = _file_sha(archive, MAX_PACKAGE)
    if actual != expected_sha:
        raise ValueError("Portable ciphertext archive differs from independently supplied SHA PIN")
    try:
        with ZipFile(archive, "r") as zipped:
            info = zipped.infolist()
            if not 3 <= len(info) <= MAX_SLOTS*7+2 or (
                    len({i.filename for i in info}) != len(info)):
                raise ValueError("Duplicate or excessive custody ZIP members")
            if any(i.filename == MANIFEST for i in info) is False:
                raise ValueError("Missing original portable SHA manifest")
            manifest_entry = zipped.getinfo(MANIFEST)
            if manifest_entry.file_size > 65_536:
                raise ValueError("Oversized portable custody evidence manifest")
            raw = zipped.read(MANIFEST)
            meta = _parse(raw)
            if _bytes(meta) != raw:
                raise ValueError("Rewritten/noncanonical portable custody manifest")
            slots, items, pins = _validate_manifest(meta)
            if {i.filename for i in info} != {MANIFEST,*[x["name"] for x in items]}:
                raise ValueError("Extra untrusted file in encrypted custody archive")
            declared = {x["name"]: x for x in items}
            destination.mkdir(mode=0o700, exist_ok=False)
            for member in info:
                if (member.compress_type != ZIP_STORED or member.flag_bits & 1 or
                        (member.external_attr >> 16 & 0o170000) != stat.S_IFREG):
                    raise ValueError("Unsafe/nonregular ciphertext member in portable archive")
                if member.filename == MANIFEST:
                    continue
                name = member.filename
                item = declared[name]
                if (member.file_size != item["bytes"] or
                        member.compress_size != item["bytes"]):
                    raise ValueError("Portable encrypted evidence ZIP member length spoof")
                path = destination.joinpath(*name.split("/"))
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
                digest = sha256()
                count = 0
                with os.fdopen(fd, "wb") as sink, zipped.open(member, "r") as original:
                    while True:
                        part = original.read(1024*1024)
                        if not part:
                            break
                        count += len(part)
                        if count > item["bytes"]:
                            raise ValueError("Oversized ciphertext extracted from portable custody")
                        sink.write(part)
                        digest.update(part)
                    sink.flush()
                    os.fsync(sink.fileno())
                if count != item["bytes"] or digest.hexdigest() != item["sha256"]:
                    raise ValueError("Portable custody member SHA mismatch")
            # Preserve the exact manifest in reconstructed archive for audit.
            fd = os.open(destination/MANIFEST,
                         os.O_CREAT|os.O_EXCL|os.O_WRONLY|
                         getattr(os,"O_NOFOLLOW",0), 0o600)
            with os.fdopen(fd,"wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            cert = destination/CERT_NAME
            for slot in slots:
                verified = _verified(destination/"vault", slot, destination/"witness", cert)
                pin = pins[slot]
                if (verified["archive_sha256"] != pin["archive_sha256"] or
                        verified["encrypted_sha256"] != pin["cipher_sha256"] or
                        verified["original_witness_sha256"] != pin["witness_sha256"]):
                    raise ValueError("Portable encrypted bundle contradicts initial witness SHA")
            if _file_sha(archive, MAX_PACKAGE)[0] != expected_sha:
                raise ValueError("Portable archive changed during integrity proof")
            return len(slots), len(items), pins
    except BadZipFile as exc:
        raise ValueError("Malformed encrypted-only custody package") from exc


def create_portable_native_custody(project, slots, vault_root, witness_root,
                                   cert, destination, *, allow_colocated_research=False,
                                   clock=None):
    """First encrypted-only portable archive. O_EXCL; never overwrite originals.

    Default only permits a THIRD distinct filesystem (st_dev); the explicit
    colocated flag is solely for local synthetic research/trial packages.
    Even distinct filesystems are NOT proof of geographic/offsite separation.
    """
    slots = _slot_names(slots)
    p,v,w,c,files,seals = _members_source(
        project, slots, vault_root, witness_root, cert)
    target = _safe_path(destination, exists=False)
    if (p == target or p in target.parents or v == target or v in target.parents or
            w == target or w in target.parents):
        raise ValueError("Cold encrypted original backup must not go inside its source roots")
    parent = _safe_private_root(target.parent, must_exist=True)
    isolated = _distinct_filesystems(p,v,w,target)
    if not isolated and allow_colocated_research is not True:
        raise ValueError("Independent THIRD filesystem required for production cold custody")
    if type(allow_colocated_research) is not bool:
        raise ValueError("Research-only storage fallback must be explicitly boolean")
    with TemporaryDirectory(prefix=".encrypted-only-custody-", dir=parent) as temp:
        candidate = Path(temp)/"candidate.zip"
        entries = []
        with ZipFile(candidate,"x",compression=ZIP_STORED,allowZip64=True) as zipped:
            for name in sorted(files):
                cap = MAX_CMS if name.endswith(".cms") else MAX_SMALL
                entries.append(_transfer_member(zipped,name,files[name],cap))
            meta = {
                "schema": SCHEMA,
                "created_at_local_utc": _when(clock).isoformat(),
                "slots": list(slots),
                "members": entries,
                "original_first_shas": seals,
                "no_plaintext_or_private_key": True,
                "independent_timestamp_attested": False,
                "offsite_geography_attested": False,
            }
            zipped.writestr(_info(MANIFEST),_bytes(meta))
        sha, length = _file_sha(candidate, MAX_PACKAGE)
        scratch = Path(temp)/"selfcheck"
        _extract_and_check(candidate,sha,scratch)
        # Source must remain byte-for-byte equal after packaging (TOCTOU).
        for name,file in files.items():
            expected = next(x for x in entries if x["name"] == name)
            digest, size = _file_digest(
                file, MAX_CMS if name.endswith(".cms") else MAX_SMALL,
                allow_empty=name.endswith(".lock"))
            if (digest, size) != (expected["sha256"], expected["bytes"]):
                raise ValueError("Original first encrypted ciphertext changed during custody export")
        for slot in slots:
            if _verified(v,slot,w,c)["encrypted_sha256"] != seals[slot]["cipher_sha256"]:
                raise ValueError("Original first SHA changed while portable bundle was staged")
        fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                     getattr(os,"O_NOFOLLOW",0), 0o600)
        with os.fdopen(fd,"wb") as output, open(candidate,"rb") as source:
            shutil.copyfileobj(source,output,1024*1024)
            output.flush()
            os.fsync(output.fileno())
        if _file_sha(target,MAX_PACKAGE) != (sha,length):
            raise ValueError("Published cold backup differs from audited original ZIP")
    return {
        "status": "PORTABLE_ENCRYPTED_NATIVE_CUSTODY_CREATED_NOT_OFFSITE_ATTESTED",
        "package_sha256": sha, "slots": list(slots), "slot_count": len(slots),
        "file_count": len(entries),
        "third_filesystem_st_dev_distinct": isolated,
        "offsite_geography_attested": False,
        "separate_package_sha_pin_required_for_recovery": True,
        "plaintext_or_private_key_included": False,
        "original_source_changed": False,
        "actual_future_leader_skill_certified": False,
        "independent_market_pit_certified": False,
        "official_leader_promotions": 0, "messages_sent":0,"external_api_calls":0,
    }


def check_portable_native_custody(archive, expected_sha256, *, restore_target=None):
    """SHA-pinned read-only verification or NEW encrypted-only reconstruction."""
    if type(expected_sha256) is not str or DIGEST.fullmatch(expected_sha256) is None:
        raise ValueError("Portable custody verification REQUIRES original separately kept SHA256")
    archive = _safe_path(archive, exists=True)
    if restore_target is not None:
        final = _safe_path(restore_target, exists=False)
        if archive == final or final in archive.parents or archive in final.parents:
            raise ValueError("Portable custody recovery cannot overlap source archive")
        private_parent = _safe_private_root(final.parent, must_exist=True)
    else:
        final = None
        private_parent = None
    if final is None:
        with TemporaryDirectory(prefix=".verify-cold-native-ciphertext-") as tmp:
            # macOS can expose /var as a symlink to /private/var. Resolve the
            # private temporary root before invoking the strict no-link verifier.
            scratch = Path(tmp).resolve(strict=True)
            count,files,_ = _extract_and_check(
                archive,expected_sha256,scratch/"extracted")
    else:
        with TemporaryDirectory(prefix=".restore-cold-native-ciphertext-",dir=private_parent) as tmp:
            root = Path(tmp)/"extracted"
            count,files,_ = _extract_and_check(archive,expected_sha256,root)
            if final.exists() or final.is_symlink():
                raise FileExistsError("Cold first native package recovery target was claimed")
            os.rename(root,final)
    return {
        "status": ("PORTABLE_ENCRYPTED_NATIVE_CUSTODY_RESTORED_NOT_DECRYPTED"
                   if final is not None else
                   "PORTABLE_ENCRYPTED_NATIVE_CUSTODY_SHA_VERIFIED_NOT_DECRYPTED"),
        "package_sha256": expected_sha256,
        "slot_count": count,
        "file_count": files,
        "ciphertext_and_first_witness_verified": True,
        "plaintext_authenticated_or_replayed": False,
        "offsite_geography_attested": False,
        "private_key_accessed": False,
        "real_future_leader_accuracy_certified": False,
        "independent_market_pit_certified": False,
        "official_leader_promotions": 0, "messages_sent":0,"external_api_calls":0,
    }
