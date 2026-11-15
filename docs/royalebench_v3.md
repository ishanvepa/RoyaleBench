# RoyaleBench v3

**RoyaleBench v3** is the default benchmark: all **11 released continuation scenarios** use
direct coordinate actions against Planner. The source is
[`benchmarks/royalebench-v3`](../benchmarks/royalebench-v3), benchmark version `3.0.0`.
The stable action protocol is named `coordinates-v1`; that protocol version is separate from
the benchmark release and Valkyrie's immutable dataset revision (`@1`, `@2`, ...).
The published revision is **`royalebench/royalebench-v3@1`**, tagged `v3`.

V3 promotes the coordinate harness tested in the [historical three-task pilot](coordinate_harness.md)
to the full released task set. It preserves the exact v1 decks, seeds, tower HP, starting hands,
unit positions, match phases, objectives, cadence and Planner settings. Frozen v1 and pilot
task files remain unchanged. The three configurations from gated families 11 and 12 remain
under `candidates/` without `task.toml`; they are not runnable or scored.

## Default player flow

```mermaid
flowchart LR
    A[Text board and numbered hand slots] --> B[Model chooses slot and coordinates]
    B --> C[cr play SLOT X Y or cr wait]
    C --> D[Protected referee checks the submitted placement]
    D --> E[Apply both players' actions]
    E --> F[Advance up to two simulated seconds]
    F --> A
```

Run `cr` to observe; use `cr play SLOT X Y` to deploy hand slot **0–3**, or `cr wait`.
Coordinates are own-frame tiles: `0 <= x < 18`, `0 <= y < 32`. There are no prepared target
choices, placement suggestions, or automatic placement snapping. The game pauses during
thinking. A well-formed illegal deployment consumes its interval as a wait; malformed command
syntax does not advance time. Card availability and explicit decision-count restrictions apply.
Spending/lane budgets are scored after play, so an accepted but excessive expenditure can fail
the objective. The [coordinate protocol guide](coordinate_harness.md#player-flow) specifies
logging, rejection, timing and replay in full.

Planner continues to generate and search its own coordinate candidates. It sees full engine
state, including hidden hand/elixir information; the model receives ordinary player information.
Both choose from the same frozen state, with a two-second decision cadence and zero command delay.
The model is instructed to submit its own decisions, without scripts or loops choosing/submitting plays.

## Tasks and scores

The [original task table](royalebench_v1.md#tasks-and-grading) gives unchanged objectives and
matchups. The runnable tasks cover lethal, efficient defense, spell placement, tank/support,
successive threats, unequal threats, counterpush, cycling, two tower races, and protecting a lead.

Rewards are binary and require completed play and replay integrity. Report the mean over the
11 variants, per-family means (tower race has two variants), and the lethal control separately.
CSV archetype rates and privileged reference successes are not model benchmark scores.

V3 references are translated from the actual protected v1 action traces, including the exact
coordinates stored there. The builder inserts explicit waits where the historical menu forced
them, verifies each coordinate reference twice, and requires wait/empty/malformed controls to
score zero before packaging. Each task's evidence pins configuration, protocol and reference-log
hashes. Matching cached calibration is reused only after another reference replay; stale evidence
is recalibrated. Isolated calibration processes may work on disjoint task directories, and only
the parent writes the dataset manifest.

See [`manifest.json`](../benchmarks/royalebench-v3/manifest.json) and
[`runs/royalebench-v3`](../runs/royalebench-v3) for actual release/validation evidence.
All **11/11 references** pass local calibration and actual CLI/socket validation in Docker,
including player isolation, restart persistence, and fresh-container grading with no network.
Every replay reproduces its frame hashes. The related checks pass **185 Python tests plus
13 subtests**, **208 web tests**, API type generation, typechecking, lint, and a production build.
Web checks used Node **20.20.2**; validation commands and provenance are recorded in
[`checks.json`](../runs/royalebench-v3/checks.json).
The published revision also passed a hosted lethal control with Sonnet 4.6 through
`claude_code-v1.0.0` on Modal: run `5b0afc35-e137-4143-b288-249634c0f181`, reward **1**,
integrity **1**, and zero rejected deployments. Results are retained in
[`model-lethal-results.json`](../runs/royalebench-v3/model-lethal-results.json). This is one
control task, not an eleven-task model score.
Full-cohort frontier-model scores are not established by reference validation. Historical pilot
scores (coordinates 3/3, menu 2/3 in one Sonnet 4.6 attempt each) remain attributed to their original
dataset revisions; they are not renamed v3 results.

## Build, validate and run

```bash
uv run python -m cr_arena.build_v3 --jobs 2
uv run --with pytest python -m pytest -q tests/test_royalebench_v3.py tests/test_coordinate_task.py tests/test_royale_task.py
uv run python -m cr_arena.validate_v3_docker --jobs 2
```

`--jobs` only parallelizes independent local validation processes/containers. Each Planner still
uses `workers=0`, with no wall-clock search cutoff. Docker validation exercises player isolation,
the actual CLI, restart persistence, and fresh-container grading with networking disabled.
Use `--fresh` with the builder to rerun all negative controls, or `--tasks 1 3` with the Docker
validator for a diagnostic subset. A subset does not prove that the entire dataset passed.

Publish through the existing [Valkyrie/Modal workflow](valkyrie_guide.md):

```bash
valkyrie dataset push royalebench/royalebench-v3 ./benchmarks/royalebench-v3 --tag v3
```

The initial immutable published revision is `@1`; use a new revision after future task changes:

```bash
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-v3@1 \
  --model anthropic/claude-sonnet-4-6 --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}" \
  --task-ids 01-immediate-lethal --concurrency 1 --label royalebench-v3-lethal-pilot
```

Start small, inspect the model's decisions and replay, then expand. Record exact revisions,
model/harness settings, resources, run IDs, costs and failure classifications. New runs should
be enrolled in [evidence collection](data_collection.md).

The dashboard's `default_dataset = "royalebench-v3"` setting selects v3 for a new job once it is
published. Explicit benchmark links and manual selections take precedence. If the configured
default is unavailable/unpublished, the form falls back to an available published benchmark.
Historical datasets and existing runs retain their original interfaces and scores.
