# Designing RoyaleBench tasks

How to design, build, and validate a benchmark task. Read this before adding or editing anything under `benchmarks/`. Task format mechanics follow [Harbor](https://docs.harborframework.com/tasks/overview); the working reference is [`benchmarks/smoke/elixir-check/`](../benchmarks/smoke/elixir-check/).

The track is judged on novelty, execution, difficulty, and importance ([track guide](build_eval_track.md)). A task earns its place only if a capable model can fail it for a reason that says something about the model, and our grader can tell, without doubt, whether it failed.

## Design principles

1. **Test reasoning and play, not trivia.** A task that can be answered by recalling a card stat from memory is a weak task. Prefer tasks that require combining mechanics, planning under constraints, using tools to investigate, or acting in a simulation.
2. **Verifiable by construction.** The grader computes or checks the truth. It does not ask another LLM and does not rely on a hand-written answer that might be wrong. Prefer a simulator, a rules engine, or exact arithmetic over data we typed in by hand.
3. **One clear failure story per task.** You should be able to finish the sentence "models fail this because ...". If you cannot, the task is probably noisy or too easy.
4. **Fair and fully specified.** Everything needed to succeed is in `instruction.md` or in the sandbox. A model that fails should have failed at the skill, not at guessing the output format, a hidden rule, or which game version applies.
5. **Calibrated difficulty.** Aim for tasks that a strong solution can solve (the reference solution proves this) but frontier models solve only sometimes. Consistent 100% means the task is too easy; consistent 0% means check for a broken task before declaring it hard.
6. **Quality over quantity.** A handful of validated tasks beats dozens of unchecked ones ([AGENTS.md](../AGENTS.md)).

## Choosing a task: questions to answer first

Write these down in the task's `task.toml` description or in a short design note before building:

- What capability does this isolate (e.g. elixir-trade evaluation, counter selection, spatial placement, multi-step planning, rule consistency)?
- What does a correct answer look like, and how does the verifier establish it?
- What are the cheap wrong strategies (guessing, always picking the same option, copying an example), and does the grader give them a low score?
- What is the expected failure mode of a frontier model? How will we recognize it in a trace?
- Is the outcome deterministic? If the task involves a simulator or randomness, which seeds are fixed, and is the score stable across reruns of the same answer?

### Candidate task families

These are starting points, not decisions. Pick the ones where the verifier is strongest.

| Family | Agent does | Verifier checks |
| --- | --- | --- |
| Simulation outcome prediction | Predicts the result of a fixed scenario (who wins, tower HP, surviving units) | Runs the engine and compares |
| Counter / defense construction | Chooses a defensive placement or response to a fixed attack | Simulates it and scores elixir efficiency or damage taken |
| Deck construction under constraints | Builds a legal 8-card deck meeting stated goals | Validates legality, then scores against fixed opponents |
| Elixir-trade planning | Plans a sequence of plays over a timeline | Replays the plan and scores the final state |
| Rule or mechanic probing | Uses tools in the sandbox to infer behavior, then answers | Compares with engine ground truth |
| Full-match play | Writes or controls a player for a fixed match setup | Win/crown outcome over fixed seeds |

The game engine used by the dashboard is [`royalegym`](../cr_arena/game.py). If a task depends on it, install it in the task's image at build time and pin the version so the verifier's ground truth is reproducible. Check that behavior in the image matches what the dashboard uses.

Record the player action protocol as part of the benchmark version. New win-only continuations use
[RoyaleBench Win](royalebench_win.md), using `cr play SLOT X Y` and `cr wait` through the stable
`coordinates-v1` protocol. Frozen v1 retains its numbered placement menu, and the earlier
[coordinate pilot](coordinate_harness.md) remains separate. Do not mix their scores or infer that menu reference validation proves an arbitrary
coordinate protocol works. Revalidate submission, rejection, restart and replay for each protocol.
The historical merged [v6 release](royalebench_v6.md) merges unchanged v5 and win@2 packages;
retain each source's objective and packaged runtime when reproducing that merge.
The separate [v7 challenge cohort](royalebench_v7.md) ends its scoring windows before
the overtime deadline, so every successful continuation must take a crown. Keep
its scores distinct from v6's mixture of defensive objectives and match wins.
The default [v8 merge](royalebench_v8.md) preserves all 18 v6@1 and v7@1 packages
and weights each source-task binary objective equally. Its aggregate score is
objective success, not an all-task match-win rate.

For the harder [RoyaleBench Win](royalebench_win.md) cohort, every gameplay objective is
an actual terminal match win. Do not award success for merely surviving a short window,
remaining within a spending budget, or leading on HP before the match ends. Require a
winning reference and failing cheap-policy controls before packaging each new position.

## Task levers

Every game-based task is a point in a space defined by three levers. Choose them deliberately, state them in `instruction.md`, and record them in the task's `task.toml` description so a result can be traced back to its setup. Vary one lever at a time when comparing tasks, so a difference in model performance has an identifiable cause.

The engine (`royalegym`, wrapped by [`cr_arena/game.py`](../cr_arena/game.py)) is deterministic: the same decks, seed, and sequence of commands give the same game. Reproducibility therefore depends on pinning the levers below, not on the engine.

### 1. Time left in the game

A match is 180 s of regular time followed by up to 120 s of overtime (3600 and 2400 ticks of 50 ms). `Game.time_left_s()` reports time left and whether overtime has started. Elixir regenerates faster late in the match (`elixir_rate` is above 1 in the last minute and in overtime), and overtime is sudden death: the next tower destroyed wins.

Time left changes what the right answer is, not just how hard it is:

| Phase | What it tests |
| --- | --- |
| Early (full time left) | Opening plays, elixir discipline, information gathering about the opponent's deck |
| Mid-game | Defending efficiently, counter-pushing, trading elixir |
| Final minute (double elixir) | Adjusting to faster elixir, committing to or defending a last push |
| Overtime (sudden death) | Risk assessment: a crown ends the game, so defending and tempo dominate |

State the time left in the instruction as a number and say whether the elixir rate is boosted. Tasks that start with little time left are cheaper to run (short simulation) and have a sharper correct answer, so they suit verifiers that replay a game to the end. Decide whether to score a full game, a fixed window (for example the next 30 s), or the result at timeout, and say which.

### 2. Game state

The state the agent starts from. The levers inside it:

- **Player deck and opponent deck.** Eight distinct cards each. Presets are in `CLASSIC_DECKS` in [`cr_arena/decks.py`](../cr_arena/decks.py) (giant-beatdown 3.38 average elixir, hog-2.6-cycle 2.62, lavaloon 3.75, log-bait 3.25, golem-beatdown 4.0, xbow-cycle 3.0, pekka-bridge-spam 4.0); the legal card pool is `POOL` there, and `validate_deck` rejects duplicates and unknown cards. Name the deck in the task (preset name or the card list) instead of describing it loosely.
- **Average elixir cost.** The sum of the eight card costs divided by eight. It sets the tempo: cheap cycle decks (hog-2.6-cycle averages 2.62) can cycle cards much faster than heavy decks (golem-beatdown and pekka-bridge-spam average 4.0), so the same board position needs different answers. Compute it from the engine's card table instead of typing it by hand, and report it for both decks. It is also a confound, since matchups between decks of very different cost differ in difficulty for reasons unrelated to the skill being tested. When you want to test deck-independent skill, use mirrored or matched-cost decks.
- **Deck strength.** A stronger deck makes a match easier independently of tempo and archetype. [`data/deck_strength.csv`](../data/deck_strength.csv) and [`data/deck_matchups.csv`](../data/deck_matchups.csv) track CrownScribe win rates (Ladder and Ranked since the Oct 19, 2026 patch) for the archetype each classic deck belongs to, and `uv run python -m cr_arena.deck_strength` prints the rankings and the head-to-head matrix. To choose a deck by difficulty:
  - Strength within the set is each deck's mean win rate against the other six; decks in one tier cannot be told apart. Tier 1: giant-beatdown 53.7%, log-bait 52.2%. Tier 2: pekka-bridge-spam 52.1%, golem-beatdown 50.5%. Tier 3: hog-2.6-cycle 47.5%, xbow-cycle 47.4%, lavaloon 46.5%. The tier 3 decks sit 2.9 to 7.1 points below the other four, which span 3.2 points between them.
  - For a pair, read the matrix in [`data/README.md`](../data/README.md#head-to-head-within-the-set): the row deck's win rate is how favourable the matchup is for the agent when it plays that deck. Golem against xbow-cycle is 67.3% for golem, an easy task, and 32.7% for xbow-cycle, a hard one.
  - Rank is only a rough guide. The decks beat each other in cycles (lavaloon, the weakest, beats hog-2.6-cycle 56.5% of the time), so check the pair. A mirrored match cancels strength, which is why the giant-beatdown match tasks do not vary it.
  - The numbers are real-game win rates for the archetype, not our exact eight cards (golem-beatdown does not even contain its archetype's Night Witch), this engine's ~2018 card balance or a heuristic-bot opponent, so confirm a chosen gap by simulation before relying on it.
- **Archetype matchup.** Beatdown, cycle, bait, bridge spam, and siege decks create different strategic problems. Choose matchups that create the situation you want to test, and check by simulation that neither deck is hopeless in it.
- **Board position.** Elixir held by each side, hand and next card, tower HP and crowns, and units on the field with HP and position. The v3 view includes time, crowns, elixir, tower HP, indexed hand slots, enemy cards seen, units and recent events. The numbered placement menu belongs to historical menu tasks.
- **Hidden information.** The model sees only what a real player sees: it does not see the opponent's hand or elixir. The reference bots below are not subject to this limit.
- **Randomness.** The match seed.

Two ways to build a non-trivial starting state, both reproducible:

1. **Scripted prefix.** Start a game with fixed decks and seed, apply a fixed list of commands for both sides up to a chosen tick, and hand the agent the resulting state. This is simple, transparent, and easy to audit.
2. **Saved engine state.** `RustEngine.save_state()` and `load_state()` capture and restore an exact position. Use it for hand-picked positions and for checking that the verifier and the agent's tools start from identical states. Commit the state file with the task (under `tests/` if the answer can be derived from it).

Whatever is chosen, the instruction must describe the state fully enough that a model can reason from it, or the sandbox must give the model the same view the game gives a player.

### 3. Opponent

Bots are the opponents. Each has a fixed, known behavior, which is what makes results comparable across models. They differ a lot in strength:

| Bot | Behavior | Information | Use it for |
| --- | --- | --- | --- |
| `random-bot` | Picks a random legal move | Legal moves only | Sanity floor; a model must beat it clearly |
| `heuristic-bot` | A few readable rules: spell clusters of 3 or more, defend the threatened lane cheaply, attack with the most expensive troop once elixir is 8 or more | Own view | Easy opponent whose weaknesses can be exploited deliberately |
| `search-bot` | Tries every legal move on a copy of the engine, with sampled opponent replies and a short look-ahead (rollouts and horizon are tunable; the shipped config uses 4 rollouts and 12 s) | True engine state, including the opponent's hand and elixir | Strong reference opponent on the same numbered move list the models use |
| `planner-bot` | Looks about 10 s ahead exactly on a private engine copy, considers the opponent's best reply, plays only if it beats waiting | True engine state | Strongest opponent; made for live play |

Notes for choosing an opponent:

- **Opponent strength sets the difficulty.** Beating `random-bot` is a floor check. Matching `search-bot` is hard. Choose the opponent so the task is solvable but not trivial, then confirm with real runs.
- **Opponent fixes the failure story.** A task against `heuristic-bot` can test whether the model finds and exploits its rules; a task against `search-bot` tests general play quality. Say which one you intend.
- **Reproducibility.** `random-bot` and `search-bot` take a seed, so record it. `planner-bot` and `search-bot` read the true state, so they have an information advantage over a model; this is a legitimate part of the difficulty but must not be described as a fair fight.
- **Seat and deck luck.** Sides and decks matter. When scoring games, play each pairing from both sides, as `cr_arena/duel.py` does, or average over several fixed seeds.
- **Bots in the sandbox.** If the opponent runs inside the sandbox, its code and its deck are readable by the agent. That is acceptable only when reading it is not a shortcut to the answer; otherwise the verifier should run the opponent outside the agent's reach. Pin the bot code and the `royalegym` version in the image.

### Combining levers

Record each task as a tuple, for example in the `task.toml` description:

```
time_left=0:45 (double elixir) | player=hog-2.6-cycle (avg 2.62) | opponent_deck=giant-beatdown (avg 3.38) | opponent=search-bot | seed=7 | scoring=crown diff at timeout
```

Guidelines:

- Prefer a small grid over many one-off tasks, for example three time phases by two opponents on the same decks, so the results show which lever causes failure.
- Keep at least one lever fixed across a family of tasks, and say which one.
- A task should still isolate one capability. Several levers moving together make a failure impossible to attribute.
- Check that the correct answer is not the same for every setting of a lever. If the best play is identical regardless of time left or opponent, the lever is decoration and the task is redundant.

## Task layout

Tasks live in `benchmarks/<benchmark>/<task-id>/`. A folder with a `task.toml` is a task, and the folder name is the task id. `benchmark.toml` in the parent folder holds display metadata only. **Never add a `dataset.toml`**: Valkyrie treats it as a digest lock that freezes the task list.

```
benchmarks/<benchmark>/
  benchmark.toml          # title, description, kind = "eval" (or "smoke")
  <task-id>/
    task.toml             # name, description, metadata, timeouts, resources
    instruction.md        # what the agent sees
    environment/
      Dockerfile          # sandbox image; add task files here (COPY)
    tests/
      test.sh             # verifier; writes the reward
    solution/
      solve.sh            # reference solution; never visible to the agent
```

All shell scripts and the Dockerfile must use **LF** line endings (CRLF breaks them in Linux sandboxes). The repo enforces this, but check after editing on Windows.

### `task.toml`

```toml
schema_version = "1.4"

[task]
name = "royalebench/<task-id>"
description = "One sentence: capability tested and how it is graded."

[metadata]
category = "<family>"
difficulty = "easy | medium | hard"   # our estimate; revise after real runs

[agent]
timeout_sec = 600.0

[verifier]
timeout_sec = 120.0

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
```

Set timeouts from what the task needs, with headroom. Keep `cpus`, `memory_mb`, and `storage_mb` identical across models in a comparison. Keep real tasks distinct from smoke tests by `kind` in `benchmark.toml`; smoke tasks are excluded from reported results.

For published packages, revise dashboard difficulty labels with a
`[task_difficulties]` table in the parent `benchmark.toml`, mapping task IDs to
`easy`, `medium` or `hard`. Record the observed attempts, passes, thresholds
and capture time alongside the benchmark evidence. The override changes display
metadata without editing task bytes or invalidating source digests. Tasks
without an override retain their `task.toml` difficulty. See the
[v9 calibration](royalebench_v9.md#difficulty-calibrated-from-observed-pass-rates).

## Writing `instruction.md`

The instruction is the entire interface. Write it so that a careful human could complete the task with no other information.

- State the scenario with concrete numbers and fixed rules: card levels, arena level, elixir rate, starting elixir, timing, and the game version or engine if relevant. Hidden assumptions are the most common cause of unfair failures.
- State exactly what to produce, **where** (for example `/app/answer.json`), and in **what schema**, with an example of the shape (not the answer).
- Say that creating the file is required: "a chat response alone does not complete the task."
- State any limits on what the agent may use or modify.
- Do not hint at the answer or describe the verifier's internals beyond what the agent needs to produce a valid output. Do tell the agent how it is scored if that affects strategy (for example "score is crowns won over 5 fixed seeds").
- Keep it short. Length that does not carry information makes the task harder for the wrong reasons.

Prefer a structured answer file (JSON) over free text. If free-text reasoning matters, require it separately and do not grade it by string matching.

## Writing the verifier (`tests/test.sh`)

The verifier runs after the agent finishes and writes a reward to `/logs/verifier/reward.txt` (a single number) or `/logs/verifier/reward.json`. Follow the pattern in [`elixir-check/tests/test.sh`](../benchmarks/smoke/elixir-check/tests/test.sh).

- **Always write a reward, even on failure.** Missing file, malformed JSON, wrong type, extra keys: reward 0, and no crash. A crashed verifier is an infrastructure error, not a model failure, and corrupts the results.
- **Be strict on schema, tolerant of irrelevant variation.** Reject wrong types and unexpected keys if the instruction specified them. Do not reject for whitespace, key order, or trailing newlines.
- **Compute ground truth in the verifier**, from the engine, rather than shipping a fixed expected value that could drift. If a fixed expected value is correct (pure arithmetic, a fixed scenario), store it only under `tests/`, never in the agent's environment.
- **Use partial credit deliberately.** Binary reward is simplest and easiest to defend. Use graded reward (0 to 1, or several keys in `reward.json`) only when intermediate quality is meaningful and the scale is documented in the task description. Never let partial credit reward a degenerate answer.
- **Deterministic.** Fix seeds. Run the verifier on the same answer repeatedly and confirm the same reward. Where unavoidable randomness exists, average over fixed seeds inside the verifier.
- **Set the `PYTHONHASHSEED`, locale, and library versions** through the image rather than relying on the host.
- **Fast.** Stay well inside `verifier.timeout_sec`.
- Print a one-line summary of the score and the reason to stdout. It makes traces much easier to read.

## Preventing shortcuts and leaks

- The agent must not be able to read `tests/`, `solution/`, or any file containing the expected answer. Do not `COPY` them into the image. Harbor supplies `tests/` to the verifier only after the agent finishes; confirm this in the current Harbor docs for the version in use.
- Do not put the answer in file names, comments, git history, environment variables, or default config inside the image.
- The track recommends **no public internet access** for agents, so models cannot look up answers. Bake everything the task needs into the image at build time. Check the current Harbor and Valkyrie docs for how to disable network access and confirm that the setting is applied.
- Try to beat your own task. Ask: could the agent satisfy the verifier without doing the intended work (hard-coding a common answer, writing a trivially valid output, editing the verifier's inputs)? If so, tighten the verifier or the environment.
- If the agent can run code against the engine, decide whether that is intended. Tool use is fine when it is the skill being tested; it is a leak if the engine exposes the answer directly.

## Environment

- Start from the smoke Dockerfile (`python:3.12-slim-bookworm`, `WORKDIR /app`) and add only what the task needs.
- Pin versions of every dependency, including `royalegym`.
- Put any task inputs under `/app` and say so in the instruction.
- Keep images small and builds fast: each run builds or pulls the image on Modal, and `build_timeout_sec` applies.
- Do not depend on a secret or private network resource inside the task. The agent harness gets only the model key.

## Validating a task

A task is not done until it passes all of these. Record the result of each in the task folder or PR description.

1. **Static checks.** `task.toml` parses, `instruction.md` is non-empty, `tests/test.sh` writes a reward, scripts use LF, there is an agent timeout. The dashboard's task checks (`rb_evals/benchmarks.py: task_problems`) flag the most common problems.
2. **Reference solution scores full reward.** Run `solution/solve.sh` through the same path the agent would use and confirm the verifier gives the maximum reward. This proves the task is solvable and the verifier agrees with the intended answer.
3. **Do-nothing scores zero.** Run the verifier with no answer file. Also try a malformed file, a wrong type, and a plausible-but-wrong answer. Each must score low and none may crash the verifier.
4. **Verifier is deterministic.** Same answer, repeated runs, same reward.
5. **Run a real model on one task.** Use a single-task Valkyrie run (`--slice 0:1 --concurrency 1`) with a frontier model first, as in the [Valkyrie guide](valkyrie_guide.md). Cost is small and it catches most setup problems.
6. **Read the trace.** For every failure, decide whether it is:
   - a **genuine model failure** (wrong reasoning, bad plan, ignoring a constraint): keep it and note it as a failure example for the README; or
   - a **task defect** (ambiguous instruction, undocumented rule, format the model could not have known, verifier bug, infrastructure error): fix the task, bump the dataset version, and rerun.
   Also read some **successes**, to check they succeeded for the intended reason and not by a shortcut.
7. **Check difficulty.** After a few runs, a task that every model always passes needs to be made harder or dropped. A task that every model always fails needs a second look for defects before it is declared hard.

Only after a task passes these checks should it be included in a scaled run.

## Publishing and versioning

- Published datasets are immutable revisions. Any change to a task (instruction, verifier, environment) means a new tag or version, and runs must say which revision they used.
- Push with `valkyrie dataset push royalebench/<name> ./benchmarks/<name> --tag vN`, then run against the revision it returns. See the [Valkyrie guide](valkyrie_guide.md).
- Compare models only on the same dataset revision, harness, resource limits, and verifier.
- Do not mix smoke tasks into the benchmark dataset.

## Task checklist

Copy this into the PR description for each new task.

- [ ] Isolates one named capability; not answerable by recall alone
- [ ] `instruction.md` fully specifies scenario, rules, answer path, and schema
- [ ] Verifier computes or checks truth objectively; no LLM judge
- [ ] Verifier always writes a reward and never crashes on bad input
- [ ] Deterministic scoring (fixed seeds, pinned versions)
- [ ] Answer, tests, and solution are not visible to the agent; no internet
- [ ] Reference solution gets full reward; empty and malformed answers get zero
- [ ] Ran at least one frontier model and read the trace
- [ ] Failures classified as model failures vs task defects, defects fixed
- [ ] LF line endings; `task.toml` complete with timeouts and resources
- [ ] Dataset revision recorded with the run results
