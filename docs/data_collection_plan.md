# Standardizing benchmark data collection

Status: implementation design for future local arena and Harbor/Valkyrie matches. The shared recorder, collector, archives and table exports are implemented; see [data collection](data_collection.md) for commands and current limitations. Existing runs stay in their current format; no backfill is planned. Chart/dashboard presentation and campaign-wide uncertainty analysis remain separate from collection.

## Goal

Every attempted match should leave a durable, versioned bundle describing its setup, what each player saw and did, what the simulator did, what it cost, and how it was graded. Preserve raw evidence so later analyses can be added without another model run.

| Analysis | Evidence to retain |
| --- | --- |
| Performance and uncertainty | Scheduled task grid and repetitions, every attempt and result, seed, seat, decks, opponent, budget, and failure category. |
| Performance versus cost | Recorded API charges, token/cache/reasoning usage where available, estimate provenance, and coverage. Compute charges stay separate. |
| Speed and activity | Observation and command times, provider request times, retries, interruptions, and simulation versus wall time. |
| Gameplay style | Legal alternatives, structured actions and placements, applied/refused deployments, spending, voluntary/forced waits, and both players' state. |
| Match trajectories | Tower HP/crowns, elixir, units, deployments, and available engine events, including intervals without model decisions. |
| Case studies | Exact observations, available explanations, tool calls/results, authoritative actions, and replay frames joined to the same decision. |
| Reproduction | Original instructions/configuration, exact software/dataset/scoring versions, raw artifacts, hashes, and completeness reports. |

These support the leaderboard, efficiency, behavior, timeline, and example analyses in Vals AI's [Poker Agent](https://www.vals.ai/benchmarks/poker_agent), [CUA-bench](https://www.vals.ai/benchmarks/cua_bench), and [KSP](https://www.vals.ai/benchmarks/time_horizon_index) writeups. Their scores and interfaces differ from ours.

## Starting point

- [`cr_arena/match.py`](../cr_arena/match.py) records local observations, responses, moves, errors, latency, usage, and optional full replays. Its database callback also records structured elixir and tower HP, already plotted by the local web app.
- [`cr_arena/royale_task.py`](../cr_arena/royale_task.py) records accepted actions with decision/tick/label and timing. Invalid requests are absent; re-observing resets the timing baseline. The verifier emits outcomes and attempts replay generation.
- [`rb_evals/results.py`](../rb_evals/results.py) imports a subset of usage from agent output and analyzes finished runs. It does not collect a complete referee/verifier archive or normalize gameplay telemetry.
- The checked-in six-match Sonnet bundle contains 294 accepted decisions, transcripts, and $15.92 reported API cost, but no downloaded verifier replay/report files. Local and hosted formats differ.

## Shared data contract

Implement a versioned Python schema, JSON Schema, and representative fixtures. JSON/JSONL is the durable format; SQLite and CSV tables are rebuildable views. Specify units: integer simulation ticks, coordinates with frame/subtile scale, integer resource units where provided, seconds, and USD.

### Identity and manifest

Records carry schema version, stable ID, source, and applicable join keys: run, task, attempt, match, seat, decision, observation, command, and model-call IDs. One model call may support several commands; use an explicit link table with confidence/provenance for inferred transcript associations.

Retries create new attempts linked to predecessors. Resuming a persisted match retains match/decision identity and adds a process segment. Re-importing identical artifacts produces no duplicate rows.

The manifest records:

- Planned task grid, repetitions, lifecycle/status, original and resumed execution segments, comparison cohort, and inclusion/retry policy.
- Requested/resolved model IDs, provider and harness versions, supplied and reported effective settings, effort, token limits, sampling, tools, and context/memory policy. Unreported settings remain unknown.
- Dataset revision/digest; task, config, instruction, and rubric hashes; repository commit plus dirty patch/content hashes; lockfile hash; installed engine/library versions; image digest.
- Deck card lists, seed and seat mapping, opponent implementation/config/seed/information access, arena/rules/card data, decision interval, command delay, game/agent limits, sandbox resources, and concurrency.
- UTC start/end times, artifact inventory, collection status, and archive location. Capture allowlisted configuration without credentials or secret values.

### Normalized records

