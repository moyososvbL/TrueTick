"""Text messages: non-AI checks first, then Muse Spark with those facts as evidence."""

import logging

from backend.app.ai import meta_client, prompts
from backend.app.analyzers.common import apply_findings, fallback_verdict, parse_model_json, verdict_from_model
from backend.app.checks.link_inspect import inspect_links
from backend.app.checks.links import extract_urls, run_checks
from backend.app.models import Verdict

log = logging.getLogger("truetick.text")


async def analyze_text(text: str) -> Verdict:
    findings = run_checks(text)
    seen = {f.message for f in findings}
    findings += [f for f in await inspect_links(extract_urls(text)) if f.message not in seen]
    messages = [
        {"role": "system", "content": prompts.text_system_prompt()},
        {"role": "user", "content": prompts.text_user_prompt(text, [f.message for f in findings])},
    ]
    try:
        raw = await meta_client.chat(messages)
        verdict = verdict_from_model(parse_model_json(raw))
    except meta_client.MetaAPIError as e:
        log.error("Muse Spark call failed: %s", e)
        return fallback_verdict(findings, "service unreachable")
    except (ValueError, TypeError) as e:
        log.error("Couldn't read Muse Spark reply: %s", e)
        return fallback_verdict(findings, "unexpected reply")
    return apply_findings(verdict, findings)
