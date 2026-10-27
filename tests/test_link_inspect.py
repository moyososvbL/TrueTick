import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.checks import link_inspect
from backend.app.config import get_settings

REAL_GUARD = link_inspect._assert_public_host  # saved before the fixture replaces it


@pytest.fixture(autouse=True)
def allow_test_hosts(monkeypatch):
    """Tests use fake websites, so skip real DNS (the real check is tested separately)."""
    async def fake_assert(host):
        if host == "internal.test":
            raise link_inspect.UnsafeTarget("it points to a private network address")
    monkeypatch.setattr(link_inspect, "_assert_public_host", fake_assert)


def rdap(days_old):
    date = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return httpx.Response(200, json={"events": [{"eventAction": "registration", "eventDate": date}]})


FAKE_LOGIN = b"""<html><head><title>PayPal: Log in to your account</title></head>
<body><h1>PayPal</h1><form><input name="email"><input type="password" name="pass">
<input name="card_number" placeholder="Card number"><input name="cvv"></form>
<script>alert('never run')</script></body></html>"""


def site(handler_map):
    def handler(request: httpx.Request) -> httpx.Response:
        return handler_map(request)
    return httpx.MockTransport(handler)


def msgs(findings):
    return " | ".join(f.message for f in findings)


def run(url, transport):
    return asyncio.run(link_inspect.inspect_url(url, transport))


def test_shortened_link_to_new_fake_paypal_login():
    def h(r):
        if r.url.host == "bit.ly":
            return httpx.Response(301, headers={"location": "https://secure-acct-check.top/login"})
        if r.url.host == "secure-acct-check.top":
            return httpx.Response(200, content=FAKE_LOGIN, headers={"content-type": "text/html"})
        if r.url.host == "rdap.org":
            return rdap(3)
        return httpx.Response(404)

    m = msgs(run("https://bit.ly/abc", site(h)))
    assert "redirects to a different website: secure-acct-check.top" in m
    assert "looks like PayPal" in m and "a password" in m and "card security code" in m
    assert "registered only 3 days ago" in m


def test_official_site_is_not_flagged():
    def h(r):
        if r.url.host == "www.paypal.com":
            return httpx.Response(200, content=FAKE_LOGIN, headers={"content-type": "text/html"})
        return httpx.Response(404)

    assert run("https://www.paypal.com/signin", site(h)) == []


def test_old_normal_site_with_no_forms_is_quiet():
    def h(r):
        if r.url.host == "rdap.org":
            return rdap(3000)
        return httpx.Response(200, content=b"<html><title>Cafe menu</title><p>Jollof rice</p></html>",
                              headers={"content-type": "text/html"})

    assert run("https://cafe-lumen.example/menu", site(h)) == []


def test_redirect_to_internal_address_refused():
    def h(r):
        return httpx.Response(302, headers={"location": "http://internal.test/admin"})

    assert "couldn't safely open" in msgs(run("https://evil.example/x", site(h)))


def test_download_link_flagged():
    def h(r):
        if r.url.host == "rdap.org":
            return rdap(1000)
        return httpx.Response(200, content=b"PK..", headers={"content-type": "application/octet-stream",
                                                             "content-disposition": "attachment; filename=a.apk"})

    assert "downloads a file" in msgs(run("https://files.example/get", site(h)))


def test_dead_site():
    def h(r):
        raise httpx.ConnectError("refused")

    assert "didn't respond" in msgs(run("https://gone.example", site(h)))


def test_too_many_redirects():
    def h(r):
        return httpx.Response(302, headers={"location": "https://loop.example/again"})

    assert "redirects too many times" in msgs(run("https://loop.example", site(h)))


def test_real_dns_guard_blocks_localhost_and_private_ips():
    for host in ("localhost", "127.0.0.1", "10.0.0.5", "169.254.169.254"):
        with pytest.raises(link_inspect.UnsafeTarget):
            asyncio.run(REAL_GUARD(host))


def test_disabled_by_setting(monkeypatch):
    monkeypatch.setenv("LINK_INSPECTION", "false")
    get_settings.cache_clear()
    assert asyncio.run(link_inspect.inspect_links(["https://x.example"])) == []


def test_registrable_domain():
    assert link_inspect.registrable_domain("login.secure.zenora.com.ng") == "zenora.com.ng"
    assert link_inspect.registrable_domain("a.b.example.com") == "example.com"
