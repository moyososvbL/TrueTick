"""Draws TrueTick's own 3D-style illustrations (coin, rings, chat bubbles, chain, flag, microphone) as SVG files.

    python scripts/make_ui_assets.py

Everything is drawn from scratch in code (no stock images), so the app owns all its artwork.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_art  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "frontend" / "img"


def save(name: str, svg: str) -> None:
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    svg = svg.replace(' class="art"', "").replace(' class="obj"', "")
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    print("saved", name)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    save("coin", ui_art.disc("d"))
    save("rings", ui_art.rings("r"))
    save("bubbles", ui_art.bubbles("b"))
    save("chain", ui_art.chain("c"))
    save("flag", ui_art.flag("f"))
    save("mic", ui_art.mic("m"))
    save("qr", ui_art.qr("q"))
