# RoyaleBench demo

The active edit is a **72-second Remotion composition** in [remotion](remotion/README.md). It compares an Opus 5.5 loss with a validated winning reference for `04-critical-cycle-and-connect`. Both use the same six cards, deployment order, and total elixir; the video shows how their placements and defensive spell use lead to opposite outcomes. The model saw text observations; the arena footage is a replay visualization.

The edit is ready for review in Remotion Studio. The final narration, MP4 export, and public video link are pending. The historical Pillow cut and its assembly script have been removed from the submission tree.

## Source and edit files

- [evidence.json](evidence.json): run ID, actions, outcomes, and reference provenance.
- [production.json](production.json): source checksums, capture and edit status.
- [storyboard.md](storyboard.md), [script.md](script.md), [shot-list.md](shot-list.md): timing, narration, and footage plan.
- [remotion/README.md](remotion/README.md): preview, asset preparation, checks, and export.
- `prepare_capture.py`, `prepare_ending_capture.py`, `capture.js`: recreate gameplay footage from archived replay payloads and the current renderer.

Captured media and exports under `assets/` and `exports/` are ignored by Git. To edit on a fresh machine, obtain the checksum-verified source captures described in [production.json](production.json), then run the asset preparation and Studio commands in [remotion/README.md](remotion/README.md). `python demo/prepare_capture.py --offline` can rebuild capture pages from those saved sources without a model call.

For a fresh capture, the recorded model run must be available through the local dashboard and the validated reference under `runs/royalebench-v6/docker/04-critical-cycle-and-connect/`. From the repository root, run `python demo/prepare_capture.py`, then follow [the Remotion capture workflow](remotion/README.md#refresh-the-ending-footage). The source v6 validation and replay files are retained for this purpose. Use the final exported MP4 for submission; the local Studio URL is only a preview.
