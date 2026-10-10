#!/usr/bin/env python3
"""EraLeader proof-of-reuse: query an existing Korean Parquet price cache.

The source folder is read-only; no download, no mutation, no network.
Use only for input/data validation. This does NOT establish full PIT
validity, corporate-action adjusted performance, or a tradeable strategy.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path

DEFAULT_ROOT="/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"

def load_cached_prices(root: Path, code: str, first: date, last: date) -> list[dict]:
    import pyarrow.dataset as ds
    if first>last:raise ValueError("start date after end date")
    code=code.strip()
    if code.isdigit():code=code.zfill(6)
    records=[]
    for y in range(first.year,last.year+1):
        path=root/f"datasets/external_validation/marcap/data/marcap-{y}.parquet"
        if not path.exists():raise FileNotFoundError(f"Local cache missing: {path}")
        dataset=ds.dataset(str(path),format="parquet")
        predicate=(
          (ds.field("Code")==code) &
          (ds.field("Date")>=datetime.combine(first,datetime.min.time())) &
          (ds.field("Date")<=datetime.combine(last,datetime.min.time()))
        )
        cols=["Code","Name","Market","Date","Open","High","Low","Close","Volume","Amount","Marcap"]
        part=dataset.to_table(filter=predicate,columns=cols)
        for row in part.to_pylist():
            row["Date"]=str(row["Date"])[:10]
            records.append(row)
    records.sort(key=lambda z:z["Date"])
    if len(records)!=len({v["Date"] for v in records}):
        raise ValueError("duplicate security+Date; stop before merging into PIT store")
    return records

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--code",default="005930")
    p.add_argument("--start",default="2025-01-02")
    p.add_argument("--end",default="2025-01-31")
    p.add_argument("--source",default=os.environ.get("ERALEADER_LEGACY_ROOT",DEFAULT_ROOT))
    p.add_argument("--out",default="/Volumes/T5DATA/eraleader/results/reuse_probe/marcap_sample_query.json")
    args=p.parse_args()
    first=date.fromisoformat(args.start);last=date.fromisoformat(args.end)
    r=load_cached_prices(Path(args.source),args.code,first,last)
    if not r:raise SystemExit("NO_LOCAL_ROWS")
    report={
       "status":"OK_READ_ONLY_CACHED_DATA",
       "security_code":str(args.code).zfill(6),
       "range_requested":[args.start,args.end],"rows":len(r),
       "first_observed_date":r[0]["Date"],"last_observed_date":r[-1]["Date"],
       "first_row":r[0],"last_row":r[-1],
       "source": "FinanceData/marcap cached yearly Parquet",
       "adjustment_status":"UNVERIFIED",
       "point_in_time_quality":"PRICE_OBSERVATION_ONLY_NOT_PIT_CERTIFIED",
       "source_root":str(args.source),
    }
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"code":report["security_code"],
                       "rows":len(r),"first":r[0]["Date"],"last":r[-1]["Date"],
                       "output":str(out)},ensure_ascii=False))
if __name__=="__main__":
    main()
