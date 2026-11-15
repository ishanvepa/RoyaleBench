"""Generate the Harbor match tasks under benchmarks/clash-royale (one full match per task).

    uv run python -m cr_arena.build_tasks            # writes benchmarks/clash-royale/
    valkyrie dataset push royalebench/clash-royale ./benchmarks/clash-royale --tag vN

Each task: the agent plays one complete match, through the `cr` CLI, against a fixed rule-based
opponent, from a given seed and seat. The game server runs as a separate `referee` user the agent
(user `player`) cannot read or signal; grading replays the server's action log in a fresh verifier
container. Regenerate after changing the referee or game code so every task ships the same files.
Task design follows docs/task_design.md; see docs/match_tasks.md for this benchmark.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .decks import CLASSIC_DECKS
from .game import Game
from .players import RULES

ROOT = Path(__file__).resolve().parent
REFEREE_FILES = ["__init__.py", "game.py", "player_types.py", "decks.py", "royale_task.py", "replay.py",
                 "rendering.py", "replay.html", "battle_renderer.js", "card_art.js",
                 "bots/__init__.py", "bots/registry.py", "bots/baselines.py"]
ROYALEGYM, ROYALESIM = "0.1.28", "0.1.48"  # keep in step with uv.lock

OUT_DIR = Path("benchmarks/clash-royale")
DECK_NAME = "giant-beatdown"
SEEDS = [1, 2, 3]
SEATS = {0: "blue", 1: "red"}
OPPONENT = "heuristic"
DECISION_TICKS = 40  # 2.0 s of game time per decision, as in the arena
AGENT_TIMEOUT_S = 3600

DOCKERFILE = f"""FROM python:3.12-slim-bookworm

