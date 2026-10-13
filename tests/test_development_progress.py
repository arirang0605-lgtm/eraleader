"""EraLeader 30-ID acceptance progress: deterministic, honest and fail-closed."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader.development_progress import (
    acceptance_progress, render_html, render_markdown, AS_OF, _checked,
)
from scripts.publish_development_progress import publish


def test_all_thirty_id_scoring_is_arithmetically_reproducible():
    report=acceptance_progress()
    assert report["earned"]==45
    assert report["possible"]==120
    assert report["exact_percent"]==37.5
    assert report["display_percent"]==38
    assert [p["earned"] for p in report["stages"]]==[7,10,7,6,5,10]
    assert len(report["stages"])==6
    assert len({row["work_id"] for p in report["stages"] for row in p["tasks"]})==30
    assert sum(len(p["tasks"]) for p in report["stages"])==30
    assert [row["work_id"] for p in report["stages"] for row in p["tasks"]] == [
        f"{phase}_{i}" for phase in range(1,7) for i in range(1,6)
    ]


def test_no_fake_PIT_certification_or_future_leader_hindsight():
    report=acceptance_progress()
    assert report["official_composite_leader_ranking_ready"] is False
    assert report["future_leader_accuracy_certified"] is False
    assert report["real_continuous_20_session_operation_verified"] is False
    assert all(row["accepted_gates"]<=2
               for stage in report["stages"] for row in stage["tasks"])
    assert [row["accepted_gates"] for stage in report["stages"]
            for row in stage["tasks"] if row["work_id"]=="1_3"]==[0]


def test_html_and_md_describe_true_limitations_not_99_percent():
    report=acceptance_progress()
    html=render_html(report)
    md=render_markdown(report)
    assert "38%" in html and "37.5%" in html
    assert "**37.5%" in md
    assert "종전 99%" in html
    assert "30개" in html and "120점" in html
    assert "전향적 성능 N/A" in html
    assert "2026-10-13" in md
    assert "1_1" in md and "6_5" in md
    assert report["evidence_sha256"] in md


def test_progress_snapshot_SHA_tamper_blocks_rendering():
    report=acceptance_progress()
    changed=deepcopy(report)
    changed["stages"][0]["tasks"][0]["accepted_gates"]=4
    with pytest.raises(ValueError,match="SHA witness"):
        render_html(changed)
    changed2=deepcopy(report)
    changed2["official_composite_leader_ranking_ready"]=True
    with pytest.raises(ValueError,match="SHA witness"):
        render_markdown(changed2)


def make_site(tmp_path):
    site=tmp_path/"research"/"site"
    site.mkdir(parents=True)
    before={}
    for page,label in (("index.html","연구 메인"),("kr.html","시장 순위")):
        path=site/page
        body=f"<!doctype html><html lang='ko'><body><h1>{label}</h1></body></html>".encode()
        path.write_bytes(body)
        before[page]=body
    docs=tmp_path/"docs"
    docs.mkdir()
    return site,docs/"140_NEW_PROGRESS.md",before


def test_publish_new_progress_sidecar_and_navigation_without_changing_rank(tmp_path):
    site,doc,old=make_site(tmp_path)
    result=publish(site,doc)
    assert result["status"].startswith("PROGRESS_HUMAN_REVIEWED")
    assert result["exact_percent"]==37.5
    assert doc.is_file()
    manifest=site.parent/"development_progress_20261013.json"
    assert manifest.is_file()
    assert json.loads(manifest.read_bytes())["earned"]==45
    page=site/"development_progress_20261013.html"
    assert "38%" in page.read_text()
    assert "development_progress_20261013.html" in (site/"index.html").read_text()
    assert "development_progress_20261013.html" in (site/"kr.html").read_text()
    for name,content in old.items():
        new=(site/name).read_bytes()
        assert content.split(b"</body>")[0] in new
        assert new.endswith(b"</body></html>")


def test_rerun_never_overwrites_progress_or_existing_dashboard(tmp_path):
    site,doc,_=make_site(tmp_path)
    publish(site,doc)
    first={path:path.read_bytes() for path in (
        doc,site/"development_progress_20261013.html",
        site/"index.html",site/"kr.html")}
    with pytest.raises(ValueError):
        publish(site,doc)
    assert all(path.read_bytes()==before for path,before in first.items())


def test_invalid_existing_site_rejected_before_generating_files(tmp_path):
    site,doc,_=make_site(tmp_path)
    (site/"kr.html").write_text("<html>no complete body</html>")
    with pytest.raises(ValueError,match="Invalid existing dashboard page|template mismatch"):
        publish(site,doc)
    assert not doc.exists()
    assert not (site/"development_progress_20261013.html").exists()


def test_symlinked_research_site_fails_closed(tmp_path):
    site,doc,_=make_site(tmp_path)
    linked=tmp_path/"fake"
    linked.symlink_to(site,target_is_directory=True)
    with pytest.raises(ValueError):
        publish(linked,doc)
    assert not doc.exists()
