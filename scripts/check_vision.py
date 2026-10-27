"""Checks whether Muse Spark can read a screenshot.

Run from the project root (virtual environment active):
    python scripts/check_vision.py path/to/screenshot.jpg
"""

import asyncio
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.meta_client import MetaAPIError, output_text, respond, upload_file  # noqa: E402
from backend.app.config import get_settings  # noqa: E402


async def main(path: Path) -> None:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    model = get_settings().vision_model
    try:
        print(f"Uploading {path.name} ...")
        file_id = await upload_file(path.read_bytes(), path.name, mime)
        print(f"Asking {model} to read it ...")
        events = await respond(model, [
            {"type": "input_text", "text": "Write out all the text you can see in this image, then describe it in one sentence."},
            {"type": "input_image", "file_id": file_id},
        ])
    except MetaAPIError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    text = output_text(events)
    if text:
        print(f"\n✅ Muse Spark read the image:\n{text}")
    else:
        print("\n⚠️ No text came back. Event types received:")
        print(sorted({str(e.get('type')) for e in events}))
        print("First event:", str(events[0])[:500] if events else "none")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_vision.py path/to/image.jpg")
        sys.exit(1)
    asyncio.run(main(Path(sys.argv[1])))
