# Handoff: RoyaleBench v7 (Crown tasks) and Opus-failure expansion

Written 2026-11-15 by a Claude Code session working with Ojas. The session could not log in to Valkyrie, so
everything below that needs Valkyrie, Modal or an API key is **not done**. Nothing has been published and no API
money has been spent by this work.

## Goal (from Ojas)

1. Grow RoyaleBench v6 (14 tasks) to **at least 20 tasks** as **v7**.
2. The new tasks should be hard: **Opus 5.5 should fail at least 4 of the 6 new ones consistently**.
3. Use **Sonnet 5.5 and Haiku 5.5 as baselines** (run both, concurrently).
4. New axis: **mirror decks** and **king-tower kills** (three-crown wins, and a duel where neither side has princess towers).
5. Verify everything. Record the harness, model, dataset version and run IDs.

## What exists now

Work is in the repo at `cr_arena/crown_benchmark.py` (new, uncommitted) and `runs/royalebench-crown/` (new, uncommitted
calibration evidence). No shared runtime file was changed.

### Design decision: no grader change

The packaged win tasks are pinned to the hash of `cr_arena/scenario_task.py` and friends
(`tests/test_win_benchmark.py` checks it). Editing the shared referee breaks that test, so a `three_crown` grading
rule was tried and **reverted**. Instead the new tasks use the unchanged "completed match win" rule with a window that
ends **before regulation does**. Then the match can only be over with Blue winning once the enemy king tower has
fallen, so a win equals a king kill. Keep this property: `add()` asserts `horizon_s <= left_s`.

### The four tasks (dataset `royalebench-crown`, ids 11 to 14)

| ID | Decks | Start (regulation left / window) | Elixir me/opp | Position | Status |
|---|---|---|---|---|---|
| 11-giant-mirror-three-crown | giant-beatdown mirror | 110 s / 105 s | 7 / 4 | Enemy princess towers at 50% and 60% HP, own Giant+Musketeer push in the left lane | calibrated |
| 12-golem-mirror-three-crown | golem-beatdown mirror | 75 s / 70 s | 7 / 4 | Enemy princess towers 50% and 60%, own Golem+Musketeer push | **FAILS a control, see below** |
| 13-giant-mirror-king-only | giant-beatdown mirror | 110 s / 105 s | 8 / 3 | No princess towers on either side, own Giant in the left lane | calibrated |
| 14-golem-mirror-king-only | golem-beatdown mirror | 75 s / 70 s | 7 / 5 | No princess towers, own Golem in the right lane | calibrated |

"Calibrated" means: a winning reference log from the privileged Planner, replayed twice with identical results, and the
negative controls (wait, spell-rush, empty, malformed, wrong-type, partial) all scoring 0. Evidence is in
`runs/royalebench-crown/<task id>/validation.json`.

### The known problem: task 12 is too easy

The cheap `spell-rush` control also wins task 12 as written, so `calibrate()` raises
`replay or difficulty controls failed`. A six-variant sweep found a fix, **not yet applied** (the edit was declined
mid-session):

