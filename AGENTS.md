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
- [`docs/simulator_foundation.md`](docs/simulator_foundation.md): RoyaleGym ecosystem, current integration, compact opponent-play observations, pinned dependencies, and benchmark validation priorities.
- [`docs/bots.md`](docs/bots.md): shared bot catalog, registry, implementation layout, adding opponents, live/turn-based bot strength comparisons, paired live duels, and planner settings.
- [`docs/search_v2.md`](docs/search_v2.md): implemented search, human-play integration, comparison commands, evaluation protocol, results, and limitations.
- [`docs/search_v2_context.md`](docs/search_v2_context.md): Plan 1 implementation context for improving CPU search, including candidate selection, rollouts, budgets, integration, and validation.
- [`docs/phone_play.md`](docs/phone_play.md): launch interactive play and share a temporary public link.
- [`docs/public_play.md`](docs/public_play.md): arena lobby, player names and deck selection, seven-match public Planner play at local-play strength without pausing, persistent CSV leaderboard, fixed Hog Cycle opponent, preloaded masks, permanent RoyaleBench share link, results before worker cleanup, and unranked hosting checks.
- [`docs/public_play_plan.md`](docs/public_play_plan.md): implementation scope, checklist, and validation for public play.
- [`docs/public_play_validation.json`](docs/public_play_validation.json): historical five-match and ten-match measurements (two Planner workers per match; the seven-match eight-worker deployment is not yet measured), latency limits, and deployment status.
- [`docs/rendering.md`](docs/rendering.md): dark replay viewer and synchronized agent decisions, lobby miniature, card previews and match result dialog, shared live/replay graphics, mobile troop sizing, Arena 1 terrain and tower references, classic-deck units, spells and card portraits, live HUD and placement cues, battle indicators, placement masks, and rendering checks.
- [`docs/task_design.md`](docs/task_design.md): how to design, build, and validate benchmark tasks, including what the deck-strength data can and cannot support as a lever.
- [`docs/royalebench_v3.md`](docs/royalebench_v3.md): historical coordinate-action benchmark, all 11 released scenarios, scoring, validation, and Harbor/Valkyrie workflow.
- [`docs/royalebench_win.md`](docs/royalebench_win.md): separate win-only continuation tasks, v3 saturation audit, calibration controls, and container/hosted validation.
- [`docs/royalebench_v6.md`](docs/royalebench_v6.md): default 14-task merge of v5@1 and win@2, exact source provenance, retained grading, runtime-specific validation, and publication.
- [`runs/royalebench-v3/checks-revision2.json`](runs/royalebench-v3/checks-revision2.json): v3 `@2` publication digest, protocol hash, validation counts and hosted Qwen pilot pointer.
- [`docs/royalebench_v1.md`](docs/royalebench_v1.md): historical menu-based continuation scenarios against Planner, scoring, calibration, release gates, revision `@2` telemetry, revision `@3` Modal Qwen networking, and Harbor/Valkyrie packaging.
- [`docs/coordinate_harness.md`](docs/coordinate_harness.md): separate coordinate-action pilot, CLI, illegal-action handling, replay grading, reference validation, and comparison with frozen v1.
- [`docs/evals_dashboard.md`](docs/evals_dashboard.md): run benchmarks on Valkyrie and Modal, watch recorded task gameplay, inspect per-run and per-task API costs and task difficulty, repair harness issues, and browse the arena.
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
- [`docs/modal_guide.md`](docs/modal_guide.md): concise Modal setup, compute workflow, and links.
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
