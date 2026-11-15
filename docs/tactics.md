# RoyaleBench Tactics

An extension dataset for four strategic capabilities: timing a spell, reserving a counter,
evaluating a tower race, and accepting a tower loss to win. It is built separately from
`royalebench-v1`; existing published scenarios and results keep their original meaning.

## Scenarios

All positions use the pinned RoyaleGym 0.1.28 / RoyaleSim 0.1.48 engine and the same three-ply
Planner configuration, observation/menu interface, protected referee, telemetry and separate
replay verifier as [v1](royalebench_v1.md). Decisions advance up to two seconds. Planner has
privileged information and unrestricted legal placements. The model sees its ordinary player view.
Hard spending limits filter the menu. These tasks measure decisions with that assistance.

The initial package contains **seven locally calibrated positions across four families**. The
right-lane counter-reservation candidate remains gated: its reference takes 1,439 damage against
the 450-damage limit. Planner's later attacks favor the left lane even when the initial setup
is reflected, so a reflected starting position is not a reflected opponent policy.

The corrected published release is **`royalebench/royalebench-tactics@2`** (tags `v2` and
`tactics-v2`). Revision `@1` is historical; use `@2` for new comparisons.

| Family | Variations | Objective | Required contrast |
| --- | --- | --- | --- |
| Timed spell | Left and right reflections of a damaged Giant followed by five Goblins | Exactly one Fireball, both princess towers survive 12 seconds, additional total tower damage at most 100 | A two-second wait then a cast succeeds; **every menu target** cast immediately or after four seconds fails |
| Reserve a counter | One validated left-lane position; right-lane candidate gated | Both princess towers survive 20 seconds, additional total tower damage at most 450, spending at most 6 | Cheap opening defense followed by Log succeeds; spending Log immediately then preparing Musketeer or using privileged menu search to recover fails |
| Tower race | Balloon at y=10.25 versus y=10.0; otherwise identical | Win within the actual remaining eight seconds of overtime, spending at most 4 | Fireball on the enemy tower wins A and loses B; opening Cannon at the left bridge loses A and wins B |
| Tower trade | Left and right reflections | Win by the end of the remaining 14 seconds of regulation, spending at most 4 | Offensive reference wins 2–1 after losing a princess tower; opening Cannon to save that tower fails the deadline |

The race's friendly Giant starts at 150 HP at y=24, rather than the full-health push in v1. The spending
limit makes committing the available resources consequential even as elixir regenerates.
Position B's defensive reference wins by the documented total-HP rule at the actual overtime
deadline. It does not destroy a tower. In the trade family, reaching overtime without a win
fails the explicitly bounded objective. The grader never requires a particular card, action
sequence, or tower sacrifice: any win within the window receives full reward.

The Barrel is a disclosed schedule constraint on Planner: the card and its three-elixir cost
are reserved until the six-second cast. All other choices are Planner's. Reflection changes
the initial attacking lane and the later Barrel target together.

## Evidence and interpretation

[`runs/tactics/validation.json`](../runs/tactics/validation.json) records reference rewards,
negative controls, replay determinism, configuration/protocol hashes and strategy contrasts.
Per-task `contrasts/` directories retain the exact action logs. The generated
[manifest](../benchmarks/royalebench-tactics/manifest.json) lists which positions passed release gates.
Locally calibrated tasks still require hosted model pilots and trace inspection before scaling.

An exhaustive audit of **immediate menu openings followed by waiting** is available with
`python -m cr_arena.audit_tactics --tasks 3`; it saves independently replayed opening logs and
results under `runs/tactics/openings/`. Race packaging requires a current, complete audit.
All winning race-A openings must use Fireball; all winning race-B openings must use Cannon.
Trade validation records the winning sacrifice and failing Cannon policy; it does not claim an
exhaustive search of every winning trade policy. `--tasks 4` additionally audits trade openings.
These audits do not exhaustively search delayed policies.

The first opening audit found a shortcut in the initial race setup at y=23: Fireball aimed at the
friendly Giant reached the enemy tower sooner and won both positions. Those exact configurations,
logs and independently verified reports are retained in
[`runs/tactics/initial-race-shortcut`](../runs/tactics/initial-race-shortcut). Moving the Giant to y=24
preserves the intended race while closing that shared opening. Published revision `@1` retains the
initial setup; use revision `@2` for comparisons.

References prove solvability. Failed alternative policies do not prove that every other policy
fails. In particular, the counter-recovery baseline uses omniscient menu-constrained Planner,
whose heuristic objective and deeper search do not optimize the scenario rubric exactly. The race
changes a quarter tile and tests a sharp timing boundary; it is not evidence of broad robustness.
The mirrored cases check spatial consistency, not independent strategic coverage. Difficulty labels
are estimates until model runs establish pass rates.

