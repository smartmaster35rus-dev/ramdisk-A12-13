#!/usr/bin/env python3
"""Render assets/header.png (GitHub README blocks SVG in img tags)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "header.png"
W, H = 900, 180


def main() -> None:
    img = Image.new("RGB", (W, H), "#0f0c29")
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(int(15 + t * 25), int(12 + t * 20), int(41 + t * 30)))

    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=18, outline=(80, 80, 100), width=2)

    for path, size in (
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 42),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", 18),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14),
    ):
        try:
            fonts = [ImageFont.truetype(path, size) for size in (42, 18, 14)]
            break
        except OSError:
            fonts = [ImageFont.load_default()] * 3

    title_font, sub_font, small_font = fonts
    draw.text((W // 2, 62), "A12 / A13 Ramdisk Catalog", fill="#ffffff", font=title_font, anchor="mm")
    draw.text(
        (W // 2, 108),
        "Live bootchain releases · iPhone & iPad · auto-updated",
        fill="#c7c7cc",
        font=sub_font,
        anchor="mm",
    )
    draw.ellipse([108, 82, 120, 94], fill="#34C759")
    draw.text((132, 90), "ONLINE", fill="#34C759", font=small_font, anchor="lm")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"OK {OUT}")


if __name__ == "__main__":
    main()
