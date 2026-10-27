"""Helpers shared by all analyzers: reading the model's JSON and combining it with facts."""

import json
import re

from backend.app.models import RISK_ORDER, Finding, Verdict

THREAT_ADVICE = [
    "Don't pay. Paying usually leads to bigger demands.",
    "Stop replying, but keep screenshots: they are evidence.",
    "Report the account and tell someone you trust. This is not your fault.",
    "If intimate images are involved: StopNCII.org helps stop them spreading; if you were under 18 when they were taken, use Take It Down (takeitdown.ncmec.org).",
]


def parse_model_json(raw: str) -> dict:
    """Models sometimes add ```json fences or a sentence around the JSON; pull out the object."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        raise ValueError("No JSON object in model reply")
    return json.loads(match.group(0))


def verdict_from_model(data: dict) -> Verdict:
    risk = str(data.get("risk", "unknown")).lower()
    if risk not in RISK_ORDER:
        risk = "unknown"
    pattern = data.get("pattern_id")
    return Verdict(
        risk=risk,
        scam_type=str(data.get("scam_type") or ""),
        pattern_id=str(pattern) if pattern not in (None, "", "null") else None,
        summary=str(data.get("summary") or ""),
        reasons=[str(r) for r in (data.get("reasons") or [])][:4],
        what_next=str(data.get("what_next") or ""),
        advice=[str(a) for a in (data.get("advice") or [])][:3],
        is_threat=bool(data.get("is_threat", False)),
        ai_used=True,
    )


def apply_findings(v: Verdict, findings: list[Finding]) -> Verdict:
    """Hard facts from non-AI checks can raise the risk but never lower it."""
    v.findings = findings
    floor = "high" if any(f.severity == "high" for f in findings) else "medium" if findings else "unknown"
    if RISK_ORDER[floor] > RISK_ORDER[v.risk]:
        v.risk = floor
        if not v.summary or v.summary.lower().startswith("no "):
            v.summary = "The links or names in this message show clear warning signs."
    if v.is_threat:
        v.advice = list(dict.fromkeys(v.advice + THREAT_ADVICE))
    return v


def fallback_verdict(findings: list[Finding], reason: str) -> Verdict:
    """Used when Muse Spark can't be reached: report only what the non-AI checks found."""
    v = Verdict(
        risk="unknown",
        summary=f"Our AI check isn't available right now ({reason}). Here's what our link checks found.",
        advice=["Don't send money, codes or card details until you've verified who this is."],
    )
    v = apply_findings(v, findings)
    if not findings:
        v.summary = f"Our AI check isn't available right now ({reason}). Please try again in a minute."
    return v
