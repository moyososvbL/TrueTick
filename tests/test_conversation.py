import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai import meta_client
from backend.app.main import app

client = TestClient(app)


def _img(color):
    buf = io.BytesIO()
    Image.new("RGB", (60, 120), color).save(buf, "PNG")
    return buf.getvalue()


def test_conversation_needs_two_to_eight_images():
    r = client.post("/api/check/conversation", files=[("files", ("a.png", _img("white"), "image/png"))])
    assert r.status_code == 422


def test_conversation_reads_all_images_in_one_request(monkeypatch):
    seen = {}

    async def fake_upload(data, name, mime):
        return f"id-{name}"

    async def fake_respond(model, content, metadata=None, transport=None):
        seen["images"] = [c["file_id"] for c in content if c["type"] == "input_image"]
        reply = {"risk": "high", "scam_type": "Romance scam", "summary": "Classic romance scam.",
                 "reasons": ["Asks for money"], "what_next": "", "advice": ["Stop replying"],
                 "extracted_text": "[1] hi dear [2] I'm on an oil rig [3] send $3000 to http://zenora-pay.top",
                 "timeline": ["[1] Friendly hello", "[3] Asks for money"],
                 "contradictions": ["[1] says surgeon in Texas, [2] says oil rig", "[1] says 45, [3] says 52"],
                 "stage": "Asking for money"}
        return [{"type": "response.output_text.delta", "delta": json.dumps(reply)}]

    monkeypatch.setattr(meta_client, "upload_file", fake_upload)
    monkeypatch.setattr(meta_client, "respond", fake_respond)
    files = [("files", (f"{n}.png", _img(c), "image/png")) for n, c in enumerate(["white", "gray", "black"], 1)]
    body = client.post("/api/check/conversation", files=files).json()
    assert len(seen["images"]) == 3
    assert body["stage"] == "Asking for money" and len(body["timeline"]) == 2
    assert any("story changes 2 times" in f["message"] for f in body["findings"])
    assert body["links"] == ["http://zenora-pay.top"]
