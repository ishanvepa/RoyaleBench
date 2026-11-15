# RoyaleBench Tactics on the v3 foundation

The current release is **`royalebench/royalebench-tactics@6`**, tagged `tactics-v6` and
`clip-defenses`, with **ten tasks**. It adds `06-mini-pekka-kite` (one-elixir Skeletons
defense of a 1-HP tower) and `07-balloon-fireball` (one Fireball, no direct Balloon hit,
240 death-bomb damage allowed). All eight `@5` packages remain byte-identical.
See [the new tasks and validation](tactics_clips.md). Rebuild with
`uv run python -m cr_arena.build_tactics_clips`.
Both new references pass protected-container and independent replay checks. One
Opus 5.5 attempt per new task failed through timing/placement, with integrity 1;
see the linked guide for the $0.3342354 API-cost pilot and its limits.

The preceding release **`royalebench/royalebench-tactics@5`**, tagged `tactics-v5` and
`one-hit-hog`, with **eight tasks**. Version 2.2.0 gives the Hog defense's threatened tower
**1 HP**, with exactly **three starting elixir and a three-elixir total spending limit**.
All seven `@3` task packages remain byte-identical, including their 2.0.0 metadata.
The revision digest is `sha256:c16e4c4b4a9a52c674542b67310c9880e5570ca49cf26ad08917fb1434fd5fe0`.
See [one-hit revision checks](../runs/tactics-hog-one-hit/checks.json) for the reference,
controls, 85 passing focused checks, container validation, and hosted pilot status. Historical
seven-task comparisons refer to `@3`; the single-task `@4` and `@5` pilots are separate.

The original coordinate Tactics version **2.0.0** uses the same **`coordinates-v1`** action protocol and runtime files as
**`royalebench/royalebench-v3@2`**. The current main changes were integrated through commit
`4eb50d4`. Tactics retains its own scenario set and scoring objectives; it does not change the
11 v3 foundation scenarios. Publication and validation evidence is recorded under
[`runs/tactics-coordinates`](../runs/tactics-coordinates).

The seven-task coordinate release is **`royalebench/royalebench-tactics@3`**, tagged
`v3-foundation` and `coordinates-v1`. Revisions `@1` and `@2` retain the old numbered menu.

## Player interface

- `cr` shows the text board, HP, your hand/elixir, zero-based hand slots and compact opponent plays.
- `cr play SLOT X Y` deploys at your chosen coordinates; `cr wait` advances one interval.
- Coordinates are player-relative tiles, `0 <= x < 18`, `0 <= y < 32`. There are no numbered
  targets, suggested placements or placement snapping. Only engine-subtile rounding applies.
- Well-formed illegal actions become waits and spend no elixir. Malformed syntax does not advance
  the simulation. Rejected attempts are recorded and independently replayed.
- Spending limits are checked **after play**. Affordable overspending is accepted by the engine
  and fails the objective. Explicit card restrictions and decision limits still apply.
- The clock pauses during model thinking. Decisions advance up to two simulated seconds. Empty
  or unaffordable hands still need explicit waits; the single-spell allowance resolves the rest
  of a timed-spell scenario automatically.

The engine remains RoyaleGym **0.1.28** / RoyaleSim **0.1.48**, level 11, zero command delay.
Planner is the same deterministic, three-ply, 10-second search with `workers=0`. It retains
privileged engine information, including the model's hidden hand/elixir. The model has its
ordinary player view. The network allowlist, telemetry, protected referee, CLI, replay format,
separate no-network verifier and resource limits come from the shared v3 packager. Each task's
runtime hash must equal the published v3 foundation's hash before packaging.

## Task families

The `05-hog-body-block` task adds a fifth family: **precise timing and body-block placement**.
It starts with a full-health, active Hog Rider at (2.5, 18.5), no friendly units, three starting
elixir, and level-11 crown towers. Version 2.2.0 lowers the threatened left princess tower to
**1 HP**; the king and right princess retain 4824 and 3052 HP. The objective is zero damage across all three towers
for 16 seconds while spending at most three elixir. Unlike the older tasks, decisions advance
0.5 seconds. Eight decisions are available, then the referee automatically resolves waits.
The reference uses Ice Golem and Skeletons; the verifier accepts any legal defense meeting the
same objective. The instruction does not disclose the defensive placement or timing.

