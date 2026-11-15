# RoyaleBench v4 challenge set

RoyaleBench v4 is a focused follow-up to the first full v3 model comparison. It keeps the
`coordinates-v1` interface, paused two-second decisions, Planner opponent, pinned engine,
binary objective rewards, and independent replay verifier. It has five new positions built
from validated v3 states. The v3 dataset and its scores remain immutable and separate.
The current published release is **`royalebench/royalebench-v4@2`**
(tag `v4-corrected`, digest prefix `c952a7188567`). Revision `@1` is superseded
because its mirrored successive-threats instruction contained contradictory coordinates.

## Why these positions

On `royalebench/royalebench-v3@2`, one attempt per task with the same
`claude_code-v1.0.0` harness and Modal provider gave Opus 5.5 **11/11** and Sonnet 5.5
**7/11**. Both runs finished all eleven tasks with replay integrity 1. The model API
costs reported by their task logs total **$1.57** and **$0.63**, respectively; sandbox
compute is excluded. The downloaded [Opus results](../runs/royalebench-v3/opus55-results.json)
and [Sonnet results](../runs/royalebench-v3/sonnet55-results.json) identify the exact
dataset revision, model, harness, and per-task rewards. Run IDs are
`42439ed0-ff88-4ef9-b19d-052f9866e651` and
`37a44c9f-870b-40ee-811c-ac4b862114d6`.

| v3 task | Opus | Sonnet | Trace finding |
| --- | ---: | ---: | --- |
| 01 immediate lethal | 1 | 1 | Both cast the same first-action Fireball. Keep as a control outside the challenge set. |
| 02 efficient defense | 1 | 0 | Opus pulled Hog with Cannon at (6.5, 10.5); Sonnet's (3.5, 11.5) placement let 634 damage through. |
| 03 spell placement | 1 | 1 | Both Fireball placements met the one-spell objective. |
| 04 tank and support | 1 | 0 | Opus's central Inferno and follow-up survived; Sonnet placed Inferno on the threatened lane and lost its weak tower. |
| 05 successive threats | 1 | 0 | Opus met the 450-damage cap by 32 HP; Sonnet allowed 1515 damage. |
| 06 unequal threats | 1 | 1 | Both allowed 1917 tower damage yet passed the survival and spending objective. |
| 07 counterpush | 1 | 1 | Both won the longer continuation. |
| 08 cycle to lethal | 1 | 0 | Opus cycled into Cannon then Fireball; Sonnet cycled with Skeletons and Ice Golemite and lost before its Fireball resolved. |
| 09 tower race, both variants | 2 | 2 | Both models won each variant; Sonnet won the commit variant with a single Fireball. The pair does not reliably separate commitment choices. |
| 10 protect the lead | 1 | 1 | Both protected the lead. |

This is a single paired run, so the table supports task revision, not a stable model ranking.
The defense failures are spatial and sequencing errors with valid play and verifier results,
not setup failures. The easy lethal and race wins reveal low ceiling in those tasks.

## Five targeted challenges

| Task | Lever and capability | Objective | Local contrast |
| --- | --- | --- | --- |
| `02-efficient-defense-mirror` | Move the Hog and weak tower to the opposite lane; place a building based on the new geometry. | Both towers survive 12 seconds, at most 400 new damage and 4 elixir spent. | A mirrored reference wins; the observed original-lane Cannon placement fails. |
| `04-tank-and-support-mirror` | Move Giant, Musketeer and weak tower to the opposite lane; separate the tank from support. | Both towers survive 20 seconds with at most 9 elixir spent. | A mirrored reference wins; the original-lane reference fails. |
| `05-successive-threats-mirror` | Move Goblin Gang and the disclosed six-second Goblin Barrel to the opposite lane; preserve the defense budget across both. | Both towers survive 20 seconds, at most 450 new damage and 8 elixir spent. | A mirrored reference wins; the original-lane reference fails. |
| `08-cycle-to-lethal-plus` | Raise the enemy tower from 158 to 180 HP, beyond one Fireball's 159 crown damage; sequence defense, cycle and a follow-up. | Win within the remaining 18 seconds of overtime. | Ice Spirits, Cannon, Fireball and Log win in replay; the v3 Fireball-only finish loses. |
| `08-cycle-to-lethal-critical` | Lower our weak tower from 458 to 250 HP relative to `08-cycle-to-lethal-plus`; choose a stronger defense before finishing. | Win within the remaining 18 seconds of overtime. | Log, Cannon and Fireball win in replay; the cheaper Ice Spirits defense from the `@1` Opus pilot loses. |

The mirrored tasks change the board position and tower HP side together so they preserve
the original tactical asymmetry. Decks, seed, clock, elixir, Planner settings, action cadence,
and budgets remain fixed. The first cycle task changes only enemy tower HP from v3;
the critical variant changes only own tower HP from that first cycle task. The agent sees the
new state through `cr` and the instruction; the private reference remains outside its sandbox.
Each task must pass a winning reference, a losing counterfactual, wait, empty and malformed
controls, repeated deterministic replay, player isolation, restart persistence and
fresh-container grading before publication. All five passed those local gates; the
[Docker validation](../runs/royalebench-v4/docker/validation.json) records the common image,
protocol hash, trace frames and per-task checks. The targeted Python suite passed
44/44 tests.

