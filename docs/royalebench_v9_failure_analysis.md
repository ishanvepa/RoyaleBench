# RoyaleBench v9: why the models fail

The strongest evidence is a gap between choosing a plausible Clash Royale plan and predicting its exact consequences: what retargets, when a spell lands, whether a deployment buys another tower shot, and whether a push finishes before the deadline. Some failures are broader planning errors, including spending a reserved counter and attacking before securing an urgent defense. A separate harness budget issue materially depresses the four mini-SWE-agent runs.

This review covers the **12 finished full runs of `royalebench/royalebench-v9@1` on November 15, 2026**, one attempt per model per task: **252 attempts, 91 passes, 161 failures**. The stopped Sol/Claude Code launch is excluded. Counts match the recorded [difficulty snapshot](../runs/royalebench-v9/difficulty.json) and the live ranking inspected during this review. These are objective-success scores; several tasks do not require winning a match.

## Evidence and limits

The [attempt audit](../runs/royalebench-v9/failure-analysis.json) records all 252 verifier results, accepted plays, source run IDs, result/trajectory SHA-256 hashes, and command traces. Every attempt has a cached trace. All 252 have verifier integrity 1, and the runs report no task errors. Of the 161 failures, **127 completed the scenario and 34 stopped early**. Only six failed attempts contain rejected actions; rejection is a contributor in those attempts, not a general explanation.

Selected policies were reconstructed from the verifier's recorded card, decision and coordinates, then executed with each task's **packaged referee Python code** and the pinned installed engines, RoyaleGym 0.1.28 / RoyaleSim 0.1.48. Nine distinct recorded policies reproduce their complete reported outcomes exactly. The [counterfactuals](../runs/royalebench-v9/failure-counterfactuals.json), [frame events](../runs/royalebench-v9/failure-mechanics.json), [aim ablations](../runs/royalebench-v9/failure-aim-ablation.json), and [allocation probes](../runs/royalebench-v9/failure-allocation.json) distinguish observed correlations from experimentally isolated changes. These local diagnostic runs are not new model attempts or new Docker validations. Existing [v9 container evidence](../runs/royalebench-v9/docker/validation.json) establishes 21 passing protected references.

Action logs and simulated outcomes take precedence over an agent's final explanation. Claude's recorded thinking fields are empty, and Codex traces do not expose private reasoning. Descriptions of planning weaknesses below are behavioral interpretations, except where a counterfactual isolates the effect.

## Results across models

| Model | Harness | Passed / 21 | Success | Incomplete attempts |
|---|---|---:|---:|---:|
| Opus 5.5 | Claude Code | 14 | 66.7% | 0 |
| Fable 5.2 | Claude Code | 13 | 61.9% | 0 |
| GPT-6.1 Sol | Codex | 12 | 57.1% | 0 |
| Fable 5.1 | Claude Code | 11 | 52.4% | 0 |
| GPT-6 Astra | Codex | 10 | 47.6% | 0 |
| GPT-6 Luna | Codex | 7 | 33.3% | 0 |
| Sonnet 5.5 | Claude Code | 7 | 33.3% | 0 |
| Haiku 5.5 | Claude Code | 4 | 19.0% | 1 |
| Inkling 2 Small | mini-SWE-agent | 4 | 19.0% | 6 |
| Kimi K3.1 Pro | mini-SWE-agent | 4 | 19.0% | 8 |
| Qwen 3.8 | mini-SWE-agent | 3 | 14.3% | 10 |
| DeepSeek V4.1 Flash | mini-SWE-agent | 2 | 9.5% | 9 |

The top models have different strengths. Opus solves three of the four newer conversion tasks but fails the air race almost immediately. Sol alone solves the second-wave air race, yet loses the split-lane task at 4.4 seconds. Fable 5.2 alone solves tower-race B but fails all four universally unsolved tasks. This is not a single ordering of game skill, and one attempt per model cannot establish stable rankings.

## 1. Immediate threat assessment: racing when defense would win

**`03-tower-race-b`: 1/12 pass.** Own left tower has 50 HP, an enemy Balloon is at `(3.5, 9.5)`, and a friendly Giant is beside an enemy tower with 366 HP. There are eight seconds of overtime and a four-elixir spending budget.

