# Bot setup and organization

Start with [`configs/bots.toml`](../configs/bots.toml) to change the human-play bot
list or its presets. The browser/phone game and paused dashboard both read this
catalog. Each entry has a stable ID, a display name, a bot type, and the modes in
which it appears. Display order follows file order.

The local default is `heuristic-bot`, using the existing readable defense, spell, and
high-elixir attack rules with `attack_elixir = 8.0`. It is available in both human
play modes. `python -m cr_arena.live --public` (or `cr_arena.share --public`)
pins the opponent to `planner-bot` with `hog-2.6-cycle`, allows only the human
to choose a deck, and caps active games at seven. Public Planner matches each use
eight search workers, the same as a lone local game, so shared play matches local strength; the other bots remain available in ordinary local mode. See [public hosting](public_play.md).

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
The planner's catalog entry is `live` only; the existing search bots support both.
`build_bot()` can also build the planner as a numbered-move player (`PlannerPlayer`)
for benchmark-style games, but the dashboard selector does not offer it yet.
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
    planner.py            Planner, its process-pool workers, and PlannerPlayer
    live.py               Shared snapshot adapter for live bot workers
    live_search_v2.py     Delayed Search v2 and completed-round deadlines
  live_duel.py            Real-time bot-vs-bot comparison on the live server loop
  turn_duel.py            Turn-based bot-vs-bot comparison on the benchmark loop
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
uv run --locked python -m unittest tests.test_bot_registry tests.test_human_search_v2 -v
```

## Which bot is strongest

Two bots-only comparisons play every pairing on mirrored classic decks with seats
swapped. Both resume an interrupted run from the same `--out` directory.

```bash
uv run --locked python -m cr_arena.live_duel --out runs/live-duel/v1 --seeds 1
uv run --locked python -m cr_arena.turn_duel --out runs/turn-duel/v1 --seeds 1 2 3 --parallel 8
```

`live_duel` runs the live server's loop: real time, a 21-tick command delay, bots
asked every 5 ticks in their own processes, and Search v2's stale-answer check.
Thinking speed is part of strength, so it plays one game at a time on an otherwise
idle machine; the planner gets 8 workers, as the live server gives a lone game.
`turn_duel` uses the benchmark's `play_match`: numbered moves every 40 ticks, no
delay, and a clock that waits for both bots. Every bot is single-process and
deterministic there, so games can run in parallel.

Both runs were stopped early once the leader was clear (November 14, 2026):

| Mode | Games | planner-bot | search-bot | search-v2 |
| --- | ---: | --- | --- | --- |
| Live ([results](../runs/live-duel/v1/summary.json)) | 13 of 18 | 12–0–0 | 1–0–6 | 0–0–7 |
| Turn-based ([results](../runs/turn-duel/v1/summary.json)) | 35 of 54 | 30–0–4 | 4–0–15 | 1–0–16 |

W–D–L. The planner won every deck against both opponents in live play, and in
turn-based play it won every decided seat-swapped pair: 6 of 6 against Search v1
(p = 0.03) and 7 of 7 against Search v2 (p = 0.016, two-sided sign tests). It wins turn-based play with free thinking time
and the models' numbered menu, so its live result is not only speed or richer
placements. Most margins were one crown. Search v1 versus Search v2 remains
unsettled: these runs played only one decided game between them. All three bots
read the true engine state.

See [human play](phone_play.md) for launch commands and [Search v2](search_v2.md)
for the search design and frozen comparison results.
