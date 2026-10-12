"""DART corporation directory ZIP parser/capture/sha gate, fake bytes only."""
from datetime import datetime,timezone
from zipfile import ZipFile
from pathlib import Path
from io import BytesIO
from hashlib import sha256
import pytest

from eraleader.official_dart_corp_directory import (
  parse_directory_zip,capture_dart_corp_directory,verify_dart_corp_directory,
  match_krx_codes,
)

NOW=datetime(2026,10,12,12,0,tzinfo=timezone.utc)
KEY={"ERALEADER_DART_API_KEY":"A"*40}


def archive(lines,filename="CORPCODE.xml"):
 b=BytesIO()
 payload=("<result>"+"".join(lines)+"</result>").encode()
 with ZipFile(b,"w") as z:z.writestr(filename,payload)
 return b.getvalue()


def item(corp,code,stamp="20261012"):
 return f"<list><corp_code>{corp}</corp_code><stock_code>{code}</stock_code><modify_date>{stamp}</modify_date></list>"


def test_directory_first_capture_asof_and_map_conservative(tmp_path):
 root=tmp_path/"private";root.mkdir(mode=0o700);root.chmod(0o700)
 raw=archive([item("00000001","005930"),item("00000002","A23456"),
              item("00000003","005930"),item("00000004","")])
 result=capture_dart_corp_directory(root,creds=KEY,
              fetch=lambda u,h:raw,clock=lambda:NOW)
 assert result["total_corporations"]==4
 assert result["listed_codes"]==2 and result["ambiguous_codes"]==1
 d=verify_dart_corp_directory(root/result["capture_id"],
                result["first_receipt_sha256"],decision_at=NOW)
 assert d["mapping"]=={"A23456":"00000002"}
 assert match_krx_codes(d,{"005930","A23456","999999"})=={
  "krx_total_observed":3,"matched_unique_dart_corporation":1,
  "ambiguous_codes_excluded":1,"unmatched_or_nonunique":2,
  "historical_pit_certified":False}
 with pytest.raises(ValueError,match="not first received"):
  verify_dart_corp_directory(root/result["capture_id"],
                result["first_receipt_sha256"],
                decision_at=datetime(2026,10,11,tzinfo=timezone.utc))
 rawpath=root/result["capture_id"]/"raw_directory.zip"
 rawpath.write_bytes(rawpath.read_bytes()+b" ")
 with pytest.raises(ValueError,match="differs from raw"):
  verify_dart_corp_directory(root/result["capture_id"],
                result["first_receipt_sha256"],decision_at=NOW)


@pytest.mark.parametrize("rows,filename",[
 ([item("00000001","005930"),item("00000001","A23456")],"CORPCODE.xml"),
 ([item("1234","005930")],"CORPCODE.xml"),
 ([item("00000001","!@")],"CORPCODE.xml"),
 ([item("00000001","005930")],"../CORPCODE.xml"),
 ([], "CORPCODE.xml"),
])
def test_dart_directory_zip_invalid_rejected(rows,filename):
 with pytest.raises(ValueError):
  parse_directory_zip(archive(rows,filename=filename))


def test_entity_attack_blocked():
 with pytest.raises(ValueError,match="DTD"):
  parse_directory_zip(archive(["<!DOCTYPE foo [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>",item("00000001","005930")]))


def test_invalid_key_no_network(tmp_path):
 root=tmp_path/"private";root.mkdir(mode=0o700);root.chmod(0o700)
 with pytest.raises(ValueError,match="key unavailable"):
  capture_dart_corp_directory(root,creds={},fetch=lambda *_:pytest.fail("network"))
