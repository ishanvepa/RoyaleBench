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
of the score and the three added defenses contribute 3/21. No source scores are
presented as a new full v9 model run.

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

The live server on port 8000 serves a separate local checkout. Its new
`benchmarks/royalebench-v9/` directory and runtime-specific resolution artifacts
were installed there with matching task hashes and tested through that running
server. On another checkout, run the build and validation commands there before
opening its dashboard. The existing dashboard default remains configurable;
the v9 benchmark page's **Run this benchmark** action selects v9 explicitly.

To compare models, start new full runs against `royalebench/royalebench-v9@1`
with `--provider modal`. Existing v8 and Tactics pilots remain source evidence.
