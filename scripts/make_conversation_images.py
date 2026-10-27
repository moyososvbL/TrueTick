"""Makes the fictional 4-screenshot romance conversation used to demo the whole-conversation check.

Everything is invented (names, places, link). The story contradicts itself on purpose:
job (surgeon → oil rig engineer), location (Houston → North Sea), age (45 → 52) and daughter's name.

    python scripts/make_conversation_images.py
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "samples" / "test_images"
FONT_DIR = Path("/usr/share/fonts/opentype/inter")
W, H = 1080, 1900


def font(size, weight="Regular"):
    for path in (FONT_DIR / f"Inter-{weight}.otf", Path("C:/Windows/Fonts/segoeui.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


BODY, SMALL, NAME = font(34), font(24), font(40, "SemiBold")

DAYS = [
    ("Mon 5 Oct", [
        ("them", "Hello, is this Sarah? I think I have the wrong number. Sorry to bother you.", "19:02"),
        ("me", "No, I'm not Sarah. No problem!", "19:10"),
        ("them", "You seem kind. I'm Daniel, 45, a heart surgeon here in Houston. Widowed, one daughter, Emily.", "19:12"),
        ("them", "Can we be friends? I don't meet many genuine people.", "19:13"),
    ]),
    ("Thu 8 Oct", [
        ("them", "Good morning my dear. I can't stop thinking about you.", "07:05"),
        ("me", "Good morning :) how is the hospital?", "07:30"),
        ("them", "I'm actually on contract as an engineer on an oil rig in the North Sea now. The signal is bad so no video calls.", "07:41"),
        ("them", "I'm 52 but my heart feels young since I met you.", "07:42"),
    ]),
    ("Sun 11 Oct", [
        ("them", "My love, I made 40% profit this week on a crypto platform my uncle uses. I want us to build a future.", "20:15"),
        ("them", "Start small, just $500. Register here: http://zenora-trade-pro.top/join", "20:16"),
        ("me", "I'm not sure about crypto...", "20:40"),
        ("them", "Trust me, I would never lead you wrong. Do it tonight, the bonus ends at midnight.", "20:41"),
    ]),
    ("Wed 14 Oct", [
        ("them", "Honey, bad news. My daughter Jessica is in hospital and my account is frozen offshore.", "06:50"),
        ("them", "I need $3,000 for the surgery deposit. Please send Bitcoin today, I will pay you back double.", "06:51"),
        ("them", "Please don't tell your family, they won't understand our love.", "06:52"),
    ]),
]


def bubble(d, y, side, text, time):
    lines = textwrap.wrap(text, 34)
    lh = 46
    bh = len(lines) * lh + 70
    bw = max(d.textlength(l, font=BODY) for l in lines) + 60
    bw = max(bw, 260)
    x = 40 if side == "them" else W - 40 - bw
    d.rounded_rectangle((x, y, x + bw, y + bh), 18, fill="#ffffff" if side == "them" else "#dcf8c6")
    for i, l in enumerate(lines):
        d.text((x + 28, y + 20 + i * lh), l, font=BODY, fill="#1b1f1d")
    d.text((x + bw - 24, y + bh - 14), time, font=SMALL, fill="#7a807c", anchor="rb")
    return y + bh + 22


def make(n, day, messages):
    im = Image.new("RGB", (W, H), "#ece5dd")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 200), fill="#075e55")
    d.text((40, 40), "9:41", font=SMALL, fill="white")
    d.ellipse((40, 95, 130, 185), fill="#c9b5a3")
    d.text((155, 108), "Daniel", font=NAME, fill="white")
    d.text((155, 158), "online", font=SMALL, fill="#d6efe9")
    d.rounded_rectangle((W / 2 - 110, 230, W / 2 + 110, 280), 14, fill="#e1f2fb")
    d.text((W / 2, 255), day, font=SMALL, fill="#3d5a66", anchor="mm")
    y = 310
    for side, text, time in messages:
        y = bubble(d, y, side, text, time)
    path = OUT / f"conversation_romance_{n}.png"
    im.save(path)
    print("saved", path.name)


if __name__ == "__main__":
    for n, (day, msgs) in enumerate(DAYS, 1):
        make(n, day, msgs)
