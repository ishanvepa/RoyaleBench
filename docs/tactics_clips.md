# Clip-inspired Tactics defenses

Published as **`royalebench/royalebench-tactics@6`**, tagged `tactics-v6` and
`clip-defenses`, on November 15, 2026. This revision appends two tasks to the
eight unchanged packages from `@5`, including `05-hog-body-block`.
Its dataset digest is
`sha256:5d9869332560e7ee325d975c6fca3340f75c69bb43f43a2f83f49775de424c37`.

These tasks use the same frozen `coordinates-v1` referee, protected `cr` CLI,
separate offline verifier, network allowlist, resource limits, and telemetry as
the Hog task. They do not change simulator rules or the default v6 benchmark.
The Tactics revision number `@6` is distinct from the `royalebench-v6` dataset.

## Tasks and failure stories

| Task | Capability | Required outcome |
|---|---|---|
| `06-mini-pekka-kite` | Timing and inward kiting with disposable troops | Exactly one Skeletons play, at most one elixir, all crown towers alive and zero additional tower damage over 16 seconds. The threatened tower starts at 1 HP. |
| `07-balloon-fireball` | Timing and directional spell knockback | Exactly one Fireball, at most four elixir, all crown towers alive and at most 240 additional total tower damage over 16 seconds. The threatened tower starts at 241 HP. |

Both start at tick 200 (170 seconds left, x1 regeneration), seed 42, with a
full-health enemy at `(3.5, 20.5)` and no friendly troops. All cards and towers
use standard level 11 stats. The Mini P.E.K.K.A. has 1390 HP; the Balloon has
1676 HP. The former advances 0.5 seconds per decision and the latter 1 second.
The clock pauses while the agent thinks. An accepted defensive play resolves
the remaining window automatically; otherwise the agent has 12 decisions.
All other cards are explicitly unavailable. Exact decks, slots, initial HP,
elixir, and restrictions appear in each instruction. The unchanged Planner
has no affordable deployments within this 16-second window.

Expected failures are choosing a plausible card placement without accounting
for its acquisition range, deployment or projectile delay, and subsequent
tower shots. The verifier grades legal simulation outcomes, not whether the
agent copied the reference. Reading an observation does not advance time.
Malformed syntax does not advance time; well-formed illegal plays consume an
interval as a rejected wait. Incomplete and tampered logs cannot pass.

The Balloon's death bomb is included in scoring. The reference preserves the
tower at 241 HP until after the Balloon dies, then leaves **1 HP** after the
240-damage explosion. A direct Balloon attack destroys it. This reproduces the
clip's no-direct-hit interaction without treating the video's early cutoff
as evidence of zero eventual damage. Damage includes every friendly crown tower.

## Provenance and normalization

See [the extracted sources and watchable recreations](tiktok_recreations.md).
The Skeletons source uses level 11. The Balloon source shows a level-16 Balloon
and level-15 Princess Tower; these benchmark tasks deliberately normalize both
to the frozen Tactics level-11 runtime. Its Fireball level and precise original
taps are not visible. The tasks use separate, explicitly disclosed continuation
states and independently calibrated references. They are inspired by the clips,
not recovered original match saves.

Reference schedules, withheld from the agent image, are:

| Task | Reference | Failing timing or placement control |
|---|---|---|
| Mini P.E.K.K.A. | Wait six 0.5-second decisions; Skeletons at `(7.5, 13.5)` | Same tap 0.5 seconds later, or x=6.5 at the reference time |
| Balloon | Wait ten 1-second decisions; Fireball at `(3.5, 7.5)` | Same tap 1 second earlier, or x=8.5 at the reference time |

For each task the reference scores 1 and twelve controls score 0: wait,
immediate, mistimed, misplaced, rejected placement, wrong card, empty log,
malformed JSON, wrong schema, wrong type, partial log, and tampered state hash.
The reference is graded twice with identical results. These controls establish
specific contrasts, not uniqueness over arbitrary coordinates.

## Build and validate

