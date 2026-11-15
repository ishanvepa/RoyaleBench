# RoyaleBench v6

RoyaleBench v6 merges **all 10 tasks from `royalebench/royalebench-v5@1`** with
**all four tasks from `royalebench/royalebench-win@2`**. It contains 14 tasks and is
the former dashboard default; [v8](royalebench_v8.md) now merges it with v7 and is the default. Published release:
**`royalebench/royalebench-v6@1`**, tagged `v6`.
No task IDs collide, and every task file retains its source bytes, with matching
published task content digests. Instructions, starting states,
runtime, opponent, resource limits, references, and grading retain their original
meaning. Source task titles and internal version metadata are intentionally retained.

## Sources and scoring

| Source | Immutable dataset digest | Tasks |
| --- | --- | ---: |
| `royalebench/royalebench-v5@1` | `sha256:456914c198d4738959064c5e409944ac320fbe70b7404d6efb1304005a4d08cd` | 10 |
| `royalebench/royalebench-win@2` | `sha256:c1e42376f700f7cafdce9b34b359c32d81fc223eb7632cded5483937451a10a9` | 4 |

The v5 revision was resolved from the linked dashboard's latest version when the
merge was requested. Future source revisions do not silently change this dataset.
[The merge manifest](../benchmarks/royalebench-v6/manifest.json) records each source,
task digest, downloaded archive checksum, objective, and packaged protocol hash.

| Task ID | Source | Retained objective type |
| --- | --- | --- |
| 01-timed-spell-a | v5@1 | Exactly one spell and defensive survival/damage constraints |
| 02-reserve-counter-a | v5@1 | Defense |
| 03-spell-placement | v5@1 | Exactly one spell and defensive survival/damage constraints |
| 03-tower-race-b | v5@1 | Match win |
| 05-successive-threats-mirror | v5@1 | Defense |
| 06-unequal-threats | v5@1 | Defense |
| 07-counterpush | v5@1 | Match win |
| 08-cycle-to-lethal-plus | v5@1 | Match win |
| 09-tower-race-defend | v5@1 | Match win |
| 10-protect-the-lead | v5@1 | Protect the lead |
| 01-cycle-and-connect | win@2 | Match win |
| 02-sustained-tower-race | win@2 | Match win |
| 03-bait-damage-sequence | win@2 | Match win |
| 04-critical-cycle-and-connect | win@2 | Match win |

The score is the **mean binary source-task reward across all 14 tasks**, equally
weighted per task. Thus v5 supplies 10/14 of the score and win@2 supplies 4/14.
Eight tasks require terminal match wins; six retain the other v5 objectives.
The four added win@2 tasks still require a completed, independently replayed match
win. **The overall v6 score is an objective success rate, not an all-task game win rate.**
For an exclusively win-only score, run the separate
[RoyaleBench Win](royalebench_win.md) dataset.

## Build, verify, and publish

```bash
uv run python -m cr_arena.build_v6
uv run --with pytest python -m pytest -q tests/test_royalebench_v6.py
uv run python -m cr_arena.validate_v6_docker --jobs 4
valkyrie dataset push royalebench/royalebench-v6 ./benchmarks/royalebench-v6 --tag v6
```

The builder uses authenticated Valkyrie access to resolve the two pinned revisions,
downloads source archives into the ignored `runs/recent/v6-sources` cache, and
checks their content against service digests before copying. It refuses duplicate
IDs, changed source versions, unexpected tasks, or changed existing output tasks.
It never rebuilds the source tasks from the current working-tree runtime.

The sources contain two packaged protocol versions. The v6 container validator
groups tasks by their complete installed environment and builds a separate image
for each group. Every reference runs through the protected `cr` interface, referee
restart, and fresh verifier container without networking. It verifies capture and
replay frame hashes, then requires zero rewards for empty, malformed, and wrong-type
action logs. It checks task digests again after validation.

[Merge evidence](../runs/royalebench-v6/merge.json),
[container evidence](../runs/royalebench-v6/docker/validation.json), and
[release checks](../runs/royalebench-v6/checks.json) record the completed checks.
All **14/14** protected references pass, all **42** invalid-submission controls
score zero, and the focused merge/configuration suite passes **27 tests**.
Publication details and the immutable v6 revision are recorded in
[publication.json](../runs/royalebench-v6/publication.json). Use that revision with
`--provider modal` for new runs; source model scores are not v6 model results.

No new v6 model score is claimed by this merge. The
[win@2 pilots](royalebench_win.md#validation-and-model-results) remain results on
their original four-task cohort. Compare future v6 runs on the same immutable
revision and harness, and retain per-task rewards to distinguish gameplay wins
from the other objectives.
