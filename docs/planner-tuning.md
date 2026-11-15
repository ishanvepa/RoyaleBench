# Planner tuning duels (lavaloon mirror, both sides, 16 games each, vs the default planner)

Run on the pre-merge code (before upstream's game.py changes). Free bot-vs-bot games via `cr_arena.duel`.

| Variant | Result (W-L) | Crowns |
|---|---|---|
| planner:horizon_s=14 | 6-10 | 6-10 |
| planner:top_k=7 | 11-5 | 11-5 |
| planner:margin=20 | 9-7 | 11-10 |
| planner:margin=70 | 5-11 | 6-12 |
| planner:horizon_s=7 | not finished (stopped before the merge) | |

Only `top_k=7` looked better, and 16 games is a small sample. Not re-verified on the merged code.
Command: `uv run python -m cr_arena.duel --a "planner:top_k=7" --b planner --games 16 --decks lavaloon --parallel 8`
