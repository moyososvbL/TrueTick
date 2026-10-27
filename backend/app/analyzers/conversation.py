"""Whole-conversation check: several screenshots of one chat, read together.

Scams are a story told over days (friendly "wrong number" → trust → an "opportunity" → money).
One screenshot rarely shows it; the whole chat does. Muse Spark reads all images in one request
and returns a timeline, the stage the scam has reached and contradictions in the other person's story.
"""

import logging

from backend.app.ai import meta_client, prompts
from backend.app.analyzers.common import apply_findings, parse_model_json, verdict_from_model
from backend.app.analyzers.image import _ext, validate_image
from backend.app.checks.link_inspect import inspect_links
from backend.app.checks.links import extract_urls, run_checks
from backend.app.config import get_settings
from backend.app.models import Finding, Verdict

log = logging.getLogger("truetick.conversation")
MAX_IMAGES = 8


async def analyze_conversation(images: list[tuple[bytes, str]], caption: str = "") -> Verdict:
    for data, _ in images:
        validate_image(data)
    s = get_settings()
    try:
        ids = [await meta_client.upload_file(d, f"chat_{n}{_ext(m)}", m or "image/jpeg")
               for n, (d, m) in enumerate(images, 1)]
        content = [{"type": "input_text", "text": prompts.conversation_prompt(len(images), caption)}]
        for n, fid in enumerate(ids, 1):
            content += [{"type": "input_text", "text": f"Screenshot [{n}]:"}, {"type": "input_image", "file_id": fid}]
        data = parse_model_json(meta_client.output_text(await meta_client.respond(s.vision_model, content)))
    except meta_client.MetaAPIError as e:
        log.error("Conversation check failed: %s", e)
        return _unavailable("service unreachable")
    except (ValueError, TypeError) as e:
        log.error("Couldn't read conversation reply: %s", e)
        return _unavailable("unexpected reply")

    verdict = verdict_from_model(data)
    verdict.input_type = "image"
    verdict.extracted_text = str(data.get("extracted_text") or "")[:12000]
    verdict.timeline = [str(t)[:200] for t in (data.get("timeline") or [])][:8]
    verdict.contradictions = [str(c)[:240] for c in (data.get("contradictions") or [])][:6]
    verdict.stage = str(data.get("stage") or "")[:60]

    findings = run_checks(verdict.extracted_text)
    seen = {f.message for f in findings}
    findings += [f for f in await inspect_links(extract_urls(verdict.extracted_text)) if f.message not in seen]
    if len(verdict.contradictions) >= 2:
        findings.append(Finding(kind="conversation", severity="medium",
                                message=f"Their story changes {len(verdict.contradictions)} times across the chat."))
    verdict = apply_findings(verdict, findings)
    verdict.links = extract_urls(verdict.extracted_text)[:3]
    return verdict


def _unavailable(reason: str) -> Verdict:
    return Verdict(risk="unknown", input_type="image",
                   summary=f"We couldn't read these screenshots right now ({reason}). Try again, or check them one at a time.",
                   advice=["Don't send money, codes or card details until you've verified who this is"])
