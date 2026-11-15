# RoyaleBench v1

This is the historical menu interface. [RoyaleBench v3](royalebench_v3.md) is the default release
and uses coordinates across the same 11 released positions. These v1 task snapshots remain frozen.

RoyaleBench v1 is a versioned set of strategic continuations based on the twelve proposed tasks. Every opponent is **Planner**. Each task starts from an exact mid-match engine setup and uses the existing `cr` interface, an isolated referee, and replay grading in a fresh container. The dataset lives at [`benchmarks/royalebench-v1`](../benchmarks/royalebench-v1); its exact title in the evals dashboard is **RoyaleBench v1**.

Reference calibration establishes solvability; measured model runs are needed to establish difficulty. The three-task Valkyrie/Modal harness pilot is recorded separately in the [coordinate guide](coordinate_harness.md#model-comparison). The [manifest](../benchmarks/royalebench-v1/manifest.json) records which tasks are runnable and why other variants are gated. Do not describe gated candidates as evaluated tasks.

The [coordinate-action pilot](coordinate_harness.md) is a separate dataset using three matching
positions with direct placement commands. Existing packaged v1 tasks retain the numbered menu
and their calibrated runtime snapshots.

The separate [Tactics extension](tactics.md) now uses the v3 coordinate foundation for timed spells,
counter reservation, tower races and tower trades. Its historical menu releases remain available;
the coordinate release does not revise published v1 positions or reuse v1 model scores.

Validation on November 14, 2026, after updating to three-ply Planner: **11/11 runnable references score 1 with integrity 1** through the actual `cr` socket, restart, and fresh-container grader with networking disabled. All eleven replay traces reproduce every frame hash. The Windows scenario/referee run passes 18 cases (socket test excluded); the Linux referee/Planner run passes 15 cases, including the socket test. Those test sets overlap. Additional Planner/registry, public-play and web checks are recorded in [checks.json](../runs/royalebench-v1/checks.json). Evidence: [local calibration](../runs/royalebench-v1/validation.json), [container checks](../runs/royalebench-v1/docker/validation.json), [trace hashes](../runs/royalebench-v1/docker/trace_validation.json), and [placement/race contrasts](../runs/royalebench-v1/contrasts.json).

## Tasks and grading

Difficulty labels below come from the proposal; they remain estimates until model runs. The CSV rates are CrownScribe archetype matchup metadata, **not simulator win probabilities, task success rates, or scoring weights**. Card names use the engine's spelling: `Archer`, `IceGolemite`, `IceSpirits`, `HogRider`, and `Xbow`.

| # | Capability | Player / Planner deck | CSV rate | Exact objective |
| --- | --- | --- | --- | --- |
| 1 | Immediate lethal; easy control | Giant / X-Bow | 62.6% | Win after the first submitted decision; then the referee automatically resolves up to 6 seconds. Enemy target tower has 158 HP; Fireball crown damage is measured as 159. |
| 2 | Efficient defensive placement; easy | Giant / Hog 2.6 | 55.9% | Both princess towers survive 12 seconds, additional total crown-tower damage at most 400, spending at most 4. |
| 3 | Compare spell placements; easy | X-Bow / LavaLoon | 58.7% | Exactly one Fireball, both princess towers survive 12 seconds, additional crown-tower damage at most 150. Waiting is allowed; other cards are unavailable. |
| 4 | Separate tank and support; medium | Log Bait / Giant | 52.8% | Both princess towers survive 20 seconds, spending at most 9. |
| 5 | Budget across successive threats; medium | Hog 2.6 / Log Bait | 52.0% | Both princess towers survive 20 seconds, additional crown-tower damage at most 450, spending at most 8. A reserved Goblin Barrel is cast at elapsed 6 seconds. |
| 6 | Prioritize unequal threats; medium | Giant / P.E.K.K.A | 51.4% | Both princess towers survive 20 seconds, spending at most 8 overall and at most 4 in the healthier right lane. |
| 7 | Convert defense into offense; medium–hard | Giant / P.E.K.K.A | 51.4% | Win the continuation, at most 35 seconds regulation plus 120 overtime. |
| 8 | Cycle while defending; hard | Hog 2.6 / Giant | 44.0% | Win within the remaining 18 seconds of overtime. Fireball is exactly two plays away in a disclosed draw queue. |
| 9a/b | Evaluate a tower race; hard | Giant / LavaLoon | 46.8% | Win within 30 seconds of overtime in each of two positions. The Balloon differs by 0.25 tile. |
| 10 | Protect a lead; hard | X-Bow / Giant | 37.3% | Retain a strict crown lead at the end of the remaining 12 seconds of regulation. |
| 11a/b | Track opponent cycle; very hard | Log Bait / X-Bow | 49.4% | **Gated:** require winning references plus evidence that different commitments improve the two histories' outcomes. |
| 12 | Plan a comeback; very hard | X-Bow / Golem | 32.7% | **Gated:** include only after a reference policy wins the continuation. |

All rewards are binary. A missing, malformed, tampered, or incomplete action log scores zero. An explicit completed sequence of waits is a negative control and fails every runnable task. Spending limits filter the agent's menu; they apply even as elixir regenerates. A defense may lose HP on the healthier tower while preserving both towers. Only damage after the starting state counts toward a damage limit.

Valkyrie's default aggregate is the mean over runnable variants. Also report per-family means so task 9 does not receive double weight, and show task 1 separately as a control. Never substitute the matchup CSV rates for measured benchmark results.

## Reproducible protocol

- RoyaleGym **0.1.28**, RoyaleSim **0.1.48**, standard level 11 cards/towers, no evolutions. The Docker base image is pinned by digest, and the Python runtime dependencies are pinned in each generated Dockerfile.
- Fixed blue seat, seed `100 + family number`, no shuffle, exact ordered hand/draw queue, HP, spawns, match phase, and initial elixir in each private `environment/task.json` and verifier `tests/task.json`. Percentages are rounded to integer HP. In runnable tasks, initial opponent elixir is zero except task 5's reserved three elixir; the model observes its usual player view.
- The model and Planner choose from the same frozen state every **40 ticks / 2 seconds**, with zero command delay. There is no wall-clock search deadline or worker scheduling noise. Forced waits do not consume agent decisions.
- Planner includes the upstream three-ply search and pending-card fix from commit `6cc1875`. Its settings are explicit: `horizon_s=10`, `top_k=4`, `margin=40`, `two_ply=true`, `three_ply=true`, `answer_k=3`, `prefilter=true`, `elixir_hp=150`, `workers=0`. The third ply answers the three worst opponent replies. A single process removes worker scheduling from replay verification; live play's eight workers accelerate the same search. It has arbitrary legal placements and privileged access to the true engine state. The model has the numbered legal menu and ordinary hidden information.
- Task 5 reserves the opponent's Goblin Barrel and its cost until the disclosed six-second cast. Planner chooses all other opponent decisions. This is an explicit schedule constraint, not an extra free spell or a different opponent.
- Scenario setup uses the engine's public `MatchSetup` / `SpawnSpec` APIs. Traces preserve this exact initial setup, so replays do not incorrectly start from an empty match.
- Task images retain their validated replay assets when unrelated live-play rendering changes land. The complete packaged source snapshot is recorded in `runs/royalebench-v1/checks.json`; the protocol hash pins the engine adapter and Planner independently.
- Overtime ties at the actual match deadline use the existing total tower-HP rule, then seed parity. Ending a defense scoring window does not manufacture a match win.

Task 3's damaged Minions, Mega Minion, Balloon HP and spacing were calibrated by comparing legal Fireball targets. The reference takes 107 damage; aiming at the Balloon takes 214, and an unrelated tower takes 1094. Task 9's commitment opening (Fireball at the enemy target tower) wins its first variant and loses the closer-Balloon variant. Defending can also win the commitment variant; the pair demonstrates sensitivity to unsafe commitment, not proof that offense is the unique winning action.

The cycle-history pair gives the opponent four initial elixir and avoids a wait-to-timeout win, but the same Barrel opening wins both histories: at the fixed decision cadence, Planner does not use the available Log in time. The pair therefore has not demonstrated a meaningful action reversal. The comeback reference loses at regulation. These failures of validation keep their configurations under `candidates/`, with no `task.toml` for Valkyrie to discover. Gating is deliberate: a proposed hard scenario is not evidence of a valid hard task.

## Build and validate

From the repository root:

```bash
uv run python -m cr_arena.validate_v1
uv run python -m cr_arena.validate_v1 --contrasts --tasks 3 9
uv run python -m cr_arena.build_v1
uv run --with pytest python -m pytest -q tests/test_royalebench_v1.py tests/test_royale_task.py
uv run python -m cr_arena.validate_v1_docker
```

On Windows, use `.venv/Scripts/python.exe` if dependencies are already installed. The socket server runs inside Linux Docker; local setup, reference play and replay verification work on Windows too. The existing socket-server unit test requires Linux. Docker validation exercises the actual socket protocol.

Calibration records winning reference logs, repeated verifier output, explicit waits, empty and malformed logs, exact config hashes, a hash of the runtime protocol sources, dependencies and provenance under [`runs/royalebench-v1`](../runs/royalebench-v1). Reference policies are handcrafted for bounded defenses; longer continuations can use privileged Planner search restricted to the same menu as the model. They prove solvability, not human or model ability.

For an instrumentation update with unchanged scenario configurations, existing winning references can
be revalidated without rerunning the reference search:

```bash
uv run python -m cr_arena.validate_v1 --tasks 1 2 3 4 5 6 7 8 9 10 --reuse-reference
uv run python -m cr_arena.build_v1
uv run python -m cr_arena.validate_v1_docker
```

Revalidation checks the prior configuration and reference-log hashes, requires the same reference
outcome, repeats grading, and reruns the negative controls. It does not bypass release gates.
The protocol hash includes telemetry code. Packaged configurations additionally record the instruction
hash, task identity, capture schema, rubric, and resource limits. The scenario specification version
remains `1.0.0`; the immutable Valkyrie dataset revision identifies the capture release.

The builder refuses to release a task if its reference fails, its negative controls pass, its reference log changes, or its config/protocol evidence is stale. It also replays an immutable copy of each reference before packaging exactly those bytes. Run calibration sequentially against a given output directory. Source configurations for all twelve families remain in [`cr_arena/royalebench_v1.py`](../cr_arena/royalebench_v1.py). Edit the source and regenerate; never patch a generated task in place. A published change requires a new immutable dataset revision.

Docker validation builds one common runtime, supplies each task's private configuration, runs its protected reference through `cr` as `player`, checks that the player cannot read private state, telemetry or replays or become root, restarts the server and confirms the completed state persists, then grades the carried log in a fresh container with networking disabled. It checks every carried replay frame against both the pre-restart trace and independent verifier trace, then re-simulates both traces to verify their hashes. It saves scores, action logs, reports and visual replays under `runs/royalebench-v1/docker/` (override with `--out`). Subset runs merge only evidence matching the current protocol hash, task configuration hash, and common image ID.

## Publish and pilot on Valkyrie

The instrumented release is **`royalebench/royalebench-v1@2`**, tagged `v2` and `telemetry-v1`.
It preserves all eleven scenario configurations, instructions, reference actions, Planner settings and
objectives from `@1`. It adds private observations, action/state/event telemetry, instruction/resource
provenance, corrected decision timing, and full carried replay checkpoints, including partial play.
Revision `@1` remains available with its original capture limitations. Revision **`@3`**
(tag `modal-qwen`) preserves `@2` task content and adds the exact Modal Qwen endpoint
hostname to the agent network allowlist. Use `@3` for new runs, including comparisons
with Qwen; see [Qwen on Modal](qwen_modal.md) for its harness and credentials.

For this release, all eleven winning references reproduce their prior outcomes; repeated grading and
fresh negative controls pass. All eleven pass player isolation, server restart and fresh-container
grading with reward and integrity 1. Carried and verifier traces reproduce every frame hash, with exact
per-tick resource accounting. The full suite passes 277 tests (9 skipped, 40 subtests). Hosted capture
validation is recorded in [the data collection report](data_collection_validation.json).

Hosted pilot `93a3a885-6ef0-46c0-96bc-23172b3b32ce` completed `10-protect-the-lead` on `@2`
with Claude Haiku 5.5, Claude Code v1.0.0 and Modal: reward 1, integrity 1, six individual decisions.
The downloaded artifacts contain seven observations, a 241-frame replay, private state/action/event
records, and model usage. Collection reports no gaps; replay hashes and exact resource accounting
verify. A restored durable archive regenerates all 19 analysis tables identically using its saved
collector code. Model API usage cost $0.00960; compute charges are unavailable. This one-task capture
pilot does not estimate aggregate benchmark performance.

The dataset is automatically discoverable in the existing evals dashboard. Before publishing, review `manifest.json`, run the tests and Docker validation, and follow the [Valkyrie guide](valkyrie_guide.md) for authentication and the existing organization. The package follows the current [Harbor task layout](https://docs.harborframework.com/tasks/overview), [separate verifier](https://docs.harborframework.com/tasks/separate-verifier) and [network policy configuration](https://docs.harborframework.com/tasks/configuration).

The next generated release uses the compact `Opponent plays: Card@(x,y), ...` observation line
described in the [simulator guide](simulator_foundation.md). This changes observation text and its
protocol hash; revalidate the existing references and publish a new immutable revision before model
comparisons. Existing published revisions and their recorded validation results keep their original
observation format.

```bash
valkyrie dataset push royalebench/royalebench-v1 ./benchmarks/royalebench-v1 --tag v2
```

Publishing changes creates a new immutable revision. The example below pins the instrumented `@2` release:

```bash
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-v1@2 \
  --model anthropic/claude-sonnet-4-6 --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}" \
  --slice 0:1 --concurrency 1 --label royalebench-v1-lethal-pilot --connect
```

Then run one defense task and inspect both the model trace and replay before scaling. Record dataset revision, model, harness, Modal resources, sampling settings, run IDs, costs, rewards and failure classifications. Harness setup has public access to install its tools; during actual play, only model API hosts are allowlisted, and verification requests no network. The task needs no external game server. Actual phase-policy enforcement still needs a Modal pilot. Keep full model decisions separate from oracle scripts; `fast_decision_frac` is only a review diagnostic, not an automatic score penalty.

The README's required opening overview remains human-authored; this implementation adds only documentation links beneath it.

Revision `@4` (tag `modal-inkling`) adds the exact Inkling Modal endpoint hostname
to all eleven agent allowlists. It retains the Qwen hostname from `@3`; scenario
inputs, scoring, resource limits and verifier isolation are unchanged. Dataset
discovery/configuration/LF checks passed. Inkling accepts the existing Qwen
credential with stock mini-SWE-agent and model `openai/inkling-2-small`; see
[Inkling setup](inkling_modal.md) for the live pilot evidence and configuration.

Revision `@5` (tag `modal-deepseek`) adds the exact DeepSeek Modal endpoint
hostname to all eleven agent allowlists, retaining prior hosts. Scenario inputs,
scoring, resources and verifier isolation are unchanged from `@4`. Dataset
discovery/configuration/LF checks passed; see [DeepSeek setup](deepseek_modal.md)
for the stock mini-SWE-agent configuration and pilot evidence.

Revision `@6` (tag `modal-kimi`) adds the exact Kimi Modal endpoint hostname
to all eleven agent allowlists, retaining existing model hosts. Instructions,
scenario inputs, scoring, resources and verifier isolation are unchanged from
`@5`. Dataset discovery/configuration/LF checks passed; see [Kimi setup](kimi_modal.md)
for the stock mini-SWE-agent configuration and pilot evidence.
