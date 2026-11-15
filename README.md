# RoyaleBench: Can language models win at Clash Royale?

> **Team action before submission:** replace this note with an entirely human-written, one-paragraph overview of the benchmark and its findings. The hackathon requires that paragraph at the top of this README.

RoyaleBench evaluates decisions in a deterministic Clash Royale simulator. An agent sees a paused mid-match position, plays a card at board coordinates with `cr play SLOT X Y`, or advances time with `cr wait`. The verifier independently replays its actions against a fixed opponent and scores the stated objective. Tasks test placement, timing, elixir discipline, defense, and conversion into tower damage.

## Submission dataset

**[RoyaleBench v9](docs/royalebench_v9.md)** is the 21-task submission dataset, published as `royalebench/royalebench-v9@1` (digest `sha256:e9e4396c2792964e4246eeb1002a6f4d8b2f72ba0b697be6c807f967be87ecc2`). Its task packages are in [benchmarks/royalebench-v9](benchmarks/royalebench-v9). It combines 18 unchanged v8 tasks with three Tactics defenses: a one-hit Hog body block, a Mini P.E.K.K.A. kite, and Fireball knockback against a Balloon.

The score is the mean of 21 binary objective rewards. Twelve tasks require a completed match win; nine have explicit spell, defense, or lead-protection goals. **The aggregate is objective success, not match win rate.** Each task fixes the starting state, opponent, decision window, permitted actions, and grader. The agent cannot read the protected reference solution. See [task design](docs/task_design.md), [source provenance](benchmarks/royalebench-v9/manifest.json), and [release checks](runs/royalebench-v9/checks.json).

All 21 reference solutions pass exact-package replay validation, and all 63 invalid-input controls score zero. The dashboard can play every validated resolution. These checks establish task operation and solvability; they do not measure model performance.

## Model results and failure examples

Twelve models completed the same published **RoyaleBench v9@1** dataset, with one full 21-task run per model. All 12 runs returned 21 graded task results, passed replay integrity on all 21 tasks, and reported no run errors. Across the 252 attempts, agents completed 218 tasks; 34 unfinished tasks received zero objective reward and remain in the denominator. The runs used concurrency 21. The mean objective success was **91/252 (36.1%)**; individual model scores ranged from 2/21 to 14/21. The full record contains the exact run IDs, per-task scores, completion counts, exclusion of a stopped duplicate run, and representative action sequences in [model-results.json](runs/royalebench-v9/model-results.json).

| Model | Harness | Objective success | Game wins |
| --- | --- | ---: | ---: |
| Claude Opus 5.5 | Claude Code | **14/21 (66.7%)** | 10/21 |
| Claude Fable 5.2 | Claude Code | 13/21 (61.9%) | 8/21 |
| GPT-6.1 Sol | Codex | 12/21 (57.1%) | 7/21 |
| Claude Fable 5.1 | Claude Code | 11/21 (52.4%) | 8/21 |
| GPT-6 Astra | Codex | 10/21 (47.6%) | 6/21 |
| Claude Sonnet 5.5 | Claude Code | 7/21 (33.3%) | 5/21 |
| GPT-6 Luna | Codex | 7/21 (33.3%) | 5/21 |
| Claude Haiku 5.5 | Claude Code | 4/21 (19.0%) | 3/21 |
| Inkling 2 Small | mini-SWE-agent | 4/21 (19.0%) | 3/21 |
| Kimi K3.1 Pro | mini-SWE-agent | 4/21 (19.0%) | 6/21 |
| Qwen 3.8 2.4T A95B | mini-SWE-agent | 3/21 (14.3%) | 2/21 |
| DeepSeek V4.1 Flash | mini-SWE-agent | 2/21 (9.5%) | 2/21 |

“Game wins” is the verifier’s match-win metric; it is separate from objective success. A match win can still fail a task’s spell, damage, survival, or resource constraint. For example, Kimi recorded six match wins but four objective successes. Since the runs used three harnesses and each model had one attempt, this is a comparison of these model-and-harness setups, not a controlled model-only ranking.

The results expose shared hard cases: none of the 12 models passed `02-reserve-counter-a`, `04-critical-cycle-and-connect`, `05-hog-body-block`, or `07-balloon-fireball`. By contrast, `03-spell-placement` and `10-protect-the-lead` each passed 11/12 times. These are single-run calibration results, not estimates of repeated-run performance.

Representative outcomes from the downloaded referee records:

- **Hog body block:** Opus used Ice Golem and Skeletons, spending the allowed three elixir, but the tower took 635 additional damage and fell. The attempt passed replay integrity and scored 0.
- **Balloon Fireball:** Opus played one Fireball for four elixir. Total tower damage was 241 HP against a 240 HP limit, so the task scored 0 despite a valid replay.
- **Second-wave air race:** GPT-6.1 Sol used Cannon, Minions, Fireball, and Musketeer, then won 1–0 in 11.1 seconds. The task scored 1 with replay integrity 1.

The record includes the run IDs and the accepted card placements for all three examples. Valkyrie retains full task artifacts; for example, retrieve an agent trace with `valkyrie run output RUN_ID TASK_ID/agent_output.tar.gz`.

## Run the benchmark

The published v9 release is ready to run with Valkyrie and Modal. After [setting up the team organization and a model secret](docs/valkyrie_guide.md), start with one task:

```bash
valkyrie run start \
  --agent claude_code-v1.0.0 \
  --dataset royalebench/royalebench-v9@1 \
  --model anthropic/claude-opus-5-5 \
  --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your Valkyrie secret name}" \
  --slice 0:1 --concurrency 1 --connect
```

Remove `--slice 0:1` for a full 21-task run. Record the immutable dataset revision, model, harness, concurrency, run ID, score, and representative traces. Use the same dataset revision and protocol for comparisons. The local dashboard starts with `uv run python -m rb_server`; its new-job page now selects v9. Build and container-validation instructions are in the [v9 guide](docs/royalebench_v9.md).

## Repository map

- [benchmarks/royalebench-v9](benchmarks/royalebench-v9): submission Harbor tasks and manifest.
- [cr_arena](cr_arena): simulator interface, task packaging, verifier support, and reference playback.
- [rb_evals](rb_evals), [rb_server](rb_server), [web](web): evaluation service and dashboard.
- [runs/royalebench-v9](runs/royalebench-v9): compact validation and resolution evidence; [runs/README.md](runs/README.md) explains artifact retention.
- [demo](demo/README.md): 67-second Remotion edit, local MP4 export, and evidence record. The public video link is pending.
- [docs/royalebench_v9.md](docs/royalebench_v9.md): scoring, exact source packages, validation, and publication. Earlier version guides preserve development provenance.

## Limitations

The simulator is a pinned approximation of Clash Royale, and the bot has access to true engine state. Agent thinking pauses the game. Each model has one attempt and the runs use different harnesses, so this cohort gives a first difficulty comparison rather than a stable cross-model ranking.

Built on RoyaleGym/RoyaleSim, with Valkyrie evaluation and Modal sandboxes. [Track requirements](docs/build_eval_track.md). Team credits and the public demo video link should be added by the team before submission.