This is inspired by the [reference clip and local recreation](hog_body_block.md), with a
continuation state calibrated independently through the actual coordinate referee. The Hog
starts already active, so its task timings and defensive coordinates differ from the experiment
that starts with an enemy deployment timer. The opponent has no affordable plays during the
window; its frozen Planner remains unchanged. New task configuration, reference, controls,
container verification, and publication evidence for the full-health `@4` task live in
[`runs/tactics-hog`](../runs/tactics-hog). The one-HP revision has separate evidence under
[`runs/tactics-hog-one-hit`](../runs/tactics-hog-one-hit).

The player starts with exactly three elixir and may spend only three over the entire defense.
Normal engine regeneration remains visible; spending more than three fails even if an extra
play is affordable and accepted. Thus regenerated elixir cannot provide a successful rescue.
A single Hog hit now visibly destroys the threatened tower. This makes the consequences concrete;
the original objective already required zero damage, so the HP change does not itself establish
greater model difficulty. The calibrated defense still preserves the tower at exactly 1 HP.

The intended failure is treating the defense as a card-cost calculation and missing the spatial
and timing interaction. The reference spends three and takes zero damage. Waiting, either card
alone, placing Skeletons one tile lower, and issuing both commands half a second earlier all
fail. These named controls do not prove uniqueness over arbitrary coordinates or action sequences.
Malformed, empty, wrong-schema and rejected-placement logs also fail; affordable overspending is
accepted and scores zero. The Docker reference passes the player CLI, protected-file checks,
server restart, fresh no-network grading, full capture, and independent replay of all 321 frames.

Seven previously released positions are eligible for coordinate calibration. Each needs fresh
winning references and contrast evidence; menu-era scores cannot release a coordinate task.

| Family | Positions | Objective and strategic contrast |
| --- | --- | --- |
| Timed spell | Two reflected positions | One Fireball, both princess towers survive 12 seconds, additional total damage at most 100. Wait two seconds for convergence; immediate and four-second-late casts fail the bounded searches. |
| Reserve a counter | One eligible position | Both princess towers survive 20 seconds, additional total damage at most 450, spending at most six. Defend the opening cheaply and retain Log for the disclosed six-second Barrel. Test early Log followed by Musketeer or privileged coordinate search recovery. |
| Tower race | Two revised positions | Win within the remaining eight seconds of overtime, spending at most four. A has a fragile surviving push and needs offense; B has a durable push but must first survive the closer Balloon. |
| Tower trade | Two reflected positions | Win by the end of the remaining 14 seconds of regulation, spending at most four. References accept a princess-tower loss and finish 2–1; tested Cannon defenses fail the deadline. Any valid win within the window is accepted. |

The mirrored counter candidate remains outside the runnable list until it has its own coordinate
reference and passing contrasts. Its historical failed menu reference does not establish
coordinate-mode impossibility.

### Why the race setup changed

Free placement can save a tower that the old numbered menu could not save. The coordinate race
therefore uses **50 HP** on the threatened tower in both positions. The friendly Giant has
**150 HP in A and 400 HP in B**; the enemy Balloon starts at **y=10.25 in A and y=9.5 in B**.
The other setup parameters are unchanged from the menu source.

The fragile Giant gets insufficient damage through without offensive support. Preserving its own
tower alone does not win A's HP tie-break. B's healthier Giant can finish the opposing tower if
an immediate defense prevents the earlier Balloon hit. This is a two-variable strategic contrast,
not the historical quarter-tile-only experiment. The grader accepts any successful placement:
for example, a defensive Fireball is not forbidden just because the reference uses Cannon.

## Calibration and its limits

