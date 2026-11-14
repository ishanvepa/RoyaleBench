"""Launch model battles through the same runner used by the CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import tomllib
import tomli_w
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from dashboard.model_ui import model_selectbox
from dashboard.loading import loading
from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK, deck_options, validate_deck
from cr_arena.tournament import schedule


def with_custom_deck(config_text: str, cards: list[str]) -> str:
    """Snapshot chosen cards into the runner config, preserving other settings."""
    cfg = tomllib.loads(config_text)
    cfg["decks"] = {"list": [validate_deck(cards)]}
    return tomli_w.dumps(cfg)


def battle_plan(config_text: str, names: list[str], mode: str) -> list[dict]:
    cfg = tomllib.loads(config_text)
    players = {p["name"]: p for p in cfg.get("players", [])
               if p.get("enabled", True) and p.get("type", "llm") in ("llm", "mock")}
    if len(names) != 2 or len(set(names)) != 2 or any(n not in players for n in names):
        raise ValueError("Choose two different enabled models.")
    if any("," in n for n in names):
        raise ValueError("Model names cannot contain commas.")
    if mode not in ("mirror", "build"):
        raise ValueError("Choose a supported deck mode.")
    deck_names = cfg.get("decks", {}).get("classic")
    decks = ([CLASSIC_DECKS[n] for n in deck_names] if deck_names else
             cfg.get("decks", {}).get("list") or [DEFAULT_DECK])
    plan = schedule([players[n] for n in names], cfg["tournament"].get("seeds", [1, 2, 3]),
                    decks, deck_names, mode)
    if not plan:
        raise ValueError("This configuration has no games scheduled. Add tournament seeds.")
    return plan


@dataclass
class BattleRun:
    name: str
    process: subprocess.Popen
    log_path: Path

    def log_tail(self) -> str:
        with self.log_path.open("rb") as log:
            log.seek(max(0, self.log_path.stat().st_size - 16000))
            return log.read().decode("utf-8", errors="replace")


def launch_battle(root: Path, config_text: str, names: list[str], mode: str,
                  parallel: int, db_target: str) -> BattleRun:
    battle_plan(config_text, names, mode)
    if not 1 <= parallel <= 6:
        raise ValueError("Parallel games must be between 1 and 6.")
    name = f"battle-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = root / "runs" / "dashboard" / name
    run_dir.mkdir(parents=True, exist_ok=False)
    config_path = run_dir / "config.toml"
    config_path.write_text(config_text, encoding="utf-8")
    log_path = run_dir / "runner.log"
    command = [sys.executable, "-u", "-m", "cr_arena.tournament", "--config", str(config_path),
               "--job", name, "--players", ",".join(names), "--deck-mode", mode,
               "--parallel", str(parallel), "--db", db_target]
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return BattleRun(name, process, log_path)


def page_battle(root: Path, config_path: Path, db_target: str, get_db):
    st.caption("Choose two models and play both sides of each matchup. Results appear in Jobs and Match replays.")
    run = st.session_state.get("battle_run")
    active = run is not None and run.process.poll() is None
    try:
        config_text = config_path.read_text(encoding="utf-8")
        cfg = tomllib.loads(config_text)
    except (OSError, ValueError) as exc:
        st.error(f"Cannot load battle configuration: {exc}")
        return
    names = [p["name"] for p in cfg.get("players", [])
             if p.get("enabled", True) and p.get("type", "llm") in ("llm", "mock")]
    if len(names) < 2:
        st.info("Enable at least two models in the dashboard configuration to start a battle.")
    else:
        left, right = st.columns(2)
        first = model_selectbox("First model", names, target=left)
        second = model_selectbox("Second model", [n for n in names if n != first], target=right)
        mode = st.selectbox("Deck mode", ["mirror", "build"],
                            format_func=lambda m: "Configured decks" if m == "mirror" else "Models build their decks")
        chosen_deck = None
        if mode == "mirror":
            decks = deck_options(get_db())
            chosen_deck = st.selectbox("Battle deck", [None, *decks],
                                      format_func=lambda key: "Use configured decks" if key is None else key,
                                      key="battle_deck")
            if chosen_deck is not None:
                config_text = with_custom_deck(config_text, decks[chosen_deck])
                st.caption(", ".join(decks[chosen_deck]))
        parallel = st.number_input("Games at once", min_value=1, max_value=6, value=1,
                                   help="More simultaneous games can reach provider rate limits sooner.")
        try:
            plan = battle_plan(config_text, [first, second], mode)
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"Cannot schedule battle: {exc}")
        else:
            deck_source = f"the selected deck and seeds from {config_path.name}" if chosen_deck else f"the seeds and decks from {config_path.name}"
            st.info(f"{len(plan)} games, with the models swapping sides. Uses {deck_source}.")
            st.caption("Starting a battle makes model calls using this server's configured credentials and may incur API charges. "
                       "Keep the dashboard server running while the battle plays.")
            if st.button("Start battle", type="primary", disabled=active, key="start_battle"):
                try:
                    with loading("Starting the model battle..."):
                        st.session_state.battle_run = launch_battle(
                            root, config_text, [first, second], mode, int(parallel), db_target)
                except (OSError, ValueError) as exc:
                    st.error(f"Could not start battle: {exc}")
                else:
                    st.rerun()

    if run is not None:
        st.subheader(run.name)
        code = run.process.poll()
        if code is None:
            st.info("Battle runner is active. Refresh to update its status and log.")
        elif code == 0:
            st.success("Battle runner finished. Open the job to see results and any games needing a retry.")
        else:
            st.error(f"Battle runner exited with code {code}. Check the log below.")
        if get_db().query("SELECT id FROM jobs WHERE name = ?", (run.name,)):
            left, right = st.columns(2)
            left.link_button("View progress and results", "?" + urlencode({"page": "Job", "job": run.name}))
            right.link_button("View matches and replays", "?" + urlencode({"page": "Match", "job": run.name}))
        st.button("Refresh battle status", key="refresh_battle")
        with st.expander("Battle log", expanded=code not in (None, 0)):
            st.code(run.log_tail() or "Starting runner...", language="text")
