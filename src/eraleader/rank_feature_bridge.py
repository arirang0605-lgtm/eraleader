"""Build original-formula input documents from existing offline PIT research.

These are contemporaneously WRITTEN features, not independently proven
historical disclosures, adjusted returns, or official leader predictions.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp
from zoneinfo import ZoneInfo
import json
import math
import os
import shutil

from .discovery import MODEL_VERSION, run_id_for
from .offline_pit import OfflineLedger, iso_time
from .offline_features import financial_snapshot
from .peer_normalization import normalize_growth_peers
from .rank_score_pipeline import TARGETS, compute_research_score
from .price_cache_witness import recheck_price_cache

ZONES = {"KR": "Asia/Seoul", "US": "America/New_York"}
CLOSE_READY = {"KR": time(15, 40), "US": time(16, 10)}


def _load_bytes(path: Path) -> tuple[dict, str]:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked source evidence")
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("Expected JSON evidence object")
    return document, sha256(raw).hexdigest()


def _finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def check_offline_pit_ledger(offline: dict, ledger_file: Path) -> str:
    """Recompute the entire research snapshot from the original read-only PIT DB.

    A local byte-level reconciliation does NOT independently authenticate the
    original membership, issuer, filing release time or market data supplier.
    """
    if offline.get("market") not in ZONES or not isinstance(offline.get("as_of"), str):
        raise ValueError("Offline snapshot lacks market or PIT cutoff")
    ledger = OfflineLedger.open_readonly(Path(ledger_file))
    try:
        regenerated = financial_snapshot(
            ledger.snapshot(offline["as_of"], market=offline["market"]))
    finally:
        ledger.close()
    try:
        baseline = json.dumps(regenerated, sort_keys=True, ensure_ascii=False,
                              allow_nan=False, separators=(",", ":"))
        supplied = json.dumps(offline, sort_keys=True, ensure_ascii=False,
                              allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid or nonfinite offline research snapshot") from exc
    if supplied != baseline:
        raise ValueError("Offline research snapshot differs from original as-of PIT ledger")
    return sha256(baseline.encode("utf-8")).hexdigest()


def build_rank_feature_inputs(
    offline_file: Path, price_file: Path, output_dir: Path, *,
    model_version: str, min_peers: int = 3, clock: datetime | None = None,
    offline_ledger: Path | None = None,
    price_cache_root: Path | None = None, price_cache_days: int = 550,
) -> dict:
    """Derive conservative four-factor research inputs without scoring WATCH.

    A full same-industry peer group, price screen at the identical PIT date,
    unhalted price observation, and all four finite factors are prerequisites.
    Price identity is only a ticker join; issuer/action completeness is unknown.
    Generated 'available_at' is NOW, never a historical backdated source time.
    """
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned nonempty model_version required")
    if price_cache_root is None and price_cache_days != 550:
        raise ValueError("Cache lookback days require an original price cache root")
    now = clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Actual feature generation clock must have timezone")
    now = now.astimezone(timezone.utc)
    offline, offline_sha = _load_bytes(Path(offline_file))
    price, price_sha = _load_bytes(Path(price_file))
    local_ledger_snapshot_sha = (check_offline_pit_ledger(offline, offline_ledger)
                                 if offline_ledger is not None else None)
    peer = normalize_growth_peers(offline, min_peers=min_peers)
    market = peer["market"]
    zone = ZoneInfo(ZONES[market])
    stamp = datetime.fromisoformat(iso_time(offline["as_of"]))
    if stamp > now:
        raise ValueError("Future offline snapshot cannot generate present features")
    market_day = stamp.astimezone(zone).date()
    if (now.astimezone(zone).date() - market_day).days > 3:
        raise ValueError("Historical research snapshot cannot be registered as current rank inputs")
    if (price.get("source_market") != market
        or price.get("as_of_requested") != market_day.isoformat()
        or price.get("model_version") != MODEL_VERSION
        or price.get("classification_quality") != "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("PIT cutoff/market or price research model mismatch")
    bars = price.get("rows")
    if (not isinstance(bars, list) or type(price.get("shown")) is not int
        or len(bars) != price["shown"] or len(bars) > 10000):
        raise ValueError("Invalid price screen row count")
    if price.get("run_id") != run_id_for(market, market_day.isoformat(), bars):
        raise ValueError("Price run fingerprint mismatch")
    quality = price.get("quality_flags")
    if not isinstance(quality, dict) or quality.get("price_only") is not True:
        raise ValueError("Original price-only quality declaration missing")
    last = date.fromisoformat(price["market_last_observation"])
    if last > market_day or (market_day-last).days > 10:
        raise ValueError("Future/stale price observation relative to PIT cutoff")
    if (last == market_day
        and stamp.astimezone(zone).time() < CLOSE_READY[market]):
        raise ValueError("Today's closing price unavailable before market close")

    prices = {}
    for row in bars:
        if not isinstance(row, dict):
            raise ValueError("Invalid price row")
        ticker = row.get("security_id")
        if not isinstance(ticker, str) or not ticker.strip() or ticker in prices:
            raise ValueError("Ambiguous or repeated price ticker identity")
        observed = date.fromisoformat(row["observed_at"])
        if observed != last or observed > market_day:
            raise ValueError("Price row observation does not match PIT header")
        value = row.get("return_6m")
        if value is not None and (not _finite(value) or value <= -1):
            raise ValueError("Invalid six-month price return")
        prices[ticker] = row
    price_witness = (recheck_price_cache(price, legacy_root=Path(price_cache_root),
                                         days=price_cache_days)
                     if price_cache_root is not None else None)

    companies = offline["companies"]
    tickers = {}
    for row in companies:
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("Missing PIT membership ticker")
        if ticker in tickers:
            raise ValueError("Ambiguous ticker maps to multiple permanent issuers")
        tickers[ticker] = row["security_id"]
    peer_ok = {row["security_id"] for row in peer["companies"]
               if row["status"] == "RESEARCH_NORMALIZED"}
    documents, deferred = {}, []
    for row in companies:
        sid, ticker = row["security_id"], row["ticker"]
        if sid not in peer_ok or ticker not in prices:
            deferred.append({"security_id":sid, "reason":(
                "PIT_PEER_SCREEN_DEFERRED" if sid not in peer_ok
                else "NO_PRICE_MOMENTUM_ASOF")})
            continue
        factors = {name: row.get(name) for name in TARGETS if name != "momentum_6m"}
        factors["momentum_6m"] = prices[ticker].get("return_6m")
        if any(not _finite(value) for value in factors.values()):
            deferred.append({"security_id":sid, "reason":"MISSING_RESEARCH_FACTOR"})
            continue
        compute_research_score(factors)  # Same strict preflight as native scorer
        doc = {
            "schema":"eraleader.rank_feature_document.v1",
            "market":market, "model_version":model_version,
            "security_id":sid, "available_at":now.isoformat(),
            "features":factors,
        }
        name = sha256((market+"|"+sid).encode()).hexdigest()[:24]+".json"
        if name in documents:
            raise ValueError("Feature evidence filename collision")
        documents[name] = doc
    if len(documents) > 1000:
        raise ValueError("Native rank input supports at most 1000 observed companies")
    output_dir = Path(output_dir)
    if output_dir.is_symlink() or output_dir.exists():
        raise FileExistsError("Rank input output directory already exists")
    manifest = {
        "schema":"eraleader.offline_rank_feature_bridge.v1",
        "market":market, "model_version":model_version,
        "as_of":stamp.isoformat(), "generated_at_utc":now.isoformat(),
        "offline_source_sha256":offline_sha,
        "local_pit_ledger_snapshot_sha256":local_ledger_snapshot_sha,
        "recomputed_from_readonly_offline_ledger":offline_ledger is not None,
        "price_source_sha256":price_sha,
        "price_source_run_id":price["run_id"],
        "price_last_observation":last.isoformat(),
        "recomputed_from_readonly_price_cache":price_witness is not None,
        "selected_cached_price_returns_sha256":(
            price_witness["original_selected_price_returns_sha256"]
            if price_witness else None),
        "min_peers":min_peers,
        "eligible_document_count":len(documents),
        "deferred_count":len(deferred),
        "deferred":deferred,
        "feature_file_sha256":{},
        "ticker_to_permanent_issuer_identity_certified":False,
        "price_adjustments_and_actions_certified":False,
        "financial_source_publication_independently_attested":False,
        "official_leader_promotions":0,
        "note":"Source hashes and local creation clock are NOT third-party PIT attestation",
    }
    for filename, doc in sorted(documents.items()):
        data = (json.dumps(doc, ensure_ascii=False, sort_keys=True,
                           indent=2, allow_nan=False)+"\n").encode()
        manifest["feature_file_sha256"][filename] = sha256(data).hexdigest()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(prefix=".rank_inputs_", dir=output_dir.parent))
    try:
        for filename, doc in sorted(documents.items()):
            with (staging/filename).open("x", encoding="utf-8") as fh:
                json.dump(doc, fh, sort_keys=True, indent=2,
                          ensure_ascii=False, allow_nan=False)
                fh.write("\n")
        metadata = staging/"_meta"
        metadata.mkdir()
        with (metadata/"source_manifest.json").open("x", encoding="utf-8") as fh:
            json.dump(manifest, fh, sort_keys=True, indent=2,
                      ensure_ascii=False, allow_nan=False)
            fh.write("\n")
        if output_dir.is_symlink() or output_dir.exists():
            raise FileExistsError("Rank input output was created concurrently")
        os.rename(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        "status":"LOCAL_ASOF_RANK_INPUTS_RESEARCH_ONLY",
        "path":str(output_dir), "market":market,
        "generated_now_not_backdated":now.isoformat(),
        "eligible_documents":len(documents), "deferred":len(deferred),
        "source_hashes_recorded":True,
        "recomputed_from_readonly_offline_ledger":offline_ledger is not None,
        "recomputed_from_readonly_price_cache":price_witness is not None,
        "rechecked_price_rows":(price_witness["rechecked_selected_price_count"]
                                if price_witness else 0),
        "real_leader_prediction_certified":False,
        "official_leader_promotions":0,
    }
