# RoyaleBench Tactics on the v3 foundation

Tactics version **2.0.0** uses the same **`coordinates-v1`** action protocol and runtime files as
**`royalebench/royalebench-v3@2`**. The current main changes were integrated through commit
`4eb50d4`. Tactics retains its own scenario set and scoring objectives; it does not change the
11 v3 foundation scenarios. Publication and validation evidence is recorded under
[`runs/tactics-coordinates`](../runs/tactics-coordinates).

The published coordinate release is **`royalebench/royalebench-tactics@3`**, tagged
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
