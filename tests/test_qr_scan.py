import json

from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.analyzers.qr import describe_qr
from backend.app.main import app

client = TestClient(app)


def msg(content):
    return describe_qr(content)[0]


def test_describes_what_a_qr_code_does():
    assert "opens: https://zenora-pay.top/fine" in msg("https://zenora-pay.top/fine").message
    wifi = msg("WIFI:T:nopass;S:Free Airport WiFi;;")
    assert "Free Airport WiFi" in wifi.message and "no password" in wifi.message
    assert msg("bitcoin:bc1qexampleaddress?amount=0.1").severity == "high"
    assert "call +2348000000000" in msg("tel:+2348000000000").message
    assert msg("https://get-app.top/zenora.apk").severity == "high"
    assert "contains text" in msg("Table 12").message


def test_live_scan_endpoint(monkeypatch):
    async def fake_chat(messages, model=None, temperature=0.2, transport=None):
        assert "has NOT been opened" in messages[1]["content"]
        return json.dumps({"risk": "high", "scam_type": "QR phishing", "summary": "Fake parking fine page.",
                           "reasons": ["Unofficial payment site"], "what_next": "", "advice": ["Don't pay here"]})
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    v = client.post("/api/check/qr", json={"content": "https://zenora-parking-fines.top/pay"}).json()
    assert v["risk"] == "high"
    assert v["links"] == ["https://zenora-parking-fines.top/pay"]
    assert v["findings"][0]["message"].startswith("This QR code opens")
    assert v["extracted_text"] == "https://zenora-parking-fines.top/pay"


def test_crypto_qr_raises_risk(monkeypatch):
    async def calm(messages, model=None, temperature=0.2, transport=None):
        return json.dumps({"risk": "low", "summary": "Looks fine.", "reasons": [], "advice": []})
    monkeypatch.setattr(meta_client, "chat", calm)
    v = client.post("/api/check/qr", json={"content": "bitcoin:bc1qexampleaddress"}).json()
    assert v["risk"] == "high"
