# RoyaleBench demo

The active edit is a **67-second Remotion composition** in [remotion](remotion/README.md). It opens with “RoyaleBench: LLM Benchmark,” explains the fixed Clash Royale task and text-to-action-to-replay loop, then shows the actual observation and first command. An Opus 5.5 loss and validated winning reference for `04-critical-cycle-and-connect` play side by side at the same simulation time. They use the same six cards, deployment order, and total elixir; placements differ. The model saw text observations; the arena footage is a replay visualization.

Captions and original effects carry the story without narration. The local [MP4 export](exports/royalebench-demo-v04.mp4) and [contact sheet](exports/v04-contact-sheet.jpg) are ready for review; both are ignored by Git. The public video link is pending.

For recording, use the [timed Ben and Ishan voiceover script](voiceover.md). It alternates speakers at each of the eight scene cuts; the current export does not include these voices yet.

Open [the recording prompter](prompter.html) in a browser to follow the scene clock, auto-scroll, and word highlighting. Its spoken-word pace is 10% faster than the original timing, leaving quiet space between scenes.

## Source and edit files

- [evidence.json](evidence.json): run ID, actions, outcomes, and reference provenance.
- [production.json](production.json): source checksums, capture and edit status.
- [storyboard.md](storyboard.md), [script.md](script.md), [shot-list.md](shot-list.md): timing, captions, and footage plan.
- [remotion/README.md](remotion/README.md): preview, asset preparation, checks, and export.
- `prepare_capture.py`, `prepare_ending_capture.py`, `capture.js`: recreate gameplay footage from archived replay payloads and the current renderer.

Captured media and exports under `assets/` and `exports/` are ignored by Git. To edit on a fresh machine, obtain the checksum-verified source captures described in [production.json](production.json), then run the asset preparation and Studio commands in [remotion/README.md](remotion/README.md). `python demo/prepare_capture.py --offline` can rebuild capture pages from those saved sources without a model call.

For a fresh capture, the recorded model run must be available through the local dashboard and the validated reference under `runs/royalebench-v6/docker/04-critical-cycle-and-connect/`. From the repository root, run `python demo/prepare_capture.py`, then follow [the Remotion capture workflow](remotion/README.md#rebuild-the-gameplay-footage). The source v6 validation and replay files are retained for this purpose. Use the exported MP4 for submission; the local Studio URL is only a preview.
