"""Model-vs-model battles: schedule a head-to-head and run it through the same tournament runner as the CLI.

    battle_plan(config_text, ["model-a", "model-b"], "mirror")   # the games it would play
    launch_battle(root, config_text, names, mode, parallel, db)   # start it in the background
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from .decks import CLASSIC_DECKS, DEFAULT_DECK, validate_deck
from .tournament import schedule

MAX_PARALLEL = 6


def with_custom_deck(config_text: str, cards: list[str]) -> str:
    """Snapshot chosen cards into the runner config, preserving other settings."""
    cfg = tomllib.loads(config_text)
    cfg["decks"] = {"list": [validate_deck(cards)]}
    return tomli_w.dumps(cfg)


def eligible_players(config_text: str) -> dict[str, dict]:
    """Enabled model players (LLMs, and the mock LLM used for testing). Bots are not offered for battles."""
    cfg = tomllib.loads(config_text)
    return {p["name"]: p for p in cfg.get("players", []) if p.get("enabled", True) and p.get("type", "llm") in ("llm", "mock")}


def battle_plan(config_text: str, names: list[str], mode: str) -> list[dict]:
    """The scheduled games of a two-model battle. Raises ValueError (with a message for the user) if it cannot run."""
    cfg = tomllib.loads(config_text)
    players = eligible_players(config_text)
    if len(names) != 2 or len(set(names)) != 2 or any(n not in players for n in names):
        raise ValueError("Choose two different enabled models.")
    if any("," in n for n in names):
        raise ValueError("Model names cannot contain commas.")
    if mode not in ("mirror", "build"):
        raise ValueError("Choose a supported deck mode.")
    deck_names = cfg.get("decks", {}).get("classic")
    decks = [CLASSIC_DECKS[n] for n in deck_names] if deck_names else cfg.get("decks", {}).get("list") or [DEFAULT_DECK]
    plan = schedule([players[n] for n in names], cfg["tournament"].get("seeds", [1, 2, 3]), decks, deck_names, mode)
    if not plan:
        raise ValueError("This configuration has no games scheduled. Add tournament seeds.")
    return plan


@dataclass
class BattleRun:
    name: str
    process: subprocess.Popen
    log_path: Path

    @property
    def exit_code(self) -> int | None:
        return self.process.poll()

    @property
    def running(self) -> bool:
        return self.exit_code is None

    def log_tail(self, limit: int = 16_000) -> str:
        try:
            with self.log_path.open("rb") as log:
                log.seek(max(0, self.log_path.stat().st_size - limit))
                return log.read().decode("utf-8", errors="replace")
        except OSError:
            return ""


def launch_battle(root: Path, config_text: str, names: list[str], mode: str, parallel: int, db_target: str) -> BattleRun:
    """Start the battle as a detached runner process. Validates first, so a bad request never spawns anything."""
    battle_plan(config_text, names, mode)
    if not 1 <= parallel <= MAX_PARALLEL:
        raise ValueError(f"Parallel games must be between 1 and {MAX_PARALLEL}.")
    name = f"battle-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = root / "runs" / "dashboard" / name
    run_dir.mkdir(parents=True, exist_ok=False)
    config_path = run_dir / "config.toml"
    config_path.write_text(config_text, encoding="utf-8")
    log_path = run_dir / "runner.log"
    command = [sys.executable, "-u", "-m", "cr_arena.tournament", "--config", str(config_path), "--job", name,
               "--players", ",".join(names), "--deck-mode", mode, "--parallel", str(parallel)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    command += ["--db", db_target]
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return BattleRun(name, process, log_path)
