#!/usr/bin/env python3
"""Generates README-light.md from README.md.

    python scripts/build_light_readme.py

GitHub has no theme toggle, so the toggle is a pair of pages that link to each
other. They have to stay identical apart from the screenshot paths and that one
link, which is why the light page is generated rather than maintained: edit
README.md, run this, commit both.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
OUT = ROOT / "README-light.md"

REPLACEMENTS = [
    ("docs/screenshots/dark/", "docs/screenshots/light/"),
    ("docs/screenshots/responsive/dark/", "docs/screenshots/responsive/light/"),
    (
        '<p><b>Dark mode</b> &middot; <a href="./README-light.md">View this page in light mode</a></p>',
        '<p><b>Light mode</b> &middot; <a href="./README.md">View this page in dark mode</a></p>',
    ),
    (
        "This page shows **dark mode**; the same gallery in light mode is at\n**[README-light.md](./README-light.md)**.",
        "This page shows **light mode**; the same gallery in dark mode is at\n**[README.md](./README.md)**.",
    ),
]

HEADER = "<!-- Generated from README.md by scripts/build_light_readme.py. Do not edit by hand. -->\n\n"


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in text:
            print(f"README.md is missing the expected marker: {old}", file=sys.stderr)
            return 1
        text = text.replace(old, new)
    OUT.write_text(HEADER + text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} from {SRC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
