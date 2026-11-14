"""Render a saved replay to HTML, with royalegym's viewer patched so scrubbing keeps playback running.

Usage: uv run python -m cr_arena.replay <match>.msgpack -o battle.html [--stride N] [--title T]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from royalegym.render import render_html

# (original, replacement) pairs of the viewer's JS. Dragging holds the clock on the dragged frame;
# releasing carries on from there if the replay was playing.
_PATCHES = [
    (
        "function onScrub() { playing = false; seek(Number(scrub.value)); }",
        "var scrubbing = false;\n"
        '  scrub.addEventListener("pointerdown", function () { scrubbing = true; });\n'
        '  window.addEventListener("pointerup", function () { scrubbing = false; });\n'
        '  window.addEventListener("pointercancel", function () { scrubbing = false; });\n'
        "  function onScrub() { seek(Number(scrub.value)); }",
    ),
    ("function frameLoop(t) {\n    if (playing) {", "function frameLoop(t) {\n    if (playing && !scrubbing) {"),
]


def patched_html(replay: str | Path, *, title: str | None = None, stride: int = 1) -> str:
    page = render_html(replay, title=title, stride=stride)
    for old, new in _PATCHES:
        if page.count(old) != 1:  # royalegym changed its template: fail instead of silently losing the fix
            raise RuntimeError(f"replay viewer patch no longer applies: {old[:50]!r}")
        page = page.replace(old, new)
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("replay", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    a.out.write_text(patched_html(a.replay, title=a.title, stride=a.stride), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
