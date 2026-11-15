# Match tasks: playing full games on Valkyrie

Each task in [`benchmarks/clash-royale/`](../benchmarks/clash-royale) asks an agent to play one complete Clash Royale match, decision by decision, through a `cr` command-line tool. The opponent is the fixed rule-based `heuristic-bot`. The task set covers seeds 1–3 from both seats (blue and red), with the `giant-beatdown` deck on both sides.

## How a run works

```text
healthcheck (root) ── starts ──> game server (user referee) ── owns engine, match, action log
agent harness (user player) ── cr / cr act N ──> Unix socket ──> game server
agent finishes ── Valkyrie carries /var/lib/royale ──> fresh verifier container
verifier ── rebuilds match from seed, replays the log against the same bot ──> reward.json
```

- **Agent interface.** The interface is the arena's: the text state, the numbered legal moves, and 2.0 seconds of game time per decision. The game pauses while the agent thinks. Intervals where the only legal move is waiting are skipped automatically, exactly as in [`match.py`](../cr_arena/match.py). Any decision the agent never makes counts as waiting, so a match always finishes.
- **Isolation.** The agent runs as `player`, which is non-root (`[agent] user`). The engine, the opponent's code, the task config and the action log belong to `referee`, with mode 0700. The agent can't read them, can't import the engine, and can't signal the server. Its only sudo right is to start the server with no arguments. A restarted server resumes the same match from the log, so the agent can't restart the game.
- **Grading.** Grading uses `environment_mode = "separate"`: a clean copy of the image, which the agent never touched, replays the carried log. Each log entry must match the replay's decision number, game tick, and move label. A mismatch sets `integrity` to 0 and the reward to 0. The verifier also writes a `replay.html`, the original log, and `match_report.json` to `/logs/verifier`.

Agent harnesses install as root under `/root/.local` and then run as `player`, so the image sets `/root` to mode 0711. That lets `player` reach the installed CLI by path without being able to list `/root`. Without it, the first pilot failed with `Permission denied: 'claude'`.

These guarantees were checked locally in Docker: permission probes, a crash and resume, a tampered log, and a full play-then-verify run. They were then confirmed on Valkyrie by the pilot below.

## Reward

`reward` is 1 for a win and 0 for a loss; there are no fractional rewards. A level overtime is decided by the tower-HP tiebreak; only an exact tie there is a draw, and a draw scores 0 like a loss. Valkyrie's score is the mean `reward` across tasks. The verifier also reports these diagnostics in `reward.json`:

| Key | Meaning |
| --- | --- |
| `win` | 1 if the agent won (with integrity intact). |
| `crowns_for`, `crowns_against` | Crowns at the end of the match. |
| `enemy_tower_damage_frac`, `own_tower_damage_frac` | Share of total tower HP destroyed. |
| `completed` | 1 if the agent's own decisions reached the end of the match. |
| `decisions` | Decisions the agent made. |
| `integrity` | 0 if the log could not be replayed; the reward is then 0. |
| `fast_decision_frac` | Share of decisions made less than 1 s after the state was shown. A high value suggests a script played the moves, which the instructions forbid. Review those runs before reporting them. |

## Build, check and publish

```bash
uv run python -m cr_arena.build_tasks
```

```bash
uv run --with pytest python -m pytest -q tests/test_royale_task.py
```

To exercise one task image locally, build it, start the server as the healthcheck would, play as `player`, then grade a copy of the state directory in a fresh container:

```bash
docker build --platform linux/amd64 -t royale-task:test benchmarks/clash-royale/match-heuristic-s1-blue/environment
```

```bash
docker run -d --platform linux/amd64 --name rt-agent royale-task:test sleep infinity
```

```bash
docker exec -u player rt-agent bash -c 'until cr act 0 | grep -q "GAME OVER"; do :; done; cr'
```

```bash
docker cp rt-agent:/var/lib/royale /tmp/royale-carry && docker run --rm --platform linux/amd64 -v /tmp/royale-carry:/var/lib/royale -v "$PWD/benchmarks/clash-royale/match-heuristic-s1-blue/tests:/tests:ro" royale-task:test bash /tests/test.sh
```

The play step waits at every decision, so it checks the plumbing and is expected to lose (reward 0).

These tasks deliberately ship without a `solution/` folder, although the [task design](task_design.md) checklist asks for a reference solution with full reward. Valkyrie and the dashboard don't require one. The checklist's goals are met by recorded runs instead: Valkyrie runs have won `s1-blue`, `s1-red` and `s3-red`, and those wins scored 1.0 through the full grading path. No recorded run has won `s2-blue`, `s2-red` or `s3-blue`, so it is not yet shown that those three can be won.

