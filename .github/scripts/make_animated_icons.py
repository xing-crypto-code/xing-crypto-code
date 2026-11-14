#!/usr/bin/env python3
"""Wrap static tech-stack SVGs into gently floating (animated) SVGs.

Why animated SVG instead of GIF:
  * crisp at any size, ~3 KB instead of ~50 KB, transparent by default
  * lives in this repo, so it can never break like a third-party service
  * GitHub serves SVG with ``Content-Type: image/svg+xml`` and browsers
    play CSS keyframes inside ``<img>`` (the contribution snake already
    proves this works on this profile)

Usage:
    python .github/scripts/make_animated_icons.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# How far (in viewBox units) the icon drifts up and down, and how long one
# full bounce takes. The baseline scale leaves room so nothing is clipped.
FLOAT_PX = 7
PERIOD_S = 3.0
SCALE = 0.88
INSET = (256 - 256 * SCALE) / 2  # centres the shrunk icon

# Staggered starts keep the row from pulsing in lockstep, which reads as
# mechanical; an offset drift feels livelier.
DELAYS = {"cpp": 0.0, "python": 0.4, "github": 0.8, "raspberrypi": 1.2}

STYLE = """  <style>
    @keyframes flt {{ 0%, 100% {{ transform: translateY({d}px); }} 50% {{ transform: translateY(-{d}px); }} }}
    .flt {{ animation: flt {p}s ease-in-out infinite; animation-delay: {delay}s; }}
    @media (prefers-reduced-motion: reduce) {{ .flt {{ animation: none; }} }}
  </style>"""


def build(src: str, delay: float) -> str:
    """Return `src` (a whole SVG document) with a float animation added."""
    open_tag = re.search(r"<svg\b[^>]*>", src, re.S)
    close_idx = src.rfind("</svg>")
    if open_tag is None or close_idx == -1:
        raise ValueError("not an SVG document")

    root = open_tag.group(0)
    body = src[open_tag.end() : close_idx]

    # Keep the 256x256 coordinate system the icons are authored in, but the
    # displayed size stays whatever the README asks for.
    root = re.sub(r'\s+width="[^"]*"', "", root)
    root = re.sub(r'\s+height="[^"]*"', "", root)
    if "xmlns:xlink" not in root:
        root = root.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"', 1)

    frame = f'<g transform="translate({INSET:.2f},{INSET:.2f}) scale({SCALE})">'
    style = STYLE.format(d=FLOAT_PX, p=PERIOD_S, delay=delay)

    return (
        f"{root}\n"
        f"{style}\n"
        f'  <g class="flt">\n'
        f"    {frame}{body}</g>\n"
        f"  </g>\n"
        f"</svg>\n"
    )


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    src_dir = repo / "assets" / "tech" / "_src"
    out_dir = repo / "assets" / "tech"

    if not src_dir.is_dir():
        print(f"missing source directory: {src_dir}", file=sys.stderr)
        return 1

    written = 0
    for name, delay in DELAYS.items():
        source = src_dir / f"{name}.svg"
        if not source.is_file():
            print(f"skip {name}: no {source}", file=sys.stderr)
            continue
        out = out_dir / f"{name}.svg"
        out.write_text(build(source.read_text(encoding="utf-8"), delay), encoding="utf-8")
        print(f"wrote {out.relative_to(repo)}  ({out.stat().st_size} bytes)")
        written += 1

    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
