# Handoff: trained hog-2.6-cycle bot (RoyaleLearn PPO), how to test and play it

Written 2026-11-15. Source: `RoyaleBench-hog-2.6-final.zip` (205 MB, from the training PC; keep it out of git, it is
over GitHub's 100 MB file limit). It was unpacked read-only into a scratch folder; nothing from it was executed.

## What the archive is

- 21 resumable checkpoints and 10 frozen actor snapshots for **hog-2.6-cycle** (RoyaleLearn 0.5.20, RoyaleGym 0.1.28, PPO self-play ladder).
- Metrics, evals, logs and `train/RESULTS.md` (the authoritative report; read it first).
- Configs for giant-beatdown and lavaloon, **not trained** (no weights exist for them).
- Best checkpoint: `runs/train/hog-2.6-cycle/hog-2.6-cycle-smoke-b3b4cf3d5a61852e/checkpoints/000005253120`
  (7,879,680 learner steps). Frozen snapshot weights are in `snapshots/<digest>/actor.safetensors` (index: `snapshots/index.json`).
- Training stopped at about 8.2M of the 10M target after the PPO importance-ratio guard failed three times
  (0.0203 and 0.025 vs a 0.02 tolerance). Cause not established.

## How strong it is (measured by the trainer, `train/RESULTS.md`)

| Opponent | Result for the best checkpoint |
|---|---|
| `scripted:noop` | 40/40 wins |
| `scripted:random_legal` | 22/200 = **11.0%** (95% interval 7.0 to 15.5%); untrained start was 3.5% |
| `scripted:defend` (simple heuristic) | 7/40 = 17.5% (interval 7.5 to 27.5%), only 20 paired seeds |

It improved over its untrained start, but **it loses to a random-move opponent about 89% of the time**. It is not a strong
bot, and it has not been measured against our Planner, the search bot, or any LLM. Treat it as a "weak trained baseline",
not as a gold-standard opponent.

## Can it be played now? No: there is no adapter

`RESULTS.md` says it directly: "The tournament adapter is not implemented yet." Nothing in `cr_arena` loads these weights.
The live game (`python -m cr_arena.live`) and the tournament drive bots through the `Player.decide` interface, and the
policy needs RoyaleGym observations and masks, not our text moves.

What an adapter has to do (the pieces exist in the installed `royalelearn` package, `.venv/.../royalelearn/ladder/actors.py`
and `coordinator.py::EnvBattlePlayer`):

1. Rebuild the env spec from the run's `config.json` and load the actor from `actor.safetensors` with `arch.json`
   (verify the snapshot's compatibility digests in `spec.json`).
2. Build the **fair** observation (`SpatialObsBuilder`, enemy hand hidden) from the live engine state every 500 ms.
   The builder keeps match memory (what the enemy has played), so it must see every step, not only the decision points.
3. Run the actor, mask illegal actions, take the highest-probability or sampled action, and convert the tile index to a deploy
   at the tile center. The policy decides every 500 ms; our live mode uses a ~1 s command delay.
4. Wrap that as a `Player`, register it in `cr_arena/bots/registry.py` and `configs/bots.toml`.

Open risks: memory/observation alignment with our `Game` wrapper (it steps the engine on its own schedule), CPU-only
PyTorch on a Mac (fine for one forward pass per decision), and the engine/version pins (RoyaleGym 0.1.28, RoyaleSim 0.1.48,
pinned in `uv.lock`; the archive's `uv.lock` matches the repo's).

## Cheapest ways to look at it without the adapter

- Watch the training run's own episodes: `episodes.jsonl` and the replay recorder in RoyaleGym (`royalegym/replay.py`,
  `viser.py`). `RESULTS.md` says the Viser sink was disabled in training, so replays have to be regenerated.
- Re-run the trainer's evaluator on the PC: `train/eval_checkpoint.py --run ... --checkpoint ... --opponent scripted:defend`.
  It needs the CUDA install described in `RESULTS.md`; the PC used an RTX 5060 Ti.

## Paste-in prompt for a teammate's Claude Code session

> Read `docs/handoff_hog_bot.md` and `train/RESULTS.md` from the unpacked RoyaleBench-hog-2.6-final archive. Goal: let a
> human play against the trained hog-2.6-cycle checkpoint through `python -m cr_arena.live`. First write a small
> script that loads `checkpoints/000005253120` and plays one full game against `scripted:random_legal` through the
> RoyaleLearn env, to prove inference works on this machine (CPU is fine). Then write a `Player` adapter in
> `cr_arena/bots/` that builds the fair observation from the live `Game` engine each step, runs the actor with the action
> mask, and returns a coordinate move; register it in `bots/registry.py` and `configs/bots.toml` as `hog-rl`. Do not edit
> shared referee files (`scenario_task.py`, `royale_task.py`, `game.py`, `bots/planner.py`) because the published benchmark
> packages are pinned to their hashes. Report plainly if the observation memory cannot be kept consistent with our
> `Game` wrapper, and measure the bot against `random-bot` and `planner-bot` before calling it playable. Do not push
> or publish the weights.

## Not verified

- No checkpoint was loaded or run in this session.
- The archive's `SHA256SUMS.txt` and the adjacent `.zip.sha256` were not checked.
- Nothing has been compared with the Planner, search bot or an LLM.
