"""EraLeader local dashboard keeps Kiwoom demo and real profiles isolated."""
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import os
import secrets
import socket
import stat

import pytest

from eraleader.kiwoom_profile_settings import (
    save_profiles,read_profiles,public_status,render,make_handler,
)


def test_separate_profiles_default_demo_real_credentials_protected(tmp_path):
    file=tmp_path/"private"/"kiwoom_profiles.json"
    initial=read_profiles(file)
    assert initial["active_mode"]=="demo"
    saved=save_profiles({"active_mode":"demo","demo_appkey":"DEMO_KEY",
                         "demo_secret":"DEMO_SECRET","demo_label":"연습 계좌"},file)
    assert saved["real"]=={}
    assert stat.S_IMODE(file.stat().st_mode)==0o600
    assert stat.S_IMODE(file.parent.stat().st_mode)==0o700
    status=public_status(saved)
    assert status["accounts"]["demo"]["configured"] is True
    assert status["accounts"]["real"]["configured"] is False
    html=render(saved,"TEST_CSRF")
    assert "DEMO_KEY" not in html and "DEMO_SECRET" not in html
    assert "mockapi.kiwoom.com" in html and "api.kiwoom.com" in html
    with pytest.raises(ValueError):
        save_profiles({"active_mode":"real"},file)
    saved=save_profiles({"active_mode":"real","real_appkey":"REAL_KEY",
                         "real_secret":"REAL_SECRET","real_label":"실전 데이터"},file)
    assert saved["active_mode"]=="real"
    assert saved["demo"]["appkey"]=="DEMO_KEY"
    assert saved["real"]["appkey"]=="REAL_KEY"
    saved=save_profiles({"active_mode":"demo","demo_appkey":"","demo_secret":""},file)
    assert saved["demo"]["secretkey"]=="DEMO_SECRET"
    assert saved["real"]["secretkey"]=="REAL_SECRET"


@pytest.mark.parametrize("data", [
    {"active_mode":"other"},
    {"active_mode":"demo","demo_appkey":"ONLY_KEY"},
    {"active_mode":"demo","demo_appkey":"hello\r\n","demo_secret":"foobar"},
    {"active_mode":"real"},
])
def test_profile_rejects_invalid_cross_mode_or_incomplete(tmp_path,data):
    with pytest.raises(ValueError):
        save_profiles(data,tmp_path/"private"/"creds.json")


def test_symlink_credentials_blocked(tmp_path):
    real=tmp_path/"real.json"
    real.write_text("{}")
    linked=tmp_path/"linked.json"
    linked.symlink_to(real)
    with pytest.raises(ValueError):
        read_profiles(linked)
    with pytest.raises(ValueError):
        save_profiles({"active_mode":"demo"},linked)
    assert real.read_text()=="{}"


def test_local_http_dashboard_csrf_and_secret_nonreflection(tmp_path):
    private=tmp_path/"private"/"profiles.json"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    secret_token=secrets.token_urlsafe(24)
    handler=make_handler(private,secret_token,port)
    server=ThreadingHTTPServer(("127.0.0.1",port),handler)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f"http://127.0.0.1:{port}"
    try:
        with urlopen(url+"/",timeout=2) as answer:
            html=answer.read().decode()
            assert answer.headers["X-Frame-Options"]=="DENY"
            assert answer.headers["Cache-Control"]=="no-store, no-cache"
            assert "모의투자 계좌" in html and "실전투자 계좌" in html
        values={"csrf":secret_token,"active_mode":"demo",
                "demo_label":"연습","demo_appkey":"PRIVATE_MOCK_KEY",
                "demo_secret":"PRIVATE_MOCK_SECRET"}
        def post(values,origin=True):
            request=Request(url+"/save",data=urlencode(values).encode(),
                headers={"Content-Type":"application/x-www-form-urlencoded",
                         **({"Origin":url} if origin else {})},method="POST")
            return urlopen(request,timeout=2)
        with pytest.raises(HTTPError) as error:
            post(dict(values,csrf="invalid"))
        assert error.value.code==403
        with pytest.raises(HTTPError) as error:
            post(values,origin=False)
        assert error.value.code==403
        with post(values) as response:
            result=response.read().decode()
            assert "설정이 로컬에 저장되었습니다" in result
            assert "PRIVATE_MOCK_KEY" not in result
            assert "PRIVATE_MOCK_SECRET" not in result
        assert read_profiles(private)["demo"]["appkey"]=="PRIVATE_MOCK_KEY"
        assert read_profiles(private)["real"]=={}
        with pytest.raises(HTTPError) as error:
            post(dict(values,active_mode="real"))
        assert error.value.code==400
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)
