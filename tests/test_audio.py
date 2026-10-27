import json
import asyncio
import io
import wave

import av
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.ai import meta_client
from backend.app.analyzers.audio import BadAudioError, to_wav_mono
from backend.app.config import get_settings
from backend.app.main import app

client = TestClient(app)


def make_audio(fmt: str, codec: str, seconds: float = 1.5, rate: int = 48000) -> bytes:
    """A short tone encoded like a real voice note (e.g. ogg/opus from WhatsApp)."""
    buf = io.BytesIO()
    with av.open(buf, "w", format=fmt) as out:
        stream = out.add_stream(codec, rate=rate)
        stream.layout = "mono"
        t = np.arange(int(seconds * rate)) / rate
        samples = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    return buf.getvalue()


def test_whatsapp_style_opus_converts_to_24k_wav():
    wav, seconds = to_wav_mono(make_audio("ogg", "libopus"))
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
    assert 1.0 < seconds < 2.0


def test_not_audio_rejected():
    with pytest.raises(BadAudioError):
        to_wav_mono(b"definitely not audio")


def test_transcript_shapes():
    f = meta_client.transcript_from_response
    assert f({"text": "hello"}) == "hello"
    assert f({"transcript": {"text": "hi there"}}) == "hi there"
    assert f({"segments": [{"text": "send"}, {"text": "the code"}]}) == "send the code"


def test_transcribe_call(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    get_settings.cache_clear()
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"text": "This is your bank"})

    try:
        text = asyncio.run(meta_client.transcribe(b"RIFF....", transport=httpx.MockTransport(handler)))
    finally:
        get_settings.cache_clear()
    assert text == "This is your bank"
    assert seen["url"].endswith("/asr/transcribe")
    assert b'name="request"' in seen["body"] and b'name="audio"' in seen["body"]
    assert b"muse-voice-transcribe-1.0" in seen["body"] and b'"audioEncoding": "WAV"' in seen["body"]


def test_voice_note_end_to_end(monkeypatch):
    async def fake_transcribe(wav, **kw):
        return "Grandma it's me, I've been arrested, send money now and don't tell mum"

    async def fake_chat(messages, **kw):
        fake_chat.prompt = messages[1]["content"]
        return '{"risk": "high", "scam_type": "Voice clone emergency", "advice": ["Call back"]}'

    monkeypatch.setattr(meta_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    r = client.post("/api/check", files={"file": ("PTT-001.opus", make_audio("ogg", "libopus"), "audio/ogg")})
    v = r.json()
    assert r.status_code == 200 and v["input_type"] == "audio" and v["risk"] == "high"
    assert "arrested" in v["extracted_text"] and "Transcript of a voice note" in fake_chat.prompt
    assert any("cloned" in a for a in v["advice"])


def test_bad_audio_upload_returns_400():
    r = client.post("/api/check", files={"file": ("note.ogg", b"garbage", "audio/ogg")})
    assert r.status_code == 400


def test_misheard_brand_is_corrected(monkeypatch):
    async def fake_transcribe(wav, **kw):
        return "Hello, can you please send me some items card, I want to go to the store"

    async def fake_chat(messages, **kw):
        fake_chat.system = messages[0]["content"]
        return json.dumps({
            "risk": "high", "scam_type": "Gift card request",
            "corrected_transcript": "Hello, can you please send me some iTunes card, I want to go to the store",
            "corrections": ["items card → iTunes card"], "advice": ["Don't buy gift cards for anyone"],
        })

    monkeypatch.setattr(meta_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    v = client.post("/api/check", files={"file": ("note.m4a", make_audio("ogg", "libopus"), "audio/mp4")}).json()
    assert v["risk"] == "high" and "iTunes card" in v["extracted_text"]
    assert v["corrections"] == ["items card → iTunes card"]
    assert "AUTOMATIC TRANSCRIPT" in fake_chat.system


def test_no_corrections_keeps_original_transcript(monkeypatch):
    async def fake_transcribe(wav, **kw):
        return "See you at lunch on Friday"

    async def fake_chat(messages, **kw):
        return json.dumps({"risk": "low", "corrected_transcript": "", "corrections": []})

    monkeypatch.setattr(meta_client, "transcribe", fake_transcribe)
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    v = client.post("/api/check", files={"file": ("n.ogg", make_audio("ogg", "libopus"), "audio/ogg")}).json()
    assert v["extracted_text"] == "See you at lunch on Friday" and v["corrections"] == []
