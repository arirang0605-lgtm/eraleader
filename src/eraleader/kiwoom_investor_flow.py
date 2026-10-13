"""Kiwoom ka10059 read-only investor flow: never assume missing values are zero.

A strictly bounded, selected-stock collector. No order/account endpoints. Captured
timestamps describe LOCAL receipt, not original exchange publication timestamps.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler

API_HOSTS = {"demo": "https://mockapi.kiwoom.com",
             "real": "https://api.kiwoom.com"}
TR = "ka10059"
FLOW_SCHEMA = "eraleader.kiwoom_selected_investor_flow.v1"
STOCK = re.compile(r"[0-9]{6}\Z")
DAY = re.compile(r"[0-9]{8}\Z")
SIGNED = re.compile(r"([+-]{0,2})([0-9]+)\Z")


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def utc(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("Explicit source received time required")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)


def day(value: str) -> str:
    if type(value) is not str or not DAY.fullmatch(value):
        raise ValueError("Expected YYYYMMDD")
    date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    return value


def shares(value: object) -> int | None:
    """Kiwoom signed-quantity string, including documented '--' prefix quirk."""
    if value is None or value == "":
        return None
    if type(value) is not str:
        raise ValueError("Investor quantity must be an explicit string")
    matched = SIGNED.fullmatch(value.strip().replace(",", ""))
    if matched is None or len(set(matched[1])) > 1:
        raise ValueError("Unrecognized signed investor quantity")
    number = int(matched[2])
    return -number if matched[1].startswith("-") else number


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_post(path: str, body: dict, headers: dict, *, mode: str = "demo") -> tuple[dict, dict]:
    """Hardcoded Kiwoom endpoint only; never follow redirects or print secrets."""
    if path not in ("/oauth2/token", "/api/dostk/stkinfo"):
        raise ValueError("Non-allowlisted read-only provider endpoint")
    if mode not in API_HOSTS:
        raise ValueError("Unknown Kiwoom environment")
    data = canonical(body)
    req = Request(API_HOSTS[mode] + path, data=data, headers={
        "Content-Type": "application/json;charset=UTF-8", **headers}, method="POST")
    try:
        with build_opener(_NoRedirect).open(req, timeout=12) as response:
            if response.status != 200:
                raise ValueError("Kiwoom HTTP response not OK")
            blob = response.read(3_000_001)
            if len(blob) > 3_000_000:
                raise ValueError("Oversized Kiwoom response")
            def unique(items):
                result = {}
                for k, v in items:
                    if k in result:
                        raise ValueError("Duplicate JSON field in Kiwoom response")
                    result[k] = v
                return result
            parsed = json.loads(blob, object_pairs_hook=unique)
            return parsed, {k.lower(): v for k, v in response.headers.items()}
    except (ValueError, OSError) as exc:
        raise ValueError("Kiwoom HTTPS request blocked (credentials hidden)") from None


def access_token(*, appkey: str, secretkey: str, post=None) -> str:
    if not appkey or not secretkey or not callable(post):
        raise ValueError("Direct OAuth disabled; dependency-injected test transport required")
    body, _ = post("/oauth2/token", {
        "grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey}, {})
    if (type(body) is not dict or body.get("return_code") != 0 or
            body.get("token_type", "").lower() != "bearer" or
            not isinstance(body.get("token"), str) or not body["token"]):
        raise ValueError("Kiwoom OAuth response invalid (credentials hidden)")
    return body["token"]


def fetch_ka10059(*, code: str, as_of: str, token: str,
                  post=None, max_pages: int = 8,
                  received_at: datetime | None = None, environment_mode: str = "demo") -> dict:
    """Return verified read-only, SHARE-unit net-buy rows, not trade instructions."""
    if type(code) is not str or not STOCK.fullmatch(code):
        raise ValueError("KR 6-digit security identifier required")
    day(as_of)
    if environment_mode not in API_HOSTS:
        raise ValueError("Unknown provider environment")
    if not token or type(token) is not str or not callable(post) or not 1 <= max_pages <= 12:
        raise ValueError("Shared read-only transport and bounded pagination required")
    now = received_at or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Aware local receipt time required")
    if int(as_of) > int(now.astimezone(timezone.utc).date().strftime("%Y%m%d")):
        raise ValueError("Future target trading date")
    fixed = {"dt": as_of, "stk_cd": code, "amt_qty_tp": "2",
             "trde_tp": "0", "unit_tp": "1"}
    seen_keys = set()
    by_date = {}
    pages = []
    cursor = None
    for _ in range(max_pages):
        headers = {"authorization": "Bearer " + token, "api-id": TR}
        if cursor is not None:
            headers.update({"cont-yn": "Y", "next-key": cursor})
        response, meta = post("/api/dostk/stkinfo", dict(fixed), headers)
        if type(response) is not dict or response.get("return_code") != 0:
            raise ValueError("Kiwoom TR rejected or response ambiguous")
        records = response.get("stk_invsr_orgn")
        if type(records) is not list:
            raise ValueError("Investor row list missing from provider")
        page_dates = []
        for item in records:
            if type(item) is not dict:
                raise ValueError("Malformed investor day row")
            observed = day(item.get("dt"))
            if observed > as_of:
                raise ValueError("Provider row is after target trading day")
            if observed in by_date:
                raise ValueError("Duplicate trading day across provider pages")
            foreign = shares(item.get("frgnr_invsr"))
            institution = shares(item.get("orgn"))
            by_date[observed] = {
                "day": observed,
                "foreign_net_shares": foreign,
                "institution_net_shares": institution,
                "combined_net_shares": (foreign + institution
                                        if foreign is not None and institution is not None
                                        else None),
            }
            page_dates.append(observed)
        pages.append({"rows": len(records), "dates": page_dates,
                      "response_sha256": sha256(canonical(response)).hexdigest()})
        cont = meta.get("cont-yn", "N")
        if cont not in ("Y", "N", ""):
            raise ValueError("Unknown provider continuation state")
        if cont != "Y":
            break
        cursor = meta.get("next-key")
        if not cursor or type(cursor) is not str or len(cursor) > 200 or cursor in seen_keys:
            raise ValueError("Missing/repeated provider continuation key")
        seen_keys.add(cursor)
    else:
        raise ValueError("Pagination cap hit: incomplete investor evidence")
    ordered = [by_date[d] for d in sorted(by_date, reverse=True)]
    latest = ordered[0]["day"] if ordered else None
    def window(n, field):
        chosen = ordered[:n]
        if latest != as_of or len(chosen) < n or any(r[field] is None for r in chosen):
            return None
        return sum(r[field] for r in chosen)
    result = {
        "schema": FLOW_SCHEMA, "source": "KIWOOM_REST_KA10059",
        "environment_mode": environment_mode,
        "security_id": code, "requested_day": as_of, "latest_observed_day": latest,
        "source_first_locally_received_at_utc": now.astimezone(timezone.utc).isoformat(),
        "unit": "shares", "trade_type": "NET_BUY", "unit_code": "1",
        "amount_quantity_code": "2", "page_count": len(pages),
        "api_response_page_hashes": pages, "observed_rows": len(ordered),
        "rows": ordered, "flow_5_observed_sessions": {
            "foreign_net_shares": window(5, "foreign_net_shares"),
            "institution_net_shares": window(5, "institution_net_shares"),
            "combined_net_shares": window(5, "combined_net_shares"),
        },
        "flow_20_observed_sessions": {
            "foreign_net_shares": window(20, "foreign_net_shares"),
            "institution_net_shares": window(20, "institution_net_shares"),
            "combined_net_shares": window(20, "combined_net_shares"),
        },
        "historical_publication_time_pit_certified": False,
        "historic_issuer_class_pit_certified": False, "official_leader": False,
        "investment_rank": None,
        "completeness": ("COMPLETE_20_OBSERVED_ROWS_NOT_CALENDAR_CERTIFIED"
                         if latest == as_of and window(20, "combined_net_shares") is not None
                         else "PARTIAL_FLOW_RESEARCH"),
    }
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    return result


def verify_flow(payload: dict, *, decision_at: datetime) -> dict:
    if type(payload) is not dict:
        raise ValueError("Flow report must be object")
    source = dict(payload)
    proof = source.pop("content_sha256", None)
    if (proof != sha256(canonical(source)).hexdigest()
            or source.get("schema") != FLOW_SCHEMA
            or source.get("source") != "KIWOOM_REST_KA10059"
            or source.get("environment_mode") not in API_HOSTS
            or source.get("unit") != "shares"
            or source.get("amount_quantity_code") != "2"
            or source.get("trade_type") != "NET_BUY"
            or source.get("official_leader") is not False
            or source.get("investment_rank") is not None
            or source.get("historical_publication_time_pit_certified") is not False):
        raise ValueError("Flow provenance/contract invalid")
    if utc(source["source_first_locally_received_at_utc"]) > decision_at.astimezone(timezone.utc):
        raise ValueError("Flow was collected after research decision time")
    if (not STOCK.fullmatch(source["security_id"]) or
            day(source["requested_day"]) < (source.get("latest_observed_day") or "00000000")):
        raise ValueError("Flow identity or trading day invalid")
    if len(source.get("rows", [])) != source.get("observed_rows"):
        raise ValueError("Flow row count mismatch")
    return payload
