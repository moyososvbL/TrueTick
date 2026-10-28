"""Tests TrueTick on REAL phishing links and real, safe websites.

    python scripts/evaluate_links.py                 # 15 fresh phishing links from OpenPhish + 15 safe sites
    python scripts/evaluate_links.py --count 25      # more phishing links
    python scripts/evaluate_links.py --no-visit      # skip the sealed-browser screenshots (faster, cheaper)
    python scripts/evaluate_links.py --file my.txt   # your own list, one per line:  phish,<link>  or  safe,<link>

Safety: the links are NEVER opened in your own browser. They are only opened in the sealed,
throwaway headless browser (no downloads, no saved data) and read as text by the safe link inspector.
Don't click any link this script prints.

Each link goes through TrueTick's three layers:
  1. instant checks (lookalike letters, risky endings, shorteners...)
  2. safe page inspection (redirects, login fields, website age)
  3. Muse Spark: the full text verdict + "we visited the website for you" (screenshot + brand check)
A phishing link counts as caught if TrueTick says high or medium risk.
A safe site counts as correct if it says low risk.
Results:  samples/private/link_eval.csv   Screenshots:  samples/private/link_shots/   (never committed)
"""

import argparse
import asyncio
import base64
import csv
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.analyzers.text import analyze_text  # noqa: E402
from backend.app.checks.link_inspect import inspect_url  # noqa: E402
from backend.app.checks.links import check_url  # noqa: E402
from backend.app.checks.site_visit import visit  # noqa: E402

OPENPHISH_FEEDS = [
    "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",  # same free feed, on GitHub
    "https://openphish.com/feed.txt",
]
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrueTick-evaluation"}
SAFE_SITES = [
    "https://www.google.com", "https://www.paypal.com/signin", "https://www.bbc.com", "https://www.wikipedia.org",
    "https://login.microsoftonline.com", "https://www.amazon.com", "https://www.apple.com", "https://www.netflix.com/login",
    "https://github.com/login", "https://www.gtbank.com", "https://www.accessbankplc.com", "https://www.jumia.com.ng",
    "https://paystack.com", "https://www.reuters.com", "https://www.facebook.com",
]
OUT = ROOT / "samples" / "private"
RISKY = {"high", "medium"}


async def fetch_phishing(count: int) -> list[str]:
    r, problems = None, []
    async with httpx.AsyncClient(timeout=20, headers=BROWSER_UA, follow_redirects=True) as client:
        for feed in OPENPHISH_FEEDS:
            try:
                r = await client.get(feed)
                r.raise_for_status()
                break
            except httpx.HTTPError as e:
                code = getattr(getattr(e, "response", None), "status_code", "")
                problems.append(f"{feed} → {e.__class__.__name__} {code}")
                r = None
    if r is None:
        print("❌ Couldn't download the phishing feed:\n  " + "\n  ".join(problems) + "\nUse --file instead.")
        sys.exit(1)
    links, seen_hosts = [], set()
    for line in r.text.splitlines():
        url = line.strip()
        host = httpx.URL(url).host if url.startswith("http") else ""
        if host and host not in seen_hosts:  # one link per website, so results aren't skewed
            seen_hosts.add(host)
            links.append(url)
        if len(links) >= count:
            break
    return links


def load_file(path: str) -> list[tuple[str, str]]:
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "," in line and not line.startswith("#"):
            label, url = line.split(",", 1)
            label = "phish" if label.strip().lower() in ("phish", "scam") else "safe"
            cases.append((label, url.strip()))
    return cases


async def evaluate(label: str, url: str, n: int, do_visit: bool) -> dict:
    t0 = time.perf_counter()
    instant = check_url(url)
    try:
        inspected = await inspect_url(url)
    except Exception:
        inspected = []
    verdict = await analyze_text(f"Is this link safe to open? {url}")
    row = {
        "n": n, "expected": label, "url": url,
        "instant_flag": "yes" if instant else "no",
        "inspect_flag": "yes" if inspected else "no",
        "muse_risk": verdict.risk, "muse_type": verdict.scam_type,
        "visit_risk": "", "looks_like": "", "visit_note": "",
    }
    if do_visit:
        v = await visit(url)
        if v.error:
            row["visit_note"] = v.error
        else:
            row["visit_risk"], row["looks_like"] = v.risk, v.looks_like
            row["visit_note"] = (v.findings[0].message if v.findings else v.summary)[:200]
            shots = OUT / "link_shots"
            shots.mkdir(parents=True, exist_ok=True)
            (shots / f"{n:02d}_{label}.jpg").write_bytes(base64.b64decode(v.screenshot.split(",", 1)[1]))
    final = "high" if "high" in (verdict.risk, row["visit_risk"]) else \
        "medium" if "medium" in (verdict.risk, row["visit_risk"]) else verdict.risk
    row["final_risk"] = final
    row["correct"] = "yes" if (final in RISKY if label == "phish" else final == "low") else "no"
    row["seconds"] = round(time.perf_counter() - t0, 1)
    return row


async def main(args) -> None:
    if args.file:
        cases = load_file(args.file)
    else:
        print(f"Downloading {args.count} fresh phishing links from OpenPhish…")
        cases = [("phish", u) for u in await fetch_phishing(args.count)] + [("safe", u) for u in SAFE_SITES]
    print(f"Testing {len(cases)} links (don't click any of them)…\n")

    sem = asyncio.Semaphore(3)

    async def run(i, case):
        async with sem:
            row = await evaluate(case[0], case[1], i, not args.no_visit)
            mark = "✅" if row["correct"] == "yes" else "❌"
            shown = row["url"] if case[0] == "safe" else row["url"].replace("http", "hxxp", 1)
            print(f"{mark} #{i:02d} {case[0]:<5} → {row['final_risk']:<7} {shown[:70]}")
            if row["looks_like"]:
                print(f"        page dressed up as: {row['looks_like']}")
            return row

    rows = await asyncio.gather(*(run(i, c) for i, c in enumerate(cases, 1)))
    rows.sort(key=lambda r: r["n"])

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "link_eval.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    phish = [r for r in rows if r["expected"] == "phish"]
    safe = [r for r in rows if r["expected"] == "safe"]
    dead = [r for r in phish if "didn't load" in r["visit_note"]]

    def rate(group, key, positive):
        return sum(1 for r in group if r[key] in positive)

    print("\nRESULT")
    print(f"  Phishing links caught:       {rate(phish, 'final_risk', RISKY)}/{len(phish)}")
    print(f"    by instant checks alone:   {rate(phish, 'instant_flag', {'yes'})}/{len(phish)}")
    print(f"    by page inspection:        {rate(phish, 'inspect_flag', {'yes'})}/{len(phish)}")
    print(f"    by Muse Spark (text):      {rate(phish, 'muse_risk', RISKY)}/{len(phish)}")
    if not args.no_visit:
        print(f"    by website visit:          {rate(phish, 'visit_risk', RISKY)}/{len(phish)}"
              f"  ({len(dead)} sites already taken down)")
    print(f"  Safe sites wrongly flagged:  {rate(safe, 'final_risk', RISKY)}/{len(safe)}")
    print(f"  Details: {OUT / 'link_eval.csv'}")
    print("  Paste everything from RESULT into the chat (and any ❌ lines).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=15)
    ap.add_argument("--file")
    ap.add_argument("--no-visit", action="store_true")
    asyncio.run(main(ap.parse_args()))
