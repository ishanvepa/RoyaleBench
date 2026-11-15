# RoyaleBench — Remotion edit

Current edit: **67 seconds, 1920×1080, 30 fps**. Composition ID: `RoyaleBench`. The active v04 cut uses the game's navy panels, blue/red team colors, gold outcomes, elixir accents, card portraits, and replay graphics. It works without narration: captions carry the story, with a quiet original effects track at scene and deployment beats.

The opening title reads “RoyaleBench: LLM Benchmark.” The first 13 seconds establish a fixed Clash Royale task state and win objective, and show the text observation → card-and-coordinate command → replay grade loop. The model's recorded defeat supplies the hook. The actual text observation and first command then appear before model and validated-reference replays run side by side at the same simulation time. Paired Cannon and Log freezes make two placement differences visible. The result is labeled as one historical v6@1 run.

## Preview and edit

From this directory:

```bash
npm ci
python3 prepare-assets.py
npm run dev -- --port 3010
```

Open [RoyaleBench in Studio](http://localhost:3010/RoyaleBench). The active timeline is `src/RoyaleBenchV04.tsx`; scenes are in `src/GameScenes.tsx`, reusable game UI and captions in `src/GameUI.tsx`, and palette tokens in `src/design.ts`. The earlier v03 source remains for historical comparison. Gameplay shots retain source, camera, source start, and speed controls. Replay clocks, card order, outcomes, and aggregate score labels derive from the evidence record. Animations are frame based and seek deterministically.

`prepare-assets.py` stages the local captured clips and freeze frames, generates card SVGs from the game's own `cr_arena/card_art.js` through `generate-card-art.cjs`, and creates the deterministic 67-second effects WAV through `generate-audio.py`. It does not call a model. The staged clips, WAV, and exports are ignored by Git; the generated card SVGs are tracked. For a fresh checkout, obtain the checksum-verified captures first; see [the production record](../production.json).

## Checks and export

```bash
npm run lint
npx remotion render RoyaleBench ../exports/review-v04-frames --frames=0,90,180,300,390,540,720,930,1110,1200,1410,1530,1800,1980 --image-format=png --sequence --is-production=false
npx remotion render RoyaleBench ../exports/royalebench-demo-v04.mp4 --codec=h264 --crf=18
```

The first render makes stills for visual review. The second exports the full local MP4 with burned-in captions and effects. All Remotion packages are pinned to `4.0.543` in the lockfile. [Storyboard](../storyboard.md), [caption script](../script.md), and [evidence manifest](../evidence.json) describe the edit and the factual boundaries.

## Rebuild the gameplay footage

The four current clips come from the checksum-verified archived `opus-source.html` and `reference-source.html` payloads with the shared renderer. Each includes 1.8 seconds of presentation after its recorded final tick. Full-arena shots use the `ending` variant; close-ups use `impact` with the result banner suppressed. Simulation clocks stop at 10.35s and 11.20s. v04 captured at a 3840×2160 browser viewport, producing 1098×1953 board frames and 1098×1954 encoded clips. The underlying action records and results are unchanged.

From the repository root:

```bash
python3 demo/prepare_ending_capture.py
python3 -m http.server 8767 --bind 127.0.0.1 --directory demo/assets/captures
```

Capture `opus-ending-capture.html`, `reference-ending-capture.html`, `opus-impact-capture.html`, and `reference-impact-capture.html` at that local server with `demo/capture.js`. The script reads each page's variant, output directory, and presentation tail. Then encode and stage the four variants:

```bash
for source in opus reference; do
  for variant in ending impact; do
    ffmpeg -hide_banner -loglevel error -y -framerate 20 \
      -i "demo/assets/captures/${source}-${variant}-frames/%04d.png" \
      -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -c:v libx264 -crf 18 \
      -pix_fmt yuv420p -movflags +faststart \
      "demo/assets/captures/${source}-${variant}-replay.mp4"
  done
done
python3 demo/remotion/prepare-assets.py
```

Capture metadata lives in `demo/assets/captures/ending-capture-metadata.json`. See [shared renderer validation](../../docs/rendering.md#tower-destruction-and-endings) and the [demo source guide](../README.md).

## Sources and guidance

- [Official Remotion skills](https://www.remotion.dev/docs/ai/skills): markup, media, timeline, editable composition, and rendering guidance.
- [Production record](../production.json): exact source provenance, capture and export hashes, and review checks.
- [Shot list](../shot-list.md): capture and assembly status.