[`cr_arena/coordinate_benchmark.py`](../cr_arena/coordinate_benchmark.py) supplies the shared runtime
hashing, instruction and task packager. Tactics adds its own scenario calibration and release gates.
Every reference is submitted through the coordinate referee, independently replayed twice, and
checked against completed waits, empty logs and malformed logs. Configurations, runtime code,
validation implementation and accepted-action logs are hashed. Cached evidence is reusable only
when those identities match, followed by another reference replay before packaging.

The new audits **do not enumerate the old menu**. They scan legal coordinates on a half-tile grid:

- Immediate and late Fireball placements for the timing tasks.
- Defensive placements in race A and offensive Fireball placements in race B.
- Cannon placements for the tower-trade defense baseline.

The fast screen advances each candidate with no future opponent deployments; it is a candidate
search, not a full Planner evaluation. The four best candidates in each sweep are then played
and independently replayed against the actual adaptive Planner. Release requires no successful
wrong-strategy screening point and no successful checked witness, alongside the winning reference.
The full grid, selected actions, reports and counts remain in the evidence directories.

These are bounded spatial and policy checks. They are **not** a proof over arbitrary subtile
positions, delayed actions or all possible action sequences. Privileged recovery search also
uses Planner's heuristic, not an exact optimizer for the task rubric. Reference solvability and
failed alternatives do not establish frontier-model difficulty or human performance.

Report each task, an equally weighted mean across family means, and Valkyrie's default flat task
mean separately. Mirrors are consistency checks rather than independent strategic families.

## Build and verify

The expanded ten-task dataset preserves all eight `@5` packages and appends the two
[clip-inspired defenses](tactics_clips.md). Rebuild and verify it with:

```bash
uv run python -m cr_arena.build_tactics_clips
uv run --with pytest python -m pytest -q tests/test_tactics_clips.py tests/test_tactics_hog.py tests/test_tactics.py
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-tactics --out runs/tactics-clips/docker --tasks 6 7 --jobs 2
```

The historical seven-task builder below requires a checkout with the original foundation
runtime and a separate `--out`. It refuses
to replace an expanded dataset. The Hog builder pins all seven source task content digests,
uses the exact frozen `@3` referee/client/viewer, and rejects local gameplay drift. It never
rebuilds the seven source tasks using the newer workspace replay viewer.

The following commands document the original seven-task release workflow. Use the expanded
builder above for the current ten-task release; the workspace's newer replay viewer is not
part of the original frozen runtime.

```bash
uv run python -m cr_arena.validate_tactics --jobs 2
uv run python -m cr_arena.build_tactics
uv run --with pytest python -m pytest -q tests/test_tactics.py tests/test_coordinate_task.py tests/test_royalebench_v3.py tests/test_royalebench_v1.py tests/test_royale_task.py
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-tactics --out runs/tactics-coordinates/docker --jobs 2
```

`--tasks 1 3` selects families for calibration. `--reuse` rechecks matching cached evidence.
Parallel calibration uses separate task directories; only the parent writes the summary.
Use separate output directories for independently launched calibration commands. The builder
checks all references before replacing the generated dataset, and gates both race members if
only one passes. It refuses to overwrite the foundation or frozen source datasets.

The immutable menu inputs and templates are pinned in
[`data/royalebench-tactics-menu-source`](../data/royalebench-tactics-menu-source). Current scenario
changes live in [`cr_arena/tactics.py`](../cr_arena/tactics.py). Edit the source and regenerate;
never patch generated task folders. The historical menu source/runtime is never mounted into
an agent image. Current player images receive only the shared v3 runtime and their private task
configuration, with no reference policies or source snapshot.

## Historical releases

- **Tactics `@5` (version 2.2.0):** same eight task IDs. The Hog defense starts its threatened
  tower at 1 HP, retains three starting elixir and the three-elixir total budget, and discloses
  that any Hog hit loses the tower and fails the task. A legal engine play beyond the total
  budget still fails grading; normal regeneration does not increase the allowance. The old
  seven packages and the shared runtime remain unchanged. Tags `tactics-v5` and `one-hit-hog`.
