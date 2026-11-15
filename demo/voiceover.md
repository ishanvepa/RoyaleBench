# RoyaleBench demo — recording script

For the current 67-second [Remotion cut](remotion/README.md). One speaker per scene, alternating Ben and Ishan. Read the spoken words in the blockquotes; timestamps, scene names, and the bracketed pause are editing cues. Leave a short pause at each cut.

### 0:00–0:04 · Opening — Ben

> RoyaleBench tests how language models play Clash Royale.

### 0:04–0:13 · Benchmark task — Ishan

> From a fixed battle state, the model reads text, chooses a card and coordinates, and a verifier grades the replay.

### 0:13–0:24 · Actual observation and command — Ben

> Here is the real observation: eighteen seconds left, a Giant incoming, and our tower at two hundred fifty health. Opus opens with Ice Spirits.

### 0:24–0:37 · Synchronized attempts — Ishan

> Now compare Opus with a validated winning reference. Same six cards, order, timing, and fifteen elixir. Their placements differ. Opus loses; the reference wins.

### 0:37–0:43 · Cannon placement — Ben

> The reference Cannon sits half a tile left and one tile higher.

### 0:43–0:50 · Log target — Ishan

> With Log, Opus targets the enemy tower. The reference targets the incoming Giant.

### 0:50–0:59 · Run result — Ben

> In the latest full v9 run on Vals AI's Valkyrie, Opus completed fourteen of twenty-one task objectives.

### 0:59–1:07 · Winning connection and end card — Ishan

> The reference finds the winning connection. [Pause for the end card.] RoyaleBench: the right cards are only the beginning.

## Recording handoff

Record each scene as a separate, dry audio file so the lines can be placed at the listed cuts. Suggested names: `ben-01.wav`, `ishan-02.wav`, through `ishan-08.wav`. Leave a little silence at the start and end of each take. The current export still has silent-viewing captions and effects; narration has not been added to the video yet.

The wording follows the [storyboard](storyboard.md), [v9 result record](../runs/royalebench-v9/model-results.json), and [headliner evidence](evidence.json). The Cannon and Log lines describe visible placement differences, not a single proven cause of the result. Fourteen of twenty-one is task-objective success in the latest full v9 run, separate from its 10/21 match wins.