Ten models make the identical opening: Fireball at `(3.5, 25.5)`. Every one loses after **1.4 seconds**. DeepSeek submits a wait and also loses. Fable 5.2 instead puts Cannon at `(4.5, 9.5)` and wins.

The independent Opus replay makes the failure concrete: Fireball lands after 0.5 seconds and deals **253** tower damage, leaving **113 HP**. The Balloon destroys the friendly tower at 1.4 seconds, before the Giant's decisive attack. The reference Cannon at `(3.5, 9.5)` pulls the Balloon away; the Giant destroys the enemy tower at **2.0 seconds**, with zero friendly tower damage.

This is a race-ordering error. A building that cannot shoot air is still the winning air defense because it changes the Balloon's target. Fireball damage alone is insufficient, and the existing Giant already supplies the eventual win. The trace does not support attributing this failure to Fireball missing or failing to arrive.

## 2. Precise physical prediction: knowing the interaction is insufficient

**`07-balloon-fireball`: 0/12 pass, including nine completed one-Fireball attempts.** Three mini-SWE attempts stop without casting. The successful reference waits 10 seconds, then casts at `(3.5, 7.5)`. It prevents a direct attack and permits only the death bomb, leaving the 241-HP tower at **1 HP**.

Sol also waits **10 seconds**, but aims at `(3.3, 6.7)` and loses. Its final message blames waiting too long. Counterfactuals contradict that diagnosis:

| Change to Sol's recorded play | Outcome |
|---|---|
| None: t=10, `(3.3, 6.7)` | Tower destroyed |
| Change x only to 3.5 | Tower destroyed |
| **Change y only to 7.5** | **Pass; tower retains 1 HP** |
| Same original center, cast one second earlier | Tower destroyed |

This is not a missed Fireball. In both Sol and the reference, Fireball hits for 688 and causes knockback. At 11.6 seconds, the Balloon has **7 HP** in both runs. In Sol's run it gets its direct attack at **11.95 seconds**; in the reference it survives without attacking until the tower kills it at **12.4 seconds**, and its death bomb deals 240 at 15.45 seconds. Aim changes projectile timing and knockback geometry enough to reverse that ordering. The probes isolate an aim error; they do not establish a unique winning coordinate.

Astra and Fable 5.2 cast at nine seconds with centers close to the reference. Both fail. Moving the reference cast one second early also fails. "Use Fireball to knock the Balloon back" is the correct broad idea, but it needs a precise prediction of movement, spell travel, attack timing and the next tower shot.

**`05-hog-body-block`: 0/12 pass.** Ten models choose both Ice Golem and Skeletons, so choosing the cards is not the central problem. All ten start deploying immediately. The reference waits **0.5 seconds**, places Ice Golem at `(1.5, 11.5)`, then Skeletons at t=1.0 at `(3.5, 13.5)`.

Keeping those exact reference placements but shifting both deployments **0.5 seconds earlier** changes the result from zero damage to **635 damage**, including loss of the threatened tower. Opus's recorded placements reproduce the same total damage. A building-targeting Hog must be delayed through collision and pathing; merely putting the right troops in its lane does not guarantee that delay.

**`06-mini-pekka-kite`: 6/12 pass.** Successful models use several distinct timings and centers, including Opus at t=3.0, `(7.5, 11.5)`, and Sol at t=4.5, `(7.5, 9.5)`. This confirms that the grader accepts alternatives to the reference. Several failures place Skeletons in the incoming unit's lane, or commit before the intended inward kite develops. Moving the reference action half a second later also fails, but later timing can work with a different placement. Timing and geometry must be analyzed jointly.

## 3. Resource allocation across threats: preserving the right counter

**`02-reserve-counter-a`: 0/12 pass.** The instructions disclose a Goblin Barrel at six seconds, a six-elixir total budget and a 450-damage limit. All twelve stay within the spending limit; they fail the damage limit. Overspending is not the explanation here.

