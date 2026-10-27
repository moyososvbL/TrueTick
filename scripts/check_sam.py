"""Shows what SAM 3.1 returns, so TrueTick can use it for receipts.

Run from the project root (virtual environment active):
    python scripts/check_sam.py path/to/receipt.jpg "amount"

The full raw output is saved to samples/private/sam_output.json (never committed).
Paste the summary this script prints (not the file) when asked.
"""

import asyncio
import json
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.ai.meta_client import MetaAPIError, respond, upload_file  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


def shorten(value, limit=120):
    """Make long values (like masks) readable."""
    if isinstance(value, str):
        return value if len(value) <= limit else f"<string, {len(value)} chars> {value[:40]}..."
    if isinstance(value, list):
        return [shorten(v, limit) for v in value[:3]] + ([f"... {len(value)} items"] if len(value) > 3 else [])
    if isinstance(value, dict):
        return {k: shorten(v, limit) for k, v in value.items()}
    return value


async def main(path: Path, prompt: str) -> None:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    model = get_settings().segment_model
    try:
        print(f"Uploading {path.name} ...")
        file_id = await upload_file(path.read_bytes(), path.name, mime)
        print(f"Asking {model} to find: {prompt!r} ...")
        events = await respond(
            model,
            [{"type": "input_text", "text": prompt}, {"type": "input_image", "file_id": file_id}],
            metadata={"mask_encoding": "lossless"},
        )
    except MetaAPIError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    out = ROOT / "samples" / "private" / "sam_output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=2), encoding="utf-8")

    print(f"\n✅ Received {len(events)} events. Full output saved to {out}")
    print("Event types:", sorted({str(e.get('type')) for e in events}))
    print("\nShortened view of each distinct event type:")
    shown = set()
    for e in events:
        t = str(e.get("type"))
        if t not in shown:
            shown.add(t)
            print(f"\n--- {t} ---")
            print(json.dumps(shorten(e), indent=2)[:1500])


def _require_file(path: Path) -> Path:
    if not path.is_file():
        print(f"❌ File not found: {path}")
        print("Put the file in your TrueTick folder and use its exact name (including .jpg/.png/.ogg),")
        print('or give the full path in quotes, e.g. "C:/Users/pc/Pictures/receipt.jpg"')
        sys.exit(1)
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python scripts/check_sam.py path/to/image.jpg "what to find"')
        sys.exit(1)
    asyncio.run(main(_require_file(Path(sys.argv[1])), sys.argv[2] if len(sys.argv) > 2 else "text"))
