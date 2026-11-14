"""Leaderboard page: the static results site (cr_arena/site.py, chessbench.ai format), rebuilt from
the database on every view and embedded full width. Ranking is games won in the round robin."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from cr_arena.site import build


def page_leaderboard(get_db, root: Path) -> None:
    jobs = [j["name"] for j in get_db().query("SELECT name FROM jobs ORDER BY created_at DESC") if j["name"] != "human-play"]
    with st.sidebar:
        st.markdown("**Leaderboard jobs**")
        classic = st.selectbox("Classic decks", jobs, index=jobs.index("classic-v2") if "classic-v2" in jobs else 0)
        build_job = st.selectbox("Deck building", jobs, index=jobs.index("build-v2") if "build-v2" in jobs else 0)
    out = build(get_db(), classic, build_job, root / "runs" / "site" / "index.html")
    st.iframe(out, height=1500)
    st.caption(f"Standalone copy: `{out.relative_to(root)}` (open it in a browser, or `uv run python -m cr_arena.site`).")