Four models spend Log on the initial threat. Astra and Qwen open with a four-elixir Musketeer, severely limiting subsequent options. Opus and Fable 5.2 preserve Log initially but later use it on a right-lane Goblin Gang while the disclosed Barrel threatens the left tower. Opus takes **904 damage**; Fable takes **1163**, despite spending only five elixir.

The reference uses central Ice Golem at t=0, Ice Spirits at t=2, and Log behind the left tower at t=8. It spends **five elixir** and takes **249 damage**. Changing only its opening Ice Golem from `(9, 10.5)` to the left lane `(3.5, 10.5)`, while preserving the remaining actions, raises damage to **1601**. Placement changes both troop movement and the reactive opponent's continuation. The challenge is more than remembering to save Log: the early defense must leave a manageable second attack.

The related successive-threats task passes only 3/12. Sol, Astra and Fable 5.2 pass; Opus opens with Log, exhausts the eight-elixir budget and takes 1683 damage. These traces support a weakness in allocating counters over a disclosed sequence rather than optimizing the immediate exchange alone.

## 4. Sustaining defense and converting it before the deadline

**`04-critical-cycle-and-connect`: 0/12 pass, all twelve completed.** Every model loses its 250-HP tower after roughly 3.35–10.6 seconds. The reference combines Ice Spirits, a precise Cannon pull, an offensive spell/Hog sequence, then defensive Log and another Ice Spirit. It wins at **11.2 seconds** without tower damage.

Sol puts Cannon at `(7, 9.5)` instead of the reference `(7, 11.5)`, inserts Skeletons before its offensive spell, and never plays the reference's defensive Log. Correcting only Cannon's position **still loses**. This is a sequence failure: establishing a pull, maintaining it and arranging the finishing attack must all work. A single bad coordinate does not explain every loss.

**`01-critical-cycle-conversion`: 2/12 pass.** Opus and Fable 5.2 defend their fragile tower and convert Hog pushes into a kill. Astra preserves its tower but fails to finish either push before 28 seconds. Defensive survival alone is not enough.

**`02-second-wave-air-race`: 1/12 pass.** Sol wins at 11.1 seconds, combining Cannon/Minions defense with Fireball on the enemy side to support its Giant. Opus's off-center Cannon fails to pull the incoming Balloon and it loses at 1.85 seconds. Fable 5.2 survives the opening but finishes the 30-second window with the enemy tower at **27 HP**. Its Fireball, Zap and troop cycle do not produce lethal damage in time. These are distinct failure stages: surviving the first attack versus spending enough resources and time on the finishing attack.

**`03-supported-tank-conversion`: 3/12 pass.** Opus, Sol and Luna pass. Fable 5.2 stops the incoming tank but spends 45 elixir across successive attacks without taking a tower. Astra similarly spends 45 without a tower kill. The behavior is consistent with insufficient coordination of attackers, removal of counters and spell finishing damage. A private reference establishes a successful sequence, but these traces do not isolate one uniquely decisive mistake.

**`04-split-lane-conversion`: 2/12 pass.** Opus and Fable 5.1 win. Seven models lose after exactly **4.4 seconds**, typically after choosing a plausible air defender but failing to stabilize both lanes before spending on offense or another ground play. Fable 5.2 survives the full window yet fails to convert, showing that emergency defense and eventual conversion are separate capabilities.

## 5. Harness limits and interface friction

The four mini-SWE-agent runs all use **`step_limit=12`**. Across their 84 tasks, **62 terminate with `LimitsExceeded`**, each after 12 model calls. **33/84 are incomplete**, accounting for 33 of the dataset's 34 incomplete attempts. Some scenarios require 14–18 moves, plus initial inspection, under the normal pattern of one move per model call. Even shorter tasks leave little room for observations and file exploration.

Six incomplete attempts have **`objective_met=1` and `win=1` after the verifier finishes unmade moves as waits**, but still receive reward zero because the agent did not complete play:

| Model | Tasks |
|---|---|
| Inkling | Counterpush |
| Kimi | Cycle and connect; bait damage sequence; counterpush |
| Qwen | Bait damage sequence |
| DeepSeek | Counterpush |

