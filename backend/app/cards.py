"""Family warning cards: a shareable image about a scam TYPE (never the user's own message).

Muse Image draws a friendly illustration; TrueTick lays out the words itself so they are always
spelled correctly. Cards are cached per scam type, so each one is generated (and paid for) once.
"""

import hashlib
import io
import logging
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.app.ai import meta_client
from backend.app.config import get_settings
from backend.app.patterns import load_patterns

log = logging.getLogger("truetick.cards")
W, H = 1080, 1350
INK, MUTED, ACCENT, WARN, BG = (20, 24, 22), (90, 98, 94), (15, 123, 95), (198, 40, 40), (250, 247, 240)

ILLUSTRATION_PROMPT = (
    "A warm, friendly flat vector illustration for a public safety poster about {topic}. "
    "Show an older person and a younger family member looking at a phone together, calm and protected, "
    "with a subtle shield motif. Soft cream background, green and warm red accents. "
    "No text, no letters, no logos, no brand names."
)


def _font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def card_content(pattern_id: str | None, scam_type: str) -> dict:
    p = next((x for x in load_patterns()["patterns"] if x["id"] == pattern_id), None)
    if p:
        return {"key": p["id"], "title": p["name"], "tips": p["advice"][:3], "topic": p["name"]}
    title = scam_type.strip()[:60] or "Scam alert"
    return {"key": "type-" + hashlib.sha1(title.lower().encode()).hexdigest()[:10], "title": title,
            "tips": ["Don't send money, gift cards or codes to anyone who contacts you first.",
                     "Hang up and call back on a number you already know.",
                     "Check any message with TrueTick before you act."],
            "topic": "online scams"}


def render_card(title: str, tips: list[str], illustration: bytes | None, site: str) -> bytes:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 150), fill=WARN)
    d.text((60, 42), "⚠  SCAM ALERT", font=_font(64, True), fill="white")
    y = 190
    for line in _wrap(d, title, _font(56, True), W - 120)[:3]:
        d.text((60, y), line, font=_font(56, True), fill=INK)
        y += 70
    art_top, art_h = y + 20, 470
    if illustration:
        try:
            art = Image.open(io.BytesIO(illustration)).convert("RGB")
            scale = max((W - 120) / art.width, art_h / art.height)
            art = art.resize((round(art.width * scale), round(art.height * scale)))
            left, top = (art.width - (W - 120)) // 2, (art.height - art_h) // 2
            art = art.crop((left, top, left + W - 120, top + art_h))
            mask = Image.new("L", art.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, *art.size), radius=36, fill=255)
            im.paste(art, (60, art_top), mask)
        except Exception as e:
            log.error("Bad illustration: %s", e)
            illustration = None
    if not illustration:
        d.rounded_rectangle((60, art_top, W - 60, art_top + art_h), radius=36, fill=(232, 241, 236))
        cx, cy = W // 2, art_top + art_h // 2
        d.polygon([(cx, cy - 150), (cx + 130, cy - 95), (cx + 110, cy + 80), (cx, cy + 160),
                   (cx - 110, cy + 80), (cx - 130, cy - 95)], fill=ACCENT)
        d.line([(cx - 55, cy + 5), (cx - 12, cy + 50), (cx + 65, cy - 45)], fill="white", width=26, joint="curve")
    y = art_top + art_h + 40
    tip_font = _font(38)
    for tip in tips[:3]:
        lines = _wrap(d, tip, tip_font, W - 170)[:2]
        d.ellipse((60, y + 10, 84, y + 34), fill=ACCENT)
        for line in lines:
            d.text((105, y), line, font=tip_font, fill=INK)
            y += 50
        y += 18
    d.rectangle((0, H - 110, W, H), fill=ACCENT)
    d.text((60, H - 82), f"Check any message free: {site}", font=_font(36, True), fill="white")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


async def make_card(pattern_id: str | None, scam_type: str, site: str) -> tuple[bytes, bool]:
    """Returns (PNG bytes, whether Muse Image drew the illustration)."""
    c = card_content(pattern_id, scam_type)
    cache_dir = Path(get_settings().data_dir) / "cards"
    cache_dir.mkdir(parents=True, exist_ok=True)
    art_path = cache_dir / f"{re.sub(r'[^a-z0-9_-]', '', c['key'].lower())}.art.png"
    art = art_path.read_bytes() if art_path.exists() else None
    if art is None:
        try:
            art = await meta_client.generate_image(ILLUSTRATION_PROMPT.format(topic=c["topic"]), size="1024x1024")
            art_path.write_bytes(art)
        except meta_client.MetaAPIError as e:
            log.error("Muse Image unavailable: %s", e)
            art = None
    return render_card(c["title"], c["tips"], art, site), art is not None
