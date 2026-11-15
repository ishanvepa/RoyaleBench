# Silent-viewing captions — 67-second edit

The active [v04 Remotion cut](remotion/README.md) has no narration. These lines are burned into the video at the exact times below; a quiet original effects track marks scene changes and matched deployments.

| Time | Caption |
| --- | --- |
| 0–4s | RoyaleBench tests gameplay decisions by language models. |
| 4–8.5s | Each task begins from a fixed Clash Royale battle state. |
| 8.5–13s | The model reads text, chooses a card and coordinates; a verifier replays the actions. |
| 13–18s | Here is the actual text observation. |
| 18–24s | The model chooses a card slot and arena coordinates. |
| 24–28s | Same six cards. Same order, timing, and 15 elixir. |
| 28–33s | The placements differ. |
| 33–37s | Opus loses. The validated reference wins. |
| 37–43s | Reference Cannon: half a tile left, one tile higher. |
| 43–50s | Model Log: enemy tower. Reference Log: incoming Giant. |
| 50–59s | In one v6 run, Opus completed 10 of 14 task objectives. |
| 59–63s | The validated reference finds the winning connection. |
| 63–67s | No caption; leave the end card clear. |

The editable source of truth is `remotion/src/GameUI.tsx`. The comparison identifies visible placement differences, not a sole cause of the outcome. The score is task objective success in one historical v6@1 run; v6 contains objectives besides match wins. The model receives text observations, and the arena is the replay visualization for viewers.