The first hosted pilot on the unchanged `08-cycle-to-lethal-plus` task in `@1` used the same Claude Code v1.0.0
harness and Modal provider as the v3 comparison. Opus 5.5 scored **1** with integrity 1
([run `530134ed-a357-4260-93ec-f71feb2e09f4`](../runs/royalebench-v4/opus-cycle-pilot-results.json));
Sonnet 5.5 scored **0** with integrity 1
([run `9fe690f8-0190-4420-82a5-f0f9444cd227`](../runs/royalebench-v4/sonnet-cycle-pilot-results.json)).
Both recognized that 180 HP exceeds Fireball's 159 crown damage and cast Log first.
Opus delayed the Giant with Ice Spirits at (3.7, 9.5), then its Fireball reached the
tower in time. Sonnet chose Ice Golemite at (3.5, 8.5); its own tower fell before the
Fireball landed. The model API costs were $0.1210 and $0.0476, excluding compute.
This pilot confirms a genuine timing failure on that task.

The four-task `@1` full runs reported Opus **3/4** and Sonnet **1/4**
([Opus](../runs/royalebench-v4/opus55-results.json),
[Sonnet](../runs/royalebench-v4/sonnet55-results.json)). **Do not use those
aggregate scores as difficulty evidence.** The `05-successive-threats-mirror`
objective said “right tower (3.5, 6.5)” while the simulated Barrel landed on
the right tower at `(14.5, 6.5)`. Both models' traces explicitly say they used
the wrong coordinate and spent four elixir defending the left lane. The `@2`
instruction and live observation both say “right tower (14.5, 6.5)”; its private
scenario, grader and winning reference are unchanged. New model runs on `@2`
are required to measure the corrected task and aggregate.

The two-task `@2` pilots tested both changed positions with the same harness and
Modal provider. Opus 5.5 and Sonnet 5.5 each scored **1/2**, with integrity 1 on
both tasks ([Opus run `de9d3146-3b85-4ee3-823f-e2f477d58966`](../runs/royalebench-v4/opus-r2-changed-results.json),
[Sonnet run `ba368f4b-68f2-43dd-b7a9-fc6d6859cc79`](../runs/royalebench-v4/sonnet-r2-changed-results.json)).
Both won the new critical-defense task by placing Cannon after Log. On corrected
`05-successive-threats-mirror`, Opus took 1593 damage and Sonnet 905 against the
450 limit. Both defended the stated right-tower Barrel, so the observed failure
is budget allocation across successive lanes rather than the old coordinate defect.
Opus used all eight elixir before a later Goblin Gang hit the left tower; Sonnet's
early units left the right tower before the Barrel landed and its later Cannon
did not contain the left-lane wave. These pilots motivate a full same-revision run;
they are not an aggregate benchmark comparison.

## Full `@2` model comparison

One complete five-task run per model used `claude_code-v1.0.0`, Modal, concurrency 5,
and the same immutable `royalebench/royalebench-v4@2` digest. Opus 5.5 scored
**3/5 (60%)** ([run `941173e3-ba01-4cb9-8374-a5dfd8e7ae88`](../runs/royalebench-v4/opus55-r2-results.json));
Sonnet 5.5 scored **1/5 (20%)**
([run `538d268f-17dd-411a-a779-d995ff2951f0`](../runs/royalebench-v4/sonnet55-r2-results.json)).
Every task completed, had verifier integrity 1, and had no rejected deployment.
Model API costs from the saved agent logs totaled **$0.6822** and **$0.2572**,
excluding Modal compute. The [revision check record](../runs/royalebench-v4/checks-revision2.json)
pins the full digest, protocol hash, container validation and per-task rewards.

| v4 `@2` task | Opus | Sonnet |
| --- | ---: | ---: |
| 02 efficient defense, mirrored | 1 | 0 |
| 04 tank and support, mirrored | 1 | 1 |
| 05 successive threats, mirrored and corrected | 0 | 0 |
| 08 cycle to lethal, extra HP | 0 | 0 |
| 08 cycle to lethal, critical defense | 1 | 0 |

Opus's corrected `05` rollout defended the right Barrel but spent four elixir
on Musketeer, two on Log and two on Ice Golemite. The later left-lane wave
then pushed total tower damage to **741**, above the **450** limit. Its `08` extra-HP
rollout cycled to Fireball and left the enemy tower on 21 HP, but waited for a
Hog Rider before casting the finishing Log; the Giant took its own tower first.
Those failures are visible in the saved decisions and independent replays, with
no instruction conflict in `@2`. Sonnet failed three additional tasks through
placement or timing choices, while its central tank defense passed.

This is a preliminary difficulty signal, not a stable model ranking. There is
one full attempt per task and model. The same `08` extra-HP task was won by Opus
in both its earlier pilot and the superseded `@1` full run, then lost in the
`@2` full run because its decisions differed. More repetitions and additional
models are needed to estimate success rates and generalization beyond these
five deterministic positions. These tasks were selected after inspecting the
first Opus/Sonnet comparison, so a broader model cohort is also needed to test
whether the measured gap generalizes.

## Build and run

```bash
uv run python -m cr_arena.build_v4 --jobs 2
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-v4 --jobs 2
valkyrie dataset push royalebench/royalebench-v4 ./benchmarks/royalebench-v4 --tag v4-corrected
```

To reproduce the published cohort, pin `@2` and use the same agent, provider and
secret mapping for each model:

```bash
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-v4@2 \
  --model anthropic/claude-opus-5-5 --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}" \
  --concurrency 5 --label royalebench-v4-opus-repeat
```

Use `anthropic/claude-sonnet-5-5` for the paired Sonnet run. After a run finishes,
`valkyrie run results RUN_ID --path results.json` saves the scores and
`valkyrie run outputs RUN_ID --output-dir run-output` saves agent logs and replays.
The v4 builder uses the tracked v3 task packages and an embedded winning action
sequence for the mirrored successive-threats state. Rebuilding does not depend
on downloaded run files. Push a new immutable revision after changing any task;
do not mix its scores with `@2`.
