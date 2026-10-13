"""ER-NC-07 original-author rule provenance research gate (no trading)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "author_rule_registry_v1"
OWNERS = {
    "N_ST": ("남석관", "SHORT"),
    "N_MT": ("남석관", "MEDIUM"),
    "Y_ST": ("유목민", "SHORT"),
    "Y_MT": ("유목민", "MEDIUM"),
}
REQUIRED = {
    "rule_id", "strategy_id", "author", "source_title", "source_location",
    "observed_publication_date", "time_frame", "selection_rule", "entry_rule",
    "exit_rule", "stop_rule", "market_handling", "exact_parameter",
    "evidence_status", "ambiguity_note", "strategy_version",
}
EVIDENCE_STATES = {"NOT_VERIFIED", "PARTIALLY_VERIFIED", "PRIMARY_VERIFIED"}


class RuleContractError(ValueError):
    """Rule input must not cause an unverified trading decision."""


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuleContractError("duplicate JSON field")
        result[key] = value
    return result


def _utc(value: str | datetime, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuleContractError("invalid " + field) from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RuleContractError(field + " must include timezone")
    return value.astimezone(timezone.utc)


def _publication(record: Mapping[str, Any]) -> date:
    try:
        return date.fromisoformat(record["observed_publication_date"])
    except (ValueError, TypeError, KeyError) as exc:
        raise RuleContractError("invalid publication date") from exc


class AuthorRuleRegistry:
    """Immutable source/version records; never executes text supplied as a rule."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._entries: dict[tuple[str, str], dict[str, Any]] = {}
        self._hashes: dict[tuple[str, str], str] = {}
        for row in records or []:
            if not isinstance(row, dict) or REQUIRED - row.keys():
                raise RuleContractError("incomplete or invalid rule record")
            strategy = row["strategy_id"]
            if strategy not in OWNERS:
                raise RuleContractError("excluded or unknown author strategy")
            if (row["author"], row["time_frame"]) != OWNERS[strategy]:
                raise RuleContractError("wrong author or timeframe")
            if row["evidence_status"] not in EVIDENCE_STATES:
                raise RuleContractError("invalid evidence state")
            for field in ("rule_id", "strategy_version"):
                if not isinstance(row[field], str) or not row[field].strip():
                    raise RuleContractError("invalid " + field)
            for field in ("source_title", "source_location", "selection_rule",
                          "entry_rule", "exit_rule", "stop_rule", "market_handling",
                          "ambiguity_note"):
                if not isinstance(row[field], str):
                    raise RuleContractError("invalid string field: " + field)
            if not isinstance(row["exact_parameter"], (str, dict)):
                raise RuleContractError("invalid exact_parameter")
            _publication(row)
            for field in ("verified_at", "available_at", "first_seen_at"):
                if row.get(field) is not None:
                    _utc(row[field], field)
            digest = hashlib.sha256(json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            key = (row["rule_id"], row["strategy_version"])
            if key in self._hashes and self._hashes[key] != digest:
                raise RuleContractError("conflicting same rule ID and revision")
            self._hashes[key] = digest
            self._entries[key] = dict(row)

    @classmethod
    def from_file(cls, path: str | Path) -> "AuthorRuleRegistry":
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise RuleContractError("missing or symlink rule registry")
        if path.stat().st_size > 2_000_000:
            raise RuleContractError("oversized rule registry")
        try:
            payload = json.loads(path.read_bytes(), object_pairs_hook=_pairs_unique)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuleContractError("invalid registry JSON") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA:
            raise RuleContractError("unsupported registry schema")
        if not isinstance(payload.get("rules"), list):
            raise RuleContractError("rules must be a list")
        return cls(payload["rules"])

    def for_strategy(self, strategy: str) -> tuple[dict[str, Any], ...]:
        if strategy not in OWNERS:
            raise RuleContractError("unknown strategy")
        return tuple(dict(self._entries[key]) for key in sorted(self._entries)
                     if self._entries[key]["strategy_id"] == strategy)


@dataclass(frozen=True)
class StrategyAssessment:
    strategy_id: str
    author: str
    time_frame: str
    as_of: str
    status: str
    reason_codes: tuple[str, ...]
    executable: bool = False
    trade_permission: str = "NO_ORDER"
    research_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id, "author": self.author,
            "time_frame": self.time_frame, "as_of": self.as_of,
            "status": self.status, "reason_codes": list(self.reason_codes),
            "executable": self.executable, "trade_permission": self.trade_permission,
            "research_only": self.research_only,
        }


