# RoyaleBench v7

v7 is a separate development cohort built from the November 15 v6 critique and is
included in the default [v8 merge](royalebench_v8.md). Every
task requires a completed match win by taking a crown within a stated window.
Each starts with 60 seconds of overtime remaining, but the scoring window ends
earlier. The existing `win` grader therefore cannot award an HP or seed tiebreak.
There are no spending limits, card restrictions, or decision-count objectives.
Historical task packages and scores retain their meaning.

## Evidence motivating the tasks

The [latest eight-model v6 audit](../runs/royalebench-v7/v6-audit.json) pins the run
IDs, immutable `royalebench/royalebench-v6@1` revision, harnesses, settings, rewards,
and verifier outcomes. These are one-attempt development results, not a stable
model ranking. The raw service responses and all 28 Opus trajectory/game archives
were downloaded under the ignored `runs/recent/v7-design/` directory.

| Model | v6 objective success |
| --- | ---: |
| Opus 5.5 | 10/14 (71.4%) |
| GPT-6.1 Sol | 9/14 (64.3%) |
| Sonnet 5.5 | 5/14 (35.7%) |
| Kimi K3.1 Pro | 4/14 (28.6%) |
| Haiku 5.5 | 3/14 (21.4%) |
| Inkling 2 Small | 3/14 (21.4%) |
| DeepSeek V4.1 Flash | 2/14 (14.3%) |
| Qwen 3.8 | 1/14 (7.1%) |

Opus's run is `45124458-3a52-4e73-b380-ee42f6934b19`. It completed all tasks with
integrity 1 and zero rejected actions, so the result does not come from harness
errors. Its score includes three successful unfinished defensive windows; seven
outcomes were terminal match wins. The successful bait continuation ended 0–0 on
crowns through the HP tiebreak. Opus explicitly described preserving that lead in
its trajectory. Two other wins used only two or three plays: building plus
Fireball, or Log/building/Fireball. These successes motivate deeper conversion
tasks rather than simply increasing resource or time limits.

## New task design

| Task | Position | Capability / expected failure |
| --- | --- | --- |
| `01-critical-cycle-conversion` | Hog Cycle / Giant; 250 HP own tower, 900 HP target, damaged incoming Giant; 28s window | Preserve a precise pull and defensive control while arranging repeated Hog damage. A premature offensive Log can lose the tower. |
| `02-second-wave-air-race` | Giant / LavaLoon; 400 HP own tower, 1,800 HP target, unsupported attacking Giant and incoming Balloon; 30s window | Allocate air defense and offensive support through a guaranteed second Minions wave at 4s, disclosed in the instruction. |
| `03-supported-tank-conversion` | Log Bait / Giant; supported incoming tank, 700 HP own tower, 1,600 HP target; 36s window | Turn tank/support defense into a tower kill against active reinforcements. Defense or an HP lead alone fails. |
| `04-split-lane-conversion` | Hog Cycle / custom Giant–Balloon deck; both own towers 600 HP, 900 HP target; 32s window | Defend air and ground in opposite lanes, then preserve enough tempo for a Hog connection. |

The custom opponent deck contains eight distinct legal cards, including both
starting threat cards. Exact unit HP, coordinates, hands and draw queues are in
each task's configuration and live observation. Instructions disclose measured
spell crown damage so the task does not depend on remembering a historical
balance patch.

Engine, player seat, triple elixir, opponent settings, action cadence, resource
limits, and `coordinates-v1` protocol are held fixed. The state changes several
levers to create each problem; differences between tasks do not isolate the
causal effect of one lever. Planner retains its privileged view of both hands
and elixir. A privileged private reference proves solvability, not model strength.

## Reproduction and release gates

```bash
uv run python -m cr_arena.build_v7 --explore --jobs 4
uv run python -m cr_arena.build_v7 --calibrate --build --jobs 4
uv run --with pytest python -m pytest -q tests/test_royalebench_v7.py tests/test_coordinate_task.py
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-v7 --jobs 4
```

The builder checks pinned dependency versions and refuses stale configuration,
runtime or reference hashes. References must independently replay twice with full
reward and a crown before the overtime deadline. Each task must fail seven
controls: wait, cheap spell rush, cheap bridge rush, empty, malformed, wrong-type,
and partial action logs. Reference scripts remain outside the agent environment.
Container checks use the protected `cr` interface, restart the referee, and verify
in a fresh container without networking, including replay frame hashes and capture.

All four references win with zero rejected actions and deterministic replay. All
28 local negative controls score zero. All four protected references pass
[container verification](../runs/royalebench-v7/docker/validation.json), including
restart, complete capture and matching replay hashes. The focused Linux suite
passes 56 tests. The split-lane container check needed one retry after a Windows
Docker bind-mount error; no task bytes changed. All four reference replays are
available through the dashboard's **View resolution** button.

Published release: **`royalebench/royalebench-v7@1`**, tagged `v7`, digest
`sha256:8cc4ceee579bdb878039229758ca2aea57660509c5a5ccec439d44bf8f9fe3b3`.
[Publication evidence](../runs/royalebench-v7/publication.json) matches every local
task digest against the hosted revision. [Checks](../runs/royalebench-v7/checks.json)
and [reference calibration](../runs/royalebench-v7/validation.json) pin the details.

