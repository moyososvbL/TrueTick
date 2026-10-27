import io
import json
import zipfile

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai import meta_client
from backend.app.analyzers.files import check_file
from backend.app.analyzers.qr import decode_qr_codes
from backend.app.main import app

client = TestClient(app)


def qr_png(content: str) -> bytes:
    qr = cv2.QRCodeEncoder.create().encode(content)
    qr = cv2.resize(qr, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    qr = cv2.copyMakeBorder(qr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    ok, buf = cv2.imencode(".png", qr)
    return buf.tobytes()


def plain_png() -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (200, 120), "white").save(b, "PNG")
    return b.getvalue()


def fake_apk() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("AndroidManifest.xml", "<manifest/>")
        z.writestr("classes.dex", "x")
    return b.getvalue()


def _fake_model(monkeypatch, payload):
    async def fake_chat(messages, **kw):
        fake_chat.messages = messages
        return json.dumps(payload)
    monkeypatch.setattr(meta_client, "chat", fake_chat)
    return fake_chat


def test_decode_qr():
    assert decode_qr_codes(qr_png("https://paypal-verify.top/pay")) == ["https://paypal-verify.top/pay"]
    assert decode_qr_codes(plain_png()) == []


def test_qr_upload_reveals_and_checks_link(monkeypatch):
    fake = _fake_model(monkeypatch, {"risk": "high", "summary": "Fake payment page."})
    r = client.post("/api/check", files={"file": ("parking.png", qr_png("http://rnicrosoft-pay.top/x"), "image/png")})
    v = r.json()
    assert r.status_code == 200 and v["input_type"] == "image" and v["risk"] == "high"
    assert v["extracted_text"] == "http://rnicrosoft-pay.top/x"
    assert any("This QR code opens" in f["message"] for f in v["findings"])
    assert "QR code" in fake.messages[1]["content"]


def test_apk_disguised_as_pdf_is_caught_by_contents():
    r = client.post("/api/check", files={"file": ("Invoice.pdf", fake_apk(), "application/pdf")})
    v = r.json()
    assert v["risk"] == "high" and v["input_type"] == "file" and "Android app" in v["findings"][0]["message"]


def test_double_extension():
    msgs = [f.message for f in check_file("wedding_invite.pdf.apk", "", b"junk")]
    assert any("double ending" in m for m in msgs)


def test_apk_named_as_image_is_still_caught():
    r = client.post("/api/check", files={"file": ("photo.jpg", fake_apk(), "image/jpeg")})
    assert r.json()["risk"] == "high"


def test_plain_image_without_qr():
    v = client.post("/api/check", files={"file": ("shot.png", plain_png(), "image/png")}).json()
    assert v["input_type"] == "image" and v["risk"] == "unknown"


def test_broken_image_rejected():
    r = client.post("/api/check", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_text_via_unified_endpoint(monkeypatch):
    _fake_model(monkeypatch, {"risk": "low", "summary": "Looks normal."})
    v = client.post("/api/check", data={"text": "Lunch on Friday?"}).json()
    assert v["risk"] == "low" and v["input_type"] == "text"


def test_nothing_sent():
    assert client.post("/api/check", data={"text": "  "}).status_code == 422


def test_safe_document():
    v = client.post("/api/check", files={"file": ("notes.txt", b"hello", "text/plain")}).json()
    assert v["risk"] == "unknown" and v["input_type"] == "file"
