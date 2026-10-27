"""Shows what SAM 3.1 returns, so TrueTick can use it for receipts.

Run from the project root (virtual environment active):
    python scripts/check_sam.py path/to/receipt.jpg "text,number,logo"

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


async def main(path: Path, prompts_arg: str) -> None:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    model = get_settings().segment_model
    prompts = [p.strip() for p in prompts_arg.split(",") if p.strip()]
    try:
        print(f"Uploading {path.name} ...")
        file_id = await upload_file(path.read_bytes(), path.name, mime)
    except MetaAPIError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    out_dir = ROOT / "samples" / "private"
    out_dir.mkdir(parents=True, exist_ok=True)
    for prompt in prompts:
        try:
            events = await respond(
                model,
                [{"type": "input_text", "text": prompt}, {"type": "input_image", "file_id": file_id}],
                metadata={"mask_encoding": "lossless"},
            )
        except MetaAPIError as e:
            print(f"\n❌ {prompt!r}: {e}")
            continue
        out = out_dir / f"sam_output_{prompt.replace(' ', '_')}.json"
        out.write_text(json.dumps(events, indent=2), encoding="utf-8")
        final = next((e for e in reversed(events) if e.get("type") == "response.completed"), {})
        output = (final.get("response") or {}).get("output") or []
        texts = [c.get("text", "") for item in output for c in (item.get("content") or [])]
        extra_keys = sorted({k for item in output for k in item.keys()} - {"content", "id", "role", "status", "type"})
        annotations = [a for item in output for c in (item.get("content") or []) for a in (c.get("annotations") or [])]
        size = len(json.dumps(events))
        print(f"\n=== {prompt!r}: {len(events)} events, {size:,} bytes ===")
        print("  text:", shorten(" | ".join(t for t in texts if t)) or "(empty)")
        print("  annotations:", len(annotations), shorten(annotations[:2]) if annotations else "")
        if extra_keys:
            print("  other output fields:", extra_keys)
        other_types = sorted({str(e.get("type")) for e in events} - {
            "response.created", "response.in_progress", "response.output_item.added", "response.content_part.added",
            "response.output_text.done", "response.content_part.done", "response.output_item.done", "response.completed"})
        if other_types:
            print("  extra event types:", other_types)
            for e in events:
                if e.get("type") in other_types:
                    print("  example:", json.dumps(shorten(e))[:800])
                    break
        print(f"  saved to {out}")


def _require_file(path: Path) -> Path:
    if not path.is_file():
        print(f"❌ File not found: {path}")
        print("Put the file in your TrueTick folder and use its exact name (including .jpg/.png/.ogg),")
        print('or give the full path in quotes, e.g. "C:/Users/pc/Pictures/receipt.jpg"')
        sys.exit(1)
    return path


if __name__ == "__main__":
    default = ROOT / "samples" / "test_images" / "receipt_edited_fictional_bank.jpg"
    image = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    asyncio.run(main(_require_file(image), sys.argv[2] if len(sys.argv) > 2 else "text,number,logo,amount of money"))