These are not six completed model wins. They are evidence that some zeros reflect the completion requirement and budget, rather than an already losing position. Other incomplete attempts would still fail their gameplay objective after continuation. Official scores should remain unchanged.

Exploration compounds the limit. DeepSeek spends its Hog attempt inspecting files, permissions, processes and package availability, making **zero game decisions**. Kimi spends several calls inspecting protected engine paths before playing its cycle task. The stock mini-SWE prompt describes a software repair workflow, which is a plausible contributor to this behavior; a controlled prompt ablation would be needed to establish causality. The current results measure **model plus harness**, with materially different execution budgets.

There is also a smaller observation issue: elixir displayed to one decimal place can show 3.0 or 6.0 while the exact amount is slightly short, producing an unaffordable-play rejection that consumes an interval. Illegal water placements also occur. Only six failed attempts contain any rejection, so these cannot explain the main pattern.

## What solvability establishes

The references demonstrate existence of a legal successful policy under the pinned runtime and grader. They do not demonstrate that a model can infer that policy from the provided mechanics information in one attempt. Some references were selected using privileged engine state and simulation search, while agents receive text observations, hidden opponent resources, paused thinking and no forward simulator or reset.

The tasks therefore mix strategic planning with engine-mechanics prediction and precision of execution. The difference matters: a 27-HP unfinished tower is a conversion failure, whereas a Fireball that leaves a Balloon at 7 HP and misses the next shot's timing is a precise interaction failure. Neither should be summarized only as "does not understand Clash Royale."

## Next diagnostic experiments

1. **Remove the budget confound first.** Rerun a small fixed subset for the four mini-SWE models with enough steps to complete the longest scenario, keeping the dataset and inference settings fixed. Report truncations separately. No such model reruns were launched for this analysis.
2. **Measure mechanics information separately from strategy.** Supply task-runtime attack damage, ranges, deployment/flight delays and exact affordability; compare against the existing prompt. This tests whether models fail to plan with known mechanics or are approximating unavailable details.
3. **Separate planning from spatial execution.** Compare free coordinates with a neutral set of legal candidate locations, or a forward-simulation tool under an explicit shared budget. The candidates must not encode the winning answer.
4. **Map robustness and repeat attempts.** Sweep timing/placement around successful policies and run repeated model attempts. Existing controls show sensitivity, but not that there is only one winning point or how large the winning region is.
5. **Score intermediate outcomes as diagnostics.** Keep binary objective reward, alongside completion, first threatened-tower survival, deadline tower HP, unused resources and spell/attack arrival times. This distinguishes immediate tactical collapse from near-lethal conversion failures.

## Complete task coverage

| Task | Passes / 12 | Incomplete / 12 |
|---|---:|---:|
| 02-reserve-counter-a | 0 | 4 |
| 04-critical-cycle-and-connect | 0 | 0 |
| 05-hog-body-block | 0 | 4 |
| 07-balloon-fireball | 0 | 3 |
| 02-second-wave-air-race | 1 | 1 |
| 03-tower-race-b | 1 | 0 |
| 01-critical-cycle-conversion | 2 | 2 |
| 04-split-lane-conversion | 2 | 0 |
| 03-supported-tank-conversion | 3 | 4 |
| 05-successive-threats-mirror | 3 | 4 |
| 08-cycle-to-lethal-plus | 3 | 0 |
| 06-unequal-threats | 4 | 2 |
| 01-cycle-and-connect | 6 | 1 |
| 02-sustained-tower-race | 6 | 0 |
| 06-mini-pekka-kite | 6 | 1 |
| 01-timed-spell-a | 8 | 0 |
| 03-bait-damage-sequence | 8 | 3 |
| 07-counterpush | 8 | 4 |
| 09-tower-race-defend | 8 | 0 |
| 03-spell-placement | 11 | 0 |
| 10-protect-the-lead | 11 | 1 |

Reproduce the audit with `uv run python runs/royalebench-v9/analyze_failure_modes.py` using the locally cached task outputs. Reproduce the simulator probes with `uv run python runs/royalebench-v9/probe_failure_modes.py`, followed by the same command with `--mechanics`, `--aim` and `--allocation`. These commands do not call a model API or launch hosted evaluations.
