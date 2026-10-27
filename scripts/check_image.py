"""Checks Muse Image and makes a sample family warning card.

Run from the project root (virtual environment active):
    python scripts/check_image.py
The card is saved to samples/private/sample_card.png (never committed). Open it to see the result.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.cards import make_card  # noqa: E402


async def main() -> None:
    print("Asking Muse Image for an illustration (about $0.01) ...")
    png, illustrated = await make_card("sugar_daddy_gift_card", "", "TrueTick")
    out = ROOT / "samples" / "private" / "sample_card.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    if illustrated:
        print(f"✅ Muse Image worked. Card saved to {out}")
    else:
        print(f"⚠️ Muse Image didn't respond, so the card was made without an illustration: {out}")
        print("   Check the error lines above (or the server log) and send them to me.")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
