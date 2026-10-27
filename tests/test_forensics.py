import base64
import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai import meta_client
from backend.app.checks.links import run_checks
from backend.app.forensics.annotate import annotate
from backend.app.forensics.dates import weekday_mismatches
from backend.app.main import app

client = TestClient(app)
RECEIPT = "samples/test_images/receipt_edited_fictional_bank.jpg"


def test_weekday_mismatch_formats():
    assert "was a Tuesday" in weekday_mismatches("Date: Monday, 27 Oct 2026")[0]
    assert weekday_mismatches("Tuesday, 27 Oct 2026") == []
    assert "was a Tuesday" in weekday_mismatches("Mon, October 27, 2026")[0]
    assert "was a Tuesday" in weekday_mismatches("Fri 27/10/2026")[0]
    assert weekday_mismatches("Monday 31 Feb 2026") == []  # impossible date: ignored, not crashed


def test_run_checks_includes_receipt_date():
    f = run_checks("Transfer Successful. Date: Monday, 27 Oct 2026")
    assert f and f[0].kind == "receipt" and f[0].severity == "high"


def test_annotate_draws_boxes():
    url = annotate(open(RECEIPT, "rb").read(), [{"box": [180, 300, 820, 380], "label": "Amount"}])
    assert url.startswith("data:image/jpeg;base64,")
    img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert img.width <= 1000
    assert annotate(open(RECEIPT, "rb").read(), [{"box": "bad"}]) == ""


def test_vision_regions_and_date_check_end_to_end(monkeypatch):
    async def fake_upload(*a, **kw):
        return "f1"

    async def fake_respond(model, content, **kw):
        assert "suspicious_regions" in content[0]["text"]
        return [{"type": "response.output_text.delta", "delta": json.dumps({
            "risk": "high", "image_kind": "receipt", "scam_type": "Edited payment receipt",
            "extracted_text": "Transfer Successful ₦2,500,000.00 Date Monday, 27 Oct 2026",
            "suspicious_regions": [{"label": "Amount in a different font", "box": [180, 300, 820, 380]}],
        })}]

    monkeypatch.setattr(meta_client, "upload_file", fake_upload)
    monkeypatch.setattr(meta_client, "respond", fake_respond)
    v = client.post("/api/check", files={"file": ("r.jpg", open(RECEIPT, "rb").read(), "image/jpeg")}).json()
    assert v["annotated_image"].startswith("data:image/jpeg") and v["marked_regions"] == ["1. Amount in a different font"]
    assert any("was a Tuesday" in f["message"] for f in v["findings"])
    assert v["advice"][0].startswith("Check the real balance")
