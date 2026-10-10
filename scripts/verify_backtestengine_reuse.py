#!/usr/bin/env python3
"""Read-only local evidence probe for CycleOS-Lab_BacktestEngine reuse.

Only reads from the legacy folder; writes a small JSON report under EraLeader.
Run with the existing legacy .venv Python (pyarrow required).
This is a dataset/schema smoke test, NOT PIT compliance certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def parquet_info(path: Path, pq) -> dict:
    p = pq.ParquetFile(path)
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "rows": p.metadata.num_rows,
        "row_groups": p.metadata.num_row_groups,
        "columns": p.schema.names,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", default="/Volumes/T5DATA/CycleOS-Lab_BacktestEngine",
        help="The other project's data vault (always read-only)")
    parser.add_argument(
        "--out", default="/Volumes/T5DATA/eraleader/results/reuse_probe/local_assets_audit.json",
        help="Write report inside EraLeader only")
    args=parser.parse_args()
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("pyarrow is needed; try legacy .venv/bin/python") from exc

    root=Path(args.source)
    parquet_dir=root/"datasets/external_validation/marcap/data"
    if not parquet_dir.is_dir():
        raise SystemExit("Missing marcap directory: "+str(parquet_dir))
    years=sorted(parquet_dir.glob("marcap-????.parquet"))
    if len(years)<20:
        raise SystemExit("Unusually few local year files: "+str(len(years)))
    counts={int(p.stem.split("-")[1]):pq.ParquetFile(p).metadata.num_rows for p in years}
    stats_path=root/"datasets/external_validation/marcap/validation_summary.json"
    stats=json.loads(stats_path.read_text(encoding="utf-8"))
    report={
       "status":"PASSED_SCHEMA_METADATA_PROBE",
       "inspection_time_utc":datetime.now(timezone.utc).isoformat(),
       "source_root":str(root),
       "marcap":{
           "year_files":len(years), "first_year":min(counts),"last_year":max(counts),
           "metadata_row_count":sum(counts.values()),
           "existing_summary_row_count":stats.get("rows"),
           "existing_summary_unique_codes":stats.get("unique_codes"),
           "existing_summary_date_min":stats.get("date_min"),
           "existing_summary_date_max":stats.get("date_max"),
           "count_matches_existing_summary":sum(counts.values())==stats.get("rows"),
       },
       "parquet_samples":{},
       "existing_engine":{
           "strategy_code":"tools/backtest_mvp/grid_mom_rotation.py",
           "strategy_registry":"strategies/registry.json",
           "returns_cache":"cache/sector_returns_sp500_sectors_w_complete_2026-03-01.csv",
       },
       "limits":[
           "Manifest/metadata checks do not establish absence of survivorship or lookahead bias.",
           "Marcap historical prices have not been certified split/dividend adjusted.",
           "US weekly series built from 2026-03-01 constituents cannot directly serve as historic PIT universe.",
           "Corporate filings/EPS revision point-in-time history is not provided by these price files.",
           "Commercial distribution/reuse of externally sourced datasets requires source license checks.",
       ],
    }
    paths={
      "kr_daily_2025":parquet_dir/"marcap-2025.parquet",
      "kr_daily_2026":parquet_dir/"marcap-2026.parquet",
      "us_sp500_weekly":root/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet",
      "us_nasdaq100_weekly":root/"datasets/yf_us_stock_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet",
      "kr_stock_weekly":root/"datasets/yf_kr_stock_w_pq_Asia_Seoul_2026-03-01_SSOT/data.parquet",
    }
    for key,path in paths.items():
        if path.exists():
            info=parquet_info(path,pq)
            report["parquet_samples"][key]=info
            cols=info["columns"]
            if key.startswith("kr_daily_") and all(x in cols for x in ["Code","Date","Close"]):
                sample=pq.ParquetFile(path).iter_batches(batch_size=10, columns=["Code","Date","Close"])
                values=next(sample,None)
                if values is not None:
                    rows=values.to_pylist()
                    info["first_sample"]=[{"Code":str(z["Code"]),"Date":str(z["Date"]),
                                             "Close":float(z["Close"]) if z["Close"] is not None else None}
                                           for z in rows[:2]]
    if not report["marcap"]["count_matches_existing_summary"]:
        report["status"]="FAIL_METADATA_ROW_MISMATCH"
    output=Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Only report, no source data copies.
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
       "status":report["status"],
       "year_files":len(years),
       "marcap_rows":sum(counts.values()),
       "existing_summary_rows":stats.get("rows"),
       "sample_files":{k:v["rows"] for k,v in report["parquet_samples"].items()},
       "out":str(output),
    },ensure_ascii=False))
    if report["status"].startswith("FAIL"):
        raise SystemExit(2)

if __name__=="__main__":
    main()
