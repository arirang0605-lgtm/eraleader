"""ER-NC-04: prices create research theme lifecycle; news facts remain separate.

PIT theme IDs and members arrive read-only from ER-NC-03. No overwrite of
EraLeader leader scoring/state machine, no automatic trading/notifications.
"""
from __future__ import annotations
from datetime import date,datetime,timezone
from hashlib import sha256
import json
from math import isfinite
from statistics import mean


def _asof(ts):
    if type(ts) is not str:raise ValueError("Theme price as-of timestamp required")
    try:dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("Theme price bad timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Theme price timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _bars(rows,*,decision,through):
    if type(rows) is not list:raise ValueError("Market bars expected list")
    valid=[];last=None
    for item in rows:
        session=date.fromisoformat(item["session"])
        if last is not None and session<=last:
            raise ValueError("Theme price sessions not strictly chronological")
        last=session
        seen=_asof(item["available_at"])
        if session>through or seen>decision:
            continue
        close=item["close"];turnover=item["turnover"]
        if (type(close) not in (int,float) or type(turnover) not in (int,float) or
                not isfinite(close) or not isfinite(turnover) or
                close<=0 or turnover<0):
            raise ValueError("Theme price invalid close/turnover")
        valid.append({"session":session,"close":float(close),
                      "turnover":float(turnover)})
    return valid


def _ret(history,period):
    return history[-1]["close"]/history[-period-1]["close"]-1


def _snapshot_digest(payload):
    return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),
                             allow_nan=False,ensure_ascii=False).encode()).hexdigest()


