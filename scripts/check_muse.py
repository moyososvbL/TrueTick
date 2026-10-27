"""Checks that TrueTick can talk to Muse Spark.

Run from the project root (with the virtual environment active):
    python scripts/check_muse.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.meta_client import MetaAPIError, chat  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


async def main() -> None:
    s = get_settings()
    print(f"Calling {s.text_model} at {s.meta_api_base_url} ...")
    try:
        reply = await chat([
            {"role": "system", "content": "You are TrueTick, a scam-checking assistant. Answer in one short sentence."},
            {"role": "user", "content": "Is this a scam: 'Your bank account is locked. Send your OTP now to unlock it.'"},
        ])
    except MetaAPIError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    print(f"\n✅ Muse Spark replied:\n{reply}")


asyncio.run(main())
