#!/usr/bin/env python3
"""Fast offline validation for an EraLeader new-chat handoff.

Does not read large datasets, use the network, change remote projects, or rerun backtests.
Run: python3 scripts/check_handoff.py
"""
from __future__ import annotations
from pathlib import Path
from xml.etree import ElementTree
import json
import re
import struct
import sys
import unicodedata

root=Path(__file__).resolve().parents[1]
required=[
 "START_HERE_NEXT_CHAT.md","AGENTS.md","PROJECT_STATE.md","DECISIONS.md","README.md",
 "docs/21_MASTER_ARCHITECTURE_NUMBERING.md",
 "docs/23_BACKTESTENGINE_LOCAL_REUSE.md",
 "docs/24_ARCHITECTURE_GAP_REVIEW.md",
 "docs/25_NEXT_IMPLEMENTATION_SPRINT.md",
 "scripts/verify_backtestengine_reuse.py",
 "scripts/read_cached_marcap.py",
 "results/reuse_probe/local_assets_audit.json",
 "results/reuse_probe/marcap_sample_query.json",
 "results/reuse_probe/sector_mom_baseline_one_config.csv",
 "docs/28_OFFLINE_PIT_FEATURE_IMPLEMENTATION.md",
 "src/eraleader/offline_pit.py",
 "src/eraleader/offline_features.py",
 "tests/test_offline_pit.py",
 "tests/fixtures/offline_synthetic.json",
 "docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md",
 "src/eraleader/research.py",
 "src/eraleader/state_history.py",
 "src/eraleader/discovery_metrics.py",
 "tests/test_research.py",
 "tests/test_state_history.py",
 "tests/test_discovery_metrics.py",
 "docs/30_WALKFORWARD_LOCAL_BATCH.md",
 "src/eraleader/walkforward.py",
 "src/eraleader/batch.py",
 "tests/test_walkforward.py",
 "tests/test_batch.py",
 "docs/31_CORPORATE_ACTION_AND_UNIVERSE_AUDIT.md",
 "src/eraleader/corporate_returns.py",
 "src/eraleader/universe_audit.py",
 "tests/test_corporate_returns.py",
 "tests/test_universe_audit.py",
 "tests/fixtures/corporate_split_dividend_synthetic.json",
]
errors=[]
for name in required:
    p=root/name
    if not p.is_file() or p.stat().st_size==0: errors.append("Missing/empty: "+name)
for name in ["README.md","START_HERE_NEXT_CHAT.md","docs/24_ARCHITECTURE_GAP_REVIEW.md",
             "docs/25_NEXT_IMPLEMENTATION_SPRINT.md","docs/21_MASTER_ARCHITECTURE_NUMBERING.md"]:
    p=root/name
    if not p.exists():continue
    links=re.findall(r"\]\(([^)]+)\)",p.read_text(encoding="utf-8"))
    for link in links:
        if link.startswith(("http://","https://","mailto:","#")):continue
        target=link.split("#",1)[0]
        if not (p.parent/target).exists():errors.append(f"Broken link: {name} -> {link}")
master=root/"EraLeader_전체설계도_1-6단계_세부번호.svg"
png=root/"EraLeader_전체설계도_1-6단계_세부번호.png"
if master.exists():
    ElementTree.parse(master)
    content=master.read_text(encoding="utf-8")
    for i in range(1,7):
        for j in range(1,6):
            if f">{i}_{j}<" not in content:errors.append(f"Missing work ID: {i}_{j}")
if png.exists():
    with png.open("rb") as f: b=f.read(24)
    if b[:8]!=b"\x89PNG\r\n\x1a\n" or struct.unpack(">II",b[16:24])!=(3240,2600):
        errors.append("Master image invalid or wrong resolution")
else:errors.append("Missing master PNG")
if (root/"results/reuse_probe/local_assets_audit.json").exists():
    audit=json.loads((root/"results/reuse_probe/local_assets_audit.json").read_text())
    if audit.get("marcap",{}).get("metadata_row_count")!=15_648_407:
        errors.append("Cached data proof differs from verified row count")
if not (root/"START_HERE_NEXT_CHAT.md").read_text().startswith("# START HERE"):
    errors.append("Invalid handoff entry point")
state_top = "\n".join((root/"PROJECT_STATE.md").read_text().splitlines()[:24])
if "## 최상위 목표" not in state_top or "## 최신 스냅샷" not in state_top:
    errors.append("Goal and latest snapshot not visible near top of state file")
images=[p for p in root.iterdir() if p.is_file() and not p.name.startswith("._")]
png_count=sum(p.suffix==".png" for p in images)
svg_count=sum(p.suffix==".svg" for p in images)
if (png_count,svg_count)!=(7,7):errors.append(f"Unexpected image inventory: {png_count} PNG, {svg_count} SVG")
print(json.dumps({
 "handoff": "PASS" if not errors else "FAIL",
 "required_files_checked":len(required),
 "numbered_work_items":30,
 "master_image_px":"3240x2600",
 "visual_inventory":{"png":png_count,"svg":svg_count},
 "project_git_initialized":(root/".git").exists(),
 "legacy_cache_online":Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine").is_dir(),
 "errors":errors[:12],
},ensure_ascii=False))
sys.exit(1 if errors else 0)
