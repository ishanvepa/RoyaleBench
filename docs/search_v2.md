# Search v2 implementation and evaluation

Search v2 is a separate CPU player (`type = "search-v2"`) behind the existing
benchmark interface. `search-bot` and its 4-rollout, 12-second configuration are
unchanged. Both bots see the full engine state, including the enemy hand and
elixir. Both choose from `Game.legal_moves` every 40 ticks with zero command
delay. This is an omniscient comparison, not a public-information opponent.

## Implementation

[`search_v2.py`](../cr_arena/bots/search_v2.py) saves the root once and restores it on a
private engine for each rollout. It screens all deduplicated candidates against
the same short scenarios, retains a bounded shortlist, and runs complete matched
rounds before halving the unprotected candidates. Long-horizon samples are kept
separate from screening scores. Final ranking uses the mean, with a stable command
ordering for ties. No downside penalty or evaluator adjustment is included.

Reservations have this priority: wait, a threatened lane defense, an air response,
a spell aimed at an enemy unit, then one move per playable card. At most
`shortlist_size - 1` moves are protected; one slot stays competitive. The best
screened placement in each category is reserved. A reservation only guarantees
simulation, not selection or a successful defense. Air responses use a small
explicit list because the pinned `CardInfo` does not expose attack targets. Unit
spell targets are opportunities to investigate, not a claim that casting is good.

The candidate cap is applied round-robin across hand slots in stable command
order. Wait is always included. Typical menus fit within the cap; diagnostics
record both supplied and searched counts. A small cap can discard useful moves.

Aggressive, defensive, and patient policies use the existing heuristic with attack
thresholds 5, 8, and 9.5 elixir. A seeded 12% variation lowers the threshold by two.
The optional `legacy` policy uses v1's 60% heuristic / 25% wait / 15% random move
mixture. Our continuation policy is independently configurable. Both sides
recompute legal moves at every simulated decision, choose from the same frozen
position, and can deploy repeatedly. The final step is clamped to the horizon;
terminal outcomes stop immediately. Python seat memory is unused. Branch RNGs
reset from shared scenario seeds, independently for each side.

Seeds derive from the configured seed and serialized root state. Allocation never
depends on wall time. Configuration must fund screening at `max_candidates` plus
one full shortlist round, in both rollout count and simulated ticks. Further work
is admitted only as a complete round. Actual ticks and rollout counts include
screening. Only `workers = 1` is currently supported; other values are rejected.
The benchmark player rejects live command delay. A separate human-play adapter
supports delay and stale-answer checks, as described below. Richer live placement
generation, hidden-state inference, evaluator changes, and tree search remain
separate work.

The evaluator is imported directly from v1: crowns, tower damage, elixir, and
HP-weighted board card value. Wins/losses score ±100,000; draws score zero.
Its known potential mistakes, including spawned-unit cost attribution, remain.
Each `Decision.raw` gives a concise action/score/work explanation. JSONL decision
logs include a separate `diagnostics` object with reservations, scenario seeds,
per-policy scores, sample counts, wait score, work, latency, and source tick.
Initial development runs stored that object inside `raw` instead.

## Run comparisons

```bash
uv run --locked python -m unittest tests.test_search_v2 tests.test_compare_search -v
uv run --locked python -m cr_arena.compare_search \
  --config configs/search_v2_frozen.toml --out runs/search-v2/my-run \
  --seeds 101 202 --parallel 3
# Add --cross-decks to test both deck assignments for every distinct deck pair.
uv run --locked python -m cr_arena.search_tactics --out runs/search-v2/tactics.json
```

The runner reuses `play_match`, preserving simultaneous decisions, logs, and
replays. It deliberately does not use tournament's classic schedule, which assigns
one seed per deck and overrides the requested seed list. Here every requested
seed runs on every deck, with seats swapped. Cross-deck cases keep deck ownership
fixed while swapping seats, then test the reverse ownership as another case.
There are no LLM calls. `--parallel` controls match processes; each bot has one
private engine. Resume with the same command and output directory; changes to
source/configuration/dependencies require a new directory. To reproduce an archived
run, check out its base commit and overlay the archive contents before using the
saved command/configuration.

The initial `dev-1` run predates source archiving and exact tick instrumentation;
its manifest retains hashes and its timings are uninstrumented. Subsequent runs
save source copies.