- Change task 12's enemy princess HP fractions from `(.5, .6)` to `(.65, .75)`, keeping elixir 7 / 4.
- With that, the Planner wins and `spell-rush` does not (also fine: `(.65,.75)` with elixir 6/6, `(.8,.9)` with 7/4).
- Rejected variants: `(.5,.6)` at 6/6 and 7/6 (spell-rush wins, Planner doesn't), `(.65,.75)` at 8/5 (neither wins).

The edit: in `cr_arena/crown_benchmark.py`, the `add(12, ...)` call, replace `(.5, .6)` with `(.65, .75)`. Then:

```bash
uv run python -m cr_arena.crown_benchmark --calibrate --tasks 12
```

Note: the spell-rush control is noisy near these thresholds. Check that it still fails after any edit.

### Planner results that shaped the positions (the Planner is the reference, not a difficulty measure)

- Full towers, even elixir: the Planner could not three-crown in 180 s from either mirror.
- Strong leads (enemy princess towers at 20 to 35%): it wins in seconds, so those positions are too easy.
- The middle band (50 to 75% HP, push on the board) is where tasks 11 to 14 sit.
- Seeds do not change the Planner's play in these positions.
- Whether Opus fails any of these is **unmeasured**; the Planner winning says nothing about that.

## Steps to finish (in order)

### A. Local (no accounts needed)

```bash
git fetch origin && git checkout -b v7-crown origin/main
# bring crown_benchmark.py and runs/royalebench-crown/ onto this branch (see "Getting the code" below)
uv sync
# apply the task 12 fix above, then:
uv run python -m cr_arena.crown_benchmark --calibrate --jobs 4     # all four must pass
uv run python -m cr_arena.crown_benchmark --build                  # writes benchmarks/royalebench-crown/
uv run --with pytest python -m pytest -q tests/test_win_benchmark.py tests/test_royalebench_v6.py tests/test_royale_task.py tests/test_coordinate_task.py
```

The tests must still pass (they check the older win and v6 packages are byte-identical to their pinned digests).
Also validate in Docker the way v6 does: see `cr_arena/validate_v6_docker.py` and copy its approach for the crown tasks
(`uv run python -m cr_arena.validate_v6_docker --jobs 4` shows the pattern; it needs Docker running).

### B. Valkyrie setup (needs a real login, a human in a browser)

```bash
uv tool install valkyrie-cli
valkyrie login
valkyrie org use hackathon-rip-ojas-e8d933c926
valkyrie provider list          # Modal should already be connected for the org; if not, see docs/modal_guide.md
valkyrie secret list            # reuse a teammate's Anthropic secret if one exists
export VALKYRIE_ANTHROPIC_SECRET="anthropic-api-key-<yourname>"
valkyrie secret set "$VALKYRIE_ANTHROPIC_SECRET"   # hidden prompt for the key; skip if it already exists
```

Details: `docs/valkyrie_guide.md`, `docs/valkyrie_smoke.md`, `docs/modal_guide.md`. Do a one-task smoke run first
(`--slice 0:1 --concurrency 1`) before the full run.

### C. Publish and run the baselines (Sonnet 5.5 and Haiku 5.5, concurrently)

```bash
valkyrie dataset push royalebench/royalebench-crown ./benchmarks/royalebench-crown --tag v1

for MODEL in anthropic/claude-sonnet-5-5 anthropic/claude-haiku-5-5; do
  valkyrie run start --agent claude_code-v1.0.0 \
    --dataset royalebench/royalebench-crown@v1 \
    --model "$MODEL" --provider modal \
    -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?set it}" \
    --concurrency 4 --label "crown-${MODEL##*/}" &
done; wait
```

Confirm the exact model ids with `valkyrie model list` (or the dashboard's model presets) before running. The harness
and flags above come from the repo docs (`docs/match_tasks.md`, `docs/valkyrie_guide.md`); the other published runs used
`claude_code-v1.0.0` on Modal. Do **not** pass `--connect` for background runs. Watch with `valkyrie tui`.

Cost: unknown for these tasks. The earlier six full-match Sonnet 4.6 runs cost $15.92 total. Run one task per model
first and read the cost before scaling.

### D. The Opus check, the real goal

Run **Opus 5.5** (`anthropic/claude-opus-5-5`) on the same dataset, with **3 attempts per task**. A task is a nominated
"hard" task if Opus wins 0 of 3. Confirm with **5 fresh attempts** (different attempt IDs; the seeds are fixed by the
task, so this measures model variance only). Keep a task as "consistently failing" if Opus wins at most 1 of 5.

Before counting a failure, read the trace. Discard tasks where the failure comes from the harness (rejected actions,
timeouts, misread coordinates, format errors), not from strategy. The README for v6 notes earlier runs had zero
rejected actions, so rejections are a warning sign.

### E. Reach 20 tasks (v7)

Current count: v6 = 14, plus 4 crown tasks = 18. Two more are needed, ideally from these (pick ones Opus fails):

- **Balloon tower race, flipped lanes**: the pattern of `02-sustained-tower-race` mirrored left to right, shifted elixir.
  Opus lost the Balloon tower race in the Win cohort.
- **Critical-health defense, other lane**: the pattern of `04-critical-cycle-and-connect` in the opposite lane with a
  different cycle position. Opus lost this too.
- Spares: three-crown log-bait mirror, golem-beatdown vs lavaloon tower race.

Before designing them, read the actual failing Opus traces (Valkyrie run archives, or `runs/royalebench-win/` and
`docs/royalebench_win.md`, `docs/royalebench_v5.md`). Do not assume the cause. Build candidates the same way as the crown
module (copy `crown_benchmark.py` or `win_benchmark.py`, new catalog, run `--calibrate`), aim for about 10 candidates,
and keep those that pass validation and fail on Opus. At least 4 of the 6 new tasks should consistently fail on Opus.

Then build v7 as a merge: the 14 unchanged v6 task packages (copy them byte-for-byte from `benchmarks/royalebench-v6/`,
as `cr_arena/build_v6.py` does) plus the 6 new packages, with a manifest recording each source and digest. Task ids must
not collide with the existing ones. Write `docs/royalebench_v7.md`, `tests/test_royalebench_v7.py` (copy
`tests/test_royalebench_v6.py`), push the dataset as `royalebench/royalebench-v7@1`, and update `README.md`
and the documentation index in `AGENTS.md`.

### Things to disclose in the README

- The new set was **selected adversarially** because Opus fails it. Say so, and run at least one other model family (GPT-6.1 Sol or Gemini if credits allow) so "hard" is not "Opus-specific noise".
- References come from a privileged Planner that sees the true state (both hands and elixir); models do not.
- The king-tower kill is enforced by window design (the window ends before regulation), not by a dedicated grader.

## Getting the code

The session's work is uncommitted in `/Users/kalra/Coding/RoyaleBench` on the branch `lavaloon-planner-adapter`, which
also has unpushed, unrelated merge commits (a Lavaloon rule bot and `Decision.move`). Only these are needed:

- `cr_arena/crown_benchmark.py`
- `runs/royalebench-crown/` (calibration evidence for tasks 11, 13 and 14; task 12 needs re-running after the fix)
- this file

Copy them to a fresh branch off `origin/main`, or ask Ojas to commit just those and push that branch.

## Copy-paste prompt for the teammate's Claude Code session

> You are finishing RoyaleBench v7. Read `docs/handoff_v7_crown.md` in this repo first and follow it in order, A to E.
> The code for the four Crown tasks is in `cr_arena/crown_benchmark.py`; task 12 needs the fix described there before
> `--calibrate` passes. Do not edit the shared referee files (`scenario_task.py`, `royale_task.py`, `coordinate_task.py`,
> `game.py`, `bots/planner.py`), because the published win and v6 packages are pinned to their hashes and
> `tests/test_win_benchmark.py` will fail. Before spending API money, run one task per model and tell me the cost.
> You need a logged-in Valkyrie CLI and an Anthropic API-key secret in the `hackathon-rip-ojas-e8d933c926` org; if either
> is missing, stop and ask me to run `valkyrie login` / `valkyrie secret set` myself. Verify your work: calibration
> passes, tests pass, and every new task has a winning reference plus zero-scoring controls. Read the Opus traces
> before counting a failure. Report which tasks Opus fails, with run IDs, and say plainly what is not verified.

## Not done / unverified

- Task 12's fix is not applied or recalibrated.
- `--build`, the Docker validation, the dataset push and every Valkyrie run were never started.
- Whether Opus, Sonnet or Haiku fail any new task is unknown.
- Tasks 5 and 6 (the two pattern repeats) and the v7 merge are not started.
- The Opus-trace analysis was not done: no Valkyrie run data was pulled.
- The model ids `anthropic/claude-sonnet-5-5`, `claude-haiku-5-5` and `claude-opus-5-5` were not checked against Valkyrie's model list.
