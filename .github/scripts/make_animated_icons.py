#!/usr/bin/env python3
"""Wrap every tech-stack icon into a gently floating, self-animated SVG.

Why animated SVG instead of GIF:
  * crisp at any size, a few KB instead of hundreds, transparent by default
  * lives in this repo, so it can never break the way a third-party
    generator did (techstack-generator started returning HTTP 402)
  * GitHub serves SVG with ``Content-Type: image/svg+xml`` and browsers run
    CSS keyframes inside ``<img>`` -- the contribution snake on this very
    profile already proves it

Inputs live in ``assets/tech/_src``:
  * ``<name>.svg`` for icons that ship as vectors
  * ``<name>.png`` for logos that only exist as raster

Run after ``fetch_icon_sources.py`` and ``shrink_png_icons.py``:
    python .github/scripts/make_animated_icons.py
"""

from __future__ import annotations

import base64
import math
import re
import sys
from pathlib import Path

# Motion tuning. Staggered starts keep the grid from pulsing in lockstep,
# which reads as mechanical; an offset drift feels alive.
FLOAT_PX = 7
PERIOD_S = 3.0
SCALE = 0.88
INSET = (256 - 256 * SCALE) / 2  # centres the shrunk artwork

# Every icon in the README table, in reading order, cycling through a few
# delays so neighbours never bounce together.
ORDER = [
    "cpp", "python", "github", "raspberrypi",
    "arduino", "c", "cmake", "bash",
    "linux", "cubeide", "visualstudio", "vscode",
    "matlab", "git", "ghdesktop", "dsh",
    "keil", "cubemx", "wch", "mounriver",
    "stlink", "jlc", "solidworks", "agents",
    "espressif", "stmicroelectronics", "kicad", "platformio",
]
DELAY_CYCLE = [0.0, 0.4, 0.8, 1.2, 0.2, 0.6, 1.0, 1.4]

STYLE = """  <style>
    @keyframes flt-{slug} {{ 0%, 100% {{ transform: translateY({d}px); }} 50% {{ transform: translateY(-{d}px); }} }}
    .flt-{slug} {{ animation: flt-{slug} {p}s ease-in-out infinite; animation-delay: {delay}s; }}
    @media (prefers-reduced-motion: reduce) {{ .flt-{slug} {{ animation: none; }} }}
  </style>"""

SHELL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
{style}
  <g class="flt-{slug}">
    <g transform="translate({inset:.2f},{inset:.2f}) scale({scale})">
{body}
    </g>
  </g>
</svg>
"""


def slug_of(name: str) -> str:
    """CSS identifiers cannot start with a digit or contain odd glyphs."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    return f"i{slug}" if not slug[:1].isalpha() else slug


def svg_body(src: str) -> str:
    """Return the inner markup of an SVG document, normalised to a 256 box.

    Sources disagree on their coordinate space -- skillicons are authored on
    256, simpleicons on 24. Dropping the wrapper without rescaling would draw
    the 24-unit artwork in a 256-unit box, so shrink it back to a 24/256
    square. ``viewBox`` is honoured when present, else width/height.
    """
    open_tag = re.search(r"<svg\b[^>]*>", src, re.S)
    close_idx = src.rfind("</svg>")
    if open_tag is None or close_idx == -1:
        raise ValueError("not an SVG document")

    attrs = open_tag.group(0)
    body = src[open_tag.end():close_idx].strip()

    box = re.search(r'viewBox="([-\d.\s]+)"', attrs)
    if box:
        _, _, w, h = (float(v) for v in box.group(1).split())
    else:
        w = float(re.search(r'width="([\d.]+)', attrs).group(1))
        h = float(re.search(r'height="([\d.]+)', attrs).group(1))

    if math.isclose(w, 256) and math.isclose(h, 256):
        return body

    sx, sy = 256 / w, 256 / h
    return f'      <g transform="scale({sx:.6f},{sy:.6f})">{body}</g>'


def png_body(path: Path) -> str:
    """Embed a raster logo at 256x256, as-is."""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'      <image x="0" y="0" width="256" height="256" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'xlink:href="data:image/png;base64,{data}" />'
    )


def build(name: str, index: int) -> str:
    src = Path(__file__).resolve().parents[2] / "assets" / "tech" / "_src"
    delay = DELAY_CYCLE[index % len(DELAY_CYCLE)]
    slug = slug_of(name)

    svg_file, png_file = src / f"{name}.svg", src / f"{name}.png"
    if svg_file.is_file():
        body = "      " + svg_body(svg_file.read_text(encoding="utf-8"))
    elif png_file.is_file():
        body = png_body(png_file)
    else:
        raise FileNotFoundError(f"no source for {name}")

    style = STYLE.format(slug=slug, d=FLOAT_PX, p=PERIOD_S, delay=delay)
    doc = SHELL.format(
        style=style, slug=slug, inset=INSET, scale=SCALE, body=body
    )
    # Raster embedding needs xlink to resolve in older renderers.
    if "xlink:href" in doc and "xmlns:xlink" not in doc:
        doc = doc.replace(
            "<svg xmlns=", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" xmlns=', 1
        )
    return doc


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    out_dir = repo / "assets" / "tech"
    written = 0

    for index, name in enumerate(ORDER):
        try:
            doc = build(name, index)
        except FileNotFoundError as err:
            print(f"skip {name}: {err}", file=sys.stderr)
            continue
        out = out_dir / f"{name}.svg"
        out.write_text(doc, encoding="utf-8")
        written += 1
        print(f"{name:<18} {out.stat().st_size:>7} B  delay={DELAY_CYCLE[index % len(DELAY_CYCLE)]}s")

    print(f"\n{written} animated icons written")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
