"""Reuse original verified annual DART consolidated statements for WATCH margins.

This is a feature adapter: existing first-receipt DART -> real current annual
revenue/operating/net margin -> WATCH. NOT a 20pt moat or issuer PIT score.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import re

from .official_dart_corp_directory import verify_dart_corp_directory
from .official_dart_financials import parse_dart_financial, SCHEMA as FIN_SCHEMA
from .official_api_pit_bridge import _private_file

RESEARCH_SOURCE="DART_CFS_ANNUAL_TWO_YEAR_MARGIN_TREND_NOT_MOAT_V2"
MAX_ORIGINALS=700


def dart_annual_margin_context(*, market:dict, capture_root:Path, now:datetime)->dict[str,dict]:
    if (not capture_root.is_absolute() or capture_root.is_symlink() or
            any(p.is_symlink() for p in capture_root.parents) or
            not capture_root.is_dir() or capture_root.stat().st_uid!=os.geteuid()):
        raise ValueError("DART_MARGIN_PRIVATE_ROOT_REQUIRED")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DART_MARGIN_AWARE_CLOCK_REQUIRED")
    timestamp=now.astimezone(timezone.utc)
    codes={s["security_id"] for s in market["securities"]
           if s.get("current_dart_directory_matched") is True}
    directory_folders=list(capture_root.glob("dart_directory_*/first_receipt.json"))
    if len(directory_folders)!=1:
        raise ValueError("DART_MARGIN_ONE_CURRENT_DIRECTORY_REQUIRED")
    dir_folder=directory_folders[0].parent
    directory_pin=sha256(directory_folders[0].read_bytes()).hexdigest()
    verified_directory=verify_dart_corp_directory(
        dir_folder,directory_pin,decision_at=timestamp)
    directory=(dir_folder,directory_pin)
    receipt_files=list(capture_root.glob("dart_fin_*/first_receipt.json"))
    if len(receipt_files)>MAX_ORIGINALS:
        raise ValueError("DART_MARGIN_TOO_MANY_FIRST_RECEIPTS")
    latest={}
    for file in receipt_files:
        if file.is_symlink() or file.parent.is_symlink() or not file.is_file():
            raise ValueError("DART_MARGIN_FIRST_RECEIPT_SYMLINK")
        raw=file.read_bytes()
        if len(raw)>20000:
            raise ValueError("DART_MARGIN_FIRST_RECEIPT_OVERSIZE")
        data=json.loads(raw)
        code=data.get("stock_code")
        if (data.get("schema")!=FIN_SCHEMA or code not in codes or
                data.get("statement")!="CFS" or
                data.get("reprt_code")!="11011" or
                type(data.get("bsns_year")) is not int or
                data["bsns_year"]>timestamp.year):
            continue
        first=datetime.fromisoformat(data["first_local_received_at_utc"])
        if first.tzinfo is None or first.astimezone(timezone.utc)>timestamp:
            continue
        if verified_directory["mapping"].get(code)!=data.get("corp_code"):
            raise ValueError("DART_MARGIN_ISSUER_CROSSWALK_MISMATCH")
        year=data["bsns_year"]
        current=(-first.timestamp(),sha256(raw).hexdigest())
        key=(code,year)
        previous=latest.get(key)
        if previous is None or current>previous[0]:
            latest[key]=(current,file.parent)
    annual={}
    for (code,_year),(_sort,folder) in sorted(latest.items()):
        first_receipt=folder/"first_receipt.json"
        pin=sha256(first_receipt.read_bytes()).hexdigest()
        # Same verified DART first-receipt contract as the existing official
        # reader, but reuse the ONE already-validated full issuer directory
        # instead of decompressing the large XML once per company.
        receipt=_private_file(first_receipt,0o600)
        source=_private_file(folder/"raw_response.json",0o600)
        if sha256(receipt).hexdigest()!=pin:
            raise ValueError("DART_MARGIN_FIRST_RECEIPT_REVISED")
        metadata=json.loads(receipt)
        first=datetime.fromisoformat(metadata["first_local_received_at_utc"])
        if (first.tzinfo is None or first.astimezone(timezone.utc)>timestamp or
                metadata["stock_code"]!=code or
                verified_directory["mapping"].get(code)!=metadata["corp_code"] or
                metadata.get("source_directory_sha256")!=directory_pin or
                metadata.get("raw_sha256")!=sha256(source).hexdigest() or
                metadata.get("raw_length")!=len(source) or
                metadata.get("official_leaders")!=0 or
                metadata.get("statement")!="CFS" or
                metadata.get("reprt_code")!="11011"):
            raise ValueError("DART_MARGIN_ORIGINAL_RECEIPT_CONFLICT")
        financial=parse_dart_financial(
            source,corp_code=metadata["corp_code"],
            year=metadata["bsns_year"],report=metadata["reprt_code"],
            statement=metadata["statement"])
        if (financial["financial_rows"]!=metadata["reported_row_count"] or
                financial["status"]!=metadata["financial_quality"] or
                financial["report_accessions"]!=metadata["report_accessions"] or
                len(financial["metrics"])!=metadata["observed_account_count"] or
                {f.name for f in folder.iterdir()}!={"raw_response.json","first_receipt.json"}):
            raise ValueError("DART_MARGIN_ORIGINAL_BODY_CONFLICT")
        original={**financial,"stock_code":code,"corp_code":metadata["corp_code"],
                  "year":metadata["bsns_year"],"statement":"CFS",
                  "first_local_received_at_utc":first.isoformat()}
        if original["year"]>timestamp.year:
            raise ValueError("DART_MARGIN_FINANCIAL_IDENTITY_MISMATCH")
        revenue=original["metrics"].get("revenue",{}).get("value")
        op=original["metrics"].get("operating_income",{}).get("value")
        net=original["metrics"].get("net_income",{}).get("value")
        def margin(v):
            if revenue is None or type(revenue) is not int or revenue<=0 or v is None:
                return None
            if type(v) is not int:
                raise ValueError("DART_MARGIN_INVALID_AMOUNT")
            pct=100*v/revenue
            if not math.isfinite(pct):
                raise ValueError("DART_MARGIN_NONFINITE")
            return round(pct,4)
        operating_pct=margin(op)
        net_pct=margin(net)
        if operating_pct is None and net_pct is None:
            continue
        annual.setdefault(code,{})[original["year"]]={
            "dart_latest_cfs_business_year":original["year"],
            "dart_cfs_revenue_krw":revenue,
            "dart_cfs_operating_income_krw":op,
            "dart_cfs_net_income_krw":net,
            "dart_cfs_operating_margin_pct":operating_pct,
            "dart_cfs_net_margin_pct":net_pct,
            "dart_cfs_first_receipt_sha256":pin,
            "dart_cfs_first_received_at_utc":original["first_local_received_at_utc"],
            "dart_cfs_issuer_corp_code":original["corp_code"],
            "dart_cfs_margin_source":RESEARCH_SOURCE,
            "dart_cfs_independent_pit_certified":False,
        }
    output={}
    for code,years in sorted(annual.items()):
        newest_year=max(years)
        current=years[newest_year]
        preceding=years.get(newest_year-1)
        operating_old=(preceding["dart_cfs_operating_margin_pct"]
                       if preceding is not None else None)
        net_old=(preceding["dart_cfs_net_margin_pct"]
                 if preceding is not None else None)
        operating_new=current["dart_cfs_operating_margin_pct"]
        net_new=current["dart_cfs_net_margin_pct"]
        current.update({
            "dart_previous_cfs_business_year":newest_year-1 if preceding else None,
            "dart_previous_cfs_operating_margin_pct":operating_old,
            "dart_previous_cfs_net_margin_pct":net_old,
            "dart_cfs_operating_margin_change_pp":(
                round(operating_new-operating_old,4)
                if operating_old is not None and operating_new is not None else None),
            "dart_cfs_net_margin_change_pp":(
                round(net_new-net_old,4)
                if net_old is not None and net_new is not None else None),
            "dart_cfs_operating_margin_positive_two_years":(
                operating_old>0 and operating_new>0
                if operating_old is not None and operating_new is not None else None),
            "dart_cfs_previous_first_receipt_sha256":(
                preceding["dart_cfs_first_receipt_sha256"] if preceding else None),
            "dart_cfs_previous_first_received_at_utc":(
                preceding["dart_cfs_first_received_at_utc"] if preceding else None),
            "dart_cfs_two_year_comparable":preceding is not None,
        })
        output[code]=current
    return output