Each final run saves `manifest.json`, source/configuration/lockfile copies under
`source/` (archived as `source.tar.gz` after completed runs), `results.json`, `summary.json`, decision JSONL, and msgpack replays.
The manifest contains source hashes, base commit, tracked diff hash, package
versions, engine/card-table identity, decks, seeds, seats, and the strength
criterion. `execution.json` records the exact final command, six match processes,
one worker per bot, and machine details. Source snapshots are necessary because implementation runs can be
uncommitted. Replays are local artifacts ignored by Git, following repository
convention. JSONL may be compressed after a run; decompress to inspect it.

The selected preset is [`search_v2_frozen.toml`](../configs/search_v2_frozen.toml).
Selection is recorded in [`selection.json`](../runs/search-v2/selection.json); its
settings are fixed before seed 101 is tested. Development scores were 3–3 for the
initial preset, 5–1 for the shorter legacy preset, and 4–2 for the balanced preset.
The shorter legacy preset was selected.

The final comparison instruments both private engines to count actual ticks,
including terminal truncation. Timings include the same instrumentation for both
bots and concurrent-machine contention. They are practical observations, not
isolated CPU microbenchmarks. Different rollout horizons and tick totals do not
constitute equal-work strength evidence.

## Evaluation protocol

Development uses seed 1 on Giant beatdown, Hog cycle, and LavaLoon, with seats
swapped. Three presets explore horizon and continuation effects:

| Configuration | Screen / full horizon | Our continuation | Enemy mixture |
| --- | --- | --- | --- |
| `search_v2.toml` | 6 / 24 seconds | defensive | aggressive, defensive, patient |
| `search_v2_legacy.toml` | 4 / 12 seconds | legacy | legacy, aggressive, patient |
| `search_v2_balanced.toml` | 12 / 18 seconds | legacy | legacy, aggressive, patient |

Choose the preset by development score, then lower measured latency on a tie.
Freeze it before testing seed 101 on all three mirror and six ordered cross-deck
matchups: 9 paired cases, 18 games. The final sample is fixed in advance; do not
add cases just to obtain significance. Improvement requires score greater than
50% and a one-sided exact sign test over non-tied paired scores with p < 0.05.
Draws count as half. Report a paired bootstrap interval as descriptive uncertainty;
small-sample intervals can be degenerate and are not the promotion criterion.
This tests performance on these simulator cases, not all Clash Royale positions.

## Frozen held-out result

**Search v2 won 11, drew 0, and lost 7 (61.1% score). This does not establish a
repeatable strength improvement, and v1 remains the reference.** The predeclared
one-sided paired sign test gives p = 0.34375, above 0.05. Four paired cases favor
v2, two favor v1, and three split. The descriptive paired bootstrap 95% interval
is 33.3–83.3%. No extra cases were added after inspecting the result.

| V2 deck | V1 deck | V2 wins / draws / losses |
| --- | --- | --- |
| Giant beatdown | Giant beatdown | 1 / 0 / 1 |
| Hog cycle | Hog cycle | 2 / 0 / 0 |
| LavaLoon | LavaLoon | 1 / 0 / 1 |
| Hog cycle | Giant beatdown | 2 / 0 / 0 |
| LavaLoon | Giant beatdown | 0 / 0 / 2 |
| Giant beatdown | Hog cycle | 0 / 0 / 2 |
| LavaLoon | Hog cycle | 2 / 0 / 0 |
| Giant beatdown | LavaLoon | 1 / 0 / 1 |
| Hog cycle | LavaLoon | 2 / 0 / 0 |

The strongest observed result is Hog cycle: v2 wins all six held-out games across
the three opposing decks. Its Giant deck wins two of six; LavaLoon wins three of
six. These breakdowns were inspected after the frozen run and are exploratory,
not independent confirmation that selecting Hog will generalize to other seeds.
Mirror games total 4–2; cross-deck games total 7–5.

| Cost across the held-out run | V1 | V2 |
| --- | ---: | ---: |
| Mean time per asked decision | 0.878 s | 2.665 s |
| 95th percentile decision time | 2.059 s | 3.655 s |
| Actual simulated ticks | 14,845,555 | 56,754,025 |
| Rollouts | 64,648 | 273,993 |

V2 uses about 3.04× the observed decision latency and 3.82× the actual simulation
work. Both ran concurrently on the same 10-core arm64 machine with six match
processes. This is neither equal-work evidence nor a demonstrated efficiency gain.
There were **zero illegal actions**. All 18 saved command traces reproduce every
recorded frame hash and final hash. The v2 tick and rollout totals in all decision
logs match the independent private-engine meters, and every decision obeys both
configured work limits. Fresh games and fresh bots also reproduce the same opening
action, scenarios, scores, and simulated work.

