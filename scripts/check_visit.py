"""Tries 'We visited the website for you' with the real Muse Spark.

    python scripts/check_visit.py https://your-deployed-truetick/demo/zenora-login.html

Needs the safe browser once:  pip install playwright  then  python -m playwright install chromium
Links on your own computer/network (localhost, 192.168...) are refused on purpose.
The screenshot is saved to samples/private/visit.jpg.
"""

import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.checks.site_visit import visit  # noqa: E402


async def main(url: str) -> None:
    r = await visit(url)
    if r.error:
        print("❌", r.error)
        return
    out = ROOT / "samples" / "private" / "visit.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(r.screenshot.split(",", 1)[1]))
    print(f"Landed on:   {r.final_url}")
    print(f"Looks like:  {r.looks_like or '-'}  |  purpose: {r.page_purpose}  |  asks for: {', '.join(r.asks_for) or '-'}")
    print(f"Summary:     {r.summary}")
    print(f"Risk:        {r.risk}")
    for f in r.findings:
        print(f"  [{f.severity}] {f.message}")
    print(f"Screenshot saved: {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_visit.py <link>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
