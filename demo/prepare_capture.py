"""Download the recorded replay and prepare isolated copies for deterministic capture.

Run from any directory: python demo/prepare_capture.py
This only writes demo assets; it does not run models or change benchmark tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent
CAPTURES = DEMO / "assets/captures"
TASK = "04-critical-cycle-and-connect"
RUN = "45124458-3a52-4e73-b380-ee42f6934b19"


def payload(page: str) -> dict:
    match = re.search(r'<script type="application/json" id="replay-data">(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("Replay data is missing")
    return json.loads(match[1])


def main(*, offline: bool = False) -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    endpoint = f"http://localhost:8000/api/evals/jobs/{RUN}/tasks/{TASK}/replay"
    source = ROOT / "runs/royalebench-v6/docker" / TASK
    if offline:
        saved = json.loads((CAPTURES / "capture-metadata.json").read_text())
        validation = saved["reference_validation"]
        sources = {}
        for name in ("opus", "reference"):
            original = (CAPTURES / f"{name}-source.html").read_text()
            digest = hashlib.sha256(original.encode()).hexdigest()
            if digest != saved["replays"][name]["source_html_sha256"]:
                raise ValueError(f"Archived {name} replay checksum does not match")
            sources[name] = original
    else:
        with urllib.request.urlopen(endpoint, timeout=60) as response:
            data = json.load(response)
        if not data.get("available"):
            raise ValueError(data.get("message", "Replay unavailable"))
        validation = json.loads((source / "v6_validation.json").read_text())
        sources = {"opus": data["html"], "reference": (source / "replay.html").read_text()}
    assert validation["reward"] == validation["integrity"] == 1
    assert validation["replay_hashes_verified"] and validation["isolated"]
    metadata = {}
    for name, original in sources.items():
        (CAPTURES / f"{name}-source.html").write_text(original)
        d = payload(original)
        ff = {key: i for i, key in enumerate(d["frame_fields"])}
        start = d["frames"][0][ff["tick"]]
        end = d["frames"][-1][ff["tick"]]
        metadata[name] = {
            "duration_s": (end - start) * d["source"]["tick_ms"] / 1000,
            "start_tick": start,
            "end_tick": end,
            "source_frames": len(d["frames"]),
            "source_html_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "deploys": d["deploys"],
            "result": d["result"],
        }
        # Capture the existing renderer at a chosen simulation time. Preserve its
        # snapshot conversion, transitions, animations, and recorded state.
        hook = """
  window.demoSeek = function(seconds) {
    playing = false;
    var target = Math.min(tick(N - 1), tick(0) + seconds * 1000 / TICK_MS);
    var i = 0;
    while (i + 1 < N && tick(i + 1) <= target) i++;
    if (i < cur) { renderer.reset(); observed = -1; }
    cur = i; simTick = target; interpBox.checked = true; draw();
    return {tick: target, frame: cur, width: cv.width, height: cv.height};
  };
"""
        assert "  function frameLoop(t) {" in original
        page = original.replace("  function frameLoop(t) {", hook + "\n  function frameLoop(t) {")
        # The capture viewport is fixed; force a 486×864 board with the same
        # renderer layout and omit surrounding controls from canvas captures.
        page = page.replace("</head>",
            '<meta name="demo-capture-directory" content="' + html.escape(str(CAPTURES) + "/", quote=True) + '">' +
            "<style>.decision-panel,.team-panels{display:none!important}</style></head>")
        (CAPTURES / f"{name}-capture.html").write_text(page)
        (CAPTURES / f"{name}-frames").mkdir(exist_ok=True)
    (CAPTURES / "capture-metadata.json").write_text(json.dumps({
        "fps": 20,
        "model_replay_endpoint": endpoint,
        "reference_source": str(source.relative_to(ROOT)),
        "reference_validation": validation,
        "rendering": "Existing battle renderer; straight-line interpolation between recorded frames.",
        "replays": metadata,
    }, indent=2) + "\n")
    print("Prepared model and validated reference capture pages.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use checksum-verified archived replay HTML without the eval server or original benchmark checkout")
    main(offline=parser.parse_args().offline)
