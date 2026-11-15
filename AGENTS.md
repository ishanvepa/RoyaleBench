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
- [`README.md`](README.md): project entry point and links to quick guides.
- [`docs/simulator_foundation.md`](docs/simulator_foundation.md): RoyaleGym ecosystem, current integration, pinned dependencies, and benchmark validation priorities.
- [`docs/bots.md`](docs/bots.md): shared bot catalog, registry, implementation layout, adding opponents, live bot-vs-bot duels, and planner settings.
- [`docs/search_v2.md`](docs/search_v2.md): implemented search, human-play integration, comparison commands, evaluation protocol, results, and limitations.
- [`docs/search_v2_context.md`](docs/search_v2_context.md): Plan 1 implementation context for improving CPU search, including candidate selection, rollouts, budgets, integration, and validation.
- [`docs/phone_play.md`](docs/phone_play.md): launch interactive play and share a temporary public link.
- [`docs/rendering.md`](docs/rendering.md): shared live/replay graphics, Arena 1 terrain and tower references, classic-deck units, spells and card portraits, live HUD and placement cues, battle indicators, placement masks, and rendering checks.
- [`docs/task_design.md`](docs/task_design.md): how to design, build, and validate benchmark tasks.
- [`docs/evals_dashboard.md`](docs/evals_dashboard.md): run benchmarks on Valkyrie and Modal from the web app and browse the arena.
- [`docs/valkyrie_guide.md`](docs/valkyrie_guide.md): concise evaluation workflow and how Valkyrie supports the hackathon goal.
- [`docs/modal_guide.md`](docs/modal_guide.md): concise Modal setup, compute workflow, and links.
- [`docs/match_tasks.md`](docs/match_tasks.md): full-match Harbor tasks played through the `cr` CLI, referee isolation, replay grading, rewards, and how to build and publish them.
- [`docs/valkyrie_smoke.md`](docs/valkyrie_smoke.md): project-specific Modal credential setup and a minimal evaluation run.
- [`docs/build_eval_track.md`](docs/build_eval_track.md): hackathon track requirements, Valkyrie setup, task format, and submission guidance. Use this as the local source for track requirements.
- [`docs/vals-hacks-opening-slides.md`](docs/vals-hacks-opening-slides.md): event context and schedule.
- [`data/README.md`](data/README.md): documentation for project data.

## Project references

- [Valkyrie repository](https://github.com/vals-ai/Valkyrie): source code for the evaluation framework.
- [Valkyrie documentation](https://docs.valkyrie.vals.ai/introduction/what-is-valkyrie): framework introduction and usage guidance.
- [Valkyrie sandbox provider setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers): connect Modal credentials for evaluation compute.
- [Modal getting started](https://modal.com/docs/guide/getting-started): account, CLI, and authentication setup.
- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes): isolated task execution and resource configuration.

Modal provides the sandbox compute for evaluation tasks run through Valkyrie. Use `--provider modal` for evaluation runs and follow the provider setup and project smoke-test guide for credentials.

The track guide names the team's Valkyrie organization and provides example CLI commands. Check current Valkyrie, Harbor, and Modal documentation when implementing their interfaces, since the project has not yet established a working benchmark structure.
