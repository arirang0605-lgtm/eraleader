"""ER-NC-03: immutable theme IDs and explicit as-of membership vintages.

NewsCatalystOS theme_hints are *proposals*, never market/security membership.
This catalog does not overwrite EraLeader issuer-lineage or WATCH tables.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
import re

ID=re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
RELATIONS={
    "DIRECT_CONTRACT","VERIFIED_SUPPLY_CHAIN",
    "VERIFIED_INDUSTRY_CLASSIFICATION","CO_MENTION",
    "UNVERIFIED_ASSOCIATION",
}
VERIFIED={"DIRECT_CONTRACT","VERIFIED_SUPPLY_CHAIN",
          "VERIFIED_INDUSTRY_CLASSIFICATION"}


def _id(value,label):
    if type(value) is not str or not ID.fullmatch(value):
        raise ValueError("Theme invalid "+label)
    return value


def _when(value):
    if type(value) is not str:
        raise ValueError("Theme date requires timestamp")
    try:dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("Theme timestamp invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Theme timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _member(value, *, published: datetime):
    if type(value) is not dict:
        raise ValueError("Theme malformed member")
    if not {"member_issuer_id","member_security_id","member_first_known_at",
            "member_effective_from","member_effective_to",
            "evidence_ids","relationship_type"}.issubset(value):
        raise ValueError("Theme member PIT identity/evidence incomplete")
    issuer=_id(value["member_issuer_id"],"issuer")
    sec=value["member_security_id"]
    if sec is not None:_id(sec,"permanent security/class")
    known=_when(value["member_first_known_at"])
    begin=_when(value["member_effective_from"])
    end=(_when(value["member_effective_to"])
         if value["member_effective_to"] is not None else None)
    if known<published or end is not None and end<begin:
        raise ValueError("Theme member chronology invalid")
    rel=value["relationship_type"]
    if rel not in RELATIONS:
        raise ValueError("Theme unknown relationship")
    evidence=value["evidence_ids"]
    if (type(evidence) is not list or len(evidence)>100 or
            any(type(x) is not str or not ID.fullmatch(x) for x in evidence)):
        raise ValueError("Theme member evidence invalid")
    if rel in VERIFIED and not evidence:
        raise ValueError("Theme verified relationship without source evidence")
    return value


def _catalog_item(value):
    required={"theme_id","taxonomy_version","theme_name","aliases",
              "parent_industry_id","created_at","available_at",
              "reclassified_at","members"}
    if type(value) is not dict or not required.issubset(value):
        raise ValueError("Theme required catalog fields missing")
    _id(value["theme_id"],"theme_id")
    _id(value["taxonomy_version"],"taxonomy_version")
    if type(value["theme_name"]) is not str or not 1<=len(value["theme_name"])<=128:
        raise ValueError("Theme name invalid")
    if value["parent_industry_id"] is not None:
        _id(value["parent_industry_id"],"parent industry")
    created=_when(value["created_at"])
    available=_when(value["available_at"])
    if created>available:
        raise ValueError("Theme vintage available before created")
    if value["reclassified_at"] is not None:
        classified=_when(value["reclassified_at"])
        if not created<=classified<=available:
            raise ValueError("Theme reclassification future leaked")
    aliases=value["aliases"]
    if type(aliases) is not list or len(aliases)>50:
        raise ValueError("Theme aliases invalid")
    seen=set()
    for alias in aliases:
        if (type(alias) is not dict or
                set(alias)!={"name","first_known_at"} or
                type(alias["name"]) is not str or not 1<=len(alias["name"])<=128):
            raise ValueError("Theme alias must carry first-known timestamp")
        if alias["name"] in seen:
            raise ValueError("Theme duplicate alias")
        seen.add(alias["name"])
        if _when(alias["first_known_at"])>available:
            # Newer alias must appear in its own later catalog revision.
            raise ValueError("Theme alias first known after catalog vintage")
    members=value["members"]
    if type(members) is not list or len(members)>10000:
        raise ValueError("Theme membership inventory invalid")
    seen_member=set()
    for member in members:
        _member(member,published=created)
        key=(member["member_issuer_id"],member["member_security_id"],
             member["member_effective_from"])
        if key in seen_member:
            raise ValueError("Theme duplicate membership observation")
        seen_member.add(key)
    return value


class ThemePITCatalog:
    """Per-theme versioned proposals; identity never inferred from ticker alone."""

    def __init__(self, versions: list[dict]):
        if type(versions) is not list or len(versions)>10000:
            raise ValueError("Theme vintages invalid")
        catalog: dict[str,list[dict]]={}
        for item in versions:
            checked=deepcopy(_catalog_item(item))
            group=catalog.setdefault(checked["theme_id"],[])
            if any(v["taxonomy_version"]==checked["taxonomy_version"] for v in group):
                raise ValueError("Theme taxonomy version collision")
            group.append(checked)
        for theme, histories in catalog.items():
            histories.sort(key=lambda x: _when(x["available_at"]))
            if any(_when(right["available_at"]) <= _when(left["available_at"])
                   for left,right in zip(histories,histories[1:])):
                raise ValueError("Theme revisions must have increasing available_at")
            initial=histories[0]["created_at"]
            if any(v["created_at"]!=initial for v in histories):
                raise ValueError("Theme immutable created_at changed across revisions")
        self._by_theme={t:tuple(v) for t,v in catalog.items()}

    def snapshot(self, as_of: str) -> dict:
        now=_when(as_of)
        output={}
        mapping_quality={"missing_permanent_class_id":0,
                         "unverified_relationship_count":0}
        for theme_id,histories in sorted(self._by_theme.items()):
            visible=[entry for entry in histories if _when(entry["available_at"])<=now
                     and _when(entry["created_at"])<=now]
            if not visible:
                continue
            current=visible[-1]
            eligible=[]
            for member in current["members"]:
                if (_when(member["member_first_known_at"])>now or
                        _when(member["member_effective_from"])>now or
                        member["member_effective_to"] is not None and
                        _when(member["member_effective_to"])<now):
                    continue
                if member["member_security_id"] is None:
                    mapping_quality["missing_permanent_class_id"]+=1
                    continue
                if member["relationship_type"] not in VERIFIED:
                    mapping_quality["unverified_relationship_count"]+=1
                    continue
                eligible.append(deepcopy(member))
            aliases=[a["name"] for a in current["aliases"]
                     if _when(a["first_known_at"])<=now]
            output[theme_id]={
                "theme_id":theme_id,"theme_name":current["theme_name"],
                "aliases":aliases,"parent_industry_id":current["parent_industry_id"],
                "taxonomy_version":current["taxonomy_version"],
                "available_at":current["available_at"],
                "created_at":current["created_at"],
                "members":eligible,"member_count":len(eligible),
                "issuer_class_pit_independently_certified":False,
                "research_only":True,
            }
        return {"schema":"eraleader.er_nc_theme_pit.v1",
                "as_of":now.isoformat(),"themes":output,
                "mapping_quality_report":mapping_quality,
                "historic_exchange_universe_pit_verified":False,
                "official_leaders":0,"research_only":True}

    def resolve_hint(self, hint: str, as_of: str) -> dict:
        """News hints can suggest *which* known theme to inspect, not add members."""
        if type(hint) is not str or not 1<=len(hint)<=128:
            raise ValueError("Theme hint invalid")
        asof=self.snapshot(as_of)
        found=[theme for theme in asof["themes"].values()
               if hint==theme["theme_name"] or hint in theme["aliases"]]
        return {"hint":hint, "as_of":asof["as_of"],
                "theme_ids":[t["theme_id"] for t in found],
                "status":("UNVERIFIED_THEME_HINT" if len(found)==1
                          else "AMBIGUOUS_THEME_HINT" if len(found)>1
                          else "NO_PIT_THEME_MATCH"),
                "auto_membership_changes":0,"official_leaders":0}
