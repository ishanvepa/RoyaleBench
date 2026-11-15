# Bot setup and organization

Start with [`configs/bots.toml`](../configs/bots.toml) to change the human-play bot
list or its presets. The browser/phone game and paused dashboard both read this
catalog. Each entry has a stable ID, a display name, a bot type, and the modes in
which it appears. Display order follows file order.

```toml
[bots.practice]
modes = ["live", "turn-based"]
name = "practice-bot"
type = "heuristic"
attack_elixir = 7.0
```

A catalog entry can instead reference a named player from an existing run config:

```toml
[bots.search-v2]
modes = ["live", "turn-based"]
preset = "search_v2_frozen.toml"
preset_player = "search-v2"
```

Preset paths are relative to the catalog. Extra player settings in the entry
can override the referenced settings. Remove a mode to hide a bot in that mode.
The planner currently supports only `live`; the existing search bots support both.
Search v2's measured settings stay in the frozen comparison config so its recorded
results retain their provenance. Tournament and comparison configs continue to
specify their players explicitly; editing the human catalog does not rewrite them.

## Code map

```text
cr_arena/
  player_types.py         Player, Decision, DeckBuild, InfraError
  players.py              LLM players, mock model, unified build_player()
  bots/
    registry.py           build_bot() and human_bot_specs()
    baselines.py          RandomBot and HeuristicBot
    search.py             Search v1 and its evaluator
    search_v2.py          Deterministic adaptive Search v2
    planner.py            Planner and its process-pool workers
    live.py               Shared snapshot adapter for live bot workers
    live_search_v2.py     Delayed Search v2 and completed-round deadlines
```

`players.build_player()` delegates bot construction to the registry and handles
LLM construction itself. Both human-play selectors obtain their bots through
`human_bot_specs()`. The live server handles the game clock and validates returned
commands; `bots/live.py` handles each implementation's snapshot interface.

To add a new implementation, put it in `cr_arena/bots/`, add its constructor to
`build_bot()` in the registry, and add a catalog entry for its supported modes.
If it needs different real-time behavior, add the adapter in `bots/live.py`.
The selectors do not need individual entries for each bot. Restart the live
server after catalog changes; refresh the dashboard to reload its choices.

The old `search_bot.py`, `search_v2.py`, `planner_bot.py`, and `live_search_v2.py`
paths re-export their public classes for existing imports. New code should import
from the corresponding `cr_arena.bots` module. Shared player types and the simple bot classes also remain
importable from `cr_arena.players` for compatibility.

Run the relevant checks with:

```bash
uv run --locked python -m unittest tests.test_bot_registry tests.test_human_search_v2 tests.test_planner -v
```

## Measuring live bots

`cr_arena/duel.py` plays bots against each other under live conditions: free placement, the
21-tick command delay, and decisions on a fixed tick schedule (planner every 8 ticks, numbered-move
bots every 20). Thinking takes no game time, and every supported bot is deterministic, so a run
repeats exactly. Each (deck, seed) is played with seats swapped.

```bash
uv run --locked python -m cr_arena.duel --a planner:prefilter=false --b planner --games 12 --parallel 4 --out runs/duel/prefilter-ab
```

A spec is a bot type plus settings, for example `planner:top_k=6,horizon_s=8`. With `--out`, games are
appended to `games.jsonl` (a rerun resumes) and `summary.json` reports W/D/L, seat-swapped pairs won
and lost with a one-sided sign test, and the mean tower margin (share of own tower HP kept minus the
opponent's, from -1 to 1). The tower margin is more sensitive than wins in small runs. Use `--seed0` to
pick a fresh seed range for a held-out check after tuning. Each game runs on one core and takes
about 1–10 minutes (longest for overtime games between planners); 12 games at `--parallel 4` take
about 30–45 minutes.

### Planner settings

| Setting | Default | Meaning |
|---|---|---|
| `horizon_s` | 10.0 | Look-ahead per candidate |
| `top_k` | 4 | Candidates checked against the opponent's reply |
| `margin` | 40 | Gain over waiting, in tower HP, needed to play |
| `two_ply` | true | Check the opponent's worst reply |
| `three_ply` | true | After the opponent's reply, try our own answer to it (for the `answer_k` replies that hurt most). About 3× the decision cost |
| `answer_k` | 3 | Worst replies that get our answer |
| `prefilter` | true | Original rule: only plays that already beat waiting by `margin` *without a reply* are checked against replies. `false` checks a shortlist of the `top_k` best plus each other card's best spot, so defensive plays that only pay off once the opponent moves are not pruned early |
| `workers` | 0 | Process-pool size (live server only) |

All of these can be set on a planner entry in `configs/bots.toml`.

### Results (2026-11-14, one deck per seed, seats swapped)

"Original" is the planner before the third ply (`three_ply=false`, `prefilter=true`).

| A | B | Seeds | A W-D-L | Pairs won-lost (of 6) | Mean tower margin |
|---|---|---|---|---|---|
| original | heuristic | 1–6 | 11-0-1 | 5-0 (p=0.03) | +0.41 |
| original + `prefilter=false` | heuristic | 1–6 | 11-0-1 | 5-0 (p=0.03) | +0.41 |
| original + `prefilter=false` | original | 1–6 | 4-0-8 | 0-2 | +0.01 |
| original + `three_ply` | original | 1–6 | 10-0-2 | 4-0 (p=0.06) | +0.14 |
| original + `three_ply`, `prefilter=false` | original | 1–6 | 8-0-4 | 3-1 | +0.11 |
| original + `three_ply` | original | 7–12 (held out) | 9-0-3 | 3-0 (p=0.13) | +0.08 |

Over both seed ranges the third ply is 19-5 against the original, winning 7 seat-swapped pairs and
losing none (p≈0.008), so it is the default. Removing the prefilter did not help, with or without the
third ply, and it doubles the cost, so `prefilter` stays `true`. With the third ply, the original planner's
average decision rises from about 100 ms to about 300 ms on one core (up to about 1 s on Hog Cycle). The
live server spreads this over its process pool. Raw games are in `runs/duel/`.

See [human play](phone_play.md) for launch commands and [Search v2](search_v2.md)
for the search design and frozen comparison results.
