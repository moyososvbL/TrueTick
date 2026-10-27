import json

from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.main import app

client = TestClient(app)


def _fake_reply(payload):
    async def fake_chat(messages, **kwargs):
        fake_chat.messages = messages
        return "```json\n" + json.dumps(payload) + "\n```"
    return fake_chat


def test_health_and_homepage():
    assert client.get("/api/health").json()["status"] == "ok"
    assert "TrueTick" in client.get("/").text


def test_scam_text_uses_model_and_link_facts(monkeypatch):
    fake = _fake_reply({
        "risk": "high", "scam_type": "Fake bank alert", "pattern_id": None,
        "summary": "This looks like a phishing message.", "reasons": ["Urgent threat"],
        "what_next": "They will steal your login.", "advice": ["Don't click the link"], "is_threat": False,
    })
    monkeypatch.setattr(meta_client, "chat", fake)
    r = client.post("/api/check/text", json={"text": "Account suspended! Verify at http://rnicrosoft-login.top now"})
    v = r.json()
    assert r.status_code == 200 and v["risk"] == "high" and v["ai_used"] is True
    assert any("Microsoft" in f["message"] for f in v["findings"])
    # The link facts were given to the model as evidence, and the message is fenced as untrusted.
    user_prompt = fake.messages[1]["content"]
    assert "MESSAGE START" in user_prompt and "Microsoft" in user_prompt


def test_link_facts_raise_low_model_risk(monkeypatch):
    monkeypatch.setattr(meta_client, "chat", _fake_reply({"risk": "low", "summary": "No problems."}))
    v = client.post("/api/check/text", json={"text": "hi see https://paypal-verify.top/login"}).json()
    assert v["risk"] == "high"


def test_threat_adds_safety_advice(monkeypatch):
    monkeypatch.setattr(meta_client, "chat", _fake_reply({"risk": "high", "is_threat": True, "advice": []}))
    v = client.post("/api/check/text", json={"text": "pay or I share your photos"}).json()
    assert any("Don't pay" in a for a in v["advice"])


def test_model_down_falls_back_to_checks(monkeypatch):
    async def broken(messages, **kwargs):
        raise meta_client.MetaAPIError("down")
    monkeypatch.setattr(meta_client, "chat", broken)
    v = client.post("/api/check/text", json={"text": "verify at https://paypal-verify.top/login"}).json()
    assert v["ai_used"] is False and v["risk"] == "high"


def test_empty_text_rejected():
    assert client.post("/api/check/text", json={"text": ""}).status_code == 422
