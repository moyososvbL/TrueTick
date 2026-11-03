"""How often do TrueTick's non-AI link checks wrongly flag real websites?

Runs the instant link checks (no AI, no network) on samples/legit_links.txt: real links people
share every day (banks, government, delivery, social media, shorteners, Nigerian services).
Prints every link that gets a warning, and the false-alarm rate.

    python scripts/check_false_alarms.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.checks.links import run_checks  # noqa: E402

links = [l.strip() for l in (Path(__file__).resolve().parents[1] / "samples" / "legit_links.txt").read_text().splitlines()
         if l.strip() and not l.startswith("#")]
high = medium = 0
for url in links:
    found = run_checks(f"Here is the link: {url}")
    sev = {f.severity for f in found}
    if "high" in sev:
        high += 1
    elif "medium" in sev:
        medium += 1
    if found:
        print(f"[{'HIGH' if 'high' in sev else 'medium'}] {url}")
        for f in found:
            print("     -", f.message[:140])
n = len(links)
print(f"\n{n} real links checked")
print(f"High-risk false alarms: {high} ({high / n:.1%})")
print(f"Medium warnings:        {medium} ({medium / n:.1%})")
print(f"No warning:             {n - high - medium} ({(n - high - medium) / n:.1%})")
