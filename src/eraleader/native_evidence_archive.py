"""5_5 private, read-only first-WATCH/native Top-K complete-source evidence vault.

Archives EXACT original plan/first-WATCH/score/features/label and sealed
capture+census receipts. A restore is into a new directory only; sources are
re-audited offline from the restored copy without rewriting original paths.
Neither local clocks nor original self-hashes certify issuer PIT or future alpha.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
import fcntl
import json
import os
import re
import sqlite3
import stat

from .native_first_capture import (
    read_capture_plan, _inspect_complete,
    CAPTURE_NAME, FROZEN_NAME, RULE_NAME, SOURCE_NAME, SPEC_NAME,
)
from .ranked_maturity import audit_ranked_maturity
from .ranked_discovery import _frozen, _time
from .prospective_census import _read as read_census
from .prospective_census_seal import _index_path, _verified_index

SCHEMA="eraleader.native_original_evidence_archive.v1"
MANIFEST="VAULT_MANIFEST.json"
ZIP_MAX_BYTES=250*1024*1024
MAX_FILE=48*1024*1024
MAX_TOTAL=180*1024*1024
MAX_FILES=1030
SHA=re.compile(r"[a-f0-9]{64}\Z")
FEATURE=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.json\Z")
SOURCES={
    "original/plan.json","original/watch.sqlite","original/score.sqlite",
    "original/label.json","capture/capture_receipt.json",
    "capture/evidence/"+FROZEN_NAME,
    "capture/evidence/"+RULE_NAME,
    "capture/evidence/"+SOURCE_NAME,
    "capture/evidence/"+SPEC_NAME,
    "capture/registered_receipt_index.sqlite",
    "capture/registered_native_required.json",
    "capture/first_write.lock",
}


def _slot(plan:dict)->str:
    """Same immutable model slot as native_first_capture, no unstaged dependency."""
    return plan["market"].lower()+"_"+_hash(plan["model_version"].encode())[:24]


def _bytes(value:object)->bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def _hash(value:bytes)->str:
    return sha256(value).hexdigest()


def _unique(pairs):
    result={}
    for key,val in pairs:
        if key in result:
            raise ValueError("Duplicate native source archive JSON key")
        result[key]=val
    return result


def _parse(blob:bytes):
    try:
        return json.loads(blob,object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Corrupt native source archive JSON") from exc


def _safe_file(path:Path,max_size=MAX_FILE)->None:
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked original native source evidence")
    if not 0<=path.stat().st_size<=max_size:
        raise ValueError("Oversized original native source evidence")


def _private_path(project:Path,path:Path)->Path:
    """Originals must never be archived into a public Git tracked folder."""
    path=Path(path).absolute()
    project=Path(project).absolute()
    if ".." in path.parts or any(parent.is_symlink() for parent in (path,*path.parents)):
        raise ValueError("Unsafe private archive/restore path")
    if path==project or project in path.parents:
        relative=path.relative_to(project)
        if not relative.parts or relative.parts[0]!="output":
            raise ValueError("Private original market evidence must stay in ignored output")
    return path


def _relative_ok(name:str)->bool:
    if type(name) is not str or len(name)>200 or "\\" in name or not name:
        return False
    p=PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or p.as_posix()!=name:
        return False
    if name in SOURCES:
        return True
    if len(p.parts)==2 and p.parts[0]=="features":
        return bool(FEATURE.fullmatch(p.parts[1]))
    if len(p.parts)==3 and p.parts[:2]==("capture","registered"):
        return bool(re.fullmatch(r"census_[A-Za-z0-9_-]{1,58}\.json",p.parts[2]))
    return False


def _sqlite_file(file:Path)->None:
    _safe_file(file)
    for suffix in ("-wal","-journal","-shm"):
        sidecar=Path(str(file)+suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise ValueError("Active SQLite sidecar requires independent consistent snapshot before private archive")
    try:
        with closing(sqlite3.connect(file.as_uri()+"?mode=ro",uri=True)) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("Damaged first-native SQLite original")
            pages=db.execute("PRAGMA page_count").fetchone()[0]
            size=db.execute("PRAGMA page_size").fetchone()[0]
            if (type(pages) is not int or type(size) is not int or
                    pages<=0 or size<=0 or file.stat().st_size!=pages*size):
                raise ValueError("Original native SQLite has appended/hidden unsealed bytes")
    except sqlite3.DatabaseError as exc:
        raise ValueError("Unreadable original native SQLite source") from exc


def _original_inventory(plan_file:Path,capture_root:Path,plan:dict,sources:dict)->dict[str,Path]:
    cohort=capture_root/("native_"+_slot(plan))
    receipt=cohort/CAPTURE_NAME
    evidence=cohort/"evidence"
    reg=cohort/"registered"
    sentinel=capture_root/(".capture_"+_slot(plan)+".lock")
    name="census_"+plan["cohort_id"]+".json"
    files={
        "original/plan.json":plan_file,
        "original/watch.sqlite":sources["watch_ledger"],
        "original/score.sqlite":sources["score_ledger"],
        "original/label.json":sources["label_definition_file"],
        "capture/capture_receipt.json":receipt,
        "capture/evidence/"+FROZEN_NAME:evidence/FROZEN_NAME,
        "capture/evidence/"+RULE_NAME:evidence/RULE_NAME,
        "capture/evidence/"+SOURCE_NAME:evidence/SOURCE_NAME,
        "capture/evidence/"+SPEC_NAME:evidence/SPEC_NAME,
        "capture/registered/"+name:reg/name,
        "capture/registered_receipt_index.sqlite":_index_path(reg),
        "capture/registered_native_required.json":cohort/"registered_native_required.json",
        "capture/first_write.lock":sentinel,
    }
    directory=sources["features_dir"]
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Unsafe original native feature directory")
    for feature in sorted(directory.iterdir()):
        if not FEATURE.fullmatch(feature.name) or not feature.is_file() or feature.is_symlink():
            raise ValueError("Unsafe or unexpected first-native feature evidence")
        files["features/"+feature.name]=feature
    if not 1<=len(files)-13<=1000:
        raise ValueError("Missing or oversized original native feature cohort")
    if len(files)>MAX_FILES or any(not _relative_ok(name) for name in files):
        raise ValueError("Unsafe native original file inventory")
    # The capture writer uses one exact canonical JSON encoding. SQLite
    # quick_check and normal JSON parsing ignore arbitrary trailing bytes;
    # the first receipt must therefore also match its original byte shape.
    original=receipt.read_bytes()
    canonical=(json.dumps(_parse(original),sort_keys=True,ensure_ascii=False,
                          indent=2,allow_nan=False)+"\n").encode("utf-8")
    if original!=canonical:
        raise ValueError("Reformatted or appended original first-capture receipt bytes")
    for name,file in files.items():
        _safe_file(file)
        if name.endswith(".sqlite"):
            _sqlite_file(file)
    return files


def _check_metadata(meta:object,names:set[str])->list[dict]:
    if (type(meta) is not dict or
            set(meta)!={"schema_version","market","model_version_sha256",
                        "plan_sha256","capture_receipt_sha256",
                        "original_capture_root","files","file_count","total_bytes",
                        "local_research_only"} or
            meta["schema_version"]!=SCHEMA or meta["market"] not in ("KR","US") or
            meta["local_research_only"] is not True):
        raise ValueError("Invalid native first-source archive schema")
    for key in ("model_version_sha256","plan_sha256","capture_receipt_sha256"):
        if type(meta[key]) is not str or not SHA.fullmatch(meta[key]):
            raise ValueError("Invalid original native SHA declaration")
    root=meta["original_capture_root"]
    if type(root) is not str or not 0<len(root)<4096 or not Path(root).is_absolute():
        raise ValueError("Invalid original first-capture root declaration")
    files=meta["files"]
    if (type(files) is not list or not 14<=len(files)<=MAX_FILES or
            type(meta["file_count"]) is not int or meta["file_count"]!=len(files) or
            type(meta["total_bytes"]) is not int or
            not 0<meta["total_bytes"]<=MAX_TOTAL):
        raise ValueError("Invalid original native archive file inventory")
    expected=set()
    total=0
    for item in files:
        if (type(item) is not dict or
                set(item)!={"name","original_path","bytes","sha256"}):
            raise ValueError("Malformed original native evidence manifest entry")
        name=item["name"]
        source=item["original_path"]
        length=item["bytes"]
        digest=item["sha256"]
        if (not _relative_ok(name) or name in expected or
                type(source) is not str or not 0<len(source)<=4096 or
                not Path(source).is_absolute() or ".." in Path(source).parts or
                type(length) is not int or not 0<=length<=MAX_FILE or
                type(digest) is not str or not SHA.fullmatch(digest)):
            raise ValueError("Unsafe or duplicated native original archive member")
        expected.add(name)
        total+=length
    if (not SOURCES.issubset(expected) or
            len([x for x in expected if x.startswith("features/")])==0 or
            len([x for x in expected if x.startswith("capture/registered/")])!=1 or
            expected!=names or total!=meta["total_bytes"] or total>MAX_TOTAL):
        raise ValueError("Native original archive omits required source or invents a member")
    return files


def _identity(meta:dict,blobs:dict[str,bytes])->None:
    """Cross-bind first original plan, source paths, frozen receipt and census."""
    entries={row["name"]:row for row in meta["files"]}
    plan=_parse(blobs["original/plan.json"])
    receipt=_parse(blobs["capture/capture_receipt.json"])
    native=_parse(blobs["capture/evidence/"+SOURCE_NAME])
    frozen=_parse(blobs["capture/evidence/"+FROZEN_NAME])
    rules=blobs["capture/evidence/"+RULE_NAME]
    registered=next(x for x in blobs if x.startswith("capture/registered/"))
    census=_parse(blobs[registered])
    if (type(plan) is not dict or type(receipt) is not dict or
            type(frozen) is not dict or type(census) is not dict or
            type(native) is not dict):
        raise ValueError("Malformed original native first-write source relationships")
    if (meta["plan_sha256"]!=_hash(blobs["original/plan.json"]) or
            meta["capture_receipt_sha256"]!=_hash(blobs["capture/capture_receipt.json"]) or
            plan.get("market")!=meta["market"] or
            _hash(plan.get("model_version","").encode())!=meta["model_version_sha256"] or
            receipt.get("plan_sha256")!=meta["plan_sha256"] or
            receipt.get("market")!=meta["market"] or
            receipt.get("model_version")!=plan.get("model_version") or
            receipt.get("label_file_sha256")!=_hash(blobs["original/label.json"]) or
            rules!=blobs["original/label.json"] or
            receipt.get("frozen_file_sha256")!=_hash(blobs["capture/evidence/"+FROZEN_NAME]) or
            receipt.get("census_manifest_sha256")!=_hash(blobs[registered]) or
            receipt.get("census_index_bytes_sha256")!=_hash(
                blobs["capture/registered_receipt_index.sqlite"]) or
            receipt.get("native_source_proofs_sha256")!=_hash(
                blobs["capture/evidence/"+SOURCE_NAME]) or
            receipt.get("official_leader_promotions")!=0 or
            receipt.get("first_write_pit_independently_verified") is not False or
            receipt.get("real_future_leader_accuracy_certified") is not False or
            frozen.get("requested_k")!=plan.get("top_k") or
            frozen.get("label_definition_sha256")!=receipt.get("label_file_sha256") or
            frozen.get("retrospective_freeze") is not False):
        raise ValueError("Revised first-native original receipt/plan/frozen evidence")
    for key,name in (("watch_ledger","original/watch.sqlite"),
                     ("score_ledger","original/score.sqlite"),
                     ("label_definition_file","original/label.json")):
        if entries[name]["original_path"]!=plan.get(key):
            raise ValueError("Original local WATCH/score/label source path substituted")
    for entry in (row for row in meta["files"] if row["name"].startswith("features/")):
        if str(Path(entry["original_path"]).parent)!=plan.get("features_dir"):
            raise ValueError("Original native feature source directory substituted")
        if Path(entry["original_path"]).name!=entry["name"].split("/",1)[1]:
            raise ValueError("Renamed original native feature first-write")
    cohort=Path(meta["original_capture_root"])/("native_"+_slot(plan))
    expected_native=[{
        "frozen_sha256":receipt["frozen_file_sha256"],
        "watch_ledger":plan["watch_ledger"],
        "score_ledger":plan["score_ledger"],
        "features_dir":plan["features_dir"],
    }]
    if (native.get("cohorts")!=expected_native or
            census.get("source_dir")!=str(cohort/"evidence") or
            registered!="capture/registered/census_"+plan.get("cohort_id","")+".json" or
            receipt.get("original_selected_top_k")!=plan.get("top_k") or
            receipt.get("original_outcome_unknown")!=plan.get("top_k")):
        raise ValueError("First native cohort source registry/denominator inconsistent")
    if entries["capture/first_write.lock"]["original_path"]!=str(
            Path(meta["original_capture_root"])/(".capture_"+_slot(plan)+".lock")):
        raise ValueError("Replaced original first-write capture sentinel")


def verify_native_evidence_archive(archive:Path,*,expected_sha256:str|None=None)->dict:
    """SHA-verify every private member and cross-bind original plan+receipts."""
    file=Path(archive)
    _safe_file(file,ZIP_MAX_BYTES)
    original_sha=_hash(file.read_bytes())
    if expected_sha256 is not None and (
            type(expected_sha256) is not str or not SHA.fullmatch(expected_sha256) or
            original_sha!=expected_sha256):
        raise ValueError("Native original archive SHA-256 anchor mismatch")
    try:
        with ZipFile(file,"r") as reader:
            info=reader.infolist()
            names=[item.filename for item in info]
            if (len(names)!=len(set(names)) or names.count(MANIFEST)!=1 or
                    not 0<len(info)<=MAX_FILES+1):
                raise ValueError("Missing/duplicate native archive manifest")
            for member in info:
                unix_mode=(member.external_attr>>16)&0xffff
                if (member.is_dir() or
                        stat.S_IFMT(unix_mode)==stat.S_IFLNK or
                        member.flag_bits&0x1 or
                        member.file_size>MAX_FILE):
                    raise ValueError("Linked, encrypted or oversized private source member")
            manifest_raw=reader.read(MANIFEST)
            if len(manifest_raw)>256_000:
                raise ValueError("Oversized native archive manifest")
            manifest=_parse(manifest_raw)
            if manifest_raw!=_bytes(manifest):
                raise ValueError("Reformatted original source manifest")
            selected=_check_metadata(manifest,set(names)-{MANIFEST})
            blobs={}
            for item in selected:
                payload=reader.read(item["name"])
                if len(payload)!=item["bytes"] or _hash(payload)!=item["sha256"]:
                    raise ValueError("Native original source archive member SHA mismatch")
                blobs[item["name"]]=payload
            _identity(manifest,blobs)
    except (OSError,RuntimeError,BadZipFile,KeyError,TypeError,AttributeError,IndexError) as exc:
        raise ValueError("Unreadable/invalid native original archive contents") from exc
    return {
        "status":"PRIVATE_NATIVE_EVIDENCE_ARCHIVE_VERIFIED",
        "archive_sha256":original_sha,
        "file_count":manifest["file_count"],
        "source_input_bytes":manifest["total_bytes"],
        "market":manifest["market"],
        "sealed_source_relationships_verified":True,
        "independent_market_pit_certified":False,
        "real_future_leader_accuracy_certified":False,
        "official_leader_promotions":0,
        "messages_sent":0,"external_api_calls":0,
    }


def create_native_evidence_archive(
    plan_file:Path,capture_root:Path,archive:Path,*,project:Path,
    clock:datetime|None=None,
)->dict:
    """Capture exact original inputs after a complete existing native census.

    Read-only source; all raw bytes remain PRIVATE. Never create a missing
    prediction/census or retroactively register an incomplete cohort.
    """
    now=clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Archive requires aware original research audit clock")
    now=now.astimezone(timezone.utc)
    project=Path(project).absolute()
    plan_file=Path(plan_file).absolute()
    capture_root=Path(capture_root).absolute()
    archive=_private_path(project,archive)
    if (archive.exists() or archive.is_symlink() or
            capture_root.is_symlink() or capture_root.parent.is_symlink() or
            not capture_root.is_dir()):
        raise ValueError("Unsafe or previously published private native archive/capture root")
    plan,plan_sha,sources=read_capture_plan(plan_file)
    slot=_slot(plan)
    capture=capture_root/("native_"+slot)
    lock=capture_root/(".capture_"+slot+".lock")
    if lock.is_symlink() or not lock.is_file() or capture.is_symlink() or not capture.is_dir():
        raise ValueError("Absent original first-native capture or first-write sentinel")
    # The uncommitted source module is never modified. Hold the SAME lock as
    # the original first-score capture while the archive reads its evidence.
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent first-native freeze/registry writer") from exc
        try:
            verified=_inspect_complete(capture,plan,plan_sha,sources,now)
            if (verified.get("status")!="ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY" or
                    verified.get("native_watch_score_provenance_rechecked") is not True or
                    verified.get("official_leader_promotions")!=0):
                raise ValueError("Only an already verified prospective first-native cohort can be archived")
            inventory=_original_inventory(plan_file,capture_root,plan,sources)
            if archive in inventory.values() or archive.parent==sources["features_dir"]:
                raise ValueError("Private archive cannot overwrite original native evidence")
            catalog=[]
            total=0
            for name,file in sorted(inventory.items()):
                body=file.read_bytes()
                length=len(body)
                total+=length
                if total>MAX_TOTAL or length>MAX_FILE:
                    raise ValueError("Private original native archive size exceeded")
                catalog.append({"name":name,"original_path":str(file),
                                "bytes":length,"sha256":_hash(body)})
            manifest={
                "schema_version":SCHEMA,
                "market":plan["market"],
                "model_version_sha256":_hash(plan["model_version"].encode()),
                "plan_sha256":plan_sha,
                "capture_receipt_sha256":_hash((capture/CAPTURE_NAME).read_bytes()),
                "original_capture_root":str(capture_root),
                "files":catalog,"file_count":len(catalog),
                "total_bytes":total,"local_research_only":True,
            }
            archive.parent.mkdir(parents=True,exist_ok=True)
            with TemporaryDirectory(dir=archive.parent,prefix=".native-private-snapshot-") as staging:
                tmp=Path(staging)/"archive.zip"
                tmp.touch(mode=0o600,exist_ok=False)
                os.chmod(tmp,0o600)
                with ZipFile(tmp,"w",ZIP_DEFLATED,compresslevel=6,allowZip64=False) as writer:
                    for item in catalog:
                        original=inventory[item["name"]]
                        body=original.read_bytes()
                        if len(body)!=item["bytes"] or _hash(body)!=item["sha256"]:
                            raise ValueError("Original native evidence changed during private archive")
                        writer.writestr(item["name"],body)
                    writer.writestr(MANIFEST,_bytes(manifest))
                verified_archive=verify_native_evidence_archive(tmp)
                if verified_archive["file_count"]!=len(catalog):
                    raise ValueError("Private native original ZIP verification inconsistent")
                # Detect TOCTOU modifications during serialization, including
                # later source writes and changes to the first registry/index.
                for item in catalog:
                    original=inventory[item["name"]]
                    _safe_file(original)
                    if original.suffix==".sqlite":
                        _sqlite_file(original)
                    if (original.stat().st_size!=item["bytes"] or
                            _hash(original.read_bytes())!=item["sha256"]):
                        raise ValueError("Original native evidence SHA changed after archive snapshot")
                again=_inspect_complete(capture,plan,plan_sha,sources,now)
                if again!=verified:
                    raise ValueError("First-native capture provenance changed during archive")
                # T5DATA may be exFAT: hard links are unsupported. Publish
                # only to O_EXCL brand-new bytes, never overwrite a historical
                # backup. Interrupted copies remain visibly incomplete and
                # MUST fail verification, not be silently recreated.
                source_sha=_hash(tmp.read_bytes())
                fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                           getattr(os,"O_NOFOLLOW",0),0o600)
                with os.fdopen(fd,"wb") as destination, open(tmp,"rb") as original:
                    while True:
                        part=original.read(1024*1024)
                        if not part:
                            break
                        destination.write(part)
                    destination.flush()
                    os.fsync(destination.fileno())
                archive_sha=_hash(archive.read_bytes())
                if archive_sha!=source_sha:
                    raise ValueError("Published private evidence ZIP SHA differs from verified snapshot")
                verify_native_evidence_archive(archive,expected_sha256=archive_sha)
            return {
                "status":"PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_PIT_CERTIFIED",
                "archive_sha256":archive_sha,
                "file_count":len(catalog),"source_input_bytes":total,
                "market":plan["market"],"source_bytes_unchanged":True,
                "offline_first_watch_score_provenance_rechecked":True,
                "real_future_leader_accuracy_certified":False,
                "official_leader_promotions":0,
                "messages_sent":0,"external_api_calls":0,
            }
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def _replay_restored(root:Path,meta:dict)->dict:
    """Independent offline replay of exact frozen WATCH, scores and features.

    The old census manifest preserves ABSOLUTE first-write source paths and
    cannot be silently rebound as an entirely new prospective prediction.
    Therefore this validates its copy's first receipts/index while replaying
    numeric provenance against the restored source copies explicitly.
    """
    catalog={item["name"]:item for item in meta["files"]}
    expected=set(catalog)|{MANIFEST}
    present={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if expected!=present:
        raise ValueError("Restored original-native evidence differs from sealed inventory")
    for item in meta["files"]:
        file=root/item["name"]
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or linked restored original native member")
        if file.stat().st_size!=item["bytes"] or _hash(file.read_bytes())!=item["sha256"]:
            raise ValueError("Restored original first-write member SHA mismatch")
        if file.suffix==".sqlite":
            _sqlite_file(file)
    frozen=root/"capture"/"evidence"/FROZEN_NAME
    label=root/"original"/"label.json"
    watch=root/"original"/"watch.sqlite"
    score=root/"original"/"score.sqlite"
    features=root/"features"
    receipt=read_census(root/"capture"/"capture_receipt.json")
    captured_at=_time(receipt["captured_at_utc"])
    ranked=_frozen(frozen)
    if ranked["market"]!=meta["market"] or ranked["retrospective_freeze"] is not False:
        raise ValueError("Replaced restored prospective native frozen cohort")
    local=audit_ranked_maturity(
        frozen,label,score,watch,features,
        as_of=captured_at.isoformat(),clock=captured_at,sample_limit=1,
    )
    if (local.get("local_native_provenance_rechecked") is not True or
            local.get("prospective_maturity_eligible") is not True or
            local.get("outcome_labels_read") is not False or
            local.get("actual_future_leader_skill_certified") is not False or
            local.get("frozen_first_score_count")!=receipt["original_positive_watch_count"] or
            local.get("selected_top_k_count")!=receipt["original_selected_top_k"]):
        raise ValueError("Offline restored native WATCH/score/feature replay failed")
    registry=root/"capture"/"registered"
    index=root/"capture"/"registered_receipt_index.sqlite"
    with closing(sqlite3.connect(index.as_uri()+"?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        validation=_verified_index(db,registry)
    if (validation.get("count")!=1 or
            validation.get("head")!=receipt["census_index_head_sha256"]):
        raise ValueError("Restored native first census receipt/index chain mismatch")
    return {
        "offline_original_score_provenance_verified":True,
        "registered_index_chain_verified":True,
        "original_selected_top_k":receipt["original_selected_top_k"],
    }


def restore_native_evidence_archive(
    archive:Path,target:Path,*,expected_sha256:str|None=None,project:Path|None=None,
)->dict:
    """Restore RAW private files only into a new path, never original ledgers."""
    if expected_sha256 is None:
        raise ValueError("Restoring first-native original bytes requires separately pinned archive SHA-256")
    result=verify_native_evidence_archive(archive,expected_sha256=expected_sha256)
    target=Path(target).absolute()
    if project is not None:
        target=_private_path(Path(project),target)
    if (target.exists() or target.is_symlink() or target.parent.is_symlink()):
        raise FileExistsError("Original native restore target already exists or is unsafe")
    target.parent.mkdir(parents=True,exist_ok=True)
    # The on-disk private ZIP may be replaced during extraction; SHA pin both
    # before and after, and never overwrite a prior first-write restoration.
    with TemporaryDirectory(dir=target.parent,prefix=".native-private-restore-") as temp:
        stage=Path(temp)/"restored"
        stage.mkdir(mode=0o700)
        with ZipFile(archive,"r") as reader:
            meta=_parse(reader.read(MANIFEST))
            for item in meta["files"]:
                relative=item["name"]
                if not _relative_ok(relative):
                    raise ValueError("Unsafe archive member during original source recovery")
                member=stage/relative
                member.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                if member.exists() or member.is_symlink():
                    raise ValueError("Duplicate recovered native evidence path")
                fd=os.open(member,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                           getattr(os,"O_NOFOLLOW",0),0o600)
                with os.fdopen(fd,"wb") as out:
                    content=reader.read(relative)
                    out.write(content)
                    out.flush()
                    os.fsync(out.fileno())
            mf=stage/MANIFEST
            fd=os.open(mf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                       getattr(os,"O_NOFOLLOW",0),0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(_bytes(meta))
                out.flush()
                os.fsync(out.fileno())
        replay=_replay_restored(stage,meta)
        final=verify_native_evidence_archive(archive,expected_sha256=result["archive_sha256"])
        if final!=result:
            raise ValueError("Private archive changed during restored-native replay")
        if target.exists() or target.is_symlink():
            raise FileExistsError("Refusing to replace an existing restored native original")
        os.rename(stage,target)
    return {
        "status":"PRIVATE_NATIVE_EVIDENCE_RESTORED_AND_REPLAYED_NOT_PIT_CERTIFIED",
        "market":result["market"],"archive_sha256":result["archive_sha256"],
        "file_count":result["file_count"],**replay,
        "real_future_leader_accuracy_certified":False,
        "official_leader_promotions":0,
        "messages_sent":0,"external_api_calls":0,
    }