| File | Required content |
| --- | --- |
| `matches.jsonl` | Configuration and lifecycle; termination reason/tick; final HP/crowns; original reward, rubric and tiebreak reason; grading integrity and telemetry completeness. Later regrades are separate records. |
| `observations.jsonl` | Seat/decision/observation IDs, state tick/hash, exact delivered text, structured legal moves and ordering, generation/delivery times, raw transcript reference. |
| `commands.jsonl` | Every observe/action request, requested index, validation/error, resolved card/type/cost/slot/target/lane/coordinates, command/application tick, result, and action source. Include both players. |
| `states.jsonl` | Initial and pre/post decision states: phase, elixir/rate, hand/cycle, individual tower HP/max HP/crowns, and units with stable ID/team/card/position/HP/status/target where exposed. Full replay covers intervening ticks. |
| `events.jsonl` | Available engine events, accepted/refused deployments, resource changes, tower destruction, phase changes, waits, termination, and server lifecycle; sequence number and source tick. |
| `model_calls.jsonl` | Provider request/message ID, times, status/stop reason, usage/cache/reasoning fields, recorded cost or estimate basis, exposed retries/errors, and raw message/tool references. |
| `artifacts.jsonl` | Role/path/origin, size, SHA-256, capture status, parser version, and captured/reconstructed provenance. |

Keep privileged state and opponent details in referee-owned files inaccessible to the player. Analyst state is separate from the exact observation received by the model; capture must not widen the agent's information access.

### Timing, usage, and missingness

- Preserve UTC timestamps for joins, monotonic durations for measurement, simulation ticks for game time, and process/clock segment IDs. Never subtract monotonic clocks from different processes/hosts.
- Start decision duration at the first observation delivered for that decision. Re-reading adds an observation event without resetting the clock. Command receipt and action application are separate events. Label server-side delivery approximations explicitly.
- Separate decision duration, provider call time, retry/backoff, environment/tool work, setup, queueing, and verification. Record downtime/pause intervals where available.
- Missing data is null plus a reason/source/capability flag, never an invented zero. Distinguish captured, reconstructed, inferred, partial, and unavailable data.
- Deduplicate streamed messages by stable request/message IDs before summing usage. Preserve provider definitions: cached input may be inclusive or separate; reasoning may already be included in output. Reconcile constituent calls against harness totals rather than adding both.
- Separate grading integrity, collection completeness, provider failures, and archive failures. Missing analytics must not silently alter rewards or remove matches from score denominators.

## Storage and collection

Maintain three layers: immutable raw artifacts, normalized records with source references, and versioned derived metrics. Collection runs independently of the browser and dashboard cache.

```text
runs/analysis/<run_id>/
  manifest.json
  raw/<task_id>/<attempt_id>/
  normalized/
  derived/<analysis_version>/
  collection_report.json
```

Retain original downloaded archives and inventory their contents. Compress full traces/transcripts; use atomic writes, append-only events, checksums, and resumable imports. Retain replay headers and initial states with frames/events. Do not silently truncate oversized evidence.

Archive all statuses and attempts, including failures, cancellations, partial matches, resumes, and retries. Download paginated logs completely; UI preview limits must not constrain exports. Discover actual artifact paths and verify current Valkyrie/Harbor interfaces when implementing collection and task packaging.

Mirror full bundles to a configured durable archive outside the disposable cache and test a restore. Keep compact manifests/reports/selected examples in Git. Initial retention policy: raw benchmark evidence for the project lifetime, deduplicated by checksum.

## Implementation sequence

### 1. Define schemas and identity

- [ ] Add a shared telemetry module, schema/data dictionary, migration policy, and local/hosted fixtures.
- [ ] Define IDs, units, lifecycle, capabilities, missingness, and source links.
- [ ] Generate run manifests and comparison-cohort definitions before execution starts.

**Acceptance:** fixtures validate, joins are unambiguous, and manifests describe failed as well as successful attempts.

### 2. Build durable artifact collection

- [ ] Add an offline `rb_evals` collector for run/task/attempt metadata, raw results/errors, complete agent output, carried referee artifacts, and verifier outputs, including replays/reports.
- [ ] Track each expected/downloaded/verified/unavailable artifact instead of treating the agent-output `.done` marker as archive completion. Transient failures stay retryable.
- [ ] Collect new local matches into the same archive contract, retaining original configs, logs, results, and replays.
- [ ] Reconstruct any derived gameplay for new runs only with their recorded task/dependency versions. Check final outcomes and decision/tick/move sequences and mark reconstructed fields.

**Acceptance:** a new-run fixture archives all declared artifacts and reproduces its recorded decisions, outcome, and available API cost. Re-import changes nothing. Missing artifacts have explicit reasons. Local matches use the same schema.

### 3. Complete trusted gameplay capture

