"""Shrink the local PNG logos so they can be embedded inside animated SVGs.

The README renders these at 48px, so 128px is plenty. Palette-quantising
with an alpha channel typically cuts the originals by 70-90%, which matters
because base64 inflates whatever is left by another third.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "assets" / "tech" / "_src"
TARGET = 128
COLOURS = 128


def main() -> None:
    total_before = total_after = 0
    for png in sorted((REPO / "assets" / "tech").glob("*.png")):
        before = png.stat().st_size
        total_before += before

        image = Image.open(png).convert("RGBA")
        image = image.resize((TARGET, TARGET), Image.LANCZOS)
        # Quantise while preserving transparency.
        quantised = image.quantize(colors=COLOURS, method=Image.FASTOCTREE)

        out = SRC / f"{png.stem}.png"
        quantised.save(out, format="PNG", optimize=True)
        after = out.stat().st_size
        total_after += after
        print(f"{png.stem:<14} {before:>7} -> {after:>6} B")

    saved = 100 * (1 - total_after / total_before) if total_before else 0
    print(f"\ntotal {total_before} -> {total_after} B  ({saved:.0f}% smaller)")


if __name__ == "__main__":
    main()
