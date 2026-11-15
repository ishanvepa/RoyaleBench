# Search v2: implementation context

Status: proposed, November 14, 2026. This is Plan 1 from the bot alternatives discussion. No Search v2 implementation or strength result is implied by this document.

## Objective

Build a stronger CPU search bot using the RoyaleGym/RoyaleSim infrastructure already in the project. Combine the planner's richer placement candidates with the search bot's repeated deployments for both sides. Improve how simulations are allocated and how opponent responses are modeled before adding a training pipeline.

The intended result is a versioned opponent with explicit compute limits, reproducible decisions in benchmark mode, and logs that explain its choices. Strength must be established through games and representative tactical examples. More simulations or a more complicated evaluator do not establish improvement on their own.

Read [AGENTS.md](../AGENTS.md) for benchmark requirements and the [simulation foundation](simulator_foundation.md) for the ecosystem and dependency snapshot.

## Existing implementation

| File | What to reuse or understand |
| --- | --- |
| [`cr_arena/search_bot.py`](../cr_arena/search_bot.py) | `SearchBot`, private simulation engine, root snapshot restoration, repeated two-sided rollouts, common random seeds across root moves, and a handwritten position evaluator. |
| [`cr_arena/planner_bot.py`](../cr_arena/planner_bot.py) | `Planner.candidates`, troop/building placements, spell cluster targets, deployment legality checks, a second evaluator, and process-pool workers with one engine per worker. |
| [`cr_arena/game.py`](../cr_arena/game.py) | Engine construction, legal numbered moves, coordinate transforms, decision interval, command delay, and replay recording. |
| [`cr_arena/players.py`](../cr_arena/players.py) | `Player`, `Decision`, `HeuristicBot`, and `build_player` registration. |
| [`cr_arena/match.py`](../cr_arena/match.py) | Frozen-state simultaneous decisions, match outcomes, decision logs, and replay output. |
| [`cr_arena/live.py`](../cr_arena/live.py) | Worker snapshots, live command delay, bot registration, and application of answers after the real battle has advanced. |
| [`cr_arena/tournament.py`](../cr_arena/tournament.py) | Existing scheduling and result persistence; inspect before adding a comparison runner. |
| [`configs/search_bot.toml`](../configs/search_bot.toml) | Existing v1 reference configuration. It includes model players; use a separate bots-only configuration for development. |

Search v1 evaluates every numbered root move with four rollouts by default, looking ahead 12 seconds. Its continuation policy chooses the heuristic 60% of the time, waits 25%, and otherwise plays a random non-wait move. Subsequent decisions occur at the game's configured decision interval.

The live planner uses a default 10-second horizon. Its initial scoring plays one card and lets the battle continue without additional deployments. For selected candidates, it tries one enemy response after command delay plus ten ticks, then again advances without additional plays. It does not search a sequence of alternating responses beyond that.

Both bots read the true engine state, including the opponent's hidden hand and elixir. The planner also has a richer placement interface than the LLMs. These advantages must remain explicit in comparisons.

## Specific weaknesses to address

1. **Premature pruning in the planner.** `Planner.act` retains only candidates whose quiet rollout beats quiet waiting by `margin`, before testing enemy replies. This can remove preventative moves that become useful when the opponent attacks.
2. **Unrealistic continuations.** The planner permits at most one enemy response. Search v1 permits many deployments but relies on a weak, mostly single-policy model of both players.
3. **Uniform work allocation.** Search v1 spends the same number of rollouts on every root move, even when many appear clearly inferior.
4. **Different action and timing protocols.** The planner's richer placements and live decision timing cannot be silently mixed into an LLM comparison using numbered moves every 40 ticks.
5. **Handwritten evaluation.** Both evaluators use tower damage, elixir, and surviving units. They can misvalue expiring buildings, spawned units, overcommitted attacks, and damage that lies just beyond the rollout horizon. Treat these as hypotheses to inspect, not already measured failure rates.

## Scope and operating modes

Implement a separate `search-v2` player so existing `search-bot` results and behavior remain attributable to v1. Keep the existing bots available for comparisons.

