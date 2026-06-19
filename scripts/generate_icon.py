#!/usr/bin/env python3
"""Render the app icon SVG to a 256x256 PNG.

Tries real SVG rasterizers in order of fidelity:
    rsvg-convert -> inkscape -> cairosvg -> ImageMagick (convert/magick)
and falls back to drawing the icon directly with Pillow if none are available,
so the icon can always be produced on a minimal machine.

Usage:
    python3 scripts/generate_icon.py [output.png] [--size 256]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"

# Theme colours — "Thermal Glow" (kept in sync with assets/icon.svg and the app).
BG_TOP = (18, 24, 58)        # deep indigo
BG_BOTTOM = (10, 13, 28)     # blue-black
BORDER = (58, 63, 158)
HEAT_L = (161, 77, 255)      # electric purple (M, left)
HEAT_R = (255, 77, 157)      # fiery pink (M, right)
ARROW_T = (255, 122, 61)     # arrow top (orange)
ARROW_B = (255, 180, 84)     # arrow bottom (amber)


def _run(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def render_with_rasterizer(out: Path, size: int) -> bool:
    if shutil.which("rsvg-convert"):
        if _run(["rsvg-convert", "-w", str(size), "-h", str(size),
                 str(SVG), "-o", str(out)]):
            return True
    if shutil.which("inkscape"):
        if _run(["inkscape", str(SVG), "--export-type=png",
                 f"--export-filename={out}", "-w", str(size), "-h", str(size)]):
            return True
    try:
        import cairosvg  # type: ignore

        cairosvg.svg2png(url=str(SVG), write_to=str(out),
                         output_width=size, output_height=size)
        return True
    except Exception:
        pass
    for magick in ("magick", "convert"):
        if shutil.which(magick):
            base = [magick] if magick == "magick" else []
            if _run(base + ["-background", "none", "-density", "300",
                            str(SVG), "-resize", f"{size}x{size}", str(out)]):
                return True
    return False


def render_with_pillow(out: Path, size: int) -> bool:
    """Fallback: draw the icon directly with Pillow at the requested size."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return False

    s = size / 256.0  # scale factor relative to the 256px design
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Vertical background gradient inside a rounded tile.
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(tile)
    for y in range(size):
        t = y / max(size - 1, 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        tdraw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    radius = round(48 * s)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [8 * s, 8 * s, size - 8 * s, size - 8 * s], radius=radius, fill=255
    )
    img.paste(tile, (0, 0), mask)
    draw.rounded_rectangle(
        [8 * s, 8 * s, size - 8 * s, size - 8 * s],
        radius=radius, outline=BORDER + (255,), width=max(1, round(2 * s)),
    )

    def sc(points):
        return [(x * s, y * s) for x, y in points]

    def hgrad(c1, c2):
        g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for x in range(size):
            t = x / max(size - 1, 1)
            col = tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
            gd.line([(x, 0), (x, size)], fill=col + (255,))
        return g

    def vgrad(c1, c2):
        g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for y in range(size):
            t = y / max(size - 1, 1)
            col = tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
            gd.line([(0, y), (size, y)], fill=col + (255,))
        return g

    # Stylized "M" with a purple→pink heat gradient.
    m = [
        (56, 184), (56, 84), (92, 84), (128, 132), (164, 84), (200, 84),
        (200, 184), (170, 184), (170, 124), (138, 166), (118, 166),
        (86, 124), (86, 184),
    ]
    m_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m_mask).polygon(sc(m), fill=255)
    img.paste(hgrad(HEAT_L, HEAT_R), (0, 0), m_mask)

    # Download arrow with an incandescent amber gradient.
    a_mask = Image.new("L", (size, size), 0)
    am = ImageDraw.Draw(a_mask)
    am.rounded_rectangle([118 * s, 150 * s, 138 * s, 190 * s], radius=4 * s, fill=255)
    am.polygon(sc([(100, 182), (156, 182), (128, 214)]), fill=255)
    img.paste(vgrad(ARROW_T, ARROW_B), (0, 0), a_mask)

    img.save(out, "PNG")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", nargs="?", default=str(ROOT / "assets" / "icon.png"),
        help="output PNG path (default: assets/icon.png)",
    )
    parser.add_argument("--size", type=int, default=256, help="square size in px")
    args = parser.parse_args(argv)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    if render_with_rasterizer(out, args.size):
        print(f"Rendered {out} via SVG rasterizer ({args.size}px).")
        return 0
    if render_with_pillow(out, args.size):
        print(f"Rendered {out} via Pillow fallback ({args.size}px).")
        return 0

    print("No SVG rasterizer and Pillow is unavailable; cannot render icon.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
