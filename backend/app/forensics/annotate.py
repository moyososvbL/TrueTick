"""Draws the suspicious areas Muse Spark found onto the screenshot, so the user can SEE them."""

import base64
import io

from PIL import Image, ImageDraw, ImageFont

MAX_W = 1000
RED = (220, 38, 38)


def _font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(image_bytes: bytes, regions: list[dict]) -> str:
    """regions: [{"box": [x1, y1, x2, y2] on a 0-1000 scale, "label": "..."}]. Returns a data: URL."""
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)))
    W, H = im.size
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = _font(max(16, W // 40))
    drawn = 0
    for i, r in enumerate(regions[:6], start=1):
        try:
            x1, y1, x2, y2 = [float(v) for v in r["box"]]
        except (KeyError, TypeError, ValueError):
            continue
        x1, x2 = sorted((max(0, min(1000, x1)), max(0, min(1000, x2))))
        y1, y2 = sorted((max(0, min(1000, y1)), max(0, min(1000, y2))))
        if x2 - x1 < 5 or y2 - y1 < 5:
            continue
        box = (x1 * W / 1000, y1 * H / 1000, x2 * W / 1000, y2 * H / 1000)
        d.rectangle(box, fill=RED + (40,), outline=RED + (255,), width=max(3, W // 250))
        tag = str(i)
        tw, th = d.textbbox((0, 0), tag, font=font)[2:]
        bx, by = box[0], max(0, box[1] - th - 10)
        d.rectangle((bx, by, bx + tw + 14, by + th + 8), fill=RED + (255,))
        d.text((bx + 7, by + 2), tag, font=font, fill=(255, 255, 255, 255))
        drawn += 1
    if not drawn:
        return ""
    out = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
