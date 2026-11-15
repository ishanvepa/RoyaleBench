# RoyaleBench hackathon demo

Current edit: **76 seconds**, within the **1–2 minute** target. The active version is rebuilt in Remotion with larger gameplay, close-ups, brief annotations, and hard cuts. The earlier slide-like v01 is superseded. The new preview is silent; final human narration/audio and publication are pending.

- [Open the editable preview](http://localhost:3008/RoyaleBench) while Studio is running.
- [Remotion project and commands](remotion/README.md).
- [Current scene contact sheet](exports/v02-contact-sheet.jpg).

Historical v01 assets:

- [Watch review cut v01](exports/royalebench-demo-v01.mp4).
- [Scene contact sheet](exports/storyboard-contact-sheet.jpg).
- [Subtitle file](exports/royalebench-demo-v01.srt): approximate timing against the temporary voice; retime after final narration.
- [Production record](production.json): capture provenance, render details, and remaining work.

The headliner is **04-critical-cycle-and-connect**, featuring Claude Opus 5.5 in [this recorded run](http://localhost:8000/evals/jobs/45124458-3a52-4e73-b380-ee42f6934b19?task=04-critical-cycle-and-connect).

Core story: **Same cards. Same order. Different placements. Opposite result.** The model loses; a validated reference wins using the same six cards and total elixir. Show the differences in placement and defensive spell use through synchronized gameplay.

## Working files

- [Storyboard](storyboard.md): timing, visuals, and on-screen text.
- [Narration](script.md): first voiceover draft, ready for a timed read.
- [Shot list](shot-list.md): capture plan and production checklist.
- [Evidence](evidence.json): selected run metadata, outcomes, action sequences, trace excerpt, and reference provenance.
- `prepare_capture.py`: retrieve the model replay and prepare copies of the existing replay renderer for capture.
- `capture.js`: capture the board at 20 frames per second through Playwright.
- `assemble.py`: compose the scenes, generate temporary narration and captions, and export the MP4.

## Media layout

- `assets/captures/`: original replay and dashboard recordings.
- `assets/audio/`: narration takes and audio assets.
- `assets/graphics/`: title cards, annotations, and results graphics.
- `edit/`: editor project and edit notes.
- `exports/`: review cuts and final video.

Media and editor files in those folders are ignored by Git. The linked review cut is local; share or upload it separately for submission. Keep source notes and small graphics elsewhere in this folder if they should be committed.

## Production defaults

- 1920×1080, 16:9, 30 fps H.264 MP4. The review cut composes at 20 fps and repeats frames for the 30 fps export.
- Label the two sides **Claude Opus 5.5** and **Validated reference**.
- Keep the initial tower health, Giant, Hog, and key placements readable.
- Show 10/14 as **task objective success**, attributed to this single run.
- The model receives text observations; the rendered arena is our replay visualization.
- Label freezes, slow motion, and repeated footage when needed to preserve the game timeline.

## Next steps

1. Review the current Remotion edit for pacing and whether the comparison is clear.
2. Record human narration if desired and time it to the new edit; the old Samantha voice is not used.
3. Refine placement annotations and transitions as needed.
4. Export the submission cut, review audio and readability, and publish it.
5. Add the public video link to the root README.

Submission video URL: pending. The end card uses the repository's configured origin: [ishanvepa/RoyaleBench](https://github.com/ishanvepa/RoyaleBench).

## Rebuild the historical v01 cut

For the active edit, use the [Remotion instructions](remotion/README.md). These commands reproduce the older Pillow cut only.

Requires Python with Pillow, Node/npm, the Playwright CLI skill wrapper, ffmpeg/ffprobe, and macOS `say` with the Samantha voice. `prepare_capture.py` requires the dashboard running at port 8000; rendering after capture runs locally without model calls.

From the repository root:

```bash
python demo/prepare_capture.py
python -m http.server 8766 --bind 127.0.0.1 --directory demo/assets/captures
```

In another terminal, capture both prepared pages:

```bash
PWCLI="${CODEX_HOME:-$HOME/.codex}/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" --session royalebench-demo open http://127.0.0.1:8766/opus-capture.html --headed
"$PWCLI" --session royalebench-demo run-code --filename demo/capture.js
"$PWCLI" --session royalebench-demo goto http://127.0.0.1:8766/reference-capture.html
"$PWCLI" --session royalebench-demo run-code --filename demo/capture.js
python demo/assemble.py
```

Use `python demo/assemble.py --preview` for scene stills without generating audio or encoding video. The optional `assets/captures/dashboard.png` insert is a screenshot of the linked run's overview; if absent, the results scene omits it.

The dashboard's v6 **View resolution** endpoint returned unavailable during capture. The reference comes directly from `runs/royalebench-v6/docker/04-critical-cycle-and-connect/replay.html`, with passing Docker evidence and matching packaged task configuration. Both recorded sequences have matching deployment ticks and card IDs; the arena payloads also match. No new benchmark runs are needed.

The original benchmark and evaluation guides belong to the source checkout recorded in [production.json](production.json). The demo carries its captured footage and scoring evidence so it can run separately from that checkout.

To regenerate capture pages from the archived, checksum-verified replay HTML without the original eval server or benchmark files, run `python demo/prepare_capture.py --offline`. This also updates the capture output directory after moving the demo. The Remotion preview only needs the existing captures; see its [setup instructions](remotion/README.md).

See the [track requirements](../docs/build_eval_track.md), [captured scoring evidence](evidence.json), and [playback instructions](remotion/README.md).
