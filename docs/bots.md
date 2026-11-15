# Bot setup and organization

Start with [`configs/bots.toml`](../configs/bots.toml) to change the human-play bot
list or its presets. The browser/phone game and paused dashboard both read this
catalog. Each entry has a stable ID, a display name, a bot type, and the modes in
which it appears. Display order follows file order.

The local default is `heuristic-bot`, using the existing readable defense, spell, and
high-elixir attack rules with `attack_elixir = 8.0`. It is available in both human
play modes. `python -m cr_arena.live --public` (or `cr_arena.share --public`)
pins the opponent to `planner-bot` with `hog-2.6-cycle`, allows only the human
to choose a deck, and caps active games at five. Public Planner matches each use
two search workers; the other bots remain available in ordinary local mode. See [public hosting](public_play.md).

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
uv run --locked python -m unittest tests.test_bot_registry tests.test_human_search_v2 -v
```

See [human play](phone_play.md) for launch commands and [Search v2](search_v2.md)
for the search design and frozen comparison results.
