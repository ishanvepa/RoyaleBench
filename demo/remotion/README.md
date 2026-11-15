# RoyaleBench — Remotion edit

Current edit: **76 seconds, 1920×1080, 30 fps**. Composition ID: `RoyaleBench`.

The video opens on Opus's loss, explains the position, plays both attempts, then freezes the Cannon and Log differences. Gameplay close-ups and short annotations carry the story. The preview is silent; the previous computer voice is not used.

## Preview and edit

From this directory:

```bash
npm ci
python prepare-assets.py
npm run dev -- --port 3008
```

Open [RoyaleBench in Studio](http://localhost:3008/RoyaleBench). Keep the server running. The active timeline is in `src/RoyaleBench.tsx`; scenes and editable text are in `src/Scenes.tsx`.

Each scene has an explicit timeline item. Text uses `Interactive` elements; gameplay shots expose source, crop, source start, and speed controls. Computed replay clocks, evidence-dependent labels, and aggregate score marks are programmatic. Frame-based animations remain deterministic when seeking or rendering.

`prepare-assets.py` stages existing captures from `../assets/captures/`, selected freeze frames, and the local macOS Impact font. These media/font copies are ignored by Git. It never starts model inference. For a fresh machine, obtain the original captures first; see [the production record](../production.json).

## Checks and exports

```bash
npm run lint
npx remotion render RoyaleBench ../exports/v02-frames --frames=90,210,390,660,990,1260,1590,1860,2190 --image-format=png --sequence --is-production=false
```

The stills are for visual review. To export an MP4, use Studio's Render control, or:

```bash
npx remotion render RoyaleBench ../exports/royalebench-demo-v02.mp4
```

Use Remotion's bundled browser. All Remotion packages are pinned to `4.0.543` in the lockfile.

## Sources and guidance

- [Evidence manifest](../evidence.json): exact model run, result, and validated reference.
- [Storyboard](../storyboard.md): current cut timing.
- [Official Remotion skills](https://www.remotion.dev/docs/ai/skills): creation, markup, video layout, editable timelines, interactivity, Studio, media, local fonts, and review-frame rendering.

The old Pillow edit and v01 export remain for history, but are superseded by this composition. Human narration and the final audio mix remain production work.
