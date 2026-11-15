# RoyaleBench Win

This separate dataset addresses saturation in v3 and makes every task's gameplay
success condition **winning the actual match**. Historical datasets retain their
original scores. The player uses the existing `coordinates-v1` protocol, paused
observations, and independently replayed actions against the unchanged Planner.
The dashboard now defaults to [RoyaleBench v9](royalebench_v9.md). The historical
[v6 merge](royalebench_v6.md) includes these four tasks unchanged alongside v5's ten tasks. This separate win-only revision is
`royalebench/royalebench-win@2`, tagged `win-v2`.
The initial three-task revision remains `royalebench/royalebench-win@1`, tagged `win-v1`.
The expanded cohort adds a critical-health paired position after both frontier
models solved the first cycling pilot. Revisions and run results are recorded below.

## Evidence behind the change

The [downloaded run audit](../runs/royalebench-win/saturation/summary.json) records
immutable revisions, harnesses, run IDs, and raw results. In the November 15 runs,
Opus 5.5 and GPT-6.1 Sol each scored **11/11 on v3@2**, while their actual match-win
metric was **6/11**. Both averaged 6.27 decisions per task. Five short defense or
placement objectives could pass without winning a game. This is objective
saturation, rather than evidence of consistently strong full-match play.

Representative inspected successes include Cannon followed by waits for efficient
defense, one Fireball for spell placement, and Ice Spirits, Cannon, Fireball for
cycle-to-lethal. The newer hosted v4@2 is harder (Opus 3/5; Sonnet 1/5), but three
of its five tasks still use short defensive objectives. Opus's v4 two-hit lethal
failure demonstrates a useful timing error: it used Ice Spirits on the incoming
Giant, cast Fireball leaving 21 enemy tower HP, and lost before its late Log arrived.
Opus's tactics run scored 5/7; it is a separate dataset and is not a v3 score.

## Tasks and grading

The four positions start with **18–30 seconds of overtime**, no crown lead, a damaged
own left princess tower, an incoming attack, and enemy tower HP exceeding a single
finishing spell. The agent must defend and create a winning continuation. There
are no spending, lane, damage, card, or maximum-decision objectives.

| Task | Player / opponent decks | Capability and expected failure |
| --- | --- | --- |
| 01-cycle-and-connect | Hog Cycle / Giant; 18s | Cycle into building defense and a Hog connection; Fireball plus Log leave 256 enemy HP. |
| 02-sustained-tower-race | Giant / LavaLoon; 30s | Protect a 305 HP tower from Balloon while clearing Minions off a push against a full-health enemy tower. |
| 03-bait-damage-sequence | Log Bait / Giant; 24s | Separate tank/support defense, preserve surviving attackers, and finish a 1,000 HP enemy tower. |
| 04-critical-cycle-and-connect | Hog Cycle / Giant; 18s | Same state as task 01 except own tower HP is 250 instead of 700. Combine a precise pull with defensive spell timing; the reference wins without taking tower damage. |

Reward is 1 only when submitted play reaches the scenario end, the authenticated
action log independently replays, and `game.state.game_over` with `winner == 0`.
Otherwise reward is 0. At the final overtime deadline, the existing simulator
adapter resolves remaining crown ties by total tower HP, then seed parity; that
terminal match win counts. Leading on HP in an unfinished match does not.
Report the mean binary reward over the four tasks. Diagnostic damage and elixir
metrics do not contribute to the score.

The state grid holds opponent settings, cadence, player seat, engine,
resources, and action protocol fixed. Time, decks and board threats vary together to
create each skill test; cross-task differences cannot isolate deck strength.
Tasks 01 and 04 are an explicit paired exception: only own starting tower HP changes,
so the difference measures tolerance for defensive timing and placement errors.
Human-game archetype win rates are not simulator difficulty measurements.

## Reproduce and validate

```bash
uv run python -m cr_arena.win_benchmark --calibrate --jobs 3
uv run python -m cr_arena.win_benchmark --build
uv run --with pytest python -m pytest -q tests/test_win_benchmark.py tests/test_coordinate_task.py
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-win --jobs 2
```

The builder refuses stale configuration, runtime, or reference hashes and replays
every winning reference before packaging. A privileged Planner reference proves
solvability through the same coordinate submission rules; the reference and its
search code are not installed as an agent-accessible tool. It does not estimate
model performance. Calibration also checks deterministic replay and zero rewards
for wait, spell rush, empty, malformed, wrong-type, and partial logs.
The initial 60-second proposals failed the reference-solvability gate and were
excluded. The released positions use 18–30 seconds with multi-step conversion
pressure, rather than treating a longer window alone as evidence of difficulty.