- [ ] Record every request, including repeated observations, malformed/invalid actions, refused deployments, disconnects, and restarts. Keep the authoritative accepted-action replay log separate from diagnostic events.
- [ ] Capture both players' structured moves, forced waits, and verifier-added waits after termination. Preserve the original termination tick separately from the simulated continuation.
- [ ] Implement stable decision timing/state hashes and share serialization between local matches and hosted verification.
- [ ] Generate full traces, snapshots, and events during trusted replay; keep online recording lightweight and measure overhead. Explicitly report replay-generation failures.
- [ ] Capture or exactly reconstruct regeneration, spending, and overflow at engine-tick resolution. Decision snapshots alone cannot establish exact elixir waste. Preserve available damage events; unsupported causal attribution remains unavailable.
- [ ] Regenerate task bundles through `cr_arena/build_tasks.py`, following [task design](task_design.md). Changed images/verifiers require a new dataset revision; historical results retain theirs.

**Acceptance:** equivalent local/hosted command sequences produce identical gameplay records/outcomes; invalid requests and re-observations are retained; tracing changes neither game behavior nor information access.

### 4. Normalize usage and automate archival

- [ ] Add adapters for local SDK/CLI players and hosted harnesses actually used, declaring supported timing/reasoning/usage/retry fields and preserving full raw output.
- [ ] Normalize counts/cost without duplicate streaming usage; retain resolved model IDs, harness versions, settings, and cost precision/provenance.
- [ ] Preserve exposed failed calls/retries and unknown hidden attempts. Separate recorded API charges, estimates, and compute billing, each with coverage.
- [ ] Collect after terminal task/run states, including failures/stops; reconcile after resume/retry. Provide an explicit offline collect/rebuild command independent of dashboard visits.
- [ ] Verify durable archive transfer and restore before marking archival complete.

**Acceptance:** adapter fixtures reconcile with harness totals; absent usage differs from free calls; downloads resume and imports are idempotent; archives survive dashboard-cache deletion.

### 5. Export analysis tables and figure inputs

- [ ] Build per-match/player/decision/call tables with metric version, cohort filters, numerators/denominators, missingness, and artifact links.
- [ ] Derive wins/crowns/damage by seed, seat, deck, opponent, and termination; expose model failures separately from infrastructure errors under an explicit inclusion policy.
- [ ] Derive cost/match, usage, timing distributions, actions per wall/game minute, voluntary wait rate, card/lane/placement frequencies, time at full elixir, and exact overflow where supported.
- [ ] Export HP/elixir/crown timelines and synchronized observation/action/replay references. Keep interpretations such as "bad defense" as reviewed annotations separate from measurements.
- [ ] Compare a declared matched task grid with equal task weighting and all scheduled repetitions; distinguish pilots and retries. Report sample sizes and uncertainty accounting for seed/seat pairing. Decisions are not independent match samples.
- [ ] First figures: win rate with uncertainty versus API cost; HP/elixir timelines; decision-time/activity plots; card/placement behavior; two annotated replay examples. Dashboard views should consume the same tables.

**Acceptance:** tables and figure inputs rebuild from archived bundles alone, reconcile with original rewards/usage, and cannot silently pool different revisions or cohorts.

### 6. Validate before scaling

- [ ] Exercise both seats, ordinary play, voluntary/forced waits, invalid actions, re-observation, deployment refusal, timeout, crash/resume, empty/partial/tampered logs, and replay-generation failure.
- [ ] Check clocks within segments, stable IDs, state/action joins, units/coordinates, resource accounting, grade parity, checksums, and collector retries.
- [ ] Test missing provider fields, duplicate streaming usage, cache/reasoning accounting, and partial costs with recorded fixtures.
- [ ] Run existing referee/backend tests and focused telemetry/collector tests; run web checks if API/UI integration changes.
- [ ] Validate a local full-match archive and one small frontier-model Valkyrie pilot on the new revision. Inspect the trace/restored replay, measure recording/verification overhead, and record capture gaps.

**Release gate:** required identity/configuration/outcome/command/observation/trace artifacts are complete and restorable; provider-specific gaps are declared; available usage reconciles; grades match; hidden telemetry stays private. Incomplete runs remain visible with original scores and gap reports. Fix collection before expanding comparison runs.

## Priority and deliverables

Complete stages 1–4 and stage-6 pilot checks before the next scaled evaluation. Stage 5 grows once raw evidence is durable. A complete, restorable archive from one new local match is the first useful milestone.

Deliver a shared schema/data dictionary, collectors/adapters, archived new-run bundles, machine-readable collection reports, reproducible metric exports, and validation evidence. Update [match tasks](match_tasks.md), [dashboard documentation](evals_dashboard.md), the [README](../README.md), and the documentation index as implementation lands.
