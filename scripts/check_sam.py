"""Finds out how SAM 3.1 answers on the Meta Model API, so TrueTick can use it for receipts.

Run from the project root (virtual environment active):
    python scripts/check_sam.py

Step 1: a very easy test image (a red circle and a blue square) to see if SAM answers at all.
Step 2: the test receipt with a few prompts.
Each attempt tries three request styles (streaming with mask settings, streaming without, and
non-streaming). Full raw replies are saved in samples/private/sam/ (never committed).
Paste the printed summary (not the files).
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.ai.meta_client import MetaAPIError, _base_and_headers, upload_file  # noqa: E402
from backend.app.config import get_settings  # noqa: E402

OUT = ROOT / "samples" / "private" / "sam"


def make_shapes_image() -> Path:
    path = OUT / "shapes.png"
    im = Image.new("RGB", (800, 500), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((80, 120, 340, 380), fill=(220, 30, 30))
    d.rectangle((460, 130, 720, 390), fill=(30, 80, 220))
    im.save(path)
    return path


def shorten(value, limit=160):
    if isinstance(value, str):
        return value if len(value) <= limit else f"<{len(value)} chars> {value[:60]}..."
    if isinstance(value, list):
        return [shorten(v, limit) for v in value[:3]] + ([f"... {len(value)} items"] if len(value) > 3 else [])
    if isinstance(value, dict):
        return {k: shorten(v, limit) for k, v in value.items()}
    return value


def summarize(name: str, payload) -> bool:
    """Print what came back. Returns True if anything beyond an empty text answer appeared."""
    blob = json.dumps(payload)
    events = payload if isinstance(payload, list) else [payload]
    final = None
    for e in reversed(events):
        if isinstance(e, dict) and (e.get("type") == "response.completed" or e.get("object") == "response"):
            final = e.get("response", e)
            break
    output = (final or {}).get("output") or []
    item_types = sorted({str(i.get("type")) for i in output if isinstance(i, dict)})
    texts = [c.get("text", "") for i in output if isinstance(i, dict) for c in (i.get("content") or [])
             if isinstance(c, dict)]
    other_keys = sorted({k for i in output if isinstance(i, dict) for k in i} - {"content", "id", "role", "status", "type"})
    event_types = sorted({str(e.get("type")) for e in events if isinstance(e, dict)})
    interesting = any(t for t in texts) or any(t != "message" for t in item_types) or bool(other_keys) or \
        any(w in blob for w in ('"mask', '"masks', '"bbox', '"box', '"segment', '"polygon', '"rle'))
    print(f"    {name}: {len(blob):,} bytes | output item types: {item_types or '-'}")
    if any(texts):
        print(f"      text: {shorten(' | '.join(t for t in texts if t))}")
    if other_keys:
        print(f"      extra fields: {other_keys}")
    extra_events = [t for t in event_types if t not in {
        "response.created", "response.in_progress", "response.output_item.added", "response.content_part.added",
        "response.output_text.done", "response.content_part.done", "response.output_item.done", "response.completed"}]
    if extra_events:
        print(f"      extra event types: {extra_events}")
    if interesting:
        sample = next((i for i in output if isinstance(i, dict) and i.get("type") != "message"), output[0] if output else payload)
        print(f"      sample: {json.dumps(shorten(sample))[:900]}")
    else:
        print("      (empty answer)")
    return interesting


async def try_prompt(client, base, headers, model, file_id, prompt, tag) -> bool:
    content = [{"type": "input_text", "text": prompt}, {"type": "input_image", "file_id": file_id}]
    styles = [
        ("stream + mask_encoding", {"stream": True, "metadata": {"mask_encoding": "lossless"}}),
        ("stream, no metadata", {"stream": True}),
        ("no streaming", {"stream": False, "metadata": {"mask_encoding": "lossless"}}),
    ]
    found = False
    print(f"\n  Prompt {prompt!r}")
    for name, extra in styles:
        payload = {"model": model, "input": [{"type": "message", "role": "user", "content": content}], **extra}
        try:
            if extra["stream"]:
                events = []
                async with client.stream("POST", f"{base}/responses", json=payload,
                                         headers={**headers, "Accept": "text/event-stream"}) as r:
                    if r.status_code >= 400:
                        print(f"    {name}: HTTP {r.status_code}: {(await r.aread()).decode(errors='replace')[:400]}")
                        continue
                    async for line in r.aiter_lines():
                        if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                            try:
                                events.append(json.loads(line[6:]))
                            except json.JSONDecodeError:
                                events.append({"type": "raw", "data": line[6:200]})
                result = events
            else:
                r = await client.post(f"{base}/responses", json=payload, headers=headers)
                if r.status_code >= 400:
                    print(f"    {name}: HTTP {r.status_code}: {r.text[:400]}")
                    continue
                result = r.json()
        except httpx.HTTPError as e:
            print(f"    {name}: connection problem ({e.__class__.__name__})")
            continue
        (OUT / f"{tag}_{prompt.replace(' ', '_')}_{name.replace(' ', '_').replace(',', '').replace('+', 'and')}.json"
         ).write_text(json.dumps(result, indent=2), encoding="utf-8")
        found = summarize(name, result) or found
    return found


async def main(receipt: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        base, headers = _base_and_headers()
    except MetaAPIError as e:
        print(f"❌ {e}")
        sys.exit(1)
    model = get_settings().segment_model
    async with httpx.AsyncClient(timeout=180) as client:
        print(f"STEP 1: easy test image (red circle + blue square) with {model}")
        shapes = make_shapes_image()
        shapes_id = await upload_file(shapes.read_bytes(), shapes.name, "image/png")
        ok_shapes = False
        for p in ("circle", "red circle", "square"):
            ok_shapes = await try_prompt(client, base, headers, model, shapes_id, p, "shapes") or ok_shapes

        print(f"\nSTEP 2: test receipt ({receipt.name})")
        receipt_id = await upload_file(receipt.read_bytes(), receipt.name, "image/jpeg")
        ok_receipt = False
        for p in ("text", "number", "logo", "check mark"):
            ok_receipt = await try_prompt(client, base, headers, model, receipt_id, p, "receipt") or ok_receipt

    print("\nRESULT")
    print(f"  Easy image: {'✅ SAM returned something' if ok_shapes else '❌ empty for every style'}")
    print(f"  Receipt:    {'✅ SAM returned something' if ok_receipt else '❌ empty for every style'}")
    print(f"  Raw replies saved in {OUT}")
    print("  Paste everything above (from STEP 1) into the chat.")


if __name__ == "__main__":
    default = ROOT / "samples" / "test_images" / "receipt_edited_fictional_bank.jpg"
    receipt = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not receipt.is_file():
        print(f"❌ File not found: {receipt}")
        sys.exit(1)
    asyncio.run(main(receipt))
