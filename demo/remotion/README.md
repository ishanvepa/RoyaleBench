# RoyaleBench — Remotion edit

Current edit: **72 seconds, 1920×1080, 30 fps**. Composition ID: `RoyaleBench`.

The v03 video opens on Opus's loss and introduces the benchmark immediately. Both attempts share a six-play progress strip; the reference cuts to the winning connection. Explicitly timed Cannon and Log freezes explain the differences. The shared renderer now animates tower destruction and reveals victory/defeat on the full arena. The preview is silent; the previous computer voice is not used.

## Preview and edit

From this directory:

```bash
npm ci
python prepare-assets.py
npm run dev -- --port 3010
```

Open [RoyaleBench in Studio](http://localhost:3010/RoyaleBench). Keep the server running. The active timeline is in `src/RoyaleBench.tsx`; scenes and editable text are in `src/Scenes.tsx`.

Each scene has an explicit timeline item. Text uses `Interactive` elements; gameplay shots expose source, crop, source start, and speed controls. Computed replay clocks, evidence-dependent labels, and aggregate score marks are programmatic. Frame-based animations remain deterministic when seeking or rendering.

`prepare-assets.py` stages the current renderer ending/impact captures from `../assets/captures/`, selected freeze frames, and the local macOS Impact font. These media/font copies are ignored by Git. It never starts model inference. For a fresh machine, obtain the original captures first; see [the production record](../production.json).

## Checks and exports

```bash
npm run lint
npx remotion render RoyaleBench ../exports/v03-frames --frames=0,90,210,390,585,660,840,1095,1170,1230,1320,1410,1500,1590,1740,1830,1950,2070 --image-format=png --sequence --is-production=false
```

The stills are for visual review. To export an MP4, use Studio's Render control, or:

```bash
npx remotion render RoyaleBench ../exports/royalebench-demo-v03.mp4
```

Use Remotion's bundled browser. All Remotion packages are pinned to `4.0.543` in the lockfile.

## Polish review and decisions

The 76-second v02 cut had a strong recorded loss/reference story and a coherent cream/charcoal palette. Its main weaknesses were late project context, replay comparisons that relied on memory, generic placement labels, and long static holds near the end.

The 72-second v03 pass:

- Identifies RoyaleBench at the opening and explains the benchmark in the setup.
- Gives both attempts the same six-play strip, aligned to the verified deployment times; keeps recorded gameplay at normal speed.
- Cuts the reference close-up to offense for its winning connection.
- Separates Cannon and Log into named, timed comparison items. Circles point to the actual units/targets, with model/reference and loss/win labels.
- Uses short eased entrances for key text, a clearer terminal treatment, and labeled result marks. Keeps the existing palette, display font, and hard cuts.
- Trims one second from the comparison, one from the interface, and two from results. Includes an updated optional human narration script.

The remaining production improvement is a measured human voice take and a restrained audio mix. The preview remains silent. No benchmark evidence or recorded action timing changed.

Review the local `../exports/v03-contact-sheet.jpg` after rendering, alongside the [storyboard](../storyboard.md) and [narration](../script.md). Media is ignored by Git.

## Refresh the ending footage

The current clips are rebuilt from the checksum-verified `opus-source.html` and `reference-source.html` payloads with the shared renderer. Each includes 1.8 seconds of presentation after its recorded final tick. Full-arena shots use the `ending` variant; close-ups use the `impact` variant with the result banner suppressed. Simulation clocks stop at 10.35s and 11.20s respectively. Original v01/v02 captures remain intact.

From the repository root:

```bash
python3 demo/prepare_ending_capture.py
python3 -m http.server 8767 --bind 127.0.0.1 --directory demo/assets/captures
```

Capture `opus-ending-capture.html`, `reference-ending-capture.html`, `opus-impact-capture.html`, and `reference-impact-capture.html` at that local server with `demo/capture.js`. The capture script reads each page's variant, output directory, and presentation tail. Then encode the four variants:

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

The capture manifest is `demo/assets/captures/ending-capture-metadata.json`; the production record stores rendered clip hashes and dimensions. These are local ignored media. [Shared renderer behavior and validation](../../docs/rendering.md#tower-destruction-and-endings).

## Sources and guidance

- [Evidence manifest](../evidence.json): exact model run, result, and validated reference.
- [Storyboard](../storyboard.md): current cut timing.
- [Official Remotion skills](https://www.remotion.dev/docs/ai/skills): creation, markup, video layout, editable timelines, interactivity, Studio, media, local fonts, and review-frame rendering.

Human narration, the final audio mix, and the submission MP4 remain production work.
