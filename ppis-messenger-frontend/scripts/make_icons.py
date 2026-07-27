"""Generate PPIS Campus Care PWA icons.

Draws a graduation cap (mortarboard) with a small heart (care) on the
brand-blue gradient, and writes all icon sizes used by the app.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

PUBLIC = os.path.join(os.path.dirname(__file__), "..", "public")

BLUE_TOP = (37, 99, 235)      # #2563eb
BLUE_BOTTOM = (29, 78, 216)   # #1d4ed8
WHITE = (255, 255, 255)
GOLD = (250, 204, 21)         # tassel


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BLUE_BOTTOM)
    top, bottom = BLUE_TOP, BLUE_BOTTOM
    for y in range(size):
        t = y / max(size - 1, 1)
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        for x in range(size):
            img.putpixel((x, y), (r, g, b))
    return img


def _rounded(img: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    size = img.width
    radius = int(size * radius_ratio)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _draw_cap(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float) -> None:
    # Mortarboard: a diamond (rotated square) board.
    w = 190 * scale  # half-width of the board
    h = 96 * scale   # half-height of the board
    board = [
        (cx, cy - h),
        (cx + w, cy),
        (cx, cy + h),
        (cx - w, cy),
    ]
    draw.polygon(board, fill=WHITE)

    # Cap body (the head part) below the board.
    band_top = cy + 8 * scale
    bw = 96 * scale
    bh = 78 * scale
    draw.polygon(
        [
            (cx - bw, band_top),
            (cx + bw, band_top),
            (cx + bw * 0.86, band_top + bh),
            (cx - bw * 0.86, band_top + bh),
        ],
        fill=WHITE,
    )
    # curved bottom of cap
    draw.ellipse(
        [cx - bw * 0.86, band_top + bh - 26 * scale,
         cx + bw * 0.86, band_top + bh + 26 * scale],
        fill=WHITE,
    )

    # Tassel button + string + gold tassel on the right.
    btn_r = 14 * scale
    draw.ellipse(
        [cx - btn_r, cy - btn_r, cx + btn_r, cy + btn_r],
        fill=GOLD,
    )
    string_x = cx + w * 0.78
    draw.line([(cx, cy), (string_x, cy)], fill=GOLD, width=max(2, int(9 * scale)))
    draw.line(
        [(string_x, cy), (string_x, cy + 92 * scale)],
        fill=GOLD,
        width=max(2, int(9 * scale)),
    )
    # tassel knot
    draw.ellipse(
        [string_x - 22 * scale, cy + 92 * scale - 22 * scale,
         string_x + 22 * scale, cy + 92 * scale + 26 * scale],
        fill=GOLD,
    )


def make(size: int, maskable: bool = False) -> Image.Image:
    base = _gradient(size)
    draw = ImageDraw.Draw(base)
    # For maskable, shrink content to the safe zone (~78%).
    content = 0.62 if maskable else 0.78
    scale = (size * content) / 400.0
    cx = size / 2
    cy = size * (0.46 if not maskable else 0.47)
    _draw_cap(draw, cx, cy, scale)
    if maskable:
        # maskable: full-bleed background square, no rounding.
        return base.convert("RGBA")
    return _rounded(base)


def main() -> None:
    make(192).save(os.path.join(PUBLIC, "pwa-192x192.png"))
    make(512).save(os.path.join(PUBLIC, "pwa-512x512.png"))
    make(512, maskable=True).save(os.path.join(PUBLIC, "pwa-maskable-512x512.png"))
    make(180).save(os.path.join(PUBLIC, "apple-touch-icon.png"))
    make(192).save(os.path.join(PUBLIC, "icon-192.png"))
    make(512).save(os.path.join(PUBLIC, "icon-512.png"))
    print("icons written to", os.path.abspath(PUBLIC))


if __name__ == "__main__":
    main()
