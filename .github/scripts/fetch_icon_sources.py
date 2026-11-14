"""Fetch every tech-stack icon used by the README into assets/tech/_src.

Keeps a single manifest so the animation generator does not guess URLs.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

SKILLICONS = [
    "cpp", "python", "github", "raspberrypi",
    "arduino", "c", "cmake", "bash",
    "linux", "visualstudio", "vscode", "matlab", "git",
]

SIMPLEICONS = {
    "espressif": "E7352C",
    "stmicroelectronics": "03234B",
    "kicad": "2C2C2C",
    "platformio": "F5822D",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    src = repo / "assets" / "tech" / "_src"
    src.mkdir(parents=True, exist_ok=True)

    for name in SKILLICONS:
        data = fetch(f"https://skillicons.dev/icons?i={name}&theme=light")
        (src / f"{name}.svg").write_bytes(data)
        print(f"skillicons  {name:<16} {len(data):>6} B")

    for name, colour in SIMPLEICONS.items():
        data = fetch(f"https://cdn.simpleicons.org/{name}/{colour}")
        (src / f"{name}.svg").write_bytes(data)
        print(f"simpleicons {name:<16} {len(data):>6} B")

    (src / "sources.json").write_text(
        json.dumps({"skillicons": SKILLICONS, "simpleicons": SIMPLEICONS}, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