| Mode | Action and timing contract | Compute contract |
| --- | --- | --- |
| Benchmark | Root and continuation moves for both sides use `Game.legal_moves`; use the match's decision interval and zero benchmark command delay. Return the original root move's index. | Fixed work budget and deterministic allocation. |
| Live, after benchmark integration | Use the planner's richer candidate placements, respect pending commands and live delay, and revalidate returned actions against the current battle. | Deadline with a completed-search fallback. |

The first version may retain full engine information to isolate search changes. Label it `information_mode = omniscient` in configuration/results and do not describe it as a fair public-information reference. Hidden-state inference is Plan 2 and a separate extension.

This plan requires no GPU, human replay download, PPO training, new simulator, or LLM calls. Native observation builders and learned policies can be integrated later, but are not prerequisites.

## Recommended search design

Start with adaptive root search and multi-step rollouts. A full tree search is an optional later experiment, after this simpler version is measured.

1. **Snapshot the root once.** Search only on private engines with matching decks, card data, and engine configuration. Do not step the real match engine. Define how any policy memory and random generators reset between branches; engine bytes alone do not restore Python-side state.
2. **Generate legal root candidates.** In benchmark mode, use the supplied numbered menu without adding placements. For live mode, extract and reuse the planner's candidate generation. Deduplicate by command while retaining the mapping to the original move.
3. **Screen candidates cheaply.** Allocate a small equal set of short, two-sided rollouts to each candidate. Use stable ordering and shared scenario seeds. Quiet rollouts can be a ranking feature, but cannot be the sole test that removes defenses before an enemy acts.
4. **Retain a diverse shortlist.** Always retain waiting. Reserve bounded slots for legal responses to imminent tower threats, air threats, and high-value spell opportunities, where present. Retain at least one candidate per playable card if the budget permits. These are search candidates, not forced actions; define and log how reservations compete when the cap is small.
5. **Simulate repeated decisions.** After the root move, both sides continue choosing and deploying at each permitted decision point. Recompute legal actions from each simulated state. Stop on terminal states and clamp the final advance to the remaining horizon.
6. **Vary opponent behavior.** Begin with aggressive, defensive, and patient policies, all using legal actions. Run each surviving root move against the same scenario schedule. Our continuation policy should also be capable of multiple deployments. Neither side may inspect the other side's not-yet-applied action when choosing a simultaneous move.
7. **Allocate further work in rounds.** Give surviving candidates equal additional scenarios, then eliminate the weakest fraction while preserving reserved candidates. Compare candidates on matched scenarios, and make budget consumption independent of worker completion order. This is sequential halving; no claim of optimality is required.
8. **Choose and explain.** Initially rank by mean outcome score across the fixed opponent mixture. Log per-policy scores and worst outcomes. Test a downside penalty as a separate ablation rather than adding an unmeasured risk coefficient immediately. Break ties with a stable command ordering.

For a small later tree-search experiment, expand only a few promising actions at each decision and retain a bounded set of branches. Carry root-action identity through every branch. Preserve simultaneous choice semantics and measure whether the extra depth helps at the same compute budget.

## Evaluation function

Begin with one documented evaluator shared by Search v2's rollouts. Keep its weights configurable and frozen during a comparison. Evaluate terminal wins, losses, and draws explicitly, with terminal outcomes dominating nonterminal scores.

Retain tower damage/crowns, spendable elixir, and surviving board value as an initial baseline. Inspect whether a surviving unit is valued by its own type or the card that spawned it before assigning card-cost value. Handle pending costs and avoid counting the same commitment twice. Consider remaining lifetime and time left only when relevant engine fields are available and validated.

Separate evaluator changes from search changes in experiments. A useful first comparison is v1-style rollouts versus v2 allocation using the same evaluator, followed by evaluator ablations. Longer horizons should be tested against their cost and possible rollout-policy errors.

## Budgets, concurrency, and logs

For benchmark mode, bound simulated ticks and rollout count, including screening work. Also cap root candidates and horizon. A fixed rollout count alone does not equalize work when horizons differ; report both simulated ticks and measured latency. If the budget cannot cover the minimum comparison round, reject the configuration or use a documented deterministic fallback.

