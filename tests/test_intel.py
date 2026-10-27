import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.config import get_settings
from backend.app.intel.reports import extract_indicators
from backend.app.main import app

client = TestClient(app)


def _model(monkeypatch, risk):
    async def fake_chat(messages, **kw):
        return '{"risk": "%s", "summary": "s"}' % risk
    monkeypatch.setattr(meta_client, "chat", fake_chat)


def test_extract_indicators():
    kinds = {k for k, _, _ in extract_indicators(
        "Pay at https://www.paypal-verify.top/x or call +234 803 123 4567, wallet bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")}
    assert kinds == {"link", "number", "wallet"}


def test_reports_counted_across_users(monkeypatch):
    _model(monkeypatch, "high")
    msg = "Verify now at http://zenora-verify-acct.top/login"
    first = client.post("/api/check/text", json={"text": msg}).json()
    assert first["community_reports"] == 0
    client.post("/api/check/text", json={"text": "Different words, same link zenora-verify-acct.top/login"})
    third = client.post("/api/check/text", json={"text": msg}).json()
    assert third["community_reports"] == 2
    assert any("flagged as risky 2 times" in f["message"] for f in third["findings"])


def test_reported_link_raises_low_to_medium(monkeypatch):
    _model(monkeypatch, "high")
    for _ in range(2):
        client.post("/api/check/text", json={"text": "call 08031234567 now"})
    _model(monkeypatch, "low")
    v = client.post("/api/check/text", json={"text": "hi, my number is 0803 123 4567"}).json()
    assert v["risk"] == "medium" and v["community_reports"] == 2


def test_safe_checks_not_recorded_and_no_content_stored(monkeypatch):
    _model(monkeypatch, "low")
    client.post("/api/check/text", json={"text": "Lunch at https://example.org/menu?"})
    _model(monkeypatch, "high")
    secret = "my-secret-scam-site.top"
    client.post("/api/check/text", json={"text": f"go to http://{secret}/pay"})
    db = Path(get_settings().data_dir) / "truetick.db"
    con = sqlite3.connect(db)
    dump = "\n".join(con.iterdump())
    assert secret not in dump and "example.org" not in dump  # only salted fingerprints are stored
    assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1


def test_stats(monkeypatch):
    _model(monkeypatch, "high")
    client.post("/api/check/text", json={"text": "send the OTP"})
    s = client.get("/api/stats").json()
    assert s["checks_7d"] == 1 and s["risky_7d"] == 1
