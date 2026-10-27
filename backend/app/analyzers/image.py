"""Screenshots and photos.

Step 1 (done): QR codes. Decode them without opening, then check the hidden link.
Step 2 (next): Muse Spark vision reads the screenshot (chat, SMS, receipt) and judges it.
Step 3 (next): SAM 3.1 isolates receipt fields so edited areas can be inspected.
"""

import io

from PIL import Image, UnidentifiedImageError

from backend.app.analyzers.qr import decode_qr_codes
from backend.app.analyzers.text import analyze_text
from backend.app.models import Finding, Verdict


class BadImageError(ValueError):
    pass


def validate_image(data: bytes) -> None:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise BadImageError("This doesn't look like a valid image.") from e


async def analyze_image(data: bytes, mime: str = "", caption: str = "") -> Verdict:
    validate_image(data)

    qr_contents = decode_qr_codes(data)
    if qr_contents:
        joined = "\n".join(qr_contents)
        context = "The user scanned a QR code. It contains:\n" + joined
        if caption:
            context += f"\n\nThe user added: {caption}"
        verdict = await analyze_text(context)
        # Informational: added after the risk was decided, so it doesn't change the risk level.
        qr_facts = [Finding(kind="qr", severity="medium", message=f"This QR code opens: {c}") for c in qr_contents]
        verdict.findings = qr_facts + verdict.findings
        verdict.input_type = "image"
        verdict.extracted_text = joined
        return verdict

    # Screenshot reading with Muse Spark vision is added once the API format is confirmed.
    if caption:
        verdict = await analyze_text(caption)
        verdict.input_type = "image"
        return verdict
    return Verdict(
        risk="unknown",
        input_type="image",
        summary="No QR code found. Reading screenshots and receipts is coming next.",
        advice=["For now, paste the text from the screenshot to check it",
                "For payment receipts: always confirm the money in your own bank app"],
    )
