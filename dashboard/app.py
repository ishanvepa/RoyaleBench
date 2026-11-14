"""CR Arena dashboard: jobs, live progress, leaderboards, per-model metrics, match drill-down.

    uv run streamlit run dashboard/app.py
Reads runs/arena.db (override with CR_ARENA_DB=...). Read-only except the "check models" button.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cr_arena.db import DB  # noqa: E402
from cr_arena.ratings import standings  # noqa: E402
from dashboard.leaderboard import page_leaderboard  # noqa: E402
from dashboard.play import page_play  # noqa: E402

DB_PATH = Path(os.environ.get("CR_ARENA_DB", ROOT / "runs" / "arena.db"))
CONFIG_PATH = Path(os.environ.get("CR_ARENA_CONFIG", ROOT / "config.toml"))

st.set_page_config(page_title="CR Arena", page_icon="👑", layout="wide")

# ---------------------------------------------------------------- palette (validated, see dataviz skill)
DARK = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
BLUE_SIDE = "#3987e5" if DARK else "#2a78d6"   # categorical slot 1
RED_SIDE = "#d95926" if DARK else "#eb6834"    # categorical slot 2
NEUTRAL = "#383835" if DARK else "#f0efec"     # diverging midpoint
DIV_LOW = "#e66767" if DARK else "#e34948"     # diverging red pole
BOT_GRAY = "#8a8984"
INK = "#f0efec" if DARK else "#0b0b0b"          # text-primary
INK_2 = "#c3c2b7" if DARK else "#52514e"        # text-secondary
STATUS = {"done": "✅ done", "running": "🔄 running", "queued": "⏳ queued", "crashed": "❌ crashed", "stopped": "⏸ stopped", "skipped": "⏭ skipped"}


@st.cache_resource
def get_db() -> DB:
    return DB(DB_PATH)


def q(sql: str, params=()) -> pd.DataFrame:
    return pd.DataFrame(get_db().query(sql, params))


def load_config() -> dict:
    try:
        return tomllib.loads(CONFIG_PATH.read_text())
    except Exception:
        return {"players": []}


def prices() -> dict[str, tuple[float, float]]:
    out = {}
    cfgs = [load_config()] + [tomllib.loads(r["config_toml"]) for r in get_db().query("SELECT config_toml FROM jobs") if r["config_toml"]]
    for cfg in cfgs:
        for p in cfg.get("players", []):
            if "price_in" in p and p["name"] not in out:
                out[p["name"]] = (float(p["price_in"]), float(p.get("price_out", 0)))
    return out


def jl(v, default=None):
    """json.loads for a DB cell that may be NULL (NaN once it passes through pandas)."""
    return json.loads(v) if isinstance(v, str) and v else default


def fmt_dur(s: float | None) -> str:
    if s is None or pd.isna(s):
        return "-"
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


def player_metrics(job_id: int | None) -> pd.DataFrame:
    where, params = ("", ())
    if job_id is not None:
        where, params = ("WHERE job_id = ?", (job_id,))
    df = q(f"""
        SELECT player,
               COUNT(*) AS decisions,
               SUM(asked) AS asked,
               SUM(CASE WHEN asked = 1 AND ok = 0 AND error NOT LIKE 'no MOVE%' AND error NOT LIKE 'illegal%' THEN 1 ELSE 0 END) AS api_errors,
               SUM(CASE WHEN asked = 1 AND ok = 0 AND (error LIKE 'no MOVE%' OR error LIKE 'illegal%') THEN 1 ELSE 0 END) AS bad_replies,
               SUM(CASE WHEN result LIKE 'played%' THEN 1 ELSE 0 END) AS plays,
               SUM(CASE WHEN result LIKE 'tried%' THEN 1 ELSE 0 END) AS refused,
               AVG(CASE WHEN asked = 1 THEN latency_s END) AS avg_latency_s,
               MAX(CASE WHEN asked = 1 THEN latency_s END) AS max_latency_s,
               SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out,
               SUM(cache_read) AS cache_read, SUM(cache_write) AS cache_write,
               SUM(COALESCE(cost_usd, 0)) AS reported_cost
        FROM decisions {where} GROUP BY player""", params)
    if df.empty:
        return df
    pr = prices()

    def cost(r):
        if r.reported_cost and r.reported_cost > 0:  # provider-reported (claude CLI) beats a price estimate
            return r.reported_cost
        pin, pout = pr.get(r.player, (0.0, 0.0))
        return (r.tokens_in * pin + r.tokens_out * pout + r.cache_read * pin * 0.1 + r.cache_write * pin * 1.25) / 1e6

    df["est_cost_usd"] = df.apply(cost, axis=1)
    asked = df["asked"].where(df["asked"] > 0)
    df["error_rate"] = df["api_errors"] / asked
    df["bad_reply_rate"] = df["bad_replies"] / asked
    bots = (df["tokens_in"] == 0) & (df["max_latency_s"].fillna(0) < 0.001)  # no API calls -> not applicable
    for col in ("avg_latency_s", "max_latency_s", "error_rate", "bad_reply_rate", "tokens_in", "tokens_out", "cache_read"):
        df[col] = df[col].astype("float").where(~bots)
    return df


# ---------------------------------------------------------------- charts
def rating_chart(lb: pd.DataFrame, llm_names: set[str]) -> alt.Chart:
    d = lb.copy()
    d["kind"] = d["player"].map(lambda p: "LLM" if p in llm_names else "baseline bot")
    order = list(d.sort_values("rating", ascending=False)["player"])
    color = alt.Color("kind:N", scale=alt.Scale(domain=["LLM", "baseline bot"], range=[BLUE_SIDE, BOT_GRAY]),
                      legend=alt.Legend(title=None, orient="top"))
    y = alt.Y("player:N", sort=order, title=None)
    tip = [alt.Tooltip("player:N"), alt.Tooltip("rating:Q"), alt.Tooltip("ci_low:Q", title="95% low"),
           alt.Tooltip("ci_high:Q", title="95% high"), alt.Tooltip("games:Q"), alt.Tooltip("score:Q", format=".0%")]
    rule = alt.Chart(d).mark_rule(strokeWidth=2).encode(y=y, x=alt.X("ci_low:Q", title="Rating (Elo scale, random-bot = 400)"),
                                                         x2="ci_high:Q", color=color, tooltip=tip)
    pts = alt.Chart(d).mark_circle(size=110, opacity=1).encode(y=y, x="rating:Q", color=color, tooltip=tip)
    labels = alt.Chart(d).mark_text(align="left", dx=8, dy=-10, fontSize=11, color=INK_2).encode(y=y, x="rating:Q", text="rating:Q")
    return (rule + pts + labels).properties(height=alt.Step(40))


def h2h_chart(res: pd.DataFrame) -> alt.Chart:
    rows = []
    for r in res.itertuples():
        s = {0: 1.0, 1: 0.0, 2: 0.5}[r.winner]
        rows += [(r.blue, r.red, s), (r.red, r.blue, 1 - s)]
    d = pd.DataFrame(rows, columns=["player", "opponent", "score"]).groupby(["player", "opponent"]).agg(
        score=("score", "mean"), points=("score", "sum"), games=("score", "count")).reset_index()
    d["label"] = d.apply(lambda r: f"{r.points:g}/{r.games}", axis=1)
    players = sorted(set(d["player"]) | set(d["opponent"]))
    base = alt.Chart(d).encode(
        x=alt.X("opponent:N", sort=players, title="opponent", axis=alt.Axis(labelAngle=-30, labelOverlap=False, labelLimit=160)),
        y=alt.Y("player:N", sort=players, title=None))
    cells = base.mark_rect(stroke=("#1a1a19" if DARK else "#fcfcfb"), strokeWidth=2).encode(
        color=alt.Color("score:Q", scale=alt.Scale(domain=[0, 0.5, 1], range=[DIV_LOW, NEUTRAL, BLUE_SIDE], interpolate="rgb"),
                        legend=alt.Legend(title="row player's score", format=".0%")),
        tooltip=[alt.Tooltip("player:N"), alt.Tooltip("opponent:N"), alt.Tooltip("score:Q", format=".0%"),
                 alt.Tooltip("label:N", title="points / games")])
    text = base.mark_text(fontSize=12).encode(
        text="label:N",
        color=alt.condition("abs(datum.score - 0.5) > 0.3", alt.value("#ffffff"), alt.value(INK)))
    return (cells + text).properties(height=alt.Step(44), width=alt.Step(84))


def side_line(d: pd.DataFrame, field: str, title: str, names: tuple[str, str]) -> alt.Chart:
    dd = d[["time_elapsed", "side", field]].rename(columns={field: "value"})
    dom = [f"blue: {names[0]}", f"red: {names[1]}"]
    return alt.Chart(dd).mark_line(strokeWidth=2, interpolate="step-after").encode(
        x=alt.X("time_elapsed:Q", title="game time elapsed (s)"),
        y=alt.Y("value:Q", title=title),
        color=alt.Color("side:N", scale=alt.Scale(domain=dom, range=[BLUE_SIDE, RED_SIDE]), legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("side:N"), alt.Tooltip("time_elapsed:Q", title="t (s)"), alt.Tooltip("value:Q", title=title)],
    ).properties(height=220)


# ---------------------------------------------------------------- pages
def page_overview():
    st.title("👑 CR Arena")
    st.caption("LLMs playing Clash Royale against each other: round-robin jobs, standings and live progress.")
    jobs = q("SELECT * FROM jobs ORDER BY created_at DESC")
    if jobs.empty:
        st.info("No jobs yet. Start one with `uv run python -m cr_arena.tournament --job my-first-run`.")
        return
    m = q("SELECT job_id, status, COUNT(*) AS n FROM matches GROUP BY job_id, status")
    calls = q("SELECT COUNT(*) AS n FROM decisions WHERE asked = 1 AND state != ''").iloc[0]["n"]
    pm = player_metrics(None)
    spend = pm["est_cost_usd"].sum() if not pm.empty else 0.0
    c = st.columns(4)
    c[0].metric("Jobs (running)", f"{len(jobs)} ({int((jobs['status'] == 'running').sum())})")
    c[1].metric("Matches finished", f"{int(m.loc[m.status == 'done', 'n'].sum()) if not m.empty else 0}"
                f" / {int(m['n'].sum()) if not m.empty else 0}")
    c[2].metric("Model decisions made", f"{int(calls):,}")
    c[3].metric("Est. API spend", f"${spend:,.2f}", help="provider-reported cost where available (claude CLI), else tokens × list prices from the config")

    pv = m.pivot_table(index="job_id", columns="status", values="n", fill_value=0) if not m.empty else pd.DataFrame()
    rows = []
    for j in jobs.itertuples():
        counts = pv.loc[j.id] if j.id in pv.index else {}
        done = int(counts.get("done", 0))
        total = int(j.total_matches or 0)
        end = j.finished_at if j.status in ("done", "stopped") and j.finished_at else time.time()
        rows.append({"job": j.name, "status": STATUS.get(j.status, j.status), "progress": done / total if total else 0,
                     "done": f"{done}/{total}", "running": int(counts.get("running", 0)), "crashed": int(counts.get("crashed", 0)),
                     "players": ", ".join(json.loads(j.players or "[]")),
                     "started": pd.to_datetime(j.started_at, unit="s", utc=True).tz_convert(None) if j.started_at else None,
                     "elapsed": fmt_dur(end - j.started_at) if j.started_at else "-", "notes": j.notes or ""})
    st.subheader("Jobs")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "progress": st.column_config.ProgressColumn("progress", min_value=0, max_value=1, format="percent"),
        "started": st.column_config.DatetimeColumn("started (UTC)", format="MMM D, HH:mm")})
    st.caption("Open a job from the sidebar for its leaderboard, matches and per-model metrics.")


def job_header(job: dict):
    m = q("SELECT status, COUNT(*) AS n FROM matches WHERE job_id = ? GROUP BY status", (job["id"],))
    counts = dict(zip(m["status"], m["n"])) if not m.empty else {}
    done, total = counts.get("done", 0), job["total_matches"] or 0
    st.title(f"Job: {job['name']}")
    if job.get("notes"):
        st.caption(job["notes"])
    eta_txt = ""
    if job.get("started_at") and done and job["status"] == "running":
        eta_txt = f" · ETA ~{fmt_dur((time.time() - job['started_at']) / done * (total - done))}"
    st.progress(done / total if total else 0.0, text=f"{STATUS.get(job['status'], job['status'])} · {done}/{total} matches{eta_txt}")
    pm = player_metrics(job["id"])
    c = st.columns(5)
    c[0].metric("Running now", counts.get("running", 0))
    c[1].metric("Queued", counts.get("queued", 0))
    c[2].metric("Crashed", counts.get("crashed", 0))
    c[3].metric("Est. spend", f"${pm['est_cost_usd'].sum():,.2f}" if not pm.empty else "$0.00")
    if job.get("started_at"):
        end = job["finished_at"] if job["status"] in ("done", "stopped") and job.get("finished_at") else time.time()
        el = end - job["started_at"]
        c[4].metric("Elapsed", fmt_dur(el))


REG_TICKS, OT_TICKS = 3600, 2400


def ending(r) -> str:
    """How a finished match ended, from crowns and length (50 ms ticks)."""
    crowns = jl(r["crowns"]) or [0, 0]
    if max(crowns) >= 3:
        return "3-crown knockout"
    if r["ticks"] is not None and r["ticks"] <= REG_TICKS:
        return "more crowns at full time" if crowns[0] != crowns[1] else "draw"
    if r["ticks"] is not None and r["ticks"] < REG_TICKS + OT_TICKS:
        return "overtime crown"
    return "tower-HP tiebreak" if r["winner"] in (0, 1) else "draw"


def win_table(res: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for r in res.to_dict("records"):
        crowns = jl(r["crowns"]) or [0, 0]
        how = ending(r)
        for team, name in ((0, r["blue"]), (1, r["red"])):
            t = rows.setdefault(name, {"player": name, "games": 0, "W": 0, "D": 0, "L": 0, "crowns for": 0,
                                       "crowns against": 0, "3-crown wins": 0, "won at full time": 0,
                                       "won in overtime": 0, "won on tiebreak": 0, "as blue": 0, "as red": 0})
            t["games"] += 1
            t["crowns for"] += crowns[team]
            t["crowns against"] += crowns[1 - team]
            if r["winner"] == 2:
                t["D"] += 1
            elif r["winner"] == team:
                t["W"] += 1
                t["as blue" if team == 0 else "as red"] += 1
                key = {"3-crown knockout": "3-crown wins", "more crowns at full time": "won at full time",
                       "overtime crown": "won in overtime", "tower-HP tiebreak": "won on tiebreak"}.get(how)
                if key:
                    t[key] += 1
            else:
                t["L"] += 1
    df = pd.DataFrame(rows.values())
    if df.empty:
        return df
    df["win rate"] = df["W"] / df["games"]
    df["avg crowns"] = (df["crowns for"] / df["games"]).round(2)
    df["avg conceded"] = (df["crowns against"] / df["games"]).round(2)
    return df.sort_values(["win rate", "avg crowns"], ascending=False)[
        ["player", "games", "W", "D", "L", "win rate", "avg crowns", "avg conceded", "3-crown wins",
         "won at full time", "won in overtime", "won on tiebreak", "as blue", "as red"]]


def page_job(job: dict):
    job_header(job)
    cfg = tomllib.loads(job["config_toml"]) if job.get("config_toml") else {"players": []}
    llm_names = {p["name"] for p in cfg.get("players", []) if p.get("type", "llm") in ("llm", "mock")}
    anchor = cfg.get("tournament", {}).get("anchor", "random-bot")
    res = q("SELECT * FROM matches WHERE job_id = ? AND status = 'done'", (job["id"],))
    tabs = st.tabs(["Leaderboard", "Win rates & endings", "Per-model metrics", "Matches", "Config"])

    with tabs[0]:
        if res.empty:
            st.info("No finished matches yet.")
        else:
            lb = pd.DataFrame(standings(res.to_dict("records")))
            left, right = st.columns([1, 1])
            with left:
                st.markdown("**Standings** · ranked by games won")
                st.dataframe(lb[["rank", "player", "games", "W", "D", "L", "win_rate", "crowns_for", "crowns_against"]],
                             hide_index=True, width="stretch", column_config={
                                 "win_rate": st.column_config.ProgressColumn("win %", format="percent", min_value=0, max_value=1),
                                 "crowns_for": st.column_config.NumberColumn("crowns won"),
                                 "crowns_against": st.column_config.NumberColumn("crowns lost")})
            with right:
                st.markdown("**Head to head** · row player's points / games")
                st.altair_chart(h2h_chart(res))

    with tabs[1]:
        if res.empty:
            st.info("No finished matches yet.")
        else:
            wt = win_table(res)
            st.markdown("**Win rate per player** · all finished matches in this job")
            st.dataframe(wt, hide_index=True, width="stretch", column_config={
                "win rate": st.column_config.ProgressColumn("win rate", format="percent", min_value=0, max_value=1),
                "as blue": st.column_config.NumberColumn("wins as blue"),
                "as red": st.column_config.NumberColumn("wins as red")})
            ends = res.assign(ending=[ending(r) for r in res.to_dict("records")])
            order = ["3-crown knockout", "more crowns at full time", "overtime crown", "tower-HP tiebreak", "draw"]
            cnt = ends["ending"].value_counts().reindex(order, fill_value=0).reset_index()
            cnt.columns = ["ending", "matches"]
            left, right = st.columns([1, 2])
            with left:
                st.markdown("**How matches ended**")
                st.altair_chart(alt.Chart(cnt).mark_bar(color="#8a8984", cornerRadiusEnd=4, height=18).encode(
                    x=alt.X("matches:Q", title="matches", axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("ending:N", sort=order, title=None, axis=alt.Axis(labelLimit=220)),
                    tooltip=["ending", "matches"]).properties(height=alt.Step(30)), width="stretch")
            with right:
                st.markdown("**Final scoreboard per match**")
                hp = [jl(x) or [[0] * 3, [0] * 3] for x in ends["tower_hp"]]
                fin = pd.DataFrame({
                    "match": ends["match_id"], "blue": ends["blue"], "red": ends["red"],
                    "winner": [{0: b, 1: r_, 2: "draw"}.get(w, "") for b, r_, w in zip(ends.blue, ends.red, ends.winner)],
                    "crowns": [f"{c[0]}-{c[1]}" for c in (jl(x) or [0, 0] for x in ends["crowns"])],
                    "ending": ends["ending"],
                    "length": [fmt_dur(t * 0.05) for t in ends["ticks"]],
                    "blue towers left (K/L/R)": [" / ".join(str(v) for v in h[0]) for h in hp],
                    "red towers left (K/L/R)": [" / ".join(str(v) for v in h[1]) for h in hp]})
                st.dataframe(fin, hide_index=True, width="stretch", height=320)
            st.caption("Regulation is 3:00, overtime adds up to 2:00 (sudden death: first crown wins); if still tied, "
                       "the engine's tower-HP tiebreak decides. Towers are king / left princess / right princess; 0 = destroyed.")

    with tabs[2]:
        pm = player_metrics(job["id"])
        if pm.empty:
            st.info("No decisions logged yet.")
        else:
            show = pm[["player", "asked", "plays", "refused", "error_rate", "bad_reply_rate", "avg_latency_s",
                       "max_latency_s", "tokens_in", "tokens_out", "cache_read", "est_cost_usd"]].sort_values("player")
            st.dataframe(show, hide_index=True, width="stretch", column_config={
                "asked": st.column_config.NumberColumn("decisions asked", help="decision points where a move other than wait was possible (the model is only called on these)"),
                "tokens_in": st.column_config.NumberColumn("tokens in", format="localized"),
                "tokens_out": st.column_config.NumberColumn("tokens out", format="localized"),
                "cache_read": st.column_config.NumberColumn("cached tokens read", format="localized"),
                "plays": st.column_config.NumberColumn("cards played"),
                "refused": st.column_config.NumberColumn("plays refused by engine"),
                "error_rate": st.column_config.NumberColumn("API error rate", format="percent", help="timeouts, API errors, refusals"),
                "bad_reply_rate": st.column_config.NumberColumn("bad reply rate", format="percent", help="no MOVE line or illegal number"),
                "avg_latency_s": st.column_config.NumberColumn("avg latency (s)", format="%.2f"),
                "max_latency_s": st.column_config.NumberColumn("max latency (s)", format="%.1f"),
                "est_cost_usd": st.column_config.NumberColumn("est. cost", format="$%.2f"),
            })
            st.caption("Errors and bad replies are played as 'wait'. Bots make no API calls, so their latency/token/error columns are blank.")

    with tabs[3]:
        allm = q("SELECT * FROM matches WHERE job_id = ? ORDER BY COALESCE(started_at, 9e18) DESC", (job["id"],))
        live = q("""SELECT match_id, MIN(time_left) AS time_left, MAX(step) AS step FROM decisions
                    WHERE job_id = ? AND match_id IN (SELECT match_id FROM matches WHERE job_id = ? AND status = 'running')
                    GROUP BY match_id""", (job["id"], job["id"]))
        live = dict(zip(live["match_id"], live["time_left"])) if not live.empty else {}
        f1, f2 = st.columns(2)
        status_f = f1.multiselect("status", ["done", "running", "queued", "crashed"], default=[])
        players = sorted(set(allm["blue"]) | set(allm["red"])) if not allm.empty else []
        player_f = f2.multiselect("player", players, default=[])
        rows = []
        for r in allm.itertuples():
            if status_f and r.status not in status_f:
                continue
            if player_f and r.blue not in player_f and r.red not in player_f:
                continue
            sb = jl(r.stats_blue, {})
            sr = jl(r.stats_red, {})
            winner = {0: r.blue, 1: r.red, 2: "draw"}.get(r.winner, "") if r.status == "done" else ""
            crowns = jl(r.crowns)
            prog = f"{live[r.match_id]:.0f}s left" if r.match_id in live else ""
            rows.append({"match": r.match_id, "status": STATUS.get(r.status, r.status), "blue": r.blue, "red": r.red,
                         "seed": r.seed, "winner": winner, "crowns / live": f"{crowns[0]}-{crowns[1]}" if crowns else prog,
                         "errors (b/r)": f"{sb.get('errors', 0) + sb.get('illegal_or_unparsed', 0)}/{sr.get('errors', 0) + sr.get('illegal_or_unparsed', 0)}" if sb else "",
                         "wall time": fmt_dur(r.wall_s) if pd.notna(r.wall_s) else ""})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        crashed = allm[allm.status == "crashed"] if not allm.empty else allm
        for r in crashed.itertuples():
            with st.expander(f"❌ {r.match_id}"):
                st.code(r.error or "", language="text")

    with tabs[4]:
        st.code(job.get("config_toml") or "", language="toml")


def page_match(job: dict):
    ms = q("SELECT match_id, status FROM matches WHERE job_id = ? AND status IN ('done', 'running', 'crashed') "
           "ORDER BY COALESCE(started_at, 0) DESC", (job["id"],))
    if ms.empty:
        st.info("No matches started in this job yet.")
        return
    labels = [f"{STATUS.get(s, s).split()[0]} {m}" for m, s in zip(ms.match_id, ms.status)]
    pick = st.selectbox("Match", range(len(ms)), format_func=lambda i: labels[i])
    mid = ms.match_id.iloc[pick]
    m = get_db().query("SELECT * FROM matches WHERE job_id = ? AND match_id = ?", (job["id"], mid))[0]
    d = q("SELECT * FROM decisions WHERE job_id = ? AND match_id = ? ORDER BY step, team", (job["id"], mid))
    st.title(f"🔵 {m['blue']}  vs  🟠 {m['red']}")
    winner = {0: f"🔵 {m['blue']}", 1: f"🟠 {m['red']}", 2: "draw"}.get(m["winner"])
    crowns = jl(m["crowns"])
    c = st.columns(4)
    c[0].metric("Status", STATUS.get(m["status"], m["status"]))
    c[1].metric("Winner", winner or "-")
    c[2].metric("Crowns (blue-red)", f"{crowns[0]}-{crowns[1]}" if crowns else "-")
    c[3].metric("Wall time", fmt_dur(m["wall_s"]) if m["wall_s"] else "-")
    deck = jl(m.get("deck"))
    if isinstance(deck, dict):
        st.markdown(f"**Decks** · 🔵 {', '.join(deck['blue'])}  \n🟠 {', '.join(deck['red'])}")
    elif deck:
        st.markdown(f"**Deck (mirror)** · {', '.join(deck)}")
    if d.empty:
        st.info("No decisions logged yet.")
        return
    ticks = tomllib.loads(job["config_toml"]).get("tournament", {}).get("decision_ticks", 40) if job.get("config_toml") else 40
    d["time_elapsed"] = d["step"] * ticks * 0.05
    names = (m["blue"], m["red"])
    d["side"] = d["team"].map({0: f"blue: {names[0]}", 1: f"red: {names[1]}"})
    a, b = st.columns(2)
    a.altair_chart(side_line(d, "my_towers", "own tower HP (sum of 3)", names), width="stretch")
    b.altair_chart(side_line(d, "elixir", "elixir at decision", names), width="stretch")

    st.subheader("Decisions")
    only_asked = st.toggle("only decisions where the model was asked", value=True)
    dd = d[d.asked == 1] if only_asked else d
    view = dd[["step", "time_left", "side", "move", "result", "ok", "latency_s", "tokens_in", "tokens_out", "error"]]
    ev = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", height=320,
                      column_config={"ok": st.column_config.CheckboxColumn("parsed ok"),
                                     "time_left": st.column_config.NumberColumn("time left (s)", format="%.0f")})
    sel = ev.selection.rows if ev and hasattr(ev, "selection") else []
    if sel:
        row = dd.iloc[sel[0]]
        s1, s2 = st.columns(2)
        s1.markdown("**What the model saw**")
        s1.code(row["state"] or "(not asked: only 'wait' was legal)", language="text")
        s2.markdown("**Model reply**")
        s2.code(row["raw"] or "(empty)", language="text")
    else:
        st.caption("Select a row to see the exact board text the model saw and its full reply.")

    st.subheader("Replay")
    rp = Path(m["replay_path"]) if m.get("replay_path") else None
    if rp and not rp.is_absolute():
        rp = ROOT / rp
    if not rp or not rp.exists():
        st.caption("Replay is saved when the match finishes." if m["status"] != "done" else
                   "No replay saved for this game: only the first few games of each pairing keep one "
                   "(replays_per_pair in the config). The decisions above are always logged.")
        return
    html_path = rp.with_suffix(".html")
    if st.button("Render replay" if not html_path.exists() else "Re-render replay"):
        with st.spinner("rendering..."):
            subprocess.run([sys.executable, "-m", "cr_arena.replay", str(rp), "-o", str(html_path), "--stride", "2",
                            "--title", mid], check=False, cwd=ROOT, capture_output=True)
    if html_path.exists():
        # Locally generated by cr_arena.replay (royalegym viewer) from our own trace file (no model text in it).
        st.iframe(html_path, height=900)


def page_models():
    st.title("Models")
    cfg = load_config()
    checks = q("SELECT * FROM model_checks ORDER BY checked_at DESC")
    last = {} if checks.empty else {r["name"]: r for r in checks.drop_duplicates("name").to_dict("records")}
    allres = pd.DataFrame(get_db().results(None))
    lb = {r["player"]: r for r in standings(allres.to_dict("records"))} if not allres.empty else {}
    rows = []
    for p in cfg.get("players", []):
        kind = p.get("type", "llm")
        prov = p.get("provider", "-")
        env = p.get("api_key_env") or {"anthropic": "ANTHROPIC_API_KEY", "openai_compat": "OPENROUTER_API_KEY"}.get(prov)
        key_ok = (bool(os.environ.get(env)) or _dotenv_has(env)) if env else None
        chk = last.get(p["name"])
        rows.append({
            "player": p["name"], "type": kind, "provider": prov, "model id": p.get("model", "-"),
            "effort": p.get("effort", ""), "enabled": p.get("enabled", True),
            "key": "-" if key_ok is None else ("✅ set" if key_ok else f"❌ {env} missing"),
            "last check": "-" if chk is None else ("✅ ok" if chk["ok"] else "❌ failed"),
            "check detail": "" if chk is None else chk["detail"],
            "checked": pd.to_datetime(chk["checked_at"], unit="s", utc=True).tz_convert(None) if chk is not None else None,
            "price in/out ($/M)": f"{p['price_in']}/{p.get('price_out', 0)}" if "price_in" in p else "",
            "games (all jobs)": lb.get(p["name"], {}).get("games", 0),
            "wins (all jobs)": lb.get(p["name"], {}).get("W", 0),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"checked": st.column_config.DatetimeColumn("checked (UTC)", format="MMM D, HH:mm")})
    st.caption(f"From {CONFIG_PATH.name}. Keys are read from the environment or .env. "
               "'games' and 'wins' pool every finished match in the database.")
    if st.button("Run model check now (1 cheap call per LLM)"):
        with st.spinner("calling each model once..."):
            out = subprocess.run([sys.executable, "-m", "cr_arena.check_models", "--config", str(CONFIG_PATH),
                                  "--db", str(DB_PATH)], cwd=ROOT, capture_output=True, text=True)
        st.code(out.stdout + out.stderr, language="text")
        st.rerun()


def _dotenv_has(name: str) -> bool:
    f = ROOT / ".env"
    if not f.exists():
        return False
    for line in f.read_text().splitlines():
        if line.strip().startswith(f"{name}=") and line.split("=", 1)[1].strip():
            return True
    return False


# ---------------------------------------------------------------- layout
def main():
    jobs = get_db().query("SELECT * FROM jobs ORDER BY created_at DESC")
    with st.sidebar:
        st.header("CR Arena")
        pages = ["Leaderboard", "Play", "Overview", "Job", "Match", "Models"]
        qp = st.query_params  # pages are linkable: ?page=Job&job=main-v1
        page = st.radio("Page", pages, index=pages.index(qp.get("page", "Leaderboard")) if qp.get("page") in pages else 0,
                        label_visibility="collapsed")
        qp["page"] = page
        job = None
        if page in ("Job", "Match") and jobs:
            names = [f"{STATUS.get(j['status'], j['status']).split()[0]} {j['name']}" for j in jobs]
            by = [j["name"] for j in jobs]
            default = by.index(qp["job"]) if qp.get("job") in by else 0
            job = jobs[st.selectbox("Job", range(len(jobs)), index=default, format_func=lambda i: names[i])]
            qp["job"] = job["name"]
        live = st.toggle("Auto-refresh", help="Job / Overview every 5 s, Leaderboard every 30 s", value=any(j["status"] == "running" for j in jobs) and page != "Play")
        st.caption(f"DB: {DB_PATH.relative_to(ROOT) if DB_PATH.is_relative_to(ROOT) else DB_PATH}")

    def render():
        nonlocal job
        if job is not None:  # re-read so status/timestamps are fresh on every auto-refresh
            job = get_db().query("SELECT * FROM jobs WHERE id = ?", (job["id"],))[0]
        if page == "Leaderboard":
            page_leaderboard(get_db, ROOT)
        elif page == "Overview":
            page_overview()
        elif page == "Models":
            page_models()
        elif job is None:
            st.info("No jobs yet.")
        elif page == "Job":
            page_job(job)
        else:
            page_match(job)

    if page == "Play":  # interactive game: never auto-refresh
        page_play(ROOT, get_db)
        return
    if live and page == "Leaderboard":  # rebuild the site every 30 s; it restores its own tab/sort state
        st.fragment(render, run_every=30)()
        return
    if live and page != "Match":  # the match page has interactive selection; refresh manually there
        st.fragment(render, run_every=5)()
    else:
        render()


main()
