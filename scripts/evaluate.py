"""Measures TrueTick's accuracy on samples/test_cases.csv.

Run from the project root (virtual environment active):
    python scripts/evaluate.py            # full check with Muse Spark (uses API credit)
    python scripts/evaluate.py --offline  # only the non-AI link/lookalike checks (free)

A "scam" case counts as correct if TrueTick says high or medium risk.
A "safe" case counts as correct if TrueTick says low risk.
Detailed results are saved to samples/private/eval_results.csv (never committed).
"""

import asyncio
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.analyzers.text import analyze_text  # noqa: E402
from backend.app.checks.links import run_checks  # noqa: E402


def load_cases() -> list[dict]:
    with open(ROOT / "samples" / "test_cases.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def offline(cases: list[dict]) -> None:
    print("Non-AI checks only (links + lookalike letters):\n")
    false_alarms = 0
    for c in cases:
        findings = run_checks(c["text"])
        if findings:
            if c["expected"] == "safe":
                false_alarms += 1
            mark = "FALSE ALARM" if c["expected"] == "safe" else "flagged"
            print(f"#{c['id']:>2} {mark:<11} {c['category']}: {findings[0].message}")
    flagged = sum(1 for c in cases if c["expected"] == "scam" and run_checks(c["text"]))
    scams = sum(1 for c in cases if c["expected"] == "scam")
    print(f"\nLink checks alone flagged {flagged}/{scams} scams (most scams have no link: that's Muse Spark's job).")
    print(f"False alarms on safe messages: {false_alarms}")


async def full(cases: list[dict]) -> None:
    sem = asyncio.Semaphore(3)
    results: dict[str, object] = {}

    async def run(c):
        async with sem:
            t0 = time.perf_counter()
            v = await analyze_text(c["text"])
            results[c["id"]] = (v, time.perf_counter() - t0)

    await asyncio.gather(*(run(c) for c in cases))

    correct, rows, misses = 0, [], []
    for c in cases:
        v, secs = results[c["id"]]
        ok = v.risk in ("high", "medium") if c["expected"] == "scam" else v.risk == "low"
        correct += ok
        if not ok:
            misses.append((c, v))
        rows.append([c["id"], c["expected"], c["category"], v.risk, v.pattern_id or "", v.scam_type,
                     "OK" if ok else "MISS", f"{secs:.1f}", v.ai_used])
        print(f"{'OK  ' if ok else 'MISS'} #{c['id']:>2} {c['expected']:<4} -> {v.risk:<7} {c['category']:<22} {v.scam_type[:40]}")

    out = ROOT / "samples" / "private" / "eval_results.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "expected", "category", "risk", "pattern_id", "scam_type", "result", "seconds", "ai_used"])
        w.writerows(rows)

    scams = [c for c in cases if c["expected"] == "scam"]
    safes = [c for c in cases if c["expected"] == "safe"]
    caught = sum(1 for c in scams if results[c["id"]][0].risk in ("high", "medium"))
    false_alarms = sum(1 for c in safes if results[c["id"]][0].risk in ("high", "medium"))
    avg = sum(s for _, s in results.values()) / len(results)
    print(f"\nScore: {correct}/{len(cases)} correct")
    print(f"Scams caught: {caught}/{len(scams)}   False alarms: {false_alarms}/{len(safes)}   Avg time: {avg:.1f}s")
    if any(not v.ai_used for v, _ in results.values()):
        print("⚠️ Some checks ran without AI (Muse Spark unreachable). Check your key and internet.")
    if misses:
        print("\nMisses to look at:")
        for c, v in misses:
            print(f"  #{c['id']} ({c['category']}) got {v.risk}: {v.summary[:120]}")
    print(f"\nDetails saved to {out}")


if __name__ == "__main__":
    cases = load_cases()
    if "--offline" in sys.argv:
        offline(cases)
    else:
        asyncio.run(full(cases))
