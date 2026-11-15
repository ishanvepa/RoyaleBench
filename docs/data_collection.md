# Benchmark data collection

New local matches and instrumented Valkyrie tasks record the same versioned evidence format. Existing runs are left as they are. The [implementation plan](data_collection_plan.md) describes the design; [the JSON Schema](telemetry.schema.json) specifies the record envelope.

RoyaleBench v1 continuation tasks are instrumented in **`royalebench/royalebench-v1@2`**
(tags `v2` and `telemetry-v1`). This revision carries full replay checkpoints and standardized telemetry
for all eleven runnable tasks. Revision `@1` retains its original action-log-only game artifacts;
new runs must select `@2` or its current tag to receive the capture. Scenario configurations,
instructions, reference actions, opponent and scoring are unchanged. Rebuilding future snapshots
requires the validation gates in the [v1 guide](royalebench_v1.md).

The default [v3 benchmark](royalebench_v3.md) and historical [coordinate pilot](coordinate_harness.md) record raw coordinate attempts,
acceptance/rejection metadata and application ticks. Rejected deployments consume an interval
as `rejected_action`; exports count them as error waits rather than voluntary waits.
V3 revision `@2` additionally packages the explicit task identity, instruction hash, rubric,
capture schema and resource limits used by the v1 instrumented releases. Its eleven carried
captures and replay hashes pass isolated Docker validation; a hosted Qwen smoke run has a complete,
checksum-verified archive. See the [v3 evidence](royalebench_v3.md#tasks-and-scores).

## What gets captured

| Record | Contents |
| --- | --- |
| `observations` | Exact response text, decision/seat, legal moves with costs and positions, complete analyst state, state hash, and server-side response creation time. Private analyst state is never sent to the player. |
| `commands` | Every hosted request, including invalid requests, and both players' applied actions. Records distinguish requests, forced waits, player choices, and verifier-added waits. |
| `states` | Initial, decision-boundary, and final snapshots with named player/entity fields. |
| `events` | Per-tick player/resource state, fine-unit regeneration/overflow, resolved deployments, invalid requests, restarts, termination, and exposed CLI retries. |
| `model_calls` | Native SDK requests/responses, usage and durations; hosted Claude messages deduplicated by message ID, with original stream events retained. Provider-specific unavailable fields remain null. |
| `matches` | Terminal state, outcome/error, original reward and verifier report. Partial agent play is distinguished from the verifier's wait-to-finish continuation. |

Each record has schema/version, record/match/attempt IDs, producer source, process segment, sequence, UTC and monotonic time, and a `data` payload. Normalization adds hosted run/task IDs. Decision IDs are `seat:simulation_tick`. Coordinates identify engine subtiles and the subtile scale; own-frame tile coordinates are also retained. Elixir is integer milli-units or explicit fine units with a scale, duration is seconds, and cost is USD.

Manifests preserve configuration, decks, opponent, dependency versions, source hashes, and runtime source copies. Generated tasks also carry task identity, instruction hash, rubric and resource limits. Model settings reported by the provider remain separate from requested settings; unknown image digests/effective settings are null.

The accepted-action log remains the grading authority. The verifier independently replays it, checks decision/tick/move and any recorded state hash, then emits replay files and telemetry. Valkyrie currently returns rewards but does not expose that verifier directory as a downloadable artifact. The private game server therefore checkpoints its full replay and telemetry into the carried referee directory after every response, including partial play. The collector uses verifier telemetry when supplied, otherwise the isolated referee's evidence, and keeps the grading results separately.

The game remains paused during model thinking. Re-reading an observation no longer resets its decision timer; timings before the first observation are unknown, and clocks are separated across restart segments.

## Local matches

`play_match` automatically writes an attempt bundle under `<out_dir>/analysis/<attempt_id>/`, including for failed matches. Every new attempt keeps a full replay, even when the legacy arena's replay display/pruning settings select fewer games. On completion it normalizes data, exports tables, hashes files, and copies a verified snapshot to the durable archive.

Working files remain under the match output directory. The durable destination defaults to `~/.local/share/royalebench/archive`, outside the worktree and dashboard cache. Set `ROYALEBENCH_ARCHIVE_DIR` to another filesystem or mounted storage location. The archive is a verified local copy unless that destination supplies off-machine storage.

## Valkyrie runs

Launches through the dashboard or `rb_evals.valkyrie.Valkyrie.start_run` automatically enroll the new run. The real dashboard server starts a collector thread; it continues without a browser being open. Simulated dashboard sessions do not collect real runs.

For a run started with the upstream Valkyrie CLI, explicitly enroll its new ID, then run the standalone collector while the dashboard server is closed:

```bash
uv run python -m rb_evals.archive enroll RUN_ID
uv run python -m rb_evals.archive watch
```

Only enrolled IDs are visited. There is no discovery/backfill of earlier organization runs. The watcher collects terminal task/run evidence, including failures/stops and replaced retry attempts, and retries incomplete downloads. Stop it with Ctrl-C. For a one-off collection:

```bash
uv run python -m rb_evals.archive collect RUN_ID
```

`ROYALEBENCH_ANALYSIS_DIR` controls hosted working bundles (default `runs/analysis`). Global `--root PATH` overrides it for the CLI. Original archives, extracted files, metadata snapshots, all service log pages, and artifact inventories are retained. `.collection.lock` serializes concurrent collectors. Cache deletion does not delete the durable copy.

The hosted collector currently requires Unix `fcntl`; its `collect` command cannot
run directly in Windows Python. The [Modal Qwen pilot](qwen_modal.md#validation)
preserves a checksum-verified raw download and durable copy instead; it has no
normalized analysis exports yet.

```text
<analysis_dir>/<run_id>/
  manifest.json
  raw/                 # current and previous-attempt artifacts, original archives
  normalized/          # common JSONL records and observation/action links
  derived/v1/          # CSV and JSONL analysis inputs
  collector/           # exact importer/exporter source and dependency lock
  collector_manifest.json
  artifacts.jsonl      # relative paths, sizes, SHA-256
  collection_report.json
```

## Analyze and restore

Exports include matches, players, decisions, per-tick HP/elixir/crown timelines, placement counts, decision timing, model calls, usage reconciliation, and hosted task outcomes/errors. Each table includes run/model/harness/dataset/cohort context when known. Original transcripts and full simulator replays support later case studies. Analysis is per attempt; datasets and task grids are not pooled automatically.

```bash
uv run python -m rb_evals.archive export BUNDLE_PATH
uv run python -m rb_evals.archive verify BUNDLE_PATH
uv run python -m rb_evals.archive mirror BUNDLE_PATH ARCHIVE_DIRECTORY
```

`verify` exits nonzero on size/checksum failures. `mirror` verifies the source and restored copy and preserves existing snapshots. A restored bundle can regenerate the analysis tables without model calls or dashboard access; the collector source snapshot records the exact code even before a Git commit.

## Completeness and interpretation

- `collection_report.json` lists missing artifacts and parse/transfer errors. A missing trace, absent task capture, or failed replay makes capture incomplete. This never changes the original reward or hides the run.
- Resource overflow is exact only while the pinned regeneration law matches the engine on every tick. A mismatch makes the derived value unavailable. `at_cap_s` counts capped engine ticks. Voluntary waits exclude forced waits, verifier continuation and recorded error fallbacks.
- Native SDK request duration includes SDK-internal retries, whose individual attempts are unavailable. Hosted per-decision duration includes agent/tool time; hosted provider-call duration is null when not reported. All raw streams remain available for richer future adapters.
- Harness cost totals are authoritative for recorded API charges. Message usage is deduplicated and reconciled against them. Claude stream output-token counters can be partial: when they disagree with final usage, per-message output totals are null with the reported partial counters retained. Cached input and reasoning are not added twice. Missing costs are null; compute billing is separate and currently unavailable.
- Complete causal damage attribution is unavailable from the engine. Raw positions/HP/deployments support descriptive analysis, but a causal claim still needs evidence. Model-to-decision links remain unknown when the stream does not establish them; exact observation/action links are retained.
- Full working snapshots are intentionally retained. Set archive storage appropriately for large campaigns; no size-based truncation is performed. Keep raw benchmark evidence for the project lifetime.

## Validation

Recorded local, container, archive and live-pilot checks are in [the validation report](data_collection_validation.json).

```bash
uv run --with pytest python -m pytest -q tests
```

Tests cover replay parity, timing across re-observations, malformed/partial logs, exact resource accounting through overtime, usage missingness, resume IDs, interrupted downloads, idempotent imports, archive restore, and no historical run discovery. Publishing changes to task images/verifiers requires a new immutable dataset revision. Record pilots and remaining gaps before scaling model comparisons.
