"""Results for a single tournament or battle, with deck rules labeled separately."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from cr_arena.site import build, result_runs


def run_label(run: dict) -> str:
    if not run["scored_games"]:
        status = str(run.get("status") or "unknown").replace("_", " ").capitalize()
        return f"{run['name']} · No results · {status}"
    games = run["scored_games"]
    return f"{run['name']} · {games} finished {'game' if games == 1 else 'games'} · {run['deck_rules']}"


def page_leaderboard(get_db, root: Path) -> None:
    st.title("Leaderboard")
    runs = result_runs(get_db())
    if not runs:
        st.info("No results yet. Open Play to start the first match.")
        return
    competition = st.radio("Competition", ["Round robin", "1 v 1"], horizontal=True, key="results_format")
    kind = "round_robin" if competition == "Round robin" else "duel"
    available = sorted((run for run in runs if run["format"] == kind),
                       key=lambda run: not bool(run["scored_games"]))
    if not available:
        st.info(f"No {competition.lower()} runs yet. Open Play to start a model battle." if kind == "duel"
                else "No round-robin tournaments yet. Individual battles are under 1 v 1.")
        return
    names = [run["name"] for run in available]
    label = "Tournament" if kind == "round_robin" else "Battle"
    empty_styles = "\n".join(
        f'[role="listbox"][aria-label="{label}"] [role="option"][data-key="{index}"] {{opacity:.45;}}'
        for index, run in enumerate(available) if not run["scored_games"])
    if empty_styles:
        st.html(f"<style>{empty_styles}</style>")
    by_name = {run["name"]: run for run in available}
    selected = st.selectbox(label, names,
                            format_func=lambda name: run_label(by_name[name]),
                            key=f"results_run_{kind}")
    run = by_name[selected]
    if not run["scored_games"]:
        status = str(run.get("status") or "unknown").replace("_", " ")
        st.info(f"This {'battle' if kind == 'duel' else 'tournament'} has no finished games. "
                f"Status: {status}. There are no standings to display yet.")
        return
    explanation = ("Every player faces the other players in this tournament." if kind == "round_robin"
                   else "Results for this two-player battle only.")
    st.caption(f"{explanation} {run['player_count']} players · {run['scored_games']} finished games · {run['deck_rules']}.")
    theme = "dark" if st.session_state.get("dark_mode", True) else "light"
    out = build(get_db(), out=root / "runs" / "site" / "index.html", embedded=True, theme=theme, job_name=selected)
    st.iframe(out, height=1500)
