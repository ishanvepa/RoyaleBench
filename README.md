# RoyaleBench: Can language models win at Clash Royale?

> **Human-written overview: [TO BE WRITTEN BY THE TEAM].** The submission requires an entirely human-written opening paragraph at the top of the README.

Working submission draft. Bracketed items are unfinished; measured results below are preliminary.

## Background

Clash Royale asks a player to manage a regenerating resource, choose where and when to deploy units, and balance defense against pressure on the opponent's towers. RoyaleBench tests those decisions through full matches and exact mid-match continuations in a simulator.

- **Resource management:** When should the agent spend elixir or save it?
- **Spatial reasoning:** Which placement changes an engagement?
- **Planning and adaptation:** Can it defend a push and turn surviving units into a counterattack?

[TODO: State the specific capability gap supported by the final results.]

## RoyaleBench v1

The [RoyaleBench v1 dataset](benchmarks/royalebench-v1) contains strategic continuation scenarios against the updated three-ply **Planner** bot. Use `royalebench/royalebench-v1@2` for automatic replay and telemetry capture. See the [v1 guide](docs/royalebench_v1.md) for exact objectives, reference validation, release gates, and run commands. The full-match results below use the earlier benchmark and opponent.

## Preliminary full-match results

The initial full evaluation used Claude Sonnet 4.6 against a fixed rule-based opponent on `royalebench/clash-royale@2`.

| Model | Harness | Matches | Wins | Win rate | Model API cost, total |
| --- | --- | --- | --- | --- | --- |
| Claude Sonnet 4.6 | Claude Code v1.0.0 | 6 | 2 | 33.3% | $15.92 |

All six matches completed with replay integrity checks passing. Costs exclude sandbox compute. This is one attempt per task, with no cross-model comparison yet.

[TODO: Add repeated runs and comparison models; plot win rate with uncertainty alongside cost per match.]

## What a match looks like

`Read battle state and legal moves → choose a numbered move → advance the simulation → repeat`

The agent plays through the `cr` CLI. Each decision advances 2 seconds of game time; the game pauses while the model thinks. Waiting-only intervals are skipped automatically.

[TODO: Embed a short clip from a scored replay, with the observation, chosen action, and resulting board state.]

## Methodology

- **Tasks:** Six full matches: seeds 1–3 from both blue and red seats. Both players use `giant-beatdown`; the opponent is `heuristic-bot`.
- **Execution:** Harbor tasks on Valkyrie with Modal sandboxes. The recorded full run used `anthropic/claude-sonnet-4-6`, `claude_code-v1.0.0`, and concurrency 6. Each task allows 60 minutes of agent time; unmade decisions become waits.
- **Verification:** A separate referee owns the engine and action log. A clean verifier replays the log and checks decision numbers, ticks, and move labels. An integrity failure receives zero reward.
- **Score:** Mean binary win reward. At the overtime limit, tied crowns are resolved by remaining total tower HP, then seed parity for an exact tie. Crown counts and tower damage are diagnostics.

[TODO: Freeze the final comparison cohort and repeated-run protocol. Instrumented tasks are published as revision `@7`; the preliminary scores above use `@2`. See [data collection](docs/data_collection.md) for capture and archive details.]

## What the traces show

- **Observed variation:** The seed-1 blue task was won 3–0 in the pilot and lost 0–1 in the full evaluation. A fixed simulator seed does not fix model decisions.
- **Strategic failure:** [TODO: Select a verified loss; show the position, action, consequence, and evidence for the interpretation.]
- **Successful play:** [TODO: Show a contrasting verified win; distinguish a good decision from a favorable outcome.]

## Limitations

- Six matches and one model support an initial difficulty signal, not a stable ranking. Three task configurations still lack a recorded winning run.
- Results concern the pinned simulator, fixed deck, opponent, and text interface. Live-game fidelity and human performance have not been established.
- Thinking pauses the game, so this setup does not measure real-time reaction speed. Scripted play is forbidden by instructions and checked through diagnostics and trace review, rather than fully prevented.

## Reproduce and inspect

- [Build, publish, run, and score the match tasks](docs/match_tasks.md).
- [Full-run results](runs/valkyrie-match-sonnet46-v2-results.json): run `eb818255-7a36-435d-aef8-9bbb9ef709ae`.
- [Simulation foundation and pinned dependencies](docs/simulator_foundation.md).
- Demo video and representative replay links: [TODO].

## Acknowledgements and precedents

Built on RoyaleGym/RoyaleSim, with evaluation through Valkyrie and Modal. [TODO: Team credits.]

Structure follows Vals AI's [Poker Agent](https://www.vals.ai/benchmarks/poker_agent) (results and behavioral case studies), [CUA-bench](https://www.vals.ai/benchmarks/cua_bench) (gameplay examples and interface boundaries), and [Time Horizon Index: KSP](https://www.vals.ai/benchmarks/time_horizon_index) (agent workflow, verification, and limitations). These are presentation precedents; their scores are not comparable to ours.

## Quick guides

- [RoyaleBench v1](docs/royalebench_v1.md): strategic continuation tasks against Planner, exact scoring, local validation, and release gates.
- [Data collection](docs/data_collection.md): shared match telemetry, automatic archival for future runs, and reproducible analysis tables ([design plan](docs/data_collection_plan.md)).
- [Evals dashboard](docs/evals_dashboard.md): run benchmarks on Valkyrie and Modal from a web app, and browse the original arena (`uv run python -m rb_server`).
- [Simulation foundation](docs/simulator_foundation.md): the RoyaleGym ecosystem, our current integration, and its role in the benchmark.
- [Bot setup](docs/bots.md): bot presets, human-play choices, and implementation registry.
- [Search v2](docs/search_v2.md): CPU search implementation and head-to-head evaluation against the original bot.
- [Phone play](docs/phone_play.md): launch the game and a temporary public link with one command.
- [Public play](docs/public_play.md): face Planner's fixed Hog Cycle deck with up to seven concurrent players; includes hosting instructions.
- [Battle graphics](docs/rendering.md): the shared renderer for live play and saved replays.
- [Valkyrie guide](docs/valkyrie_guide.md): publish tasks, run evaluations, and collect hackathon results.
- [Modal guide](docs/modal_guide.md): connect sandbox compute and manage evaluation usage.

## Valkyrie references

- [Valkyrie repository](https://github.com/vals-ai/Valkyrie)
- [Valkyrie documentation](https://docs.valkyrie.vals.ai/introduction/what-is-valkyrie)

## Modal compute

Modal provides the sandbox compute for evaluation tasks run through Valkyrie (`--provider modal`).

- [Valkyrie sandbox provider setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers): connect Modal credentials to Valkyrie.
- [Modal getting started](https://modal.com/docs/guide/getting-started): account, CLI, and authentication setup.
- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes): isolated task execution and resource configuration.
- [Match tasks](docs/match_tasks.md): full matches played through the `cr` CLI on Valkyrie, with isolated referee and replay grading.
- [Project smoke test](docs/valkyrie_smoke.md): project-specific credential setup and a minimal evaluation run.