Report binary success per task and an equally weighted mean across the four family means. Report
the race pair's two results together, and distinguish reference policies, model attempts and
infrastructure failures. Repeated model attempts remain necessary despite deterministic replay.

## Build and validate

```bash
uv run python -m cr_arena.validate_tactics
uv run python -m cr_arena.audit_tactics --tasks 3
uv run python -m cr_arena.build_tactics
uv run --with pytest python -m pytest -q tests/test_tactics.py tests/test_royalebench_v1.py tests/test_royale_task.py
uv run python -m cr_arena.validate_v1_docker --benchmark benchmarks/royalebench-tactics --out runs/tactics/docker --image royalebench-tactics:validation
```

Run calibration sequentially into a given output directory. `--tasks 1 3` selects families;
`--reference-only` writes exploratory logs without release evidence. When independently calibrating
families, use separate output directories and merge only completed, current evidence.

Edit [`cr_arena/tactics.py`](../cr_arena/tactics.py) and
[`cr_arena/validate_tactics.py`](../cr_arena/validate_tactics.py), then regenerate; do not edit packaged
tasks. The calibration implementation is hashed into each scenario, and the builder requires
matching configuration/runtime hashes, passing contrasts, a deterministic winning reference,
failing wait/empty/malformed controls, and another independent replay of the protected reference.
The race family additionally requires every immediate menu opening to be audited with
the current audit implementation, with no winning action outside the family's stated audit criteria.

The shared builder preserves the project's [Harbor task structure](https://docs.harborframework.com/tasks/overview).
Each task includes private engine configuration, an agent instruction, a protected reference,
an isolated referee image and a no-network separate verifier. Task names use neutral A/B labels.
No reference actions are copied into the agent environment.

## Release validation

- All **7/7 references** receive reward 1 with replay integrity 1; completed waits, empty logs
  and malformed logs receive zero.
- All **7/7 packaged tasks** pass protected `cr` play as `player`, private-file permission checks,
  server restart, a fresh no-network verifier, carried capture completeness and every replay-frame hash.
  Evidence: [`docker/validation.json`](../runs/tactics/docker/validation.json).
- All **80 immediate race openings** are independently replayed. A has two winning Fireball targets;
  B has one winning Cannon placement. There is no shared winning immediate opening across the pair.
- **31 targeted tests pass**, covering the new tasks and existing v1/referee behavior. Additional
  release-gate and package-discovery checks pass after packaging. See
  [`checks.json`](../runs/tactics/checks.json).

## Hosted timing pilot

Run `d3b4c7ae-98f2-4268-8c86-802524a513b9` completed `01-timed-spell-a` with
`anthropic/claude-sonnet-4-6`, `claude_code-v1.0.0`, Modal and concurrency 1. It used revision `@1`;
this task's files are unchanged in `@2` (only the two race tasks were uploaded for that revision).
The separate verifier reports **reward 1, integrity 1, zero additional tower damage and four elixir spent**.
The model ran `cr`, `cr act 0`, then `cr act 1`: wait two simulated seconds, then Fireball on the Giant.

Agent time was **575.1 seconds** and model API cost **$0.83**, excluding sandbox compute. The two
server-measured decision times were 240.7 and 323.8 seconds; game time remained paused throughout.
This successful attempt validates the hosted path and is not a measured pass rate for the family
or the complete Tactics benchmark. Other families still need model pilots and difficulty calibration.

Evidence: [results](../runs/tactics/pilot-results.json), [accepted actions](../runs/tactics/pilot-actions.jsonl),
[capture validation](../runs/tactics/pilot-capture-validation.json), and [release metadata](../runs/tactics/release.json).
The full trace, telemetry and replay are collected under the run's git-ignored `runs/analysis/` folder,
with a checksum-verified durable copy at `~/.local/share/royalebench/archive/<run-id>/`.

Pilot one task per family before a wider comparison. Follow
the [Valkyrie guide](valkyrie_guide.md) and explicitly enroll CLI-started runs in
[data collection](data_collection.md). Record the resulting dataset revision, harness/model,
run IDs, costs, scores and any task defects in this document.

For example, start one task on the corrected release:

```bash
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-tactics@2 --model anthropic/claude-sonnet-4-6 \
  --provider modal -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name}" \
  --task-ids 01-timed-spell-a --concurrency 1 --label royalebench-tactics-pilot
```