- **Tactics `@4` (version 2.1.0):** eight tasks. Adds `05-hog-body-block` and retains the
  seven `@3` packages unchanged. Tags `tactics-v4` and `hog-body-block`; new task content digest
  `sha256:b1301894b8a73544c242ef89080826765ddfb8294906e36f616f3654ed213d08`.
- **Tactics `@1` / `@2`:** numbered-move interface, version 1.0.0. The original race shortcut and
  correction remain documented under [`runs/tactics`](../runs/tactics). Its 80-opening audit
  applies only to the old menu, not free-coordinate placement.
- **Historical Sonnet pilot:** run `d3b4c7ae-98f2-4268-8c86-802524a513b9` passed menu task
  `01-timed-spell-a` on `@1`, with zero damage, integrity 1, two decisions, 575.1 seconds of agent
  time and $0.83 of API usage. This is not a coordinate Tactics result. Full artifacts remain
  checksum-verified in the durable archive.

New model runs must pin the new immutable coordinate dataset revision, use Modal, and be enrolled
in [evidence collection](data_collection.md). See the [v3 guide](royalebench_v3.md) and
[Valkyrie workflow](valkyrie_guide.md) for harness/model/secret selection. Start with a single task,
inspect the verifier and replay, and record model results separately from reference calibration.

## Coordinate release checks

- **76 focused tests pass**, covering Tactics, coordinate deployment/rejection, spending rules,
  v3 compatibility, original v1 behavior and the referee. Additional shared-packager checks confirm
  that v3's existing instruction bytes and Tactics' generated instruction bytes remain stable.
- **7/7 references** pass local calibration, repeated independent verification and negative controls.
- **7/7 packaged tasks** pass isolated player CLI play, protected-file checks, server restart,
  fresh no-network verification, carried capture completeness and every replay-frame hash.
- The spatial screens cover **17,535 legal points** across tasks and delays, with **44 selected
  spatial witnesses** replayed against Planner, in addition to the named strategy contrasts.

The complete screening assumptions and limits above apply to these counts. They are not model
scores or an exhaustive proof over continuous placements.

## Hosted coordinate pilot

Run **`88a361db-f330-4823-b202-b07f6fee8e27`** completed `03-tower-race-a` on the published
coordinate release `@3`, using Sonnet 4.6, `claude_code-v1.0.0`, Modal and concurrency 1.
The model inspected the board and submitted **`cr play 1 3.5 25.5`**. It won the continuation
with **reward 1, integrity 1, zero rejected placements and zero additional tower damage**.
Agent time was **40.2 seconds**; model API cost was **$0.09**, excluding sandbox compute.

This is one successful attempt on one position. It verifies the hosted coordinate path, not a
full-family pass rate or a model ranking. Historical menu results remain separate.

Evidence: [pilot summary](../runs/tactics-coordinates/model-pilot.json),
[service results](../runs/tactics-coordinates/model-pilot-results.json),
[accepted coordinate log](../runs/tactics-coordinates/model-pilot-actions.jsonl), and
[capture validation](../runs/tactics-coordinates/model-pilot-capture.json). Full raw traces,
replays and telemetry are in the enrolled run's git-ignored `runs/analysis/` directory and its
checksum-verified durable archive at `~/.local/share/royalebench/archive/<run-id>/`.

## Opus coordinate run

Run **`72a98358-fdd7-41d4-9b24-9eb7f7917237`** completed all seven tasks on
`royalebench/royalebench-tactics@3`, using Opus 5.5 (`anthropic/claude-opus-5-5`),
`claude_code-v1.0.0`, Modal and concurrency 7. The default flat task score was
**5/7 (71.4%)**; the equally weighted mean of the four family scores was **62.5%**.

| Family | Passed |
| --- | --- |
| Timed spell placement | 2/2 |
| Reserve a counter | 0/1 |
| Tower race | 1/2 |
| Deliberate tower sacrifice | 2/2 |

The reserve-counter attempt cast Log at elapsed six seconds, before the Barrel goblins landed,
and took 2,027 damage against a limit of 450. The race-B attempt used the offensive Fireball
that worked in A; its own tower fell first. The winning references for these positions use
Log at eight seconds and an immediate defensive Cannon, respectively.

