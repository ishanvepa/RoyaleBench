# Capture and edit checklist

The active v03 edit is the [72-second Remotion composition](remotion/README.md). Original footage is reused with larger crops. Its preview is silent and does not use the v01 computer voice. This checklist also preserves the original capture history.

## Sources

- [Headliner run and task](http://localhost:8000/evals/jobs/45124458-3a52-4e73-b380-ee42f6934b19?task=04-critical-cycle-and-connect): open **Watch replay** for the model and **View resolution** for the validated reference.
- [Playback instructions](remotion/README.md): current editable preview and captured media.
- [Evidence manifest](evidence.json): factual claims and action sequences.

These localhost links require the dashboard on port 8000. During capture the v6 resolution endpoint was unavailable, so the reference was taken from the saved v6 Docker replay directly; its configuration matches the packaged task. See [the production record](production.json).

## Capture queue

| ID | Asset | Capture notes | Status |
| --- | --- | --- | --- |
| 01 | Opening replay still | Both vulnerable tower health values and Giant visible. This is the first recorded frame, including the first deployment cue. | Captured |
| 02 | Full model attempt | All six plays and terminal state; shared destruction/defeat animation, with a banner-free close-up. | Captured |
| 03 | Full reference continuation | Same framing and simulation-time alignment; winning connection and shared victory animation. | Captured |
| 04 | Observation and action insert | Selected initial observation fields and the actual first command, typeset for readability. | Composed |
| 05 | Run results insert | Actual run overview screenshot; no personal account details shown. | Captured |
| 06 | Comparison graphics | Cannon and Log target markers; explicit freeze clocks; matched labels and outcomes. | Reviewed v03 |
| 07 | Results card | 10/14 task objectives; 10 completed / 4 missed; one attempt per task, v6@1. | Composed |
| 08 | End card | Project name and configured repository origin. | Composed |
| 09 | Voiceover | Updated optional 72-second human script; no voice in current preview. | Script ready |

## Assembly

- [x] Inspect the model and reference visually; mark key frames in simulation time.
- [x] Record at a consistent viewport, resolution, and playback rate.
- [x] Assemble the hook, model loss, and comparison before adding dashboard footage.
- [x] Synchronize comparison footage at elapsed 0; retain each outcome at its actual time.
- [x] Label the reference clearly and add initial placement highlights.
- [x] Generate temporary narration within the scene durations.
- [x] Add approximate captions; keep text clear of tower health and key units.
- [x] Confirm displayed numbers against the evidence manifest.
- [ ] Record final narration and retime captions to that recording.
- [ ] Review at normal size with sound, then muted for caption readability.
- [ ] Export final MP4 and record its duration, shared location, and published URL in `README.md`.

## Asset naming

Use descriptive names such as `02-opus-attempt-take-01.mp4`, `03-reference-take-01.mp4`, `voiceover-take-01.wav`, and `royalebench-demo-v01.mp4`. Keep original captures intact while editing.
