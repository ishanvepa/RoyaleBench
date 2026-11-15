# Current Remotion storyboard — 67 seconds

The active [v04 edit](remotion/README.md) opens with RoyaleBench's purpose and task interface before the model/reference comparison. It uses the game's navy battle panels, team colors, gold results, elixir accents, and card portraits. Captions carry the story without narration. All gameplay shown is recorded replay footage; paired comparison shots share the same simulation clock.

| Time | Scene | Viewer focus |
| --- | --- | --- |
| 0–4s | Benchmark identity and Opus defeat | “RoyaleBench: LLM Benchmark” over the arena, followed by the recorded loss and the question: could the same cards have won? |
| 4–13s | One benchmark task and model interaction loop | A fixed overtime state, the tower-race objective, text observation, `cr play` card-and-coordinate command, and independent replay grading. The arena is a viewer visualization. |
| 13–24s | Actual text observation and first command | Selected observation fields, card slot, Ice Spirits portrait, and `cr play 0 3.5 11` follow the task diagram immediately. |
| 24–37s | Synchronized model and reference attempts | Two full arenas advance at the same simulation time, alongside the shared six-card play strip and 15-elixir total. Each outcome appears at its recorded time. |
| 37–43s | Paired Cannon freeze at replay 3.00s | Game-colored placement rings and coordinates; reference Cannon is half a tile left and one tile higher. |
| 43–50s | Paired Log freeze at replay 9.00s | Model targets the enemy tower; reference targets the incoming Giant. Both placements and outcomes remain labeled. |
| 50–59s | One historical v6@1 run result | 10 of 14 task objectives completed, with completed/missed marks. |
| 59–67s | Labeled reference replay and end card | Winning connection, then RoyaleBench title, crown, and repository address. |

## Evidence boundaries

- The reference wins at 11.20 seconds; Opus loses at 10.35 seconds. Replay clocks stop at each terminal state. A 1.8-second presentation tail lets the tower burst and result animation finish.
- Both sequences have matching card IDs and deployment ticks. Placements differ across the complete sequences; the comparison does not claim that one action alone caused the outcome.
- Cannon and Log are explicit frozen comparisons. The closing attack is a labeled repeat of the reference footage.
- 10/14 means task objective success in one run; v6 includes objectives besides match wins. Outcome marks are grouped rather than shown in task order.
- 18 seconds is remaining game time, not a model thinking deadline.
