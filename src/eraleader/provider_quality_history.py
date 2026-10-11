"""6_2/6_5: append-only local quality-gate observation receipts, not certified PIT.

The source is the actual in-process candidate provider gate, never a mutable
report file. A global SHA chain and a first-write genesis sidecar detect
uncoordinated alteration, partial loss, and accidental rebasing. Both files and
the local OS clock can be changed together by a privileged actor; timestamps
and claimed publisher independence are NOT externally notarized.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import json
import os
import re
import sqlite3
import tempfile

from .delivery import BASE_CSS
from .provider_gate_quality_view import _validate

SCHEMA="eraleader.provider_quality_history.v1"
DB_NAME="provider_quality_history.sqlite"
SEAL_NAME="provider_quality_history_genesis.json"
ZERO="0"*64
MAX_EVENTS=2500
MAX_ROW_BYTES=60_000
SHA=re.compile(r"[0-9a-f]{64}\Z")
# Explicit allowlist excludes names, legal IDs, raw rows, source paths, and keys.
FIELDS=(
    "market","decision_at_utc","status","source_pair_status",
    "source_pair_digest_sha256","source_pair_bundle_sha256_a",
    "source_pair_bundle_sha256_b","source_pair_original_pin_sha256",
    "research_watch_allowed","require_original_first_ingest_pins",
    "original_first_ingest_pins_locally_consistent",
    "issuer_class_bridge_required","issuer_class_bridge_status",
    "issuer_class_evidence_sha256","issuer_class_matched_candidates",
    "candidate_issuer_count","locally_correlated_candidate_issuer_count",
    "blocker_counts","blocker_count","publisher_independently_authenticated",
    "legal_issuer_identity_independently_verified",
    "historic_membership_pit_certified","official_candidate_promotion_allowed",
    "leader_accuracy_certified","official_leader_promotions",
    "source_consistency_only","source_pair_consistency_only",
)
EVENT_COLUMNS=(
    "event_no","recorded_at_utc","market","decision_at_utc","payload_json",
    "payload_sha256","transition","previous_sha256",
)
TRANSITIONS=frozenset((
    "FIRST_LOCAL_OBSERVATION","REVISED_SAME_DECISION_REVIEW",
    "OLDER_DECISION_REPLAY_NOT_PREDICTION","WATCH_GATE_BLOCKED",
    "WATCH_GATE_REOPENED_RESEARCH_ONLY","EVIDENCE_STRENGTHENED",
    "EVIDENCE_WEAKENED","BLOCKERS_CHANGED","CLAIMED_SOURCES_CHANGED",
    "NEW_DECISION_SAME_GATE",
))


def _canonical(value:object) -> bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _digest(value:object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _unique(pairs:list) -> dict:
    data={}
    for key,value in pairs:
        if key in data:
            raise ValueError("Repeated quality history JSON field")
        data[key]=value
    return data


def _time(value:object) -> datetime:
    if type(value) is not str:
        raise ValueError("Missing local history UTC timestamp")
    try:
        parsed=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid local history UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Local history requires offset-aware timestamp")
    return parsed.astimezone(timezone.utc)


def _utc_time(value:object) -> datetime:
    instant=_time(value)
    # First-write local receipts are serialized in UTC, unlike market-local
    # decision timestamps which commonly use +09:00 / US Eastern.
    original=datetime.fromisoformat(value)
    if original.utcoffset().total_seconds()!=0:
        raise ValueError("Local OS receipt timestamp must use UTC")
    return instant


def _now(clock:datetime|None) -> datetime:
    when=datetime.now(timezone.utc) if clock is None else clock
    if (not isinstance(when,datetime) or when.tzinfo is None
            or when.utcoffset() is None):
        raise ValueError("Local quality history needs an aware clock")
    return when.astimezone(timezone.utc)


def _input(gate:dict) -> dict:
    # Reuse the strict original gate renderer's authenticity-claim contract.
    _validate(gate)
    data={key:gate[key] for key in FIELDS}
    if len(_canonical(data))>MAX_ROW_BYTES:
        raise ValueError("Oversized local quality history evidence")
    return data


def _paths(root:Path) -> tuple[Path,Path,Path]:
    root=Path(root).absolute()
    if root.is_symlink() or not root.is_dir() or root.parent.is_symlink():
        raise ValueError("Unsafe/missing local quality history output folder")
    db=root/DB_NAME
    seal=root/SEAL_NAME
    lock=root/".provider_quality_history.lock"
    for p in (db,seal,lock,root/"site"):
        if p.is_symlink():
            raise ValueError("Unsafe symlink in quality history paths")
    return db,seal,lock


@contextmanager
def _locked(root:Path):
    db,seal,lock=_paths(root)
    flags=os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(lock,flags,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        # A first-write marker without the database (or vice versa) cannot
        # be silently converted into a fresh history after a partial loss.
        if db.exists()!=seal.exists():
            raise ValueError("Missing local quality history genesis marker or ledger database")
        for item in (db,seal):
            if item.exists() and (item.is_symlink() or not item.is_file() or
                                  item.stat().st_size==0):
                raise ValueError("Unsafe/corrupt local quality history ledger or genesis")
        yield db,seal
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)


def _open(db_path:Path, seal_path:Path, *,create:bool, now:datetime|None=None
         ) -> sqlite3.Connection:
    is_new=not db_path.exists()
    if is_new and not create:
        raise ValueError("Missing local quality history ledger database")
    if is_new:
        assert now is not None
        marker={"schema":SCHEMA,"created_at_utc":now.isoformat(),
                "ledger_id":os.urandom(16).hex()}
        raw=_canonical(marker)
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
        fd=os.open(seal_path,flags,0o600)
        with os.fdopen(fd,"wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
    mode="rwc" if is_new else "rw"
    connection=sqlite3.connect(db_path.as_uri()+f"?mode={mode}",uri=True,
                               timeout=8,isolation_level=None)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout=8000")
        if is_new:
            connection.executescript("""
                CREATE TABLE quality_meta (
                  name TEXT PRIMARY KEY NOT NULL,value TEXT NOT NULL
                );
                CREATE TABLE quality_events (
                  event_no INTEGER PRIMARY KEY,
                  recorded_at_utc TEXT NOT NULL,
                  market TEXT NOT NULL,
                  decision_at_utc TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  transition TEXT NOT NULL,
                  previous_sha256 TEXT NOT NULL,
                  event_sha256 TEXT NOT NULL
                );
            """)
            with connection:
                connection.executemany(
                    "INSERT INTO quality_meta(name,value) VALUES (?,?)",(
                        ("schema",SCHEMA),("count","0"),("head",ZERO),
                        ("genesis_sha256",sha256(seal_path.read_bytes()).hexdigest()),
                    ),
                )
        return connection
    except Exception:
        connection.close()
        raise


def _strength(payload:dict) -> int:
    # Local audit dimensions requested and matched, NOT evidence of actual PIT.
    return (int(payload["source_pair_status"]==
                "LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED")+
            int(payload["require_original_first_ingest_pins"])+
            int(payload["issuer_class_bridge_required"] and
                payload["issuer_class_bridge_status"]==
                "LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"))


def _transition(previous:dict|None, current:dict) -> str:
    if previous is None:
        return "FIRST_LOCAL_OBSERVATION"
    before=_time(previous["decision_at_utc"])
    after=_time(current["decision_at_utc"])
    if after<before:
        return "OLDER_DECISION_REPLAY_NOT_PREDICTION"
    if after==before:
        return "REVISED_SAME_DECISION_REVIEW"
    if previous["research_watch_allowed"] and not current["research_watch_allowed"]:
        return "WATCH_GATE_BLOCKED"
    if not previous["research_watch_allowed"] and current["research_watch_allowed"]:
        return "WATCH_GATE_REOPENED_RESEARCH_ONLY"
    if _strength(current)<_strength(previous):
        return "EVIDENCE_WEAKENED"
    if _strength(current)>_strength(previous):
        return "EVIDENCE_STRENGTHENED"
    if previous["blocker_counts"]!=current["blocker_counts"]:
        return "BLOCKERS_CHANGED"
    if previous["source_pair_digest_sha256"]!=current["source_pair_digest_sha256"]:
        return "CLAIMED_SOURCES_CHANGED"
    return "NEW_DECISION_SAME_GATE"


def _verified(db:sqlite3.Connection,seal:Path) -> list[dict]:
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("Corrupt local quality history SQLite ledger")
        raw=seal.read_bytes()
        if not 0<len(raw)<=4096:
            raise ValueError("Invalid quality history genesis size")
        marker=json.loads(raw,object_pairs_hook=_unique)
        if (set(marker)!={"schema","created_at_utc","ledger_id"} or
                marker["schema"]!=SCHEMA or
                type(marker["ledger_id"]) is not str or
                not re.fullmatch(r"[0-9a-f]{32}",marker["ledger_id"]) or
                raw!=_canonical(marker)):
            raise ValueError("Invalid/revised local history genesis marker")
        _utc_time(marker["created_at_utc"])
        meta=dict(db.execute("SELECT name,value FROM quality_meta").fetchall())
        if (set(meta)!={"schema","count","head","genesis_sha256"} or
                meta["schema"]!=SCHEMA or
                not re.fullmatch(r"(0|[1-9][0-9]*)",meta["count"]) or
                int(meta["count"])>MAX_EVENTS or
                meta["genesis_sha256"]!=sha256(raw).hexdigest() or
                type(meta["head"]) is not str or not SHA.fullmatch(meta["head"])):
            raise ValueError("Local history genesis/head/count seal mismatch")
        rows=[dict(row) for row in db.execute(
            "SELECT * FROM quality_events ORDER BY event_no").fetchall()]
        if len(rows)!=int(meta["count"]):
            raise ValueError("Quality event count discrepancy; missing/deleted entries")
        previous_sha=ZERO
        previous_time=None
        last_by_market={}
        result=[]
        for number,row in enumerate(rows,1):
            if (set(row)!=set(EVENT_COLUMNS)|{"event_sha256"} or
                    type(row["event_no"]) is not int or row["event_no"]!=number or
                    row["market"] not in ("KR","US") or
                    row["transition"] not in TRANSITIONS or
                    not isinstance(row["payload_json"],str) or
                    len(row["payload_json"].encode())>MAX_ROW_BYTES):
                raise ValueError("Malformed local quality history event")
            at=_utc_time(row["recorded_at_utc"])
            if previous_time is not None and at<previous_time:
                raise ValueError("Local quality history clock backdated")
            previous_time=at
            payload=json.loads(row["payload_json"],object_pairs_hook=_unique)
            if (not isinstance(payload,dict) or set(payload)!=set(FIELDS) or
                    _canonical(payload).decode()!=row["payload_json"]):
                raise ValueError("Tampered/surplus history payload data")
            _validate(payload)
            if (row["market"]!=payload["market"] or
                    row["decision_at_utc"]!=payload["decision_at_utc"] or
                    _time(row["decision_at_utc"])>at or
                    row["payload_sha256"]!=_digest(payload) or
                    row["previous_sha256"]!=previous_sha or
                    row["transition"]!=_transition(last_by_market.get(row["market"]),payload)):
                raise ValueError("Local quality history payload/transition/chain mismatch")
            head=_digest({field:row[field] for field in EVENT_COLUMNS})
            if head!=row["event_sha256"]:
                raise ValueError("Local quality history event SHA digest mismatch")
            previous_sha=head
            last_by_market[row["market"]]=payload
            result.append({"row":row,"payload":payload})
        if previous_sha!=meta["head"]:
            raise ValueError("Local quality history head SHA mismatch")
        return result
    except (KeyError,TypeError,IndexError,sqlite3.DatabaseError,
            json.JSONDecodeError) as exc:
        raise ValueError("Malformed/corrupt local quality history ledger") from exc


def _report(events:list[dict], market:str) -> dict:
    if market not in ("KR","US"):
        raise ValueError("Quality history view needs market KR/US")
    scoped=[entry for entry in events if entry["payload"]["market"]==market]
    latest=scoped[-1]["payload"] if scoped else None
    if not latest:
        raise ValueError("No existing quality history events for market")
    recent=[]
    counts=Counter()
    for item in scoped:
        r=item["row"];p=item["payload"]
        counts[r["transition"]]+=1
    for item in scoped[-50:]:
        r=item["row"];p=item["payload"]
        recent.append({
            "sequence":r["event_no"],
            "recorded_at_utc":r["recorded_at_utc"],
            "decision_at_utc":p["decision_at_utc"],
            "transition":r["transition"],
            "research_gate_allowed":p["research_watch_allowed"],
            "first_ingest_pin_required":p["require_original_first_ingest_pins"],
            "issuer_class_required":p["issuer_class_bridge_required"],
            "blocker_counts":p["blocker_counts"],
            "retrospective_replay":_time(p["decision_at_utc"])<
                _utc_time(r["recorded_at_utc"]),
        })
    head=events[-1]["row"]["event_sha256"]
    return {
        "schema_version":SCHEMA,
        "market":market,
        "chain_verified":True,
        "global_event_count":len(events),
        "global_head_sha256":head,
        "market_event_count":len(scoped),
        "last_gate_allowed":latest["research_watch_allowed"],
        "last_first_ingest_pin_required":latest["require_original_first_ingest_pins"],
        "last_issuer_class_required":latest["issuer_class_bridge_required"],
        "last_transition":scoped[-1]["row"]["transition"],
        "last_decision_at_utc":latest["decision_at_utc"],
        "first_observed_at_utc":scoped[0]["row"]["recorded_at_utc"],
        "transition_counts":dict(sorted(counts.items())),
        "recent_events":recent,
        "research_gate_only":True,
        "independently_attested_timestamp":False,
        "publisher_identity_independently_verified":False,
        "historical_universe_pit_certified":False,
        "official_leader_promotions":0,
        "real_future_leader_precision":None,
        "warning":"Local SHA sequence is not a trusted clock, official issuer registry or future discovery result.",
    }


def _atomic(file:Path,raw:bytes) -> None:
    if file.is_symlink() or file.parent.is_symlink():
        raise ValueError("Unsafe linked local quality history output")
    file.parent.mkdir(parents=True,exist_ok=True)
    pending=None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",dir=file.parent,prefix=".quality-history-",
            suffix=".tmp",delete=False,
        ) as output:
            pending=Path(output.name)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if file.is_symlink():
            raise ValueError("Unsafe linked quality history output")
        os.replace(pending,file)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def render_quality_history(report:dict) -> str:
    """Read-only HTML display. Never infer true alpha from local gate receipts."""
    if (not isinstance(report,dict) or report.get("schema_version")!=SCHEMA or
            report.get("market") not in ("KR","US") or
            report.get("chain_verified") is not True or
            report.get("research_gate_only") is not True or
            report.get("independently_attested_timestamp") is not False or
            report.get("publisher_identity_independently_verified") is not False or
            report.get("historical_universe_pit_certified") is not False or
            type(report.get("official_leader_promotions")) is not int or
            report["official_leader_promotions"]!=0 or
            report.get("real_future_leader_precision") is not None or
            not isinstance(report.get("recent_events"),list) or
            not isinstance(report.get("transition_counts"),dict) or
            not isinstance(report.get("market_event_count"),int) or
            report["market_event_count"]<1 or
            len(report["recent_events"])>50 or
            not isinstance(report.get("global_head_sha256"),str) or
            not SHA.fullmatch(report["global_head_sha256"])):
        raise ValueError("Cannot render forged/nonresearch quality history")
    def s(x:object) -> str:
        return escape(str(x),quote=True)
    rows=[]
    for row in report["recent_events"]:
        if (not isinstance(row,dict) or row.get("transition") not in TRANSITIONS or
                type(row.get("sequence")) is not int or row["sequence"]<1 or
                type(row.get("research_gate_allowed")) is not bool or
                not isinstance(row.get("blocker_counts"),dict) or
                len(row["blocker_counts"])>200):
            raise ValueError("Invalid quality history event in web output")
        _time(row["recorded_at_utc"])
        _time(row["decision_at_utc"])
        if any(type(k) is not str or not re.fullmatch("[A-Z][A-Z0-9_]{0,119}",k)
               or type(v) is not int or v<1 for k,v in row["blocker_counts"].items()):
            raise ValueError("Untrusted history blocker details")
        blockers=", ".join(f"{s(k)}: {s(v)}" for k,v in sorted(row["blocker_counts"].items()))
        vals=(row["sequence"],row["recorded_at_utc"],row["decision_at_utc"],
              "연구용 허용" if row["research_gate_allowed"] else "보류",
              row["transition"],blockers or "없음",
              "소급 연구" if row["retrospective_replay"] else "현재 기록")
        rows.append("<tr>"+"".join("<td>"+s(v)+"</td>" for v in vals)+"</tr>")
    market=report["market"]
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader {s(market)} 후보 원천 품질 변화 이력</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 후보 원천 검증 변화 이력</h1>
<nav><a href="provider_quality_{market.lower()}.html">최근 원천 검증</a></nav>
<div>{s(market)} · 로컬 시각 최초 기록 영수증 및 SHA 순서체인</div></header><main>
<div class="note"><strong>미인증 로컬 연구 이력 · 공식 확정 대장주 0건</strong><p>
최초 판단 당시의 공인 원천이나 법적 회사 확인을 인증하지 않습니다.
로컬 시각 및 SQLite 원장은 외부 공증이 아니며, 두 파일을 함께 위조하면 탐지 불가.
소급 연구 기록은 과거 당시 발굴로 인정하지 않습니다.
실전 적중률 N/A · 실전 메시지 발송 0 · 외부 API 미연결.</p></div>
<div class="stats"><div class="stat">기록된 시장별 원천 검증<br><strong>{s(report["market_event_count"])}</strong></div>
<div class="stat">마지막 연구 게이트<br><strong>{"허용 (미인증)" if report["last_gate_allowed"] else "보류"}</strong></div>
<div class="stat">마지막 변화 유형<br><strong>{s(report["last_transition"])}</strong></div></div>
<h2>검증 변화 이력 (최근 50건, 원래 실행 결정시각과 OS 기록시각 구분)</h2>
<div class="wrap"><table><thead><tr><th>번호</th><th>OS 기록(UTC)</th>
<th>결정 기준시각</th><th>연구용 판정</th><th>변화 유형</th><th>보류 코드</th><th>소급 여부</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><small>체인 마지막 SHA: {s(report["global_head_sha256"])} · 독립 시간 공증 아님.</small></p>
</main></body></html>"""


