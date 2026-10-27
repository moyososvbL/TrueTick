"""Known scam formats used to give Muse Spark context and to name the matching pattern."""

import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).with_name("scam_patterns.json")


@lru_cache
def load_patterns() -> dict:
    return json.loads(_FILE.read_text(encoding="utf-8"))


def patterns_for_prompt() -> str:
    """A compact text summary of all patterns, for the Muse Spark system prompt."""
    data = load_patterns()
    lines = []
    for p in data["patterns"]:
        lines.append(f"[{p['id']}] {p['name']}: {p['description']}")
        lines.append("  Signals: " + "; ".join(p["signals"]))
        lines.append("  What happens next: " + p["what_next"])
    lines.append("Universal red flags: " + "; ".join(data["universal_red_flags"]))
    return "\n".join(lines)
