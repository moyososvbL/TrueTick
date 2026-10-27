"""'Report this scam': official reporting links for the user's country, plus a ready-to-send summary.

The country comes from the user's choice (or a guess from their browser's time zone in the app).
We never ask for or store the user's identity or location.
"""

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from backend.app.models import Verdict

_FILE = Path(__file__).with_name("authorities.json")


@lru_cache
def _data() -> dict:
    return json.loads(_FILE.read_text(encoding="utf-8"))


def countries() -> list[dict]:
    return [{"code": code, "name": c["name"]} for code, c in _data()["countries"].items()]


def report_options(country: str = "", intimate_images: bool = False) -> dict:
    data = _data()
    entry = data["countries"].get((country or "").upper(), data["default"])
    out = {
        "country": entry["name"],
        "links": list(entry["links"]),
        "note": entry.get("note", "") or data["default"].get("note", ""),
        "always": data["always"],
    }
    if intimate_images:
        out["links"] = data["intimate_images"] + out["links"]
    return out


def report_summary(v: Verdict, what_happened: str = "") -> str:
    """Plain-text summary the user can paste into a police, bank or platform report."""
    lines = [
        "SCAM REPORT (prepared with TrueTick)",
        f"Date checked: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Risk assessment: {v.risk.upper()}" + (f" ({v.scam_type})" if v.scam_type else ""),
    ]
    if v.summary:
        lines.append(f"Summary: {v.summary}")
    if what_happened.strip():
        lines += ["", "What happened (in my words):", what_happened.strip()]
    if v.extracted_text:
        lines += ["", "Message / transcript received:", v.extracted_text[:2000]]
    facts = [f.message for f in v.findings]
    if facts:
        lines += ["", "Warning signs found:"] + [f"- {f}" for f in facts[:8]]
    lines += ["", "Links, phone numbers and accounts used by the scammer: (add any you have)",
              "Money sent, if any (amount, date, method, receiving account):"]
    return "\n".join(lines)
