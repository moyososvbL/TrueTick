"""Tries the whole-conversation check with the real Muse Spark on the 4 fictional romance screenshots.

    python scripts/check_conversation.py
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.analyzers.conversation import analyze_conversation  # noqa: E402

IMAGES = [ROOT / "samples" / "test_images" / f"conversation_romance_{n}.png" for n in range(1, 5)]


async def main() -> None:
    v = await analyze_conversation([(p.read_bytes(), "image/png") for p in IMAGES])
    print(f"Risk: {v.risk}  |  Type: {v.scam_type}  |  Stage: {v.stage}")
    print(f"Summary: {v.summary}")
    print("Timeline:")
    for t in v.timeline:
        print("  -", t)
    print("Contradictions (we planted: surgeon/oil rig, Houston/North Sea, 45/52, Emily/Jessica):")
    for c in v.contradictions:
        print("  -", c)
    for f in v.findings:
        print(f"  [{f.severity}] {f.message}")


if __name__ == "__main__":
    asyncio.run(main())