Local calibration, container validation, publication and frontier calibration are
separate gates. No v7 model score is inferred from v6 or from the reference policy.

After validation, publish a separate immutable revision, pilot one task on Modal,
inspect the trajectory, then run the small full cohort with identical harness
settings. Record every attempted task and any revisions. These tasks are informed
by model results and must be reported as development calibration, not held-out
generalization.

## Frontier pilot

The first Opus 5.5 / `claude_code-v1.0.0` pilot on v7@1 used Modal, concurrency 1,
no sampling overrides and only `03-supported-tank-conversion`:
`62553e61-afff-4f15-a3bb-61d3124f39d3`. It completed with **reward 0, integrity 1,
and zero rejected actions**. Opus preserved all its starting tower HP but spent
46 elixir and left the enemy tower at 883 HP after all 18 decisions. It used its
first Rocket on defending support troops and failed to convert its surviving
units into enough tower damage. This is a reviewed gameplay loss, not a broken
interface or grader error.

[Raw results](../runs/royalebench-v7/opus-pilot-results.json) and
[reviewed trajectory with artifact checksums](../runs/royalebench-v7/opus-pilot-traces.json)
record the attempt. A single task is not an aggregate difficulty estimate.

## First full Opus calibration

Opus 5.5 scored **0/4 (0%)** on immutable v7@1 in run
`5cfa7c26-442c-4d23-8405-67c2ca263c32`, using `claude_code-v1.0.0`, Modal,
concurrency 4, one attempt per task, and no sampling overrides. Every attempt
completed with integrity 1. Three had zero rejected actions; the tank task had
one rejected river placement. Its separate zero-rejection pilot also failed.
The harness reported $1.4982 in model API cost for the full run.

| Task | Opus outcome | Target tower HP at finish | Reviewed failure |
| --- | --- | ---: | --- |
| Critical cycle | Window expired, 0–0 | 706 | Preserved all own HP but Hog pushes were intercepted. |
| Second-wave air race | Window expired, 0–0 | 75 | Spent Fireball defensively and failed to arrange the remaining damage before the deadline. |
| Supported tank | Window expired, 0–0 | 688 | Poor Rocket placement and one rejected Knight play delayed conversion. |
| Split lanes | Lost a tower at 31.95s | 72 | Stabilized the opening, but Tombstone diverted the follow-up Hog and an enemy reinforcement wave won. |

The [review](../runs/royalebench-v7/opus-review.json) uses final captured engine
states and verifier outcomes, not the model's self-assessment. The
[raw results](../runs/royalebench-v7/opus-full-results.json),
[exact settings](../runs/royalebench-v7/opus-full-metadata.json), and
[trajectories and archive checksums](../runs/royalebench-v7/opus-full-traces.json)
preserve all four attempts. Complete captures and independent replay support
classifying these as gameplay failures. Winning references prove each position
is solvable through the same protected coordinate interface.

V6's 71.4% and v7's observed 0% measure different task sets and success conditions.
The four-task result is development calibration and does not establish a stable
zero win probability or a model ranking. V7 was the dashboard default before the
[v8 merge](royalebench_v8.md); both source datasets remain separately selectable.

## First full Sol comparison

GPT-6.1 Sol scored **2/4 (50%)** on the same immutable v7@1 revision in run
`8a64cce1-a84f-48cb-ab73-b82d876abf75`, using stock `codex-v1.0.0`, Modal,
concurrency 4, one attempt per task and no sampling overrides. All four attempts
completed with integrity 1 and complete captures without capture errors.

| Task | Opus 5.5 | GPT-6.1 Sol | Reviewed Sol outcome |
| --- | ---: | ---: | --- |
| Critical cycle | 0 | 0 | Defended the opening, but Hog pushes failed; target retained 865 HP. One `NO_DEPLOY` rejection. |
| Second-wave air race | 0 | 1 | Cannon/Minions defended Balloon; offensive Fireball and Musketeer supported the Giant through both waves. Crown win at 11.1s. |
| Supported tank | 0 | 1 | Inferno/Knight defense into Princess, Barrel, Rocket and another Barrel. Crown win at 24.8s despite one `WATER` rejection. |
| Split lanes | 0 | 0 | Played Hog before stabilizing both threats; Balloon took the right tower at 4.4s. |
| **Total** | **0/4** | **2/4** | All eight attempts have reward-independent replay integrity 1. |

The [Sol review](../runs/royalebench-v7/sol-review.json),
[raw results](../runs/royalebench-v7/sol-full-results.json),
[exact settings](../runs/royalebench-v7/sol-full-metadata.json), and
[trajectories with archive checksums](../runs/royalebench-v7/sol-full-traces.json)
preserve every attempt. Stock Codex reports token usage with a null cost; cost is
unknown, not zero. Its raw event format is reviewed directly because the existing
normalized `model_calls` table does not cover this harness format.

This small comparison shows that the new cohort has successful frontier-model
solutions as well as failures. It compares each model with its native harness;
it does not isolate model weights. Both this cohort and v6 were used for task
development, and four single attempts cannot establish a stable model ranking.