RUN apt-get update \\
    && apt-get install -y --no-install-recommends bash curl git ca-certificates sudo procps \\
    && rm -rf /var/lib/apt/lists/*

# referee: owns the engine, the match and the action log. player: the agent.
# Agent harnesses install as root under /root/.local and then run as player, so /root is made
# traversable (0711: no listing) for the player to execute the installed CLI.
RUN useradd --system --home-dir /opt/referee --shell /usr/sbin/nologin referee \\
    && useradd --create-home --shell /bin/bash player

RUN python3 -m venv /opt/referee/venv \\
    && /opt/referee/venv/bin/pip install --no-cache-dir royalegym=={ROYALEGYM} royalesim=={ROYALESIM}

COPY referee/ /opt/referee/app/cr_arena/
COPY task.json /opt/referee/task.json
COPY cr /usr/local/bin/cr
COPY royale-start-server /usr/local/sbin/royale-start-server
COPY sudoers /etc/sudoers.d/royale

RUN chmod 0755 /usr/local/bin/cr /usr/local/sbin/royale-start-server \\
    && chmod 0440 /etc/sudoers.d/royale \\
    && mkdir -p /var/lib/royale /var/lib/royale-run /app /logs/agent /logs/verifier \\
    && chown -R referee:referee /opt/referee /var/lib/royale /var/lib/royale-run \\
    && chmod 0700 /opt/referee /var/lib/royale \\
    && chmod 0755 /var/lib/royale-run \\
    && chown player:player /app \\
    && chmod 0777 /logs /logs/agent /logs/verifier \\
    && chmod 0711 /root \\
    && cd /opt/referee/app && /opt/referee/venv/bin/python -c "import cr_arena.royale_task"

WORKDIR /app
"""

START_SERVER = """#!/bin/bash
# Start the game server as the referee user (idempotent: a running server keeps the match;
# a restarted one resumes it from the action log). Called by the healthcheck and by `cr`.
set -u
SOCK=/var/lib/royale-run/cr.sock
if [ "$(id -un)" != "referee" ]; then
    echo "royale-start-server must run as referee" >&2
    exit 1
fi
cd /opt/referee/app
PYTHONPATH=/opt/referee/app setsid nohup /opt/referee/venv/bin/python -m cr_arena.royale_task serve \\
    --config /opt/referee/task.json --state-dir /var/lib/royale --socket "$SOCK" \\
    >>/var/lib/royale/server.log 2>&1 </dev/null &
for _ in $(seq 1 240); do
    [ -S "$SOCK" ] && exit 0
    sleep 0.25
done
echo "game server did not start" >&2
exit 1
"""

SUDOERS = 'player ALL=(referee) NOPASSWD: /usr/local/sbin/royale-start-server ""\n'

TEST_SH = """#!/bin/bash
# Grade by replaying the carried action log from the task seed (fresh verifier container).
set -uo pipefail
mkdir -p /logs/verifier
LOG=/var/lib/royale/actions.jsonl
[ -f "$LOG" ] && cp "$LOG" /logs/verifier/actions.jsonl
cd /opt/referee/app
if ! PYTHONPATH=/opt/referee/app /opt/referee/venv/bin/python -m cr_arena.royale_task verify \\
        --config /tests/task.json --log "$LOG" --out /logs/verifier; then
    echo "verifier crashed; reward 0" >&2
    echo '{"reward": 0.0, "integrity": 0.0}' > /logs/verifier/reward.json
fi
"""

INSTRUCTION = """# Win a Clash Royale match

You are playing one complete match of Clash Royale against a fixed, rule-based opponent. You play
every decision yourself through the `cr` command. Your goal is to **win the match**.

## How to play

- Run `cr` to see the current state of the battle and a numbered list of legal moves.
- Run `cr act N` to play move `N` (move `0` is always "wait"). The game then advances
  {interval:.1f} seconds of game time and prints the next state and legal moves.
- The game is paused while you think: there is no penalty for taking time on a decision.
- When you have no move except waiting (for example, not enough elixir), the game waits for you
  automatically, so every state you are shown needs a decision.
- Keep playing until `cr` prints `GAME OVER`. A match lasts 3 minutes of game time, plus up to
  1 minute of overtime if the crowns are tied: at most {decisions} decisions, usually fewer. If you stop
  early, every decision you did not make counts as waiting for the rest of the match.

Make each decision yourself from the state `cr` shows you. Do not write programs, scripts or loops
that choose or submit moves for you: the benchmark measures your own decisions, and the timing of
each move is recorded. You cannot inspect or change the game itself; only `cr` is available.

## Scoring

Win = 1, draw = 0.5, loss = 0. The match is graded by replaying your moves, so only the moves you
submit with `cr act` count.

## Rules in brief

{rules}

## Coordinates

Positions are in tiles from YOUR point of view: x from 0 (left) to 17 (right), y from 0 (your back
edge) to 31 (the enemy's back edge). The river is at y ~15-16. Your princess towers are near y 6.5,
the enemy's near y 25.5.

## Your deck (8 cards)

{deck}
"""


def task_config(seed: int, team: int) -> dict:
    deck = CLASSIC_DECKS[DECK_NAME]
    return {"seed": seed, "agent_team": team, "agent_deck": deck, "opponent_deck": deck,
            "opponent": OPPONENT, "decision_ticks": DECISION_TICKS}


def task_toml(name: str, seed: int, team: int, avg: float) -> str:
    return f'''schema_version = "1.4"
artifacts = [{{ source = "/var/lib/royale", destination = "royale" }}]

[task]
name = "royalebench/{name}"
description = "Full-match play through the cr CLI, graded by replaying the agent's moves. time_left=3:00 (full match) | player={DECK_NAME} (avg {avg:.2f}) | opponent_deck={DECK_NAME} (avg {avg:.2f}) | opponent=heuristic-bot | seed={seed} | seat={SEATS[team]} | scoring=win 1, draw 0.5, loss 0"

[metadata]
category = "clash-royale-match"
difficulty = "hard"
opponent = "{OPPONENT}"
deck = "{DECK_NAME}"
seed = {seed}
seat = "{SEATS[team]}"
decision_ticks = {DECISION_TICKS}

[agent]
timeout_sec = {AGENT_TIMEOUT_S:.1f}
user = "player"

[verifier]
timeout_sec = 300.0
environment_mode = "separate"

[environment]
build_timeout_sec = 900.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
workdir = "/app"

[environment.healthcheck]
command = "runuser -u referee -- /usr/local/sbin/royale-start-server"
timeout_sec = 60
start_period_sec = 0
retries = 3
'''


BENCHMARK_TOML = """# Display metadata for the dashboard. Valkyrie ignores this file: `dataset push` only reads task folders.
# Do not add a dataset.toml here; Valkyrie treats it as a digest lock that freezes the task list.
# Generated by `uv run python -m cr_arena.build_tasks`; edit the generator, not the task folders.
[benchmark]
title = "Clash Royale full matches"
description = "The agent plays complete matches against heuristic-bot through the cr CLI, one decision at a time, from fixed seeds and both seats. An isolated referee owns the game; grading replays the agent's logged moves in a fresh container. Reward: win 1, draw 0.5, loss 0."
kind = "eval"
"""


def write_exec(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


def build(out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():  # replace generated task folders only; keep anything else in the benchmark
        if old.is_dir() and (old / "task.toml").is_file():
            shutil.rmtree(old)
    (out / "benchmark.toml").write_text(BENCHMARK_TOML)
    probe = Game(CLASSIC_DECKS[DECK_NAME], CLASSIC_DECKS[DECK_NAME], seed=0, record=False)
    avg = sum(c.elixir for c in probe.cards if c.name in CLASSIC_DECKS[DECK_NAME]) / len(CLASSIC_DECKS[DECK_NAME])
    interval = DECISION_TICKS * probe.state.tick_ms / 1000
    instruction = INSTRUCTION.format(interval=interval, decisions=int(240 / interval),
                                     rules=RULES, deck=probe.deck_summary(0))
    names = []
    for seed in SEEDS:
        for team, seat in SEATS.items():
            name = f"match-{OPPONENT}-s{seed}-{seat}"
            names.append(name)
            d = out / name
            env = d / "environment"
            (env / "referee").mkdir(parents=True)
            (d / "tests").mkdir()
            for f in REFEREE_FILES:
                (env / "referee" / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / f, env / "referee" / f)
            cfg = json.dumps(task_config(seed, team), indent=1) + "\n"
            (env / "task.json").write_text(cfg)
            (d / "tests" / "task.json").write_text(cfg)
            (env / "Dockerfile").write_text(DOCKERFILE)
            write_exec(env / "cr", (ROOT / "cr_client.py").read_text())
            write_exec(env / "royale-start-server", START_SERVER)
            (env / "sudoers").write_text(SUDOERS)
            write_exec(d / "tests" / "test.sh", TEST_SH)
            (d / "instruction.md").write_text(instruction)
            (d / "task.toml").write_text(task_toml(name, seed, team, avg))
    return names


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    names = build(a.out)
    print(f"wrote {len(names)} tasks to {a.out}: {', '.join(names)}")


if __name__ == "__main__":
    main()