class AuthorStrategyResearch:
    """Independent author/timeframe gate; no order, prediction, or inferred stops."""

    def __init__(self, strategy_id: str, registry: AuthorRuleRegistry | None = None):
        if strategy_id not in OWNERS:
            raise RuleContractError("unknown author/timeframe")
        self.strategy_id = strategy_id
        self.registry = registry if registry is not None else AuthorRuleRegistry()

    def evaluate(
        self, pit_context: Mapping[str, Any] | None,
        market_context: Mapping[str, Any] | None,
        catalyst_context: Mapping[str, Any] | None,
        as_of: str | datetime,
    ) -> StrategyAssessment:
        decision = _utc(as_of, "as_of")
        codes: list[str] = []
        unknown = False
        for label, context in (("PIT", pit_context), ("MARKET", market_context),
                               ("CATALYST", catalyst_context)):
            if context is None:
                continue
            if not isinstance(context, Mapping):
                raise RuleContractError(label + " must be mapping")
            avail = context.get("available_at")
            if avail is None:
                codes.append(label + "_AVAILABILITY_UNVERIFIED")
                unknown = True
            elif _utc(avail, label + "_available_at") > decision:
                codes.append(label + "_FUTURE_INPUT_BLOCKED")
                unknown = True
        entries = self.registry.for_strategy(self.strategy_id)
        if not entries:
            codes.append("ORIGINAL_SOURCE_RULES_MISSING")
        for row in entries:
            if _publication(row) > decision.date():
                codes.append("SOURCE_NOT_PUBLIC_AT_ASOF")
                unknown = True
            for field in ("first_seen_at", "verified_at", "available_at"):
                if row.get(field) and _utc(row[field], field) > decision:
                    codes.append("SOURCE_NOT_OBSERVED_AT_ASOF")
                    unknown = True
            if row["evidence_status"] != "PRIMARY_VERIFIED":
                codes.append("ORIGINAL_RULE_EVIDENCE_UNVERIFIED")
            if any(not row[f].strip() for f in (
                "source_title", "source_location", "selection_rule",
                "entry_rule", "exit_rule", "stop_rule", "market_handling",
            )) or row["ambiguity_note"].strip():
                codes.append("ORIGINAL_RULE_AMBIGUOUS")
            if not row.get("source_sha256") or not row.get("verified_at"):
                codes.append("SOURCE_REVIEW_RECEIPT_MISSING")
        # Data-only contract: an author-specific, independently reviewed implementation
        # and synthetic PIT tests must be added BEFORE real SIGNAL becomes possible.
        codes.append("AUTHOR_IMPLEMENTATION_NOT_VALIDATED")
        author, frame = OWNERS[self.strategy_id]
        return StrategyAssessment(
            self.strategy_id, author, frame, decision.isoformat(),
            "UNKNOWN" if unknown else "NOT_READY", tuple(dict.fromkeys(codes)),
        )


def assess_all(
    registry: AuthorRuleRegistry | None,
    pit_context: Mapping[str, Any] | None,
    market_context: Mapping[str, Any] | None,
    catalyst_context: Mapping[str, Any] | None,
    as_of: str | datetime,
) -> dict[str, dict[str, Any]]:
    """Return four independent research statuses without altering existing WATCH."""
    return {key: AuthorStrategyResearch(key, registry).evaluate(
        pit_context, market_context, catalyst_context, as_of
    ).as_dict() for key in OWNERS}
