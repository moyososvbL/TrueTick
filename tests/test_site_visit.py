import asyncio
import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai import meta_client
from backend.app.checks import site_visit
from backend.app.checks.site_visit import compare
from backend.app.main import app

client = TestClient(app)


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 80), "white").save(buf, "PNG")
    return buf.getvalue()


def test_brand_on_wrong_domain_is_high_when_it_asks_for_login():
    f = compare("secure-paypa1-verify.top", "PayPal", "login", ["password", "email"])
    assert f[0].severity == "high" and "paypal.com" in f[0].message


def test_real_brand_site_is_not_flagged():
    assert compare("www.paypal.com", "PayPal", "login", ["password"]) == []


def test_unknown_brand_compared_with_address():
    assert compare("zenora-verify.xyz", "Zenora Bank", "login", ["OTP"]) == []
    hit = compare("account-update-portal.top", "Zenora Bank", "login", ["card number", "OTP"])
    assert hit[0].severity == "high" and "Zenora Bank" in hit[0].message


def test_download_page_flagged():
    assert any(f.severity == "high" for f in compare("get-app.top", "", "download", []))


def test_private_addresses_are_never_opened():
    for url in ("http://127.0.0.1:8000/", "http://localhost/", "file:///etc/passwd"):
        r = asyncio.run(site_visit.visit(url))
        assert r.error and not r.screenshot


def test_visit_endpoint(monkeypatch):
    async def fake_shot(url):
        return _png(), "https://zenora-secure-login.top/verify"

    async def fake_upload(data, name, mime):
        return "file-1"

    async def fake_respond(model, content, metadata=None, transport=None):
        reply = {"looks_like": "Zenora Bank", "page_purpose": "login", "asks_for": ["password", "OTP"],
                 "visual_red_flags": ["countdown timer"], "summary": "A fake Zenora Bank sign-in page."}
        return [{"type": "response.output_text.delta", "delta": json.dumps(reply)}]

    monkeypatch.setattr(site_visit, "screenshot", fake_shot)
    monkeypatch.setattr(meta_client, "upload_file", fake_upload)
    monkeypatch.setattr(meta_client, "respond", fake_respond)
    body = client.post("/api/visit", json={"url": "zenora-secure-login.top/verify"}).json()
    assert body["screenshot"].startswith("data:image/jpeg")
    assert body["looks_like"] == "Zenora Bank" and body["risk"] == "low"  # brand word is in the address
    assert any("countdown" in f["message"] for f in body["findings"])


def test_localhost_only_opens_with_testing_switch(monkeypatch):
    from backend.app.config import get_settings
    cache = {}
    assert asyncio.run(site_visit._host_ok("127.0.0.1", cache)) is False
    monkeypatch.setattr(get_settings(), "visit_allow_localhost", True)
    assert asyncio.run(site_visit._host_ok("127.0.0.1", {})) is True
    assert asyncio.run(site_visit._host_ok("192.168.1.1", {})) is False  # the switch never opens the home network