def assess_theme_lifecycle(*,theme_record:dict,decision_at:str,
                           market_session:str,security_bars:dict,
                           benchmark_bars:list[dict],
                           news_context:dict|None=None,
                           history:list[dict]|None=None) -> dict:
    """As-of 5/20/60 RS, 20/60 breadth, turnover and episode research."""
    now=_asof(decision_at)
    day=date.fromisoformat(market_session)
    theme_id=theme_record.get("theme_id")
    if not isinstance(theme_id,str) or not theme_id:
        raise ValueError("Theme stable ID required")
    if _asof(theme_record["available_at"])>now:
        raise ValueError("Future PIT theme membership used")
    base={"schema":"eraleader.er_nc_theme_lifecycle.v1","theme_id":theme_id,
          "as_of":now.isoformat(),"market_session":market_session,
          "state":"UNKNOWN","episode_id":None,"reason_codes":[],
          "features":{},"research_only":True,"official_leaders":0,
          "catalyst_state":(news_context.get("catalyst_state","UNKNOWN")
                            if type(news_context) is dict else "UNKNOWN_NOT_COLLECTED"),
          "catalyst_is_separate_from_price_state":True}
    members=theme_record.get("members",[])
    if not isinstance(members,list) or len(members)<3:
        base["reason_codes"]=["TOO_FEW_PIT_CLASS_MEMBERS"]
        return base
    if type(security_bars) is not dict:
        base["reason_codes"]=["SECURITY_PRICE_HISTORY_UNAVAILABLE"]
        return base
    benchmark=_bars(benchmark_bars,decision=now,through=day)
    if len(benchmark)<150 or benchmark[-1]["session"]!=day:
        base["reason_codes"]=["BENCHMARK_PIT_PRICE_HISTORY_INCOMPLETE"]
        return base
    panel={};sec_ids=set()
    for member in members:
        sec=member.get("member_security_id")
        if not isinstance(sec,str) or not sec or sec in sec_ids:
            base["reason_codes"]=["PIT_SECURITY_CLASS_MISSING_OR_DUPLICATE"]
            return base
        if _asof(member["member_first_known_at"])>now:
            base["reason_codes"]=["FUTURE_THEME_MEMBER"]
            return base
        sec_ids.add(sec)
        hist=_bars(security_bars.get(sec),decision=now,through=day) if sec in security_bars else []
        if len(hist)<150 or hist[-1]["session"]!=day:
            base["reason_codes"]=["MISSING_MEMBER_PRICE_ASOF"]
            return base
        if [b["session"] for b in hist[-150:]] != [b["session"] for b in benchmark[-150:]]:
            base["reason_codes"]=["MEMBER_BENCHMARK_SESSIONS_NOT_ALIGNED"]
            return base
        panel[sec]=hist
    if all(not hist[-1]["turnover"] for hist in panel.values()):
        base["reason_codes"]=["FULL_THEME_TRADING_HALT"]
        return base
    ret5=mean(_ret(history,5) for history in panel.values())
    ret20=mean(_ret(history,20) for history in panel.values())
    ret60=mean(_ret(history,60) for history in panel.values())
    bret={p:_ret(benchmark,p) for p in (5,20,60)}
    breadth20=mean(hist[-1]["close"]>mean(x["close"] for x in hist[-20:])
                   for hist in panel.values())
    breadth60=mean(hist[-1]["close"]>mean(x["close"] for x in hist[-60:])
                   for hist in panel.values())
    latest_turnover=sorted((sum(x["turnover"] for x in hist[-5:])
                             for hist in panel.values()),reverse=True)
    latest=sum(latest_turnover)
    prior=sum(sum(x["turnover"] for x in hist[-65:-5])
              for hist in panel.values())/60*5
    if prior<=0:
        base["reason_codes"]=["NO_VALID_60_SESSION_TURNOVER_BASELINE"]
        return base
    ratio=latest/prior
    concentration=(sum(latest_turnover[:3])/latest if latest>0 else None)
    leaders=[]
    for sec,hist in panel.items():
        leaders.append({"security_id":sec,
                        "return_20":round(_ret(hist,20),6),
                        "above_ma150":hist[-1]["close"]>mean(x["close"] for x in hist[-150:]),
                        "drawdown_from_26session_high":round(
                            hist[-1]["close"]/max(x["close"] for x in hist[-26:])-1,6)})
    leaders.sort(key=lambda x:(-x["return_20"],x["security_id"]))
    top=leaders[:3]
    rs={p:round(v-bret[p],6) for p,v in ((5,ret5),(20,ret20),(60,ret60))}
    features={"return_5":round(ret5,6),"return_20":round(ret20,6),
              "return_60":round(ret60,6),"rs_excess_5":rs[5],
              "rs_excess_20":rs[20],"rs_excess_60":rs[60],
              "breadth_above_ma20":round(breadth20,6),
              "breadth_above_ma60":round(breadth60,6),
              "turnover_5_over_prior60_average":round(ratio,6),
              "turnover_top3_concentration":round(concentration,6)
                      if concentration is not None else None,
              "top_candidate_trends":top,"member_count":len(panel)}
    base["features"]=features
    prev=(history or [])[-1] if history else None
    if prev is not None:
        if (prev.get("theme_id")!=theme_id or
                _asof(prev["as_of"])>=now or
                prev.get("episode_id") is None):
            raise ValueError("Theme episode provenance/order invalid")
    rise=rs[20]>=0.06 and ratio>=1.5 and breadth20>=0.6
    dormant=rs[60]<=-0.08 and ratio<0.75 and breadth20<0.4
    weakening=rs[20]<-0.04 and (ratio<1 or breadth20<0.5)
    consolidation=abs(rs[20])<0.05 and ratio<=1.35
    if rise:
        state="REACTIVATING" if prev and prev["state"]=="DORMANT" else "RISING"
    elif dormant:state="DORMANT"
    elif weakening:state="WEAKENING"
    elif consolidation:state="CONSOLIDATING"
    elif rs[20]>0 and ratio>1.05:state="EMERGING"
    else:state="UNKNOWN"
    base["state"]=state
    base["reason_codes"]=[{
        "RISING":"PRICE_RS_TURNOVER_BREADTH_ACCELERATION",
        "REACTIVATING":"DORMANT_THEME_NEW_PRICE_EPISODE",
        "DORMANT":"PIT_MEMBER_PRICE_ACTIVITY_DORMANT",
        "WEAKENING":"RS_AND_PARTICIPATION_WEAKENING",
        "CONSOLIDATING":"RANGE_WITH_REDUCED_TURNOVER",
        "EMERGING":"EARLY_PRICE_STRENGTH_RESEARCH",
        "UNKNOWN":"CONFLICTING_THEME_PRICE_EVIDENCE"}[state]]
    # A new episode begins only on reactivation or the first explicit event;
    # otherwise retain the last episode ID. No hindsight period relabeling.
    start_new=prev is None or state=="REACTIVATING"
    base["episode_id"]=(sha256(f"{theme_id}|{market_session}|{state}".encode()).hexdigest()[:20]
                        if start_new else prev["episode_id"])
    base["episode_is_new"]=start_new
    base["source_sha256"]=_snapshot_digest({
        "theme_id":theme_id,"market_session":market_session,
        "features":features,"state":state,"previous_episode_id":(
            prev["episode_id"] if prev else None)})
    base["universe_pit_independently_certified"]=False
    base["quality_status"]="PRICE_RESEARCH_WITH_PARTIAL_ISSUER_CLASS_PROVENANCE"
    return base


