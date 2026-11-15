# RoyaleBench v9

RoyaleBench v9 extends **all 18 tasks from `royalebench/royalebench-v8@1`** with
three unchanged Tactics defenses, for **21 tasks**. Published as
**`royalebench/royalebench-v9@1`**, tagged `v9`, digest
`sha256:e9e4396c2792964e4246eeb1002a6f4d8b2f72ba0b697be6c807f967be87ecc2`.

Open the [live v9 benchmark](http://localhost:8000/evals/benchmarks/royalebench-v9).
Every task's **View resolution** opens its validated reference gameplay.
All 21 dialogs have been tested in the browser for playback, seeking to the end,
and board flipping, with no JavaScript page errors. The live API returns the
expected final replay hash for every task.

## Sources and scoring

| Source | Immutable dataset digest | Included |
|---|---|---:|
| `royalebench/royalebench-v8@1` | `sha256:e5807bda20b03468993ef75b0eeb4f881f7e70fe0a674be977888d5502f979b2` | All 18 tasks |
| `royalebench/royalebench-tactics@6` | `sha256:5d9869332560e7ee325d975c6fca3340f75c69bb43f43a2f83f49775de424c37` | The three tasks below |

| Added task | Objective |
|---|---|
| `05-hog-body-block` | Defend a 1-HP tower against a full-health Hog using at most three elixir, with zero additional crown-tower damage over 16 seconds. |
| `06-mini-pekka-kite` | Exactly one Skeletons play, at most one elixir, all towers alive and zero additional tower damage over 16 seconds. |
| `07-balloon-fireball` | Exactly one Fireball, all towers alive and at most 240 total additional tower damage over 16 seconds. The threatened tower has 241 HP; the Balloon's death bomb counts. |

The Hog is the exact package from the requested
[Opus run `f186e6ff-11df-4612-be6a-205298ba1b8a`](http://localhost:8000/evals/jobs/f186e6ff-11df-4612-be6a-205298ba1b8a),
which used Tactics `@5`. Its content digest is
`sha256:d349207ed4074ba42409a7a4ca3a6e8d367dea3bd6d9ec470755f13224a559ed`;
the builder checks that the `@5` and `@6` Hog packages are identical.
See [the Tactics guide](tactics.md) and [the two clip tasks](tactics_clips.md)
for calibrated references, negative controls and source model traces.

All task IDs, files, instructions, starting states, resources, reference
solutions, runtime and grading retain their published source bytes. The score
is the **mean binary objective reward over all 21 equally weighted tasks**.
Twelve require terminal match wins and nine use other objectives. Report it as
objective success rather than an all-task match-win rate. V8 contributes 18/21
of the score and the three added defenses contribute 3/21. The full v9 model
runs are recorded below.

## Full v9 model runs

Twelve distinct models each completed one full run against the published
`royalebench/royalebench-v9@1` dataset, with concurrency 21. Valkyrie returned
all 21 graded task results for every run; every replay passed integrity checks,
and no run reported task errors. Agents completed 218 of the 252 task attempts;
the other 34 unfinished tasks received zero objective reward and remain in the
score denominator. Across 252 model-task attempts, 91 met the binary objective
(**36.1%**). These are single attempts, and the runs used
Claude Code, Codex, and mini-SWE-agent, so the table compares model-and-harness
setups rather than isolating model effects.

| Model | Harness | Objective successes | Match wins |
|---|---|---:|---:|
| Claude Opus 5.5 | Claude Code | 14/21 (66.7%) | 10/21 |
| Claude Fable 5.2 | Claude Code | 13/21 (61.9%) | 8/21 |
| GPT-6.1 Sol | Codex | 12/21 (57.1%) | 7/21 |
| Claude Fable 5.1 | Claude Code | 11/21 (52.4%) | 8/21 |
| GPT-6 Astra | Codex | 10/21 (47.6%) | 6/21 |
| Claude Sonnet 5.5 | Claude Code | 7/21 (33.3%) | 5/21 |
| GPT-6 Luna | Codex | 7/21 (33.3%) | 5/21 |
| Claude Haiku 5.5 | Claude Code | 4/21 (19.0%) | 3/21 |
| Inkling 2 Small | mini-SWE-agent | 4/21 (19.0%) | 3/21 |
| Kimi K3.1 Pro | mini-SWE-agent | 4/21 (19.0%) | 6/21 |
| Qwen 3.8 2.4T A95B | mini-SWE-agent | 3/21 (14.3%) | 2/21 |
| DeepSeek V4.1 Flash | mini-SWE-agent | 2/21 (9.5%) | 2/21 |

“Match wins” is the verifier's match-win metric. It is separate from objective
success, since an agent can win the game but miss a task's damage, spell, or
resource constraint. For example, Kimi recorded six match wins but four
objective successes. The exact run IDs, per-task reward matrix, result-file
checksums, stopped duplicate run, and representative accepted placements are
in the [downloaded model results](../runs/royalebench-v9/model-results.json).

Four tasks received no objective successes across this cohort:
`02-reserve-counter-a`, `04-critical-cycle-and-connect`, `05-hog-body-block`,
and `07-balloon-fireball`. `03-spell-placement` and `10-protect-the-lead` each
passed 11 of 12 attempts.

Representative records show narrow, verifiable failures as well as a success.
Opus used its three-elixir allowance on the Hog defense, but its towers took
635 additional damage. On Balloon Fireball, one legal Fireball led to 241
damage against a 240 limit. GPT-6.1 Sol used Cannon, Minions, Fireball and
Musketeer to win `02-second-wave-air-race` 1–0 in 11.1 seconds. Each record
passed replay integrity; the action placements and run IDs are in the results
file. Valkyrie can provide full agent output using
`valkyrie run output RUN_ID TASK_ID/agent_output.tar.gz`.

## Difficulty calibrated from observed pass rates

The dashboard difficulty labels use a **November 15, 2026, 11:47 a.m. PST**
snapshot of the [v9 task ranking](http://127.0.0.1:5173/evals/benchmarks/royalebench-v9):
**12 finished runs and 12 attempts per task**, excluding infrastructure errors.
Each attempt has equal weight across the models, harnesses and revisions in
those runs. These are empirical labels for this sample, updated explicitly
when recalibrating; they do not change automatically as runs finish.

Use **easy for pass rates >=70%**, **medium for >=30% and <70%**, and
**hard for <30%**. This yields **2 easy, 8 medium and 11 hard tasks**.

| Task | Passed / attempts | Pass rate | Difficulty |
|---|---:|---:|---|
| `02-reserve-counter-a` | 0/12 | 0.0% | hard |
| `04-critical-cycle-and-connect` | 0/12 | 0.0% | hard |
| `05-hog-body-block` | 0/12 | 0.0% | hard |
| `07-balloon-fireball` | 0/12 | 0.0% | hard |
| `02-second-wave-air-race` | 1/12 | 8.3% | hard |
| `03-tower-race-b` | 1/12 | 8.3% | hard |
| `01-critical-cycle-conversion` | 2/12 | 16.7% | hard |
| `04-split-lane-conversion` | 2/12 | 16.7% | hard |
| `03-supported-tank-conversion` | 3/12 | 25.0% | hard |
| `05-successive-threats-mirror` | 3/12 | 25.0% | hard |
| `08-cycle-to-lethal-plus` | 3/12 | 25.0% | hard |
| `06-unequal-threats` | 4/12 | 33.3% | medium |
| `01-cycle-and-connect` | 6/12 | 50.0% | medium |
| `02-sustained-tower-race` | 6/12 | 50.0% | medium |
| `06-mini-pekka-kite` | 6/12 | 50.0% | medium |
| `01-timed-spell-a` | 8/12 | 66.7% | medium |
| `03-bait-damage-sequence` | 8/12 | 66.7% | medium |
| `07-counterpush` | 8/12 | 66.7% | medium |
| `09-tower-race-defend` | 8/12 | 66.7% | medium |
| `03-spell-placement` | 11/12 | 91.7% | easy |
| `10-protect-the-lead` | 11/12 | 91.7% | easy |

The exact counts, source endpoint, timestamp and thresholds are recorded in
[`runs/royalebench-v9/difficulty.json`](../runs/royalebench-v9/difficulty.json).
The `[task_difficulties]` table in
[`benchmark.toml`](../benchmarks/royalebench-v9/benchmark.toml) supplies the
labels for the benchmark, task and job pages. The v9 builder preserves this
benchmark-level metadata. Published task files, task digests and reference
resolution evidence retain their original bytes; the `task.toml` files inside
the frozen packages still contain their historical difficulty estimates.

## Build and prepare resolutions

```sh
uv run python -m cr_arena.build_v9
uv run python -m cr_arena.validate_v9 --jobs 3
uv run --with pytest python -m pytest -q \
  tests/test_royalebench_v9.py tests/test_royalebench_v8.py \
  tests/test_royalebench_v7.py tests/test_royalebench_v6.py \
  tests/test_api_task_resolutions.py
valkyrie dataset push royalebench/royalebench-v9 ./benchmarks/royalebench-v9 --tag v9
```

The builder downloads the immutable hosted sources and checks every package
digest before copying. It refuses duplicate task IDs, source drift, unexpected
output tasks and changed existing packages. It does not regenerate tasks from
the current workspace runtime or change the source datasets.

Resolution preparation reuses v8's passed Docker evidence only when the task
digest, complete config, packaged protocol, starting setup, seed and protected
reference commands match. It independently replays every recorded engine frame
before copying that evidence. Missing or mismatched evidence triggers fresh
Docker validation using the task's own installed environment.

The three additions receive fresh protected `cr` execution, file-isolation,
server-restart and no-network verifier checks, with complete capture and exact
321-frame parity. Empty, malformed and wrong-type submissions score zero. V9
therefore has **21/21 passing reference resolutions** and **63 zero-reward
invalid-input controls**: 54 inherited from byte-identical v8 tasks and nine
fresh controls for the additions. Use `--fresh` to repeat all 21 Docker checks.

The selected regression suite passes **41 tests and 21 API subtests**. It checks
the exact source union, original grading, task isolation, stale-evidence
rejection, and every resolution endpoint without starting a model run.

Two frozen referee protocols coexist in the dataset. Each replay is matched
against its task's config and protocol hashes. In addition to the mixed-runtime
manifest, preparation exports `docker-runtime-<hash>/validation.json` and the
matching replay files for each runtime. This supports the existing dashboard
process as well as newer mixed-runtime viewers. No weaker evidence checks or
unvalidated fallback replays are introduced.

## Evidence and live dashboard

Evidence lives under [`runs/royalebench-v9`](../runs/royalebench-v9):

- [`merge.json`](../runs/royalebench-v9/merge.json): exact source packages and provenance.
- [`docker/validation.json`](../runs/royalebench-v9/docker/validation.json): reference passes, replay checks, invalid-input controls and inherited evidence.
- [`publication.json`](../runs/royalebench-v9/publication.json): immutable hosted revision and all 21 matching task digests.
- [`resolution-check.json`](../runs/royalebench-v9/resolution-check.json): locally available resolutions for every task.
- [`api-resolution-check.json`](../runs/royalebench-v9/api-resolution-check.json): all 21 live endpoints return their expected final state hash.
- [`browser-resolution-check.json`](../runs/royalebench-v9/browser-resolution-check.json): all 21 dialogs play, seek and flip successfully.
- [`checks.json`](../runs/royalebench-v9/checks.json): combined release and dashboard checks.

The live server used for the release check on port 8000 served a separate local checkout. Its new
`benchmarks/royalebench-v9/` directory and runtime-specific resolution artifacts
were installed there with matching task hashes and tested through that running
server. On another checkout, run the build and validation commands there before
opening its dashboard. New jobs default to v9 through `evals.toml`, and the v9
benchmark page's **Run this benchmark** action selects it explicitly.

To repeat this comparison, start new full runs against
`royalebench/royalebench-v9@1` with `--provider modal`. The cohort contains one
attempt per model; repeated runs would be needed to estimate run-to-run variation.