The tasks follow the upstream layout in `benchmarks/clash-royale/`, and `benchmark.toml` is generated with `kind = "eval"`. Datasets `@1` and `@2` were published from the earlier top-level `tasks/` folder. Their task contents are the same apart from the `task.toml` description and the referee's module layout, and match behaviour is unchanged. Revision `royalebench/clash-royale@3` (tag `v3`, digest `45658a99ce95`) was published from `benchmarks/clash-royale` on November 14, 2026. Use it for the next runs. It has not been run yet.

Publish and run one task first (see the [Valkyrie guide](valkyrie_guide.md) for secrets):

```bash
valkyrie dataset push royalebench/clash-royale ./benchmarks/clash-royale --tag v3
```

```bash
valkyrie run start --agent claude_code-v1.0.0 --dataset royalebench/clash-royale@3 --model anthropic/claude-sonnet-4-6 --provider modal -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?}" --slice 0:1 --concurrency 1 --label royalebench-match-pilot --connect
```

## Pilot run

On November 14, 2026, run `f1256c95-2a0a-42bb-be41-2c7c0b2f2ccf` played `match-heuristic-s1-blue` from dataset `royalebench/clash-royale@2`. It used `anthropic/claude-sonnet-4-6`, the `claude_code-v1.0.0` harness, and Modal, with concurrency 1 and the `anthropic-api-key-ben` secret.

- **Result.** A 3–0 win (reward 1.0) in 35 decisions, with integrity 1 and `fast_decision_frac` 0. The separate verifier confirmed it.
- **Time and cost.** The agent ran for 765 s, and model usage cost $1.42, excluding sandbox charges. Decision time had a median of 21 s and ranged from 4.9 to 54 s.
- **Trajectory.** All 36 tool calls were `cr` commands, with no attempts to inspect the environment.
- **Saved evidence.** Results are in `runs/valkyrie-match-pilot-results.json`. Agent logs and the carried action log are in `runs/valkyrie-match-pilot-output/match-heuristic-s1-blue/`.

This single match showed the pipeline works end to end. The full run below shows the pilot's 3–0 win was not typical.

## Full run: Sonnet 4.6, six tasks

On November 14, 2026, run `eb818255-7a36-435d-aef8-9bbb9ef709ae` played all six tasks of `royalebench/clash-royale@2`. The setup matched the pilot, except concurrency was 6. The aggregate score was **33.3**: 2 wins and 4 losses.

| Task | Result | Crowns (agent–bot) | Enemy tower damage | Own tower damage | Decisions | Agent time | Cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| s1-blue | Loss | 0–1 | 15% | 47% | 57 | 3187 s | $4.68 |
| s1-red | **Win** | 1–0 | 41% | 32% | 47 | 729 s | $1.73 |
| s2-blue | Loss | 0–1 | 10% | 65% | 42 | 605 s | $1.39 |
| s2-red | Loss | 0–1 | 32% | 34% | 48 | 1211 s | $2.21 |
| s3-blue | Loss | 0–1 | 5% | 45% | 55 | 2305 s | $4.05 |
| s3-red | **Win** | 1–0 | 72% | 31% | 45 | 885 s | $1.86 |

- **Integrity.** Every task completed its match with integrity 1 and `fast_decision_frac` 0.
- **Trajectories.** Every move went through `cr`. The only other tool calls were Claude Code's automatic memory note after the `s3-blue` game ended (`Write`/`Read` under `/home/player/.claude`), which has no effect on the match.
- **Run-to-run variance.** `s1-blue`, which the pilot won 3–0, was lost this time. Models are not deterministic, so report results over repeated runs.
- **Time and cost.** Model usage totalled $15.92, excluding sandbox charges. Some single decisions took 6–10 minutes of thinking. `s1-blue` used 3187 s of its 3600 s agent limit. The limit stays at 60 minutes on purpose, as part of the task: decisions left unmade when time runs out count as waits. Report any timeouts alongside the scores.
- **Saved evidence.** Results are in `runs/valkyrie-match-sonnet46-v2-results.json`. Per-task agent logs and action logs are in `runs/valkyrie-match-sonnet46-v2-output/`.

`heuristic-bot` beat Sonnet 4.6 in four of six matches, so the tasks have headroom. Six matches are still a small sample. Compare models on this same dataset revision, with repeated runs.

## Cost and limits

- **Length and cost.** A match asks the agent for roughly 30–120 decisions, and each one is a full agent turn. The agent timeout is 3600 s. Expect several dollars of model usage per match with a frontier model. Run a single task before a full slice.
- **Noise.** One match per task makes results noisy. Compare models on the same dataset revision, and add seeds before drawing conclusions.
- **Opponent knowledge.** The opponent is deterministic. An agent cannot read its code, but it could learn its habits within a match. That is legitimate play.
- **Scripted play.** The rule against scripted play is enforced only through the instructions and the `fast_decision_frac` diagnostic. Inspect trajectories (`valkyrie run output`) for representative runs.
