"""Stage the archived demo payloads in the current renderer, with a 1.8s result tail.

Original replay HTML, captured frames and MP4s remain untouched. No model calls.
"""
from __future__ import annotations

import hashlib
import html
import json
import re

from prepare_capture import CAPTURES, ROOT, payload

TAIL = 1.8


def main() -> None:
    saved = json.loads((CAPTURES / "capture-metadata.json").read_text())
    template = (ROOT / "cr_arena/replay.html").read_text()
    renderer = (ROOT / "cr_arena/battle_renderer.js").read_text()
    metadata = {"fps": 20, "presentation_tail_s": TAIL,
                "renderer_sha256": hashlib.sha256(renderer.encode()).hexdigest(),
                "template_sha256": hashlib.sha256(template.encode()).hexdigest(), "replays": {}}
    for name in ("opus", "reference"):
        original = (CAPTURES / f"{name}-source.html").read_text()
        digest = hashlib.sha256(original.encode()).hexdigest()
        assert digest == saved["replays"][name]["source_html_sha256"], name
        data = payload(original)
        encoded = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
        encoded = encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        values = {"TITLE": name + " ending capture", "DATA_ID": "replay-data", "DATA": encoded}
        page = re.sub(r"__(TITLE|DATA_ID|DATA)__", lambda m: values[m[1]], template)
        page = page.replace("<!-- __BATTLE_RENDERER__ -->", "<script>\n" + renderer + "\n</script>")
        hook = """
  var demoDefaultEnding = true;
  var demoLast = -1, demoShowEnding = demoDefaultEnding;
  var demoDraw = renderer.draw;
  renderer.draw = function(a, b, alpha, now, options) {
    if (!demoShowEnding) options.ending = null;
    return demoDraw(a, b, alpha, now, options);
  };
  window.demoSeek = function(seconds, showEnding) {
    playing = false;
    if (seconds < demoLast) { renderer.reset(); observed = -1; }
    demoLast = seconds;
    demoShowEnding = showEnding === undefined ? demoDefaultEnding : showEnding;
    var target = tick(0) + seconds * 1000 / TICK_MS;
    var i = 0;
    while (i + 1 < N && tick(i + 1) <= target) i++;
    cur = i; simTick = target; interpBox.checked = true; draw();
    return {tick: Math.min(target, tick(N - 1)), frame: cur, width: cv.width, height: cv.height};
  };
"""
        page = page.replace("  function frameLoop(t) {", hook + "\n  function frameLoop(t) {")
        page = page.replace("</head>",
            '<meta name="demo-capture-directory" content="' + html.escape(str(CAPTURES) + "/", quote=True) + '">' +
            '<meta name="demo-capture-variant" content="ending">' +
            f'<meta name="demo-presentation-tail" content="{TAIL}">' +
            '<style>.decision-panel,.team-panels{display:none!important}</style></head>')
        (CAPTURES / f"{name}-ending-capture.html").write_text(page)
        (CAPTURES / f"{name}-ending-frames").mkdir(exist_ok=True)
        impact = page.replace('name="demo-capture-variant" content="ending"',
                              'name="demo-capture-variant" content="impact"')
        impact = impact.replace("var demoDefaultEnding = true;", "var demoDefaultEnding = false;")
        (CAPTURES / f"{name}-impact-capture.html").write_text(impact)
        (CAPTURES / f"{name}-impact-frames").mkdir(exist_ok=True)
        info = saved["replays"][name]
        metadata["replays"][name] = {"source_html_sha256": digest,
            "simulation_duration_s": info["duration_s"],
            "capture_duration_s": info["duration_s"] + TAIL,
            "final_tick": info["end_tick"], "result": info["result"]}
    (CAPTURES / "ending-capture-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Prepared both current-renderer captures; simulation unchanged, 1.8s presentation tail.")


if __name__ == "__main__":
    main()