class ThemeEpisodeStore:
    """Independent, append-only *research* history (never modifies PIT/WATCH DB)."""

    def __init__(self, path):
        import sqlite3
        from pathlib import Path
        path=Path(path)
        if not path.is_absolute() or path.is_symlink() or path.suffix!=".sqlite":
            raise ValueError("Theme episode store requires absolute nonlinked .sqlite")
        if not path.parent.is_dir():
            raise ValueError("Theme episode parent directory unavailable")
        self.path=path
        self.con=sqlite3.connect(str(path),timeout=10)
        self.con.execute("""CREATE TABLE IF NOT EXISTS research_theme_episodes(
            theme_id TEXT NOT NULL, as_of TEXT NOT NULL, market_session TEXT NOT NULL,
            episode_id TEXT NOT NULL, state TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(theme_id,as_of))""")
        self.con.commit()

    def close(self):
        self.con.close()

    def append(self, observation:dict)->bool:
        required={"theme_id","as_of","market_session","episode_id", "state",
                  "source_sha256","research_only","official_leaders"}
        if (type(observation) is not dict or not required.issubset(observation) or
                observation["state"] not in {"EMERGING","RISING","CONSOLIDATING",
                         "WEAKENING","DORMANT","REACTIVATING","UNKNOWN"} or
                observation["research_only"] is not True or
                observation["official_leaders"]!=0):
            raise ValueError("Uncertified theme observations only")
        at=_asof(observation["as_of"])
        if type(observation["source_sha256"]) is not str or len(observation["source_sha256"])!=64:
            raise ValueError("Theme observation requires SHA256")
        payload=json.dumps(observation,sort_keys=True,separators=(",",":"),allow_nan=False)
        latest=self.con.execute("SELECT as_of FROM research_theme_episodes WHERE theme_id=? ORDER BY as_of DESC LIMIT 1",
                                (observation["theme_id"],)).fetchone()
        prior=self.con.execute("SELECT payload FROM research_theme_episodes WHERE theme_id=? AND as_of=?",
                                (observation["theme_id"],observation["as_of"])).fetchone()
        if prior is not None:
            if prior[0]!=payload:raise ValueError("Theme episode immutable as-of conflict")
            return False
        if latest is not None and _asof(latest[0])>=at:
            raise ValueError("Theme episode historical backfill after later observation")
        # Market state must not be retroactively published as a prior-day live signal.
        if date.fromisoformat(observation["market_session"])>at.date():
            raise ValueError("Theme future market session")
        self.con.execute("INSERT INTO research_theme_episodes VALUES(?,?,?,?,?,?,?)",
                         (observation["theme_id"],observation["as_of"],
                          observation["market_session"],observation["episode_id"],
                          observation["state"],observation["source_sha256"],payload))
        self.con.commit()
        return True

    def history(self, theme_id:str, *, as_of:str)->list[dict]:
        now=_asof(as_of)
        rows=self.con.execute("SELECT payload FROM research_theme_episodes WHERE theme_id=? AND as_of<=? ORDER BY as_of",
                              (theme_id,now.isoformat())).fetchall()
        return [json.loads(row[0]) for row in rows]
