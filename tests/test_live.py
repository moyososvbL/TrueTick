import io
import math
import struct
import wave

from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.live import routes
from backend.app.live.rules import scan
from backend.app.main import app
from backend.app.models import Verdict

client = TestClient(app)


def ids(text):
    return [a.id for a in scan(text)]


def test_rules_catch_common_call_scams():
    assert "secret_code" in ids("Please read me the code we just sent to your phone")
    assert "secret_code" in ids("I need the oh tee pee to stop the transfer")
    assert "secret_code" in ids("tell me the six digit number, the six digit code")
    assert "gift_card" in ids("go to the store and buy an items card")
    assert "safe_account" in ids("we will move your money to a safe account")
    assert "remote_access" in ids("download AnyDesk so I can help you")
    assert "crypto" in ids("pay at the bitcoin ATM near you")
    assert "secrecy" in ids("don't tell anyone at the bank about this call")
    assert "threat" in ids("there is a warrant for your arrest")


def test_rules_quiet_on_normal_call_and_stop_first():
    assert ids("Hi mum, I'll be home late for dinner tonight") == []
    alerts = scan("don't tell anyone, just read me the OTP")
    assert alerts[0].severity == "stop"


def _wav(seconds=1.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(int(rate * seconds))))
    return buf.getvalue()


def test_chunk_transcribes_and_alerts_on_whole_call(monkeypatch):
    async def fake_transcribe(wav):
        return "and now read me the code"
    monkeypatch.setattr(meta_client, "transcribe", fake_transcribe)
    r = client.post("/api/live/chunk", files={"audio": ("p.wav", _wav(), "audio/wav")},
                    data={"so_far": "This is your bank fraud team."})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "and now read me the code"
    assert body["alerts"][0]["id"] == "secret_code"


def test_chunk_survives_bad_audio_and_api_errors(monkeypatch):
    r = client.post("/api/live/chunk", files={"audio": ("p.webm", b"not audio", "audio/webm")})
    assert r.status_code == 200 and r.json()["text"] == ""

    async def broken(wav):
        raise meta_client.MetaAPIError("down")
    monkeypatch.setattr(meta_client, "transcribe", broken)
    r = client.post("/api/live/chunk", files={"audio": ("p.wav", _wav(), "audio/wav")},
                    data={"so_far": "buy a google play card"})
    assert r.json()["alerts"][0]["id"] == "gift_card"
    assert "error" in r.json()


def test_assess_uses_live_prompt(monkeypatch):
    seen = {}

    async def fake_analyze(text, extra_system=""):
        seen["text"], seen["extra"] = text, extra_system
        return Verdict(risk="high", summary="Hang up now.")
    monkeypatch.setattr(routes, "analyze_text", fake_analyze)
    r = client.post("/api/live/assess", json={"transcript": "read me the OTP"})
    assert r.status_code == 200 and r.json()["risk"] == "high"
    assert "STILL IN PROGRESS" in seen["text"] and "RIGHT NOW" in seen["extra"]