def _publish(root:Path,report:dict) -> tuple[Path,Path]:
    market=report["market"].lower()
    rendered=render_quality_history(report)
    report_path=root/f"provider_quality_history_{market}_research.json"
    html_path=root/"site"/f"provider_quality_history_{market}.html"
    _atomic(report_path,_canonical(report))
    _atomic(html_path,rendered.encode("utf-8"))
    return report_path,html_path


def audit_quality_history(root:Path, *,market:str) -> dict:
    """Read-only full-ledger audit. Never trusts a cached summary or page."""
    with _locked(root) as (dbfile,seal):
        with closing(_open(dbfile,seal,create=False)) as db:
            return _report(_verified(db,seal),market)


def record_quality_snapshot(root:Path, gate:dict, *, clock:datetime|None=None) -> dict:
    """Opt-in append receipt, idempotent only for identical last market decision.

    This observes a LOCAL gate evaluation, not completed delivery of a WATCH
    and not a source release-time receipt. No API or external data is used.
    """
    payload=_input(gate)
    now=_now(clock)
    if _time(payload["decision_at_utc"])>now:
        raise ValueError("Future quality history decision cannot be registered")
    root=Path(root).absolute()
    with _locked(root) as (dbfile,seal):
        with closing(_open(dbfile,seal,create=True,now=now)) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                events=_verified(db,seal)
                last_global=events[-1] if events else None
                if (last_global is not None and
                        now<_time(last_global["row"]["recorded_at_utc"])):
                    raise ValueError("Cannot backdate local quality history clock")
                previous=next((entry["payload"] for entry in reversed(events)
                               if entry["payload"]["market"]==payload["market"]),None)
                same=(previous is not None and previous==payload)
                # Same cutoff and identical entire sanitized evidence is an
                # idempotent re-audit; new cutoff (even same source) is new.
                duplicate=bool(same)
                transition=("UNCHANGED_NO_NEW_EVENT" if duplicate
                            else _transition(previous,payload))
                if not duplicate:
                    if len(events)>=MAX_EVENTS:
                        raise ValueError("Maximum local quality event count reached")
                    encoded=_canonical(payload)
                    row={
                        "event_no":len(events)+1,
                        "recorded_at_utc":now.isoformat(),
                        "market":payload["market"],
                        "decision_at_utc":payload["decision_at_utc"],
                        "payload_json":encoded.decode("utf-8"),
                        "payload_sha256":sha256(encoded).hexdigest(),
                        "transition":transition,
                        "previous_sha256":last_global["row"]["event_sha256"] if last_global else ZERO,
                    }
                    digest=_digest(row)
                    db.execute("""INSERT INTO quality_events (
                       event_no,recorded_at_utc,market,decision_at_utc,
                       payload_json,payload_sha256,transition,previous_sha256,event_sha256
                       ) VALUES (?,?,?,?,?,?,?,?,?)""",(
                        *(row[field] for field in EVENT_COLUMNS),digest,
                    ))
                    db.execute("UPDATE quality_meta SET value=? WHERE name='count'",
                               (str(row["event_no"]),))
                    db.execute("UPDATE quality_meta SET value=? WHERE name='head'",
                               (digest,))
                checked=_verified(db,seal)
                db.commit()
            except Exception:
                db.rollback()
                raise
            report=_report(checked,payload["market"])
        # Keep rendering serialized with the same local lock, preventing
        # concurrent submitters from publishing older market summary pages.
        report_path,html_path=_publish(root,report)
    return {
        "event_added":not duplicate,
        "transition":transition,
        "market":payload["market"],
        "global_event_count":report["global_event_count"],
        "head_sha256":report["global_head_sha256"],
        "report_path":str(report_path),
        "html_path":str(html_path),
        "chain_verified":True,
        "research_gate_only":True,
        "independently_attested_timestamp":False,
        "official_leader_promotions":0,
        "real_future_leader_precision":None,
    }
