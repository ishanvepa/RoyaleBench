# RoyaleBench v8

RoyaleBench v8 combines **all 14 tasks from `royalebench/royalebench-v6@1`**
with **all four harder tasks from `royalebench/royalebench-v7@1`**. It is the
default benchmark for new dashboard jobs. Source task IDs, instructions, starting
states, runtime, opponent, resource limits, references and grading retain their
exact published bytes. The separate v6 and v7 datasets remain available.

## Sources and scoring

| Source | Immutable dataset digest | Tasks |
| --- | --- | ---: |
| `royalebench/royalebench-v6@1` | `sha256:813f00528a075f38acf4c8af9614da226de739e6a3d67e6e95be78b290e3fdf9` | 14 |
| `royalebench/royalebench-v7@1` | `sha256:8cc4ceee579bdb878039229758ca2aea57660509c5a5ccec439d44bf8f9fe3b3` | 4 |

The score is the **mean binary source-task reward across all 18 tasks**, equally
weighted per task. V6 supplies 14/18 of the score and v7 supplies 4/18. Twelve
tasks require terminal match wins; six retain v6's other objectives. The overall
score is objective success, not an all-task match-win rate. V7's four windows
still end before the overtime tiebreak, requiring a tower kill to win.

The added tasks are `01-critical-cycle-conversion`, `02-second-wave-air-race`,
`03-supported-tank-conversion`, and `04-split-lane-conversion`. Their IDs do not
collide with v6's tasks. See the [v6 guide](royalebench_v6.md) and
[v7 design and calibration](royalebench_v7.md) for task-level explanations.
The [merge manifest](../benchmarks/royalebench-v8/manifest.json) records all 18
source task digests, archive checksums, objectives and packaged protocol hashes.

## Build, validation, and publication

```bash
uv run python -m cr_arena.build_v8
uv run --with pytest python -m pytest -q tests/test_royalebench_v8.py tests/test_royalebench_v7.py tests/test_royalebench_v6.py tests/test_evals_backend.py tests/test_api_evals.py
uv run python -m cr_arena.validate_v6_docker --benchmark benchmarks/royalebench-v8 --jobs 4
valkyrie dataset push royalebench/royalebench-v8 ./benchmarks/royalebench-v8 --tag v8
```

The builder resolves the pinned hosted revisions and downloads them into the
ignored `runs/recent/v8-sources` cache. It checks every archive against its
published task digest before copying. It refuses source drift, duplicate IDs,
unexpected output tasks and changed existing packages. It does not regenerate
source tasks from the current working-tree runtime.

The shared merge validator groups tasks by their complete installed environment,
building separate images for the two source environments. Every reference uses
the protected `cr` interface, referee restart and fresh verifier without
networking. It checks complete capture and replay frame hashes, then requires
zero reward for empty, malformed and wrong-type submissions. Each task's digest
is checked before and after validation.
If infrastructure interrupts the container run, add `--resume` to reuse complete
passing checks only when the task digest, source and installed image still match.

The dashboard's reference viewer matches the configuration and protocol hash in
each validation row, allowing both packaged runtime versions in one benchmark.
An explicit incompatible common protocol or a stale per-task protocol still
prevents playback.

[Merge evidence](../runs/royalebench-v8/merge.json),
[container evidence](../runs/royalebench-v8/docker/validation.json),
[checks](../runs/royalebench-v8/checks.json), and
[publication](../runs/royalebench-v8/publication.json) record release verification.

All **18/18** protected references pass with integrity 1, all **54** invalid-input
controls score zero, and all task packages retain their source digests. The
merge/configuration regression suite passes **114 tests and 18 subtests**; the
reference viewer suite passes **four tests**. One Windows Docker bind-path error
required a retry without task changes; eight completed checks were reused after
matching their exact package and image hashes.

Published release: **`royalebench/royalebench-v8@1`**, tagged `v8`, digest
`sha256:e5807bda20b03468993ef75b0eeb4f881f7e70fe0a674be977888d5502f979b2`.
All 18 hosted task digests match the local packages. The
[live dashboard check](../runs/royalebench-v8/dashboard-check.json) confirms the
published state, all tasks in sync, no task errors and v8 as the live default.
[All 18 reference replays](../runs/royalebench-v8/resolution-check.json) are
available through **View resolution**.

## Model results

No new v8 model score is claimed by this merge. V6's Opus 10/14 and Sol 9/14,
and v7's Opus 0/4 and Sol 2/4, remain source development runs. They are not a
single execution of the merged benchmark. Compare models with new full runs on
the same immutable v8 revision, keeping per-task results to distinguish terminal
wins from the other objectives. Use `--provider modal`.