```sh
uv run python -m cr_arena.build_tactics_clips
uv run --with pytest python -m pytest -q tests/test_tactics_clips.py tests/test_tactics_hog.py tests/test_tactics.py
uv run python -m cr_arena.validate_v1_docker \
  --benchmark benchmarks/royalebench-tactics \
  --out runs/tactics-clips/docker --tasks 6 7 --jobs 2
```

The builder pins all eight `@5` task digests and copies their bytes unchanged.
The two new tasks must use the exact frozen protocol hash
`0a08b4c4dfca848149bae22c9ec898848ae116df469984a5978a34219b8c506c`.
Historical builders refuse to remove the new tasks. No `dataset.toml` is added.
The task-specific solution, expected commands, verifier config, and reference
logs remain outside the agent-readable environment.

Both Docker references pass player CLI execution, protected-file checks,
server restart, fresh no-network verification, complete carried telemetry,
and parity of all 321 frames across the online, restarted and verifier replays.
Generation and the focused suite also test wrong-card rejection and full
death-bomb resolution. Evidence is under [`runs/tactics-clips`](../runs/tactics-clips):
`build.json`, task-specific `validation.json` and action logs, Docker validation,
and `checks.json`. All 96 selected test cases pass, including seven local-socket
tests rerun outside the filesystem sandbox and a corrected death-bomb trace
assertion. The two new Docker references each score 1.

## Hosted model pilot

Run `e9173855-84c0-457d-ab2e-d2e336afccbb` completed on Tactics `@6`, using
`anthropic/claude-opus-5-5`, `claude_code-v1.0.0`, Modal, concurrency 1, and one
attempt per new task. Both attempts completed with integrity 1 and no rejected
actions. Each hosted score and all 321 carried replay frames match independent
re-execution.

| Task | Opus reward | Recorded failure | Model API cost |
|---|---:|---|---:|
| Mini P.E.K.K.A. | 0 | Played Skeletons at 1.5 s, `(7.5, 11.5)`; lost the threatened tower, then took a King hit. Total damage 756. | $0.1219072 |
| Balloon | 0 | Cast Fireball at 8 s, `(3.4, 9.3)`; a direct Balloon attack destroyed the threatened tower. Total damage 241. | $0.2123282 |

Both are timing/placement failures under the stated interface, rather than
formatting, rejection, missing-completion, or verifier failures. The model could
read successive exact observations; it committed its one allowed card too early.
Its post-match suggestions are hypotheses, not validated alternative references.
The verified references above pass the same setup and grader. One attempt per
task demonstrates failures and validates the harness; it is not a reliable
success-rate estimate. Total model API cost was **$0.3342354**, excluding Modal.

Evidence: [pilot summary and classifications](../runs/tactics-clips/model-pilot.json),
[service results](../runs/tactics-clips/model-pilot-results.json),
[Mini P.E.K.K.A. actions](../runs/tactics-clips/06-mini-pekka-kite/model-pilot-actions.jsonl),
[Balloon actions](../runs/tactics-clips/07-balloon-fireball/model-pilot-actions.jsonl),
and [combined checks](../runs/tactics-clips/checks.json). Full raw traces and all
137 captured artifacts are checksum-verified under
`runs/analysis/e9173855-84c0-457d-ab2e-d2e336afccbb` and the local durable archive.
Capture is complete with no gaps. Generated reference and pilot replay pages
are under `runs/tactics-clips/docker/` and `runs/tactics-clips/replays/`.

Publish and run a small model pilot with the existing team Modal provider:

```sh
valkyrie dataset push royalebench/royalebench-tactics ./benchmarks/royalebench-tactics \
  --tag tactics-v6 --tag clip-defenses
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-tactics@6 --model anthropic/claude-opus-5-5 \
  --provider modal -s ANTHROPIC_API_KEY anthropic-api-key-ben \
  --task-ids 06-mini-pekka-kite,07-balloon-fireball --concurrency 1
```

Only rerun publication when task bytes change; it creates a new immutable
revision. Compare models only on the same revision. Report the equally weighted
mean of all seven family means and the flat ten-task mean separately. This
revision has one task in families 2, 5, 6 and 7 and two tasks in families 1, 3 and 4.