Seed scenarios from the configured bot seed and decision identifier, not worker scheduling or wall-clock time. Use one private engine per worker and aggregate results in stable order. Test that changing worker count preserves fixed-budget choices. Retain the planner's process cleanup behavior when reusing its pool design, and account for tournament concurrency before multiplying worker processes.

Live mode needs a legal fallback when a deadline interrupts a round. Publish only completed comparisons. Tag answers with their source tick and card identity so an old hand-slot index cannot silently deploy a different card after the battle advances. Define when stale answers are discarded or re-searched; legality alone does not make an outdated tactical choice useful.

Record selected action, candidate counts, shortlist reasons, scenario seeds/policies, per-candidate sample counts and scores, wait score, simulated ticks, budget exhaustion, latency, and information/action modes. Keep the concise `Decision.raw` explanation compatible with existing logs; store larger diagnostics separately if needed.

## Implementation sequence

1. Add a bots-only comparison configuration and preserve baseline settings/results. Adapt the planner to the common evaluation interface if needed; it is currently used through the live path rather than `build_player`.
2. Add the `search-v2` player and deterministic budget/configuration validation. Reuse snapshot execution and implement multi-policy continuations first.
3. Add candidate screening, reservations, and sequential allocation. Demonstrate a tactical case where a necessary candidate survives pruning.
4. Add meaningful engine integration checks and run small full-game comparisons. Profile state reads, legality checks, and stepping before optimizing the hot path.
5. Integrate richer live candidates and deadlines only after the benchmark adapter works. Update the [documentation index](../AGENTS.md), [simulation foundation](simulator_foundation.md), and [phone-play guide](phone_play.md) when behavior changes.

Suggested settings to expose are `budget_ticks`, `max_rollouts`, `screen_horizon_s`, `horizon_s`, `shortlist_size`, `opponent_mix`, `seed`, and `workers`, with a separate `deadline_ms` for live mode. These are proposed names, not existing supported configuration keys.

## Verification and strength evaluation

Before comparing strength, verify root-state isolation, repeatability, legal action mapping for both seats, terminal handling, budget limits, and worker cleanup. Add tactical scenarios for urgent defense, anti-air response, a spell opportunity, and defense followed by a counterpush. Include the planner's premature-pruning case and a live stale-answer case. Verify expected behavior from engine traces, not from the bot's own score alone.

Start with a small bots-only smoke run. Then freeze settings and compare Search v2 against search v1, the heuristic, and the planner where the interfaces can be matched. Use the existing Giant beatdown, Hog cycle, and LavaLoon decks, plus cross-deck matchups. Separate tuning seeds/matchups from held-out evaluation cases, and play each case with seats swapped.

Report wins/draws/losses, score with draws worth one half, uncertainty over paired cases, results by opponent/deck, decision latency, simulated work, illegal actions, and representative replays. Compare fixed-work strength and practical CPU cost separately; engine ticks are a useful work proxy, not identical elapsed cost across positions or algorithms. Do not interpret unmatched placement freedom or hidden information as a search improvement.

Promote v2 only after correctness checks pass, it shows a repeatable improvement over v1 on the frozen held-out comparison, and its cost fits the declared use. Choose the sample size and improvement criterion before the final run; inconclusive evidence calls for more evaluation, not a strength claim. Freeze the resulting configuration and save the commit, lockfile, scenarios, logs, and replays with the result.

## Upstream references

- [RoyaleSim Python API](https://royalegym.github.io/RoyaleGym/repos/royalesim/api/): engine state, legality, save/load, and command-delay interfaces. Check against the locked versions before using newer APIs.
- [RoyaleGym opponents](https://royalegym.github.io/RoyaleGym/clash-royale/configuration-objects/opponents/): scripted opponent patterns and evaluation interfaces. Their action encoding needs adaptation to our numbered menus.
- [RoyaleGym repository](https://github.com/RoyaleGym/RoyaleGym) and [RoyaleSim repository](https://github.com/RoyaleGym/RoyaleSim): implementation references for adapters and engine behavior.
