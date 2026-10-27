import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai import meta_client
from backend.app.main import app

client = TestClient(app)


def _png(color):
    b = io.BytesIO()
    Image.new("RGB", (512, 512), color).save(b, "PNG")
    return b.getvalue()


def test_card_with_muse_image_and_cache(monkeypatch):
    calls = []

    async def fake_gen(prompt, size="1024x1024", **kw):
        calls.append(prompt)
        return _png("orange")

    monkeypatch.setattr(meta_client, "generate_image", fake_gen)
    r = client.post("/api/card", json={"pattern_id": "sugar_daddy_gift_card"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["x-illustrated-by"] == "muse-image"
    img = Image.open(io.BytesIO(r.content))
    assert img.size == (1080, 1350)
    assert "No text" in calls[0] and "Sugar daddy" in calls[0]
    client.post("/api/card", json={"pattern_id": "sugar_daddy_gift_card"})
    assert len(calls) == 1  # cached: Muse Image is only paid for once per scam type


def test_card_without_muse_image_still_works(monkeypatch):
    async def down(*a, **kw):
        raise meta_client.MetaAPIError("down")

    monkeypatch.setattr(meta_client, "generate_image", down)
    r = client.post("/api/card", json={"scam_type": "Fake job offer"})
    assert r.status_code == 200 and r.headers["x-illustrated-by"] == "none"
    assert Image.open(io.BytesIO(r.content)).size == (1080, 1350)