Artifacts: [summary](../runs/search-v2/held-out/summary.json),
[per-game results](../runs/search-v2/held-out/results.json),
[manifest](../runs/search-v2/held-out/manifest.json),
[execution settings](../runs/search-v2/held-out/execution.json),
[source snapshot](../runs/search-v2/held-out/source.tar.gz),
[trace verification](../runs/search-v2/held-out/replay_verification.json), and
[fresh-game reproduction](../runs/search-v2/reproducibility.json).
Decision logs are saved as `runs/search-v2/held-out/logs/*.jsonl.gz`.
The historical [test report](../runs/search-v2/validation.json), from before the
Postgres adapter was removed, records 44 tests run: 35 passed and 9 optional
PostgreSQL integration tests skipped because `ARENA_TEST_DATABASE_URL` was unset.

The useful next experiments are improving opponent responses in the losing
Giant/Hog and Lava/Giant matchups, reducing work on small menus, and comparing
search changes at matched tick budgets. Any new preset needs new held-out seeds;
seed 101 is now evaluation history. Human play is available for experimentation;
the live adapter has not been measured by this frozen benchmark run.

## Human play

Select **search-v2** in either the dashboard's **You vs model** selector or the
real-time browser/phone game's opponent selector. Both read the shared
[catalog](../configs/bots.toml), whose Search v2 entry references the selected
preset in `configs/search_v2_frozen.toml`; see the [phone-play guide](phone_play.md)
for launch commands. The existing bots remain available.

The dashboard uses the fixed-budget benchmark implementation and pauses between
moves. [`live_search_v2.py`](../cr_arena/bots/live_search_v2.py) adapts the same search
to real time: it preserves the 21-tick command delay, excludes hand slots with
pending commands, and keeps the incoming snapshot separate from rollout engines.
It still uses the numbered placement menu, rather than the planner's richer spots.

Live search has a soft 1,200 ms deadline. It always completes screening and one
full shortlist comparison, then checks the clock before each additional round.
A started round finishes, and its best completed comparison is the fallback;
there is no partial-round ranking or hard latency guarantee. The server validates
source tick, card identity, pending status, and deployment legality before applying
the answer. Answers older than 80 ticks (four seconds) are discarded; the worker
then receives a fresh snapshot. Each game uses one search worker process.

The recorded comparison predates the expanded spell targets and observation fixes
now on main. Reproduce those numbers with the archived source; they are not a new
strength measurement of the updated action interface.

This human-play adapter was added after the frozen strength comparison. That
run's archived source is the reference for its reported numbers. Live timing,
delay, and human free-placement behavior differ from the benchmark protocol;
those results do not establish live strength.

## Tactical probes and checks

Real-engine checks cover root isolation, repeated choices/diagnostics, both seats'
legal action mapping, repeated simultaneous deployments, exact horizon clamping,
minimum budget rejection, actual budget bounds, terminal draws/wins/losses, and
engine work accounting across snapshot restores. A reservation test gives defense
moves poor synthetic screen scores to verify they survive; it does not claim to
reproduce every planner pruning failure.

[`search_tactics.py`](../cr_arena/search_tactics.py) provides urgent Hog defense,
Balloon defense, a swarm/spell opportunity, and defense with a counterpush. Probes
apply each root action and then allow **no follow-up deployments for 12 seconds**.
They expose immediate root behavior separately from the full rollout assumption.
They are not four puzzle wins or independent strength samples.

For the initial 24-second preset, Minions against Balloon leaves the threatened
tower at 2,172 HP; waiting loses the tower. Both v1 and v2 find that action. The
swarm probe also avoids damage, but chooses a troop rather than a spell. The Hog
probe is a failure example: v2's root takes 2,219 tower damage versus v1's 951 when
followups are disabled. V2 assumes it can defend in a later decision. The
counterpush probe deals 681 damage with v2's root versus 904 with v1's. These
limitations remain visible in [`tactics.json`](../runs/search-v2/tactics.json).

The shorter legacy preset fixes that isolated Hog regression: it takes the same
951 damage as v1 while its Musketeer deals 434 damage to the other tower. Its
counterpush probe matches v1's 904 damage. These are engine outcomes after the
root action, recorded in [`tactics-legacy.json`](../runs/search-v2/tactics-legacy.json);
they do not establish full-game strength.

The held-out run generated a Hog cycle win replay and a Giant loss replay.
Those HTML files and the full msgpack replays are local artifacts under the ignored
`replays/` directory. Regenerate a viewer with `python -m cr_arena.replay TRACE.msgpack
--stride 4 -o VIEWER.html` after restoring a trace.

A local opening profile placed most time in native stepping, state restoration,
and legal-move generation. The implementation retains the existing state API;
no native observation pipeline or process pool inside a bot was added.
