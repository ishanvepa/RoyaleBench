"""Render a saved replay to a standalone HTML file using the live battle graphics.

Usage: uv run python -m cr_arena.replay <match>.msgpack -o battle.html [--stride N] [--title T]
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from royalegym.render import build_view
from royalegym.replay import load_trace

from .rendering import embed_renderer

_TEMPLATE = Path(__file__).with_name("replay.html")
_PLACEHOLDER = re.compile(r"__(TITLE|DATA_ID|DATA)__")


def patched_html(replay: str | Path, *, title: str | None = None, stride: int = 1) -> str:
    """Keep the existing public entry point; playback controls are now owned locally."""
    trace = load_trace(replay)
    payload = build_view(trace, stride=stride)
    payload["projectile_fields"] = list(trace.header.projectile_fields)
    # Spawned units keep their card's ID; the unit-type names tell a Golemite from its Golem.
    payload["unit_types"] = list(trace.header.unit_types)
    # A trace's card names and caller-supplied title must never become script markup.
    data = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    data = data.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    substitutions = {"TITLE": html.escape(title if title is not None else f"RoyaleBench replay - seed {trace.header.seed}"),
                     "DATA_ID": "replay-data", "DATA": data}
    page = _PLACEHOLDER.sub(lambda match: substitutions[match[1]], _TEMPLATE.read_text(encoding="utf-8"))
    return embed_renderer(page)


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
