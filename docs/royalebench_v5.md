# RoyaleBench v5

RoyaleBench v5 is a ten-task **curated coordinate-action dataset**. It combines four
cases that Opus 5.5 failed, four cases that Sonnet 5.5 passed and Haiku 5.5 failed,
and two cases that Haiku 5.5 passed. Every task folder in
[`benchmarks/royalebench-v5`](../benchmarks/royalebench-v5) is a byte-for-byte copy
of a published source task. The task instructions, starting states, reference
solutions, referee, verifier, timeouts, and resource limits have not changed.
The common action protocol is `coordinates-v1`, with protocol SHA-256
`0a08b4c4dfca848149bae22c9ec898848ae116df469984a5978a34219b8c506c`.
The source version remains embedded in each task's own configuration for traceability;
the *dataset* version is v5.

## Selection

| Selection group | Task | Source revision | Observed reward |
| --- | --- | --- | --- |
| Opus failed | `02-reserve-counter-a` | Tactics `@3` | Opus 0 |
| Opus failed | `03-tower-race-b` | Tactics `@3` | Opus 0 |
| Opus failed | `05-successive-threats-mirror` | v4 `@2` | Opus 0 |
| Opus failed | `08-cycle-to-lethal-plus` | v4 `@2` | Opus 0 |
| Sonnet passed, Haiku failed | `01-timed-spell-a` | Tactics `@3` | Sonnet 1, Haiku 0 |
| Sonnet passed, Haiku failed | `03-spell-placement` | v3 `@2` | Sonnet 1, Haiku 0 |
| Sonnet passed, Haiku failed | `06-unequal-threats` | v3 `@2` | Sonnet 1, Haiku 0 |
| Sonnet passed, Haiku failed | `09-tower-race-defend` | v3 `@2` | Sonnet 1, Haiku 0 |
| Haiku passed | `07-counterpush` | v3 `@2` | Haiku 1, Sonnet 1 |
| Haiku passed | `10-protect-the-lead` | v3 `@2` | Haiku 1, Sonnet 1 |

The exact source revisions, model and harness names, run IDs, rewards, integrity
checks, and package hashes are recorded in
[`selection.json`](../runs/royalebench-v5/selection.json). The four Opus cases come
from runs `72a98358-fdd7-41d4-9b24-9eb7f7917237` and
`941173e3-ba01-4cb9-8374-a5dfd8e7ae88`. The Sonnet/Haiku contrasts use
**the same source revision for each paired case**. Sonnet's source runs are
`7bf87ee1-d3e7-413d-9615-1c1d36503168` and
`37a44c9f-870b-40ee-811c-ac4b862114d6`; Haiku's are
`898ab4c9-52df-40e0-9e7c-ad8a5031ed09` and
`315772c0-ae81-4214-9afa-096d253643bd`.

These are **single attempts selected using their observed outcomes**. They establish
the selection rule, not an unbiased model ranking or a repeated-run pass rate.
Report future v5 results under the v5 dataset revision and run every compared
model on the same revision, harness, and provider. Do not relabel the source-run
scores as v5 scores. The v4 mirror task uses the corrected `@2` instruction,
which names the right princess tower at `(14.5, 6.5)`.

## Interface and scoring

Each task starts from a fixed RoyaleGym 0.1.28 / RoyaleSim 0.1.48 state against
the deterministic Planner opponent. `cr` shows a text observation and numbered
hand slots; `cr play SLOT X Y` deploys a card at player-relative tile coordinates,
and `cr wait` advances one interval. The game pauses while the agent thinks.
An isolated verifier replays the recorded commands and gives binary reward 1
only when the task's stated objective, completion, and integrity checks pass.
The objective and any elixir, damage, or time limit are in that task's
`instruction.md`. The agent can use the referee through `cr` but cannot read the
protected state, reference solution, or verifier files.

## Build and run

The dataset is assembled from the checked-in task folders; there is no generator
that changes scenario behavior. To validate the complete package locally:

```bash
uv run python -m cr_arena.validate_v1_docker \
  --benchmark benchmarks/royalebench-v5 \
  --out runs/analysis/v5-validation --jobs 4
```

The validator runs all reference solutions through the player CLI, checks referee
isolation and restart persistence, then grades in a fresh no-network container and
compares replay frame hashes. The local dashboard's static task checks should also
report no problems. Publish and run with the current Valkyrie CLI:

```bash
valkyrie dataset push royalebench/royalebench-v5 ./benchmarks/royalebench-v5 --tag v5
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-v5@1 \
  --model anthropic/claude-sonnet-5-5 --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}" \
  --concurrency 4 --label royalebench-v5-sonnet55
```

Set `VALKYRIE_ANTHROPIC_SECRET` to the name of an existing Valkyrie secret, as in
the [Valkyrie guide](valkyrie_guide.md). Pin the revision returned by the publish
command if it differs from `@1`. Start with one task when testing a new harness or
model. Scores are the mean of ten binary rewards; also report each selection group
separately to show where a model succeeded or failed.

## Validation record

The ten source task folders were checked for byte identity and a common packaged
protocol. Static Harbor checks reported no problems. Docker reference and negative
control results, plus hosted publication and pilot evidence, are recorded in
[`checks.json`](../runs/royalebench-v5/checks.json).
