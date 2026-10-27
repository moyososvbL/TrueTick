"""Screenshots and photos.

1. QR codes: decoded without opening, then the hidden link is checked (no AI needed).
2. Muse Spark vision reads the screenshot (chat, SMS, email, receipt...), copies out its text
   and judges it. The copied text then goes through the same link and lookalike checks.
3. (next) SAM 3.1 isolates receipt fields so edited areas can be inspected.
"""

import io
import logging

from PIL import Image, UnidentifiedImageError

from backend.app.ai import meta_client, prompts
from backend.app.analyzers.common import apply_findings, parse_model_json, verdict_from_model
from backend.app.analyzers.qr import decode_qr_codes
from backend.app.analyzers.text import analyze_text
from backend.app.checks.link_inspect import inspect_links
from backend.app.checks.links import extract_urls, run_checks
from backend.app.config import get_settings
from backend.app.forensics.annotate import annotate
from backend.app.models import Finding, Verdict

log = logging.getLogger("truetick.image")

RECEIPT_ADVICE = "Check the real balance in your own bank app before releasing goods or refunding anything. A screenshot can't prove payment."


class BadImageError(ValueError):
    pass


def validate_image(data: bytes) -> None:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise BadImageError("This doesn't look like a valid image.") from e


async def _check_qr(data: bytes, caption: str) -> Verdict | None:
    qr_contents = decode_qr_codes(data)
    if not qr_contents:
        return None
    joined = "\n".join(qr_contents)
    context = "The user scanned a QR code. It contains:\n" + joined
    if caption:
        context += f"\n\nThe user added: {caption}"
    verdict = await analyze_text(context)
    # Informational: added after the risk was decided, so it doesn't change the risk level.
    verdict.findings = [Finding(kind="qr", severity="medium", message=f"This QR code opens: {c}")
                        for c in qr_contents] + verdict.findings
    verdict.input_type = "image"
    verdict.extracted_text = joined
    return verdict


async def _read_with_vision(data: bytes, mime: str, caption: str) -> Verdict:
    s = get_settings()
    file_id = await meta_client.upload_file(data, "screenshot" + _ext(mime), mime or "image/jpeg")
    events = await meta_client.respond(s.vision_model, [
        {"type": "input_text", "text": prompts.image_prompt(caption)},
        {"type": "input_image", "file_id": file_id},
    ])
    model_data = parse_model_json(meta_client.output_text(events))
    verdict = verdict_from_model(model_data)
    verdict.input_type = "image"
    verdict.extracted_text = str(model_data.get("extracted_text") or "")[:8000]

    findings = run_checks(verdict.extracted_text) if verdict.extracted_text else []
    if verdict.extracted_text:
        seen = {f.message for f in findings}
        findings += [f for f in await inspect_links(extract_urls(verdict.extracted_text)) if f.message not in seen]
    verdict = apply_findings(verdict, findings)
    regions = [r for r in (model_data.get("suspicious_regions") or []) if isinstance(r, dict)]
    if regions:
        try:
            verdict.annotated_image = annotate(data, regions)
        except Exception as e:  # drawing is a bonus; never fail the check because of it
            log.error("Couldn't draw regions: %s", e)
        if verdict.annotated_image:
            verdict.marked_regions = [f"{n}. {str(r.get('label', '')).strip()}" for n, r in enumerate(regions[:6], 1)
                                      if r.get("label")]
    if str(model_data.get("image_kind", "")).lower() == "receipt" and RECEIPT_ADVICE not in verdict.advice:
        verdict.advice = [RECEIPT_ADVICE] + verdict.advice[:2]
    return verdict


def _ext(mime: str) -> str:
    return {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp"}.get(mime, ".jpg")


async def analyze_image(data: bytes, mime: str = "", caption: str = "") -> Verdict:
    validate_image(data)

    qr_verdict = await _check_qr(data, caption)
    if qr_verdict is not None:
        return qr_verdict

    try:
        return await _read_with_vision(data, mime, caption)
    except meta_client.MetaAPIError as e:
        log.error("Vision check failed: %s", e)
        reason = "service unreachable"
    except (ValueError, TypeError) as e:
        log.error("Couldn't read vision reply: %s", e)
        reason = "unexpected reply"

    if caption:
        verdict = await analyze_text(caption)
        verdict.input_type = "image"
        return verdict
    return Verdict(
        risk="unknown",
        input_type="image",
        summary=f"We couldn't read this screenshot right now ({reason}). Please try again, or paste the text instead.",
        advice=["Don't send money, codes or card details until you've verified who this is",
                "For payment receipts: always confirm the money in your own bank app"],
    )
