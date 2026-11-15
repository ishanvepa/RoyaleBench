# RoyaleBench

## Project goal

Build a Clash Royale benchmark for LLMs on Vals AI's Valkyrie framework. This is a Vals Hacks project in the **Build Your Own Eval** track (November 14–15, 2026). The benchmark should reveal meaningful ways that capable models struggle with Clash Royale tasks, rather than merely testing game trivia.

The exact task design, agent interface, and scoring method are still to be decided. Favor tasks with clear inputs, verifiable outcomes, and enough strategic depth to distinguish model performance. Keep the evaluation reproducible so that results across models are comparable.

## What to deliver

- A focused set of benchmark tasks in the [Harbor task format](https://docs.harborframework.com/tasks/overview), packaged as a dataset that can run on Valkyrie.
- A working Valkyrie run against at least one frontier model, with scores and representative traces or failure examples. Compare models when time and credits permit.
- A README that explains the benchmark, how to run it, the scoring method, and the results. The required one-paragraph overview at the top of the README must be written entirely by a human.
- A short demo video and a submission-ready repository for the hackathon.

## Benchmark principles

- Prioritize a few strong, well-checked tasks over a large collection of weak ones.
- Make each task's expected behavior and grading criteria explicit. Avoid ambiguous wins, hidden assumptions, and accidental shortcuts.
- Test whether the tasks actually challenge frontier models. Inspect rollouts and revise tasks or graders when failures come from unclear instructions or broken evaluation setup.
- Start with small runs to control cost, then expand only after the tasks and scoring work reliably.
- Record the harness, model, dataset version, run configuration, and results so another person can reproduce the comparison.

## Designing tasks

Before creating or changing any task under `benchmarks/`, read [`docs/task_design.md`](docs/task_design.md). It covers task selection, the Harbor layout used here, writing instructions and verifiers, preventing shortcuts, and the validation checklist every task must pass before it is run at scale.

## Documentation index

- Keep this index and the affected documentation up to date whenever documents are added, renamed, removed, or project behavior changes.
- [`README.md`](README.md): benchmark writeup, preliminary match results, evidence placeholders, and links to quick guides.
- [`demo/README.md`](demo/README.md): active 67-second Remotion demo, local export, media layout, and production status.
- [`demo/remotion/README.md`](demo/remotion/README.md): editable video project, official Remotion skills used, asset preparation, preview, and export commands.
- [`demo/storyboard.md`](demo/storyboard.md): timed headliner sequence and model/reference comparison.
- [`demo/script.md`](demo/script.md): timed silent-viewing captions and evidence-based editorial notes.
- [`demo/shot-list.md`](demo/shot-list.md): footage sources, capture queue, and edit checklist.
- [`demo/evidence.json`](demo/evidence.json): selected Opus v6 run metadata, task outcome, trace excerpt, and validated reference provenance.
- [`demo/production.json`](demo/production.json): current Remotion edit, capture provenance, historical first-cut media details, verification, and remaining production work.
- [`docs/simulator_foundation.md`](docs/simulator_foundation.md): RoyaleGym ecosystem, current integration, compact opponent-play observations, pinned dependencies, and benchmark validation priorities.
- [`docs/hog_body_block.md`](docs/hog_body_block.md): TikTok extraction and scripted Hog Rider / Ice Golem / Skeletons body-block recreation, replay verification, placement sensitivity, and controls.
- [`docs/bots.md`](docs/bots.md): shared bot catalog, registry, implementation layout, adding opponents, live/turn-based bot strength comparisons, paired live duels, and planner settings.
- [`docs/search_v2.md`](docs/search_v2.md): implemented search, human-play integration, comparison commands, evaluation protocol, results, and limitations.
- [`docs/search_v2_context.md`](docs/search_v2_context.md): Plan 1 implementation context for improving CPU search, including candidate selection, rollouts, budgets, integration, and validation.
- [`docs/phone_play.md`](docs/phone_play.md): launch interactive play and share a temporary public link.
- [`docs/public_play.md`](docs/public_play.md): arena lobby, player names and deck selection, seven-match public Planner play at local-play strength without pausing, Tactics @5 Try Benchmark challenge and reference resolution, persistent CSV leaderboard, fixed Hog Cycle opponent, preloaded masks, permanent RoyaleBench share link, results before worker cleanup, and unranked hosting checks.
- [`docs/public_play_plan.md`](docs/public_play_plan.md): implementation scope, checklist, and validation for public play.
- [`docs/public_play_validation.json`](docs/public_play_validation.json): historical five-match and ten-match measurements (two Planner workers per match; the seven-match eight-worker deployment is not yet measured), latency limits, and deployment status.
- [`docs/rendering.md`](docs/rendering.md): dark replay viewer and synchronized agent decisions, lobby miniature, card previews and match result dialog, tower destruction and animated match/case endings, shared live/replay graphics, mobile troop sizing, Arena 1 terrain and tower references, classic-deck units, spells and card portraits, live HUD and placement cues, battle indicators, placement masks, and rendering checks.
- [`docs/tiktok_recreations.md`](docs/tiktok_recreations.md): extracted TikTok references, deterministic Skeletons/Mini P.E.K.K.A. and Fireball/Balloon recreations, controls, death-bomb accounting, validation, and reconstruction limits.
- [`docs/tactics_clips.md`](docs/tactics_clips.md): Tactics @6's two clip-inspired defenses, level normalization, frozen @5 provenance, references, controls, container checks, and hosted pilot evidence.
- [`runs/tactics-clips/checks.json`](runs/tactics-clips/checks.json): ten-task @6 digest, unchanged @5 packages, static and container checks, negative controls, and independently replayed Opus pilot failures.
- [`docs/task_design.md`](docs/task_design.md): how to design, build, and validate benchmark tasks, including what the deck-strength data can and cannot support as a lever.
- [`docs/royalebench_v3.md`](docs/royalebench_v3.md): historical coordinate-action benchmark, all 11 released scenarios, scoring, validation, and Harbor/Valkyrie workflow.
- [`docs/royalebench_win.md`](docs/royalebench_win.md): separate win-only continuation tasks, v3 saturation audit, calibration controls, and container/hosted validation.
- [`docs/royalebench_v6.md`](docs/royalebench_v6.md): historical 14-task merge of v5@1 and win@2, exact source provenance, retained grading, runtime-specific validation, and publication.
- [`docs/royalebench_v8.md`](docs/royalebench_v8.md): historical 18-task merge of v6@1 and v7@1, exact source provenance, retained grading, runtime-specific validation and publication.
- [`docs/royalebench_v9.md`](docs/royalebench_v9.md): 21-task extension of v8@1 with Hog body-block, Mini P.E.K.K.A. kite and Balloon Fireball, exact provenance, validation, all-task resolution playback and observed pass-rate difficulty calibration.
- [`runs/README.md`](runs/README.md): compact evidence policy and instructions to regenerate local run artifacts.
- [`runs/royalebench-v9/difficulty.json`](runs/royalebench-v9/difficulty.json): timestamped 12-run task pass-rate snapshot and thresholds behind v9's benchmark-level difficulty labels.
- [`runs/royalebench-v9/checks.json`](runs/royalebench-v9/checks.json): source identity, passing references, publication, live API resolution hashes and browser playback checks for all 21 v9 tasks.
- [`runs/royalebench-v9/model-results.json`](runs/royalebench-v9/model-results.json): twelve complete v9 model runs from Valkyrie, per-task objective and game-win scores, run IDs, result checksums and representative action sequences.
- [`runs/royalebench-v8/merge.json`](runs/royalebench-v8/merge.json): all 18 source task digests, archive checksums, objectives and packaged protocol hashes.
- [`runs/royalebench-v8/checks.json`](runs/royalebench-v8/checks.json): merged source identity, protected reference and negative-control checks, regression tests and publication evidence.
- [`docs/royalebench_v7.md`](docs/royalebench_v7.md): separate harder tower-winning continuations included in v8, latest eight-model v6 audit, second-wave and split-lane task design, validation and frontier calibration.
- [`runs/royalebench-v7/v6-audit.json`](runs/royalebench-v7/v6-audit.json): latest v6 model scores, exact revisions and run settings, per-task rewards and independently verified gameplay outcomes informing v7.
- [`runs/royalebench-v7/checks.json`](runs/royalebench-v7/checks.json): v7 static, deterministic reference, negative-control and isolated container checks, pinned runtime and publication.
- [`runs/royalebench-v7/opus-review.json`](runs/royalebench-v7/opus-review.json): first full v7 Opus calibration, all four gameplay failure reviews, captured final states, exact run settings and model API cost.
- [`runs/royalebench-v7/sol-review.json`](runs/royalebench-v7/sol-review.json): first full v7 Sol comparison, reviewed wins and losses, final captured tower states, and token/cost reporting limits.
- [`docs/royalebench_v4.md`](docs/royalebench_v4.md): Opus and Sonnet v3 comparison, task-level failure evidence, focused challenge variants, validation, and publication workflow.
- [`runs/royalebench-v4/checks-revision2.json`](runs/royalebench-v4/checks-revision2.json): corrected v4 `@2` digest, protocol and Docker checks, full Opus/Sonnet run settings, costs, and per-task scores.
- [`docs/royalebench_v5.md`](docs/royalebench_v5.md): ten-case coordinate dataset, source revisions, Opus/Sonnet/Haiku selection evidence, scoring, validation, and Valkyrie workflow.
- [`runs/royalebench-v5/selection.json`](runs/royalebench-v5/selection.json): task-by-task source revisions, package hashes, model run IDs, and selection rewards.
- [`runs/royalebench-v3/checks-revision2.json`](runs/royalebench-v3/checks-revision2.json): v3 `@2` publication digest, protocol hash, validation counts and hosted Qwen pilot pointer.
- [`docs/royalebench_v1.md`](docs/royalebench_v1.md): historical menu-based continuation scenarios against Planner, scoring, calibration, release gates, revision `@2` telemetry, revision `@3` Modal Qwen networking, and Harbor/Valkyrie packaging.
- [`docs/tactics.md`](docs/tactics.md): ten coordinate Tactics tasks in seven families on the v3 foundation, including Hog body-blocking and two clip-inspired defenses, unchanged source packages, spatial contrasts, and release evidence.
- [`runs/tactics-hog-one-hit/checks.json`](runs/tactics-hog-one-hit/checks.json): one-HP Hog defense revision, three-elixir start and total budget, reference and failure controls, container checks, and hosted pilot evidence.
- [`runs/tactics-hog/checks.json`](runs/tactics-hog/checks.json): expanded Tactics revision, new Hog task reference and negative controls, preserved source digests, container checks, and hosted pilot evidence.
- [`runs/tactics-hog/model-pilot.json`](runs/tactics-hog/model-pilot.json): Opus 5.5 Hog defense pilot on Tactics `@4`, independently verified placement failure, cost, and archived trace locations.
- [`runs/tactics-coordinates/checks.json`](runs/tactics-coordinates/checks.json): Tactics `@3` foundation/runtime hashes, focused tests, container checks, coordinate sweeps and hosted pilot evidence.
- [`docs/coordinate_harness.md`](docs/coordinate_harness.md): separate coordinate-action pilot, CLI, illegal-action handling, replay grading, reference validation, and comparison with frozen v1.
- [`docs/evals_dashboard.md`](docs/evals_dashboard.md): run benchmarks on Valkyrie and Modal, filter the leaderboard to full benchmark runs and compare model scores, watch recorded task gameplay and validated reference resolutions, inspect per-run and per-task API costs, benchmark task rankings by average pass rate and cost, and task difficulty, repair harness issues, and browse the arena.
- [`docs/modal_billing.md`](docs/modal_billing.md): actual Modal endpoint spend, persisted task/job inference costs and verified token rates, resource breakdowns, workspace access, App mappings, completed-hour refresh, month reconciliation, and verification limits.
- [`docs/qwen_modal.md`](docs/qwen_modal.md): use the existing mini-SWE-agent harness with the Modal Qwen endpoint, configure API-key/base-URL references, and run a one-task Valkyrie pilot.
- [`docs/inkling_modal.md`](docs/inkling_modal.md): Inkling endpoint setup, revision `@4` network access, Qwen credential reuse, secure model discovery, and stock mini-SWE-agent pilot status.
- [`docs/deepseek_modal.md`](docs/deepseek_modal.md): DeepSeek endpoint setup, revision `@5` network access, shared proxy credential, and stock mini-SWE-agent pilot status.
- [`docs/kimi_modal.md`](docs/kimi_modal.md): Kimi endpoint setup, revision `@6` network access, shared proxy credential, and stock mini-SWE-agent pilot status.
- [`runs/royalebench-v1/kimi_mini_swe_pilot.json`](runs/royalebench-v1/kimi_mini_swe_pilot.json): successful stock mini-SWE-agent Kimi pilot, independent verifier result, exact configuration, token usage, and checksum-verified raw artifact locations.
- [`runs/royalebench-v1/deepseek_mini_swe_pilot.json`](runs/royalebench-v1/deepseek_mini_swe_pilot.json): successful stock mini-SWE-agent DeepSeek pilot, independent verifier result, shared credential reference, token usage, and checksum-verified artifact locations.
- [`runs/royalebench-v1/inkling_mini_swe_pilot.json`](runs/royalebench-v1/inkling_mini_swe_pilot.json): successful stock mini-SWE-agent Inkling pilot, shared credential reference, independent verifier result, usage, and checksum-verified artifact locations.
- [`runs/royalebench-v1/qwen_mini_swe_pilot.json`](runs/royalebench-v1/qwen_mini_swe_pilot.json): successful stock mini-SWE-agent Qwen pilot, independent verifier result, exact configuration, usage, and checksum-verified raw artifact locations.
- [`runs/royalebench-v1/qwen_modal_pilot.json`](runs/royalebench-v1/qwen_modal_pilot.json): historical Qwen pilot with the removed custom harness, independent rewards, token usage, and checksum-verified raw artifact locations.
- [`docs/data_collection_plan.md`](docs/data_collection_plan.md): telemetry design, implementation stages, analysis targets, and validation gates for future runs.
- [`docs/data_collection.md`](docs/data_collection.md): implemented telemetry, automatic collection for new runs, analysis exports, archive verification/restoration, and limitations.
- [`docs/telemetry.schema.json`](docs/telemetry.schema.json): machine-readable schema for versioned match evidence records.
- [`docs/data_collection_validation.json`](docs/data_collection_validation.json): local, container, archival and hosted-pilot validation evidence, including RoyaleBench v1 revision `@2`.
- [`docs/valkyrie_guide.md`](docs/valkyrie_guide.md): concise evaluation workflow and how Valkyrie supports the hackathon goal.
- [`docs/modal_guide.md`](docs/modal_guide.md): concise Modal setup, compute workflow, public writeup deployment and update command, and links.
- [`docs/writeup.html`](docs/writeup.html): standalone benchmark writeup and development leaderboard, published by `modal_writeup.py`.
- [`docs/match_tasks.md`](docs/match_tasks.md): full-match Harbor tasks played through the `cr` CLI, referee isolation, replay grading, rewards, and how to build and publish them.
- [`docs/valkyrie_smoke.md`](docs/valkyrie_smoke.md): project-specific Modal credential setup and a minimal evaluation run.
- [`docs/build_eval_track.md`](docs/build_eval_track.md): hackathon track requirements, Valkyrie setup, task format, and submission guidance. Use this as the local source for track requirements.
- [`docs/vals-hacks-opening-slides.md`](docs/vals-hacks-opening-slides.md): event context and schedule.
- [`data/README.md`](data/README.md): documentation for project data, including the frozen v1@1 build inputs used by v3, tracked deck-strength data (CrownScribe archetype win rates in `data/deck_strength.csv` and head-to-head matchups in `data/deck_matchups.csv`, ranked by `cr_arena/deck_strength.py`).

## Project references

- [Valkyrie repository](https://github.com/vals-ai/Valkyrie): source code for the evaluation framework.
- [Valkyrie documentation](https://docs.valkyrie.vals.ai/introduction/what-is-valkyrie): framework introduction and usage guidance.
- [Valkyrie sandbox provider setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers): connect Modal credentials for evaluation compute.
- [Modal getting started](https://modal.com/docs/guide/getting-started): account, CLI, and authentication setup.
- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes): isolated task execution and resource configuration.

Modal provides the sandbox compute for evaluation tasks run through Valkyrie. Use `--provider modal` for evaluation runs and follow the provider setup and project smoke-test guide for credentials.

The track guide names the team's Valkyrie organization and provides example CLI commands. Check current Valkyrie, Harbor, and Modal documentation when implementing their interfaces, since the project has not yet established a working benchmark structure.