All tasks had completion and integrity 1, with zero rejected actions and no service-reported
errors. The run took 199.5 seconds from start to finish. Harness-reported model usage totaled
**$0.80**, excluding sandbox compute. Full capture contains seven matches with no reported gaps;
archive checksum verification passed. These are single attempts per task, not repeated-run
success-rate estimates.

See the [per-task scores, outcomes and costs](../runs/tactics-coordinates/opus55-summary.json).
Raw model traces and replays remain in the ignored local and durable archive paths recorded there.

## Hog defense pilot on @4

Run **`ee02edf8-63d6-4608-9bdc-98b2ee6dd187`** completed the new task on
`royalebench/royalebench-tactics@4`, using Opus 5.5 (`anthropic/claude-opus-5-5`),
`claude_code-v1.0.0`, Modal, and concurrency 1. It scored **0**, with completion and integrity
both 1, exactly three elixir spent, and no rejected actions. The Hog dealt three hits,
**951 crown-tower damage**. Agent time was 60.0 seconds; harness-reported API cost was **$0.21**,
excluding sandbox compute.

The model chose the intended Ice Golem / Skeletons combination but deployed the Ice Golem
immediately at (3.5, 12.0), followed by Skeletons at elapsed 1.0 seconds at (3.5, 13.0). The Hog
slipped around the block. The passing reference waits 0.5 seconds, places Ice Golem outside
the lane at (1.5, 11.5), then places Skeletons at elapsed 1.0 seconds at (3.5, 13.5). The model
acknowledged its failed defense in its final response. This is a placement/timing failure,
with no evidence of an instruction, command-rejection, or verifier defect in this attempt.

The accepted action log independently reproduces the service rewards, and all 321 carried
replay frames verify. Capture is complete (one match, nine observations, eleven model calls,
no gaps), and durable archive checksum verification passes. This is one attempt on one task;
it does not establish a model success rate or an eight-task `@4` benchmark score.

Evidence: [pilot summary](../runs/tactics-hog/model-pilot.json),
[service results](../runs/tactics-hog/model-pilot-results.json),
[accepted action log](../runs/tactics-hog/model-pilot-actions.jsonl), and
[all revision checks](../runs/tactics-hog/checks.json). Generated local replays are
`runs/tactics-hog/replays/reference.html` and `runs/tactics-hog/replays/opus55-pilot.html`.

## One-HP Hog defense pilot on @5

Run **`f186e6ff-11df-4612-be6a-205298ba1b8a`** completed the revised task on
`royalebench/royalebench-tactics@5` with Opus 5.5, `claude_code-v1.0.0`, Modal, and concurrency 1.
It scored **0**: the Hog destroyed the one-HP left princess tower, then dealt additional damage
to the king, for 635 total damage. Completion and integrity were 1, with eight decisions, exactly
three elixir spent, and no rejected actions. Agent time was 40.4 seconds; API cost was **$0.19**,
excluding sandbox compute.

The model played Ice Golem immediately at (3.5, 13.0), waited, then played Skeletons at elapsed
1.0 seconds at (3.5, 12.5). It correctly identified that cycling to Cannon would exceed the budget
but failed to form the body-block. Its final response acknowledged losing the tower. This is
a placement/timing failure in one attempt, not evidence that the task is impossible or a model
success-rate estimate. The reference still succeeds with three elixir and leaves the tower at 1 HP.

The independent action-log replay matches the service rewards; all 321 replay frames verify.
Capture is complete with no gaps, and archive checksum verification passes. Evidence:
[pilot summary](../runs/tactics-hog-one-hit/model-pilot.json),
[service results](../runs/tactics-hog-one-hit/model-pilot-results.json),
[accepted actions](../runs/tactics-hog-one-hit/model-pilot-actions.jsonl), and
[revision checks](../runs/tactics-hog-one-hit/checks.json). The same 85 focused checks pass;
seven local socket tests required a rerun outside the restricted sandbox. The container check
independently verifies the player CLI, restart, isolated no-network grading, and reference capture.