The container check exercises the real `cr` CLI as the isolated `player`, protected
referee files, server restart, fresh-container verification without networking,
complete capture, and replay frame hashes. Container and hosted-model validation
are separate gates; local reference evidence alone is insufficient for scale.

Task packaging follows the current [Harbor layout](https://docs.harborframework.com/tasks/overview)
and [Valkyrie dataset workflow](https://docs.valkyrie.vals.ai/benchmarks/datasets).
Engine and runtime dependencies, task inputs, instructions, resources and
protocol hashes are pinned in the generated task configs and manifest.

```bash
valkyrie dataset push royalebench/royalebench-win ./benchmarks/royalebench-win --tag win-v2
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-win@2 \
  --model anthropic/claude-opus-5-5 --provider modal \
  -s ANTHROPIC_API_KEY anthropic-api-key-ishan \
  --slice 0:1 --concurrency 1 --label royalebench-win-opus-pilot
```

Start with one task, inspect the trace, and distinguish strategic losses from
task or infrastructure defects before expanding. Preserve the same immutable
revision, harness, resources, and inference settings for comparisons.

## Validation and model results

All four [reference solutions](../runs/royalebench-win/validation.json) win and replay
deterministically. All 24 negative controls score zero. All four tasks pass the
[isolated container check](../runs/royalebench-win/docker/validation.json), including
referee restart, complete capture, and frame-hash verification.

The first full four-task runs used immutable `royalebench/royalebench-win@2`, Modal,
concurrency 4, one attempt per task, the stock harnesses below, and no sampling
overrides. Both completed on November 15, 2026 with **50% win reward**.

| Model / harness | Cycle | Tower race | Bait sequence | Critical cycle | Wins |
| --- | --- | --- | --- | --- | --- |
| Opus 5.5 / `claude_code-v1.0.0` | Win | Loss | Win | Loss | **2/4** |
| GPT-6.1 Sol / `codex-v1.0.0` | Win | Loss | Win at overtime HP tiebreak | Loss | **2/4** |

- [Opus raw results](../runs/royalebench-win/opus-full-results.json): `042e6e32-b1e5-47be-8350-f66ed11c8a6c`.
- [Sol raw results](../runs/royalebench-win/sol-full-results.json): `b736a4c1-3e6e-463f-bd8b-3e39c106365b`.
- [Compact traces and review](../runs/royalebench-win/trace-review.json),
  [publication digests](../runs/royalebench-win/publication.json), and
  [checks and provenance](../runs/royalebench-win/checks.json).

All eight attempts completed with integrity 1 and zero rejected actions. On the
tower race, Sol placed Cannon at `(7, 10)` and lost its tower after 1.85 simulated
seconds. Opus placed Cannon at `(3.5, 11.5)`, then Fireball and Minions on the
Balloon, but lost after 5.3 seconds. The initial `@1` Opus attempt won this same
position with a different defense, confirming that the model can sometimes solve it.

On the critical cycling position, Opus placed Cannon at `(6.5, 10.5)` and later
sent Log toward the enemy tower while the Giant approached its own 250 HP tower;
it lost at 8.95 seconds. Sol used Cannon at `(7, 10)` and lost at 10.1 seconds.
The reference uses Cannon at `(7, 11.5)` and later defensive Log and Ice Spirits,
winning without taking tower damage. These comparisons show observed placement
and timing failures; they do not prove that one coordinate alone caused a loss.

The first three tasks were piloted as revision `@1` in partitioned runs: Opus won
3/3 and Sol 2/3. Revision `@2` adds task 04 without changing the first three task
packages. Its design was informed by those pilots. The full `@2` results above are
**development calibration**, not an unseen held-out evaluation, and one attempt
per task does not establish a stable difficulty estimate or model ranking.
The two harnesses differ, so the comparison measures model plus harness behavior.

Raw archives, replays, telemetry, and trajectories are checksum verified in the
locations recorded by [the archive index](../runs/royalebench-win/archive-index.json).
Gameplay capture is complete for both full runs. The existing telemetry normalizer
does not support Codex model-call events; its raw trajectory and harness usage
remain archived, and the index reports that normalization gap explicitly.
