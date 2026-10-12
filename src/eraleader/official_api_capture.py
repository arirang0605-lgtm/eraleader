"""Official HTTPS KRX/DART/SEC first-received raw evidence, kept private.

Real provider APIs are NOT the declared staged KR/US PIT bundle schema. Their
issuer/class, historical membership and publication completeness must be
independently established before WATCH promotion or historical backtesting.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib import error, parse, request
from zoneinfo import ZoneInfo
import json
import os
import re
import stat
import tempfile
import uuid

SOURCES = {
    "krx-kospi": ("data-dbg.krx.co.kr", "/svc/apis/sto/stk_bydd_trd"),
    "krx-kosdaq": ("data-dbg.krx.co.kr", "/svc/apis/sto/ksq_bydd_trd"),
    "dart-disclosures": ("opendart.fss.or.kr", "/api/list.json"),
    "sec-submissions": ("data.sec.gov", "/submissions/"),
    "sec-companyfacts": ("data.sec.gov", "/api/xbrl/companyfacts/"),
}
KEYS = ("ERALEADER_KRX_AUTH_KEY", "ERALEADER_DART_API_KEY",
        "ERALEADER_SEC_USER_AGENT")
SCHEMA = "eraleader.official_api_first_received_raw.v1"
MAX_BYTES = 24 * 1024 * 1024
MAX_ROWS = 20_000
USER_AGENT = "EraLeader/0.1 (offline research evidence; not investment advice)"


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("API redirect denied (host may change)")


def _canonical(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def _secure_file(path: Path) -> bytes:
    if (not path.is_absolute() or path.is_symlink() or
            path.parent.is_symlink() or not path.is_file() or
            path.stat().st_uid != os.geteuid() or
            stat.S_IMODE(path.stat().st_mode) != 0o600 or
            path.stat().st_size > 16_384):
        raise ValueError("Credentials must be an owner-only nonlinked 0600 file")
    return path.read_bytes()


def credentials(path: Path | None = None, *, environ=None) -> dict:
    """Read only exact allowlisted variable names, never print secrets."""
    values = {name: (environ if environ is not None else os.environ).get(name)
              for name in KEYS}
    if path is not None:
        source = Path(path)
        lines = _secure_file(source).decode("utf-8").splitlines()
        if len(lines) > 20:
            raise ValueError("Too many secret-file lines")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError("Invalid secret-file configuration")
            name, value = line.split("=", 1)
            if name not in KEYS or not value or name in values and values[name]:
                # Prevent silent overwrite of a live exported environment value.
                raise ValueError("Unexpected or duplicate secret-file key")
            values[name] = value.strip()
    return values


def _settings(source: str, *, day: str | None, cik: str | None,
              creds: dict) -> tuple[str, dict[str, str]]:
    if source not in SOURCES:
        raise ValueError("Unknown official API source")
    host, endpoint = SOURCES[source]
    headers = {"Accept": "application/json",
               "User-Agent": USER_AGENT}
    query = {}
    if source.startswith("krx-") or source == "dart-disclosures":
        if not day or cik is not None:
            raise ValueError("KRX/DART require one market day, not SEC CIK")
        try:
            clean_date = date.fromisoformat(day).strftime("%Y%m%d")
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid official API market date") from exc
        if date.fromisoformat(day) > datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("Cannot request a future provider market day")
        if source.startswith("krx-"):
            secret = creds.get("ERALEADER_KRX_AUTH_KEY")
            if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9]{40}", secret):
                raise ValueError("KRX approved AUTH_KEY is not configured")
            headers["AUTH_KEY"] = secret
            query = {"basDd": clean_date}
        else:
            secret = creds.get("ERALEADER_DART_API_KEY")
            if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9]{40}", secret):
                raise ValueError("OpenDART approved crtfc_key is not configured")
            query = {"crtfc_key": secret, "bgn_de": clean_date,
                     "end_de": clean_date, "page_no": "1",
                     "page_count": "100"}
    else:
        if day is not None or not isinstance(cik, str) or not re.fullmatch(r"[0-9]{1,10}", cik):
            raise ValueError("SEC requires an explicit 1-10 digit CIK, not market day")
        agent = creds.get("ERALEADER_SEC_USER_AGENT")
        if (not isinstance(agent, str) or not 12 <= len(agent) <= 180 or
                "\n" in agent or "\r" in agent or
                not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", agent)):
            raise ValueError("SEC requires a declared User-Agent with real contact email")
        headers["User-Agent"] = agent
        endpoint += "CIK" + cik.zfill(10) + ".json"
    url = "https://" + host + endpoint
    if query:
        url += "?" + parse.urlencode(query)
    return url, headers


def _http_get(url: str, headers: dict[str, str]) -> bytes:
    """One bounded HTTPS GET. Redirects, errors and URLs stay out of logs."""
    uri = parse.urlsplit(url)
    if uri.scheme != "https" or uri.hostname not in {
            host for host, _ in SOURCES.values()} or uri.username or uri.password:
        raise ValueError("Unapproved official HTTPS origin")
    req = request.Request(url, headers=headers, method="GET")
    opener = request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=18) as res:
            if res.status != 200:
                raise ValueError("Official API HTTP status not OK")
            raw = res.read(MAX_BYTES + 1)
    except error.HTTPError as exc:
        raise ValueError("Official API rejected request (HTTP " + str(exc.code) + ")") from None
    except error.URLError:
        raise ValueError("Official API transport unavailable") from None
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Empty/oversized official API response")
    return raw


def _decoded(raw: bytes, source: str, *, day: str | None, cik: str | None) -> tuple[int, str]:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid official API bytes")
    def unique(items):
        doc = {}
        for key, val in items:
            if key in doc:
                raise ValueError("Duplicate official API JSON key")
            doc[key] = val
        return doc
    try:
        body = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Official API response is not JSON") from None
    if not isinstance(body, dict):
        raise ValueError("Official API must return an object")
    if source.startswith("krx-"):
        rows = body.get("OutBlock_1")
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError("KRX returned no valid daily-trade response block")
        expected = date.fromisoformat(day).strftime("%Y%m%d")
        for row in rows:
            if (not isinstance(row, dict) or row.get("BAS_DD") != expected or
                    not isinstance(row.get("ISU_CD"), str) or
                    not row["ISU_CD"].strip() or
                    not isinstance(row.get("TDD_CLSPRC"), str)):
                raise ValueError("KRX day/security/closing-price schema mismatch")
        return len(rows), "NO_DAILY_ROWS" if not rows else "ROWS_RECEIVED_NOT_PIT_CERTIFIED"
    if source == "dart-disclosures":
        status = body.get("status")
        if status == "013":
            if body.get("list") not in (None, []):
                raise ValueError("DART no-data status with unexpected disclosure rows")
            return 0, "NO_DISCLOSURES_FOR_DAY"
        if status != "000":
            raise ValueError("DART error status " + (status if type(status) is str and
                             re.fullmatch(r"[0-9]{3}", status) else "unknown"))
        rows = body.get("list")
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("DART disclosure page schema/limit mismatch")
        expected = date.fromisoformat(day).strftime("%Y%m%d")
        for row in rows:
            if (not isinstance(row, dict) or row.get("rcept_dt") != expected or
                    not isinstance(row.get("rcept_no"), str) or
                    not re.fullmatch(r"[0-9]{14}", row["rcept_no"])):
                raise ValueError("DART disclosure date/receipt schema mismatch")
        total = body.get("total_count")
        if type(total) is not int and not (
                isinstance(total, str) and total.isdecimal()):
            raise ValueError("DART missing total_count")
        # First page is deliberately NOT the full day when total_count>100.
        return len(rows), ("INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY" if int(total)>len(rows)
                           else "ROWS_RECEIVED_NOT_PIT_CERTIFIED")
    seen_cik = body.get("cik")
    if (type(seen_cik) not in (str, int) or
            not str(seen_cik).isdigit() or
            int(seen_cik) != int(cik) or int(cik) <= 0):
        raise ValueError("SEC registrant CIK differs from requested issuer")
    if source == "sec-submissions":
        recent = body.get("filings", {}).get("recent")
        if (not isinstance(recent, dict) or
                not isinstance(recent.get("accessionNumber"), list) or
                not isinstance(recent.get("acceptanceDateTime"), list) or
                len(recent["accessionNumber"]) != len(recent["acceptanceDateTime"])):
            raise ValueError("SEC submissions recent acceptance-time schema missing")
        return len(recent["accessionNumber"]), "RECENT_SUBMISSIONS_NOT_FULL_HISTORY"
    facts = body.get("facts")
    if not isinstance(facts, dict) or not facts:
        raise ValueError("SEC companyfacts facts schema missing")
    return len(facts), "FINANCIAL_FACT_TAXONOMIES_NOT_PIT_CERTIFIED"


def _root(base: Path) -> Path:
    base = Path(base)
    if (not base.is_absolute() or ".." in base.parts or
            base.is_symlink() or base.parent.is_symlink() or
            not base.is_dir() or base.stat().st_uid != os.geteuid() or
            stat.S_IMODE(base.stat().st_mode) & 0o077):
        raise ValueError("Use an existing owner-only 0700 capture parent")
    return base


def _write_new(file: Path, raw: bytes) -> None:
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def capture_official_api(source: str, base: Path, *, day: str | None = None,
                         cik: str | None = None, creds: dict | None = None,
                         fetch=None, clock=None) -> dict:
    """First-observed raw HTTPS response, never pre-dated or re-signed.

    A response is NOT yet a PIT-listed-universe or security-class mapping.
    No original source in the project is rewritten and nothing is auto-ranked.
    """
    base = _root(base)
    url, headers = _settings(source, day=day, cik=cik,
                             creds=creds if creds is not None else credentials())
    response = (fetch or _http_get)(url, headers)
    count, quality = _decoded(response, source, day=day, cik=cik)
    stamp = clock() if clock is not None else datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Local first-receipt timestamp must be timezone-aware")
    observed = stamp.astimezone(timezone.utc).isoformat()
    metadata = {
        "schema": SCHEMA, "source": source, "first_local_received_at_utc": observed,
        "raw_sha256": sha256(response).hexdigest(), "raw_length_bytes": len(response),
        "provider_row_count": count, "quality": quality,
        "request_kind": "market_day" if day else "cik",
        "request_value": day or cik, "publisher_release_time_verified": False,
        "full_historic_universe_pit_certified": False,
        "issuer_share_class_independently_attested": False,
        "official_leader_promotions": 0,
        "no_external_timestamp_notary": True,
    }
    # Stage a fully private folder; never expose one completed half-capture.
    temp = Path(tempfile.mkdtemp(prefix=".api_inflight_", dir=base))
    target = base / ("first_" + uuid.uuid4().hex)
    if os.path.lexists(target):
        raise ValueError("Original live capture target already exists")
    try:
        os.chmod(temp, 0o700)
        _write_new(temp / "raw_response.json", response)
        receipt = _canonical(metadata)
        _write_new(temp / "first_receipt.json", receipt)
        os.replace(temp, target)
        os.chmod(target, 0o700)
    finally:
        if temp.exists():
            import shutil
            shutil.rmtree(temp)
    return {
        "status": "LIVE_OFFICIAL_API_RAW_RECORDED_RESEARCH_ONLY",
        "source": source, "capture_id": target.name,
        "first_local_received_at_utc": observed,
        "first_receipt_sha256": sha256(receipt).hexdigest(),
        "raw_sha256": metadata["raw_sha256"],
        "provider_row_count": count, "quality": quality,
        "historical_pit_certified": False,
        "official_leader_promotions": 0,
        "external_api_calls": 1, "messages_sent": 0,
    }
