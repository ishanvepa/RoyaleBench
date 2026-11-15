# RoyaleBench's simulation foundation

Reviewed November 14, 2026. This document describes the upstream projects behind our current implementation, their responsibilities, and how we use them to evaluate language models at Clash Royale. It separates working project code from proposed extensions; it does not establish that the simulator reproduces every live-game mechanic.

## What we are building

RoyaleBench evaluates strategic decisions by language models in simulated Clash Royale battles. The current interface gives each model a text description of its view of the battle and a numbered list of available moves. The model selects a move, the engine advances, and the process repeats. This lets us inspect resource management, placement, timing, and adaptation through both game outcomes and individual decisions.

The RoyaleGym ecosystem supplies the environment and battle engine. Our repository supplies the LLM interface, match orchestration, opponents, decision logs, and benchmark design. The project delivery target is a versioned Harbor task dataset evaluated through Valkyrie with Modal sandbox compute. The existing arena implementation and that evaluation packaging are distinct pieces of work; having local matches does not by itself establish a completed Valkyrie benchmark. See the [Valkyrie guide](valkyrie_guide.md) and [track requirements](build_eval_track.md).

## The upstream repositories

| Repository | Responsibility | Role in RoyaleBench |
| --- | --- | --- |
| [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym) | Python battle environment, observations, actions, rewards, and integration with the other packages. | Our main API for constructing and controlling battles. |
| [RoyaleSim](https://github.com/RoyaleGym/RoyaleSim) | Rust battle engine exposed to Python. Runs matches locally without the official game client. | The engine behind the `RustEngine` we already call through RoyaleGym. |
| [RoyaleViser](https://github.com/RoyaleGym/RoyaleViser) | Desktop viewer for saved battles and live training runs, including pause and step controls. | An available tool for inspecting failures and preparing demonstrations. Our current HTML replay path shares RoyaleBench's live battle graphics. |
| [RoyaleLearn](https://github.com/RoyaleGym/RoyaleLearn) | Reinforcement learning trainer for bots in RoyaleGym, with PPO and self-play support. | An optional way to train fixed opponents for future evaluations. It is not required to call frontier LLMs. |
| [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate) | Optional training extension for starting from an existing bot and retaining teacher behavior during learning. The ecosystem also documents cloning from human games. | A possible starting point for stronger trained opponents. Replay preparation, training, and opponent validation would be additional work. |

These are cooperating components of one ecosystem. RoyaleSim provides the battle mechanics; RoyaleGym makes those mechanics accessible to agents. RoyaleLearn and RoyaleImitate build trained policies on top, while RoyaleViser helps people watch what happened. The upstream descriptions are linked in the table; compatibility must be checked against our pinned package versions before adopting new APIs.

## How our current implementation uses them

The current execution path is:

```text
LLM or baseline opponent
    -> RoyaleBench text observations and numbered moves
    -> RoyaleGym's RustEngine adapter
    -> RoyaleSim battle simulation
    -> updated observations, match results, logs, and replays
```

The main implementation points are:

- [`cr_arena/game.py`](../cr_arena/game.py) creates `RustEngine`, resolves decks, resets with a seed, constructs player observations and moves, and records replay frames.
- [`cr_arena/match.py`](../cr_arena/match.py) requests both players' decisions from the same frozen state, applies their choices, and saves decision logs and a replay. It records outcomes, latency, token usage, cost, and errors.
- [`cr_arena/replay.py`](../cr_arena/replay.py) prepares saved battles through `royalegym.render.build_view` and embeds the same `battle_renderer.js` graphics as live play in a standalone HTML replay, with local playback controls. See [Battle graphics](rendering.md) for placement geometry and rendering checks. This is separate from launching the RoyaleViser desktop application.

By default, decisions occur every 40 engine ticks, described by our current interface as two seconds of game time. The game waits while agents decide. Benchmark commands have zero configured command delay; the live-play path can use a delay. Those settings affect the task and must be recorded with results.

The model's interface hides the opponent's hand and elixir and expresses positions from the player's perspective. It offers a constrained placement menu, including visible spell targets, rather than unrestricted continuous placement. Results therefore measure strategy under this particular observation and action interface.

Search v2 adds deterministic, budgeted root allocation and multi-policy rollouts
through the same numbered benchmark interface. Its evaluator is shared with v1;
both remain omniscient. It is a separately registered player and is available in
the dashboard and real-time human-play selectors. The live adapter simulates the
configured delay, excludes pending cards, stops at completed rounds after a soft
deadline, and revalidates answers against the current battle. See the [implementation and strength evaluation](search_v2.md)
for configurations, recorded comparisons, and remaining limitations.

## Dependency snapshot

[`pyproject.toml`](../pyproject.toml) requests `royalegym[all]>=0.1.28`. The checked-in [`uv.lock`](../uv.lock) currently resolves:

| Package | Locked version |
| --- | --- |
| `royalegym` | `0.1.28` |
| `royalesim` | `0.1.48` |
| `royaleviser` | `0.1.2` |
| `royalelearn` | `0.5.20` |
| `royaleimitate` | `0.2.15` |

The `[all]` extra brings all these components into the dependency graph. Their presence in the lockfile does not mean our benchmark actively uses their training or desktop-viewer features. Reproduce this snapshot with the committed lockfile, for example using `uv sync --locked`, and retain that file with published results.

## What the foundation gives us—and what we must establish

The engine gives us controlled battle execution and recorded trajectories. Our benchmark still needs explicit task instructions, a defined score, a fixed opponent protocol, and evidence that failures reflect model decisions. Deterministic simulation makes a fixed action sequence reproducible; an LLM may choose different actions on repeated runs, so a seed alone does not reproduce the entire evaluation.

For each reported comparison, record the repository commit, dependency lockfile, dataset revision, model identifier, prompts and inference settings, decks, seeds, seat assignments, decision interval, command delay, opponent configuration, and scoring rules. Keep raw decisions and replays alongside the scores. Measure game outcomes separately from invalid responses and provider failures.

Opponent information access also matters. The existing [`bots/search.py`](../cr_arena/bots/search.py) explicitly searches the true engine state, including hidden opponent information. Treat it as a privileged reference when reporting results. A fair opponent comparison requires matching the information available to each player or clearly disclosing the difference. A trained opponent would need the same review.

Validate the card interactions used by our chosen tasks before making claims about Clash Royale strategy. Simulator mistakes, ambiguous instructions, and interface restrictions can all produce apparent model failures. Inspect representative replays and verify the grader before expanding expensive runs.

## Priorities

1. Keep RoyaleGym and RoyaleSim as the current foundation while validating the interactions our tasks depend on.
2. Use recorded battles, the existing HTML viewer, and optionally RoyaleViser to explain model successes and failures.
3. Package a small, explicit task set for Valkyrie and verify its scores and traces on Modal.
4. Consider RoyaleLearn and RoyaleImitate when a trained opponent would improve the evaluation; freeze and validate any resulting policy before comparison runs.

[crforge](https://github.com/voonhous/crforge) is a separate candidate simulator discussed during research. It is not part of this dependency snapshot. Adopting it would require an integration and validation effort and a new benchmark version so results remain attributable to the engine used.
