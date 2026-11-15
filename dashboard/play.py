"""Play page: a human plays a full battle against any bot or model, through the SAME interface the
models get (a decision every 2 s of game time, one move from the numbered legal-move list). The
game pauses while you think, exactly like it does for the models. Finished games are saved to the
database (job "human-play"), so they show up on the Job / Match pages with a replay."""

from __future__ import annotations

import time
import tomllib
import uuid
from html import escape
from pathlib import Path

import streamlit as st
from royalegym.protocol import EntityKind
from royalegym.replay import save_trace

from dashboard.model_ui import model_label, model_selectbox
from dashboard.loading import loading
from cr_arena.decks import deck_options
from cr_arena.game import Game
from cr_arena.players import Decision, InfraError, build_player
from cr_arena.bots import human_bot_specs

HUMAN = 0  # you play blue, at the bottom of the board
OUT_DIR = Path("runs/round_robin/human-play")
TILE = 18  # px per tile
BLUE, RED = "#2a78d6", "#eb6834"
BLUE_DK, RED_DK = "#174a8a", "#9a3a14"


def opponents(root: Path) -> dict[str, dict]:
    """The search bots + every LLM player found in the config files (first definition of a name wins)."""
    out = {spec["name"]: spec for spec in human_bot_specs("turn-based").values()}
    for f in [root / "configs" / "claude.toml", root / "config.toml", *sorted((root / "configs").glob("*.toml"))]:
        try:
            cfg = tomllib.loads(f.read_text())
        except Exception:
            continue
        for p in cfg.get("players", []):
            if p.get("type", "llm") == "llm" and p["name"] not in out:
                out[p["name"]] = {k: v for k, v in p.items() if k != "deck"}
    return out


# ---------------------------------------------------------------- board
def board_svg(game: Game) -> str:
    s = game.state
    W, H = 18 * TILE, 32 * TILE

    def px(tx, ty):
        return tx * TILE, (32 - ty) * TILE

    parts = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
             f'style="border-radius:8px;font-family:system-ui,sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#8fc26a"/>']
    for ty in range(32):  # checkerboard
        for tx in range(18):
            if (tx + ty) % 2:
                x, y = px(tx, ty + 1)
                parts.append(f'<rect x="{x}" y="{y}" width="{TILE}" height="{TILE}" fill="#86b962"/>')
    parts.append(f'<rect x="0" y="{px(0, 32)[1]}" width="{W}" height="{15 * TILE}" fill="{RED}" opacity="0.07"/>')
    parts.append(f'<rect x="0" y="{px(0, 15)[1]}" width="{W}" height="{15 * TILE}" fill="{BLUE}" opacity="0.07"/>')
    x, y = px(0, 17)
    parts.append(f'<rect x="0" y="{y}" width="{W}" height="{2 * TILE}" fill="#4aa3df"/>')
    for bx in (2.5, 13.5):
        x, y = px(bx, 17)
        parts.append(f'<rect x="{x}" y="{y}" width="{2 * TILE}" height="{2 * TILE}" fill="#b98b5a"/>')
    # placement zones you can use (labels match the move list)
    from cr_arena.game import OWN_ZONES

    for name, (zx, zy) in OWN_ZONES.items():
        x, y = px(zx, zy)
        parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="none" stroke="#ffffff" stroke-opacity="0.7" stroke-dasharray="2 2"/>')
    for sp in s.spells:
        tx, ty = game.own_tiles(HUMAN, sp.aim_x, sp.aim_y)
        x, y = px(tx, ty)
        c = BLUE if sp.team == HUMAN else RED
        parts.append(f'<circle cx="{x}" cy="{y}" r="{1.6 * TILE}" fill="{c}" fill-opacity="0.18" stroke="{c}" stroke-dasharray="4 3"/>'
                     f'<text x="{x}" y="{y - 1.8 * TILE}" font-size="10" text-anchor="middle" fill="#1b1b1b">{escape(game.card_name(sp.card_id))}</text>')
    ents = sorted(s.entities, key=lambda e: (e.flying, e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)))
    for e in ents:
        if e.hp <= 0:
            continue
        tx, ty = game.own_tiles(HUMAN, e.x, e.y)
        x, y = px(tx, ty)
        mine = e.team == HUMAN
        fill, stroke = (BLUE, BLUE_DK) if mine else (RED, RED_DK)
        r = max(5.0, e.radius / game.sub * TILE)
        tower = e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER)
        alpha = "0.5" if e.deploy_ticks > 0 else "1"
        if tower or e.kind == EntityKind.BUILDING:
            r = r if not tower else (1.6 if e.kind == EntityKind.KING_TOWER else 1.25) * TILE
            parts.append(f'<rect x="{x - r}" y="{y - r}" width="{2 * r}" height="{2 * r}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="2" opacity="{alpha}"/>')
        else:
            if e.flying:
                parts.append(f'<ellipse cx="{x}" cy="{y + r}" rx="{r}" ry="{r * 0.4}" fill="#000" opacity="0.2"/>')
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{"#fff" if e.flying else stroke}" stroke-width="{2 if e.flying else 1.5}" opacity="{alpha}"/>')
        label = "K" if e.kind == EntityKind.KING_TOWER else ("P" if tower else game.card_name(e.card_id)[:2])
        if r >= 6:
            parts.append(f'<text x="{x}" y="{y + 4}" font-size="{min(12, r)}" font-weight="600" text-anchor="middle" fill="#fff">{escape(label)}</text>')
        frac = max(0.0, min(1.0, e.hp / e.max_hp)) if e.max_hp else 0
        bw = max(16.0, 2 * r)
        hpc = "#3ecf4a" if frac > 0.6 else ("#f2c230" if frac > 0.3 else "#f0503c")
        parts.append(f'<rect x="{x - bw / 2}" y="{y - r - 7}" width="{bw}" height="4" fill="#000" opacity="0.55"/>'
                     f'<rect x="{x - bw / 2}" y="{y - r - 7}" width="{bw * frac}" height="4" fill="{hpc}"/>')
        if tower:
            parts.append(f'<text x="{x}" y="{y - r - 10}" font-size="11" font-weight="600" text-anchor="middle" fill="#1b1b1b">{e.hp}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- game loop
def _start(opp_spec: dict, my_deck: list[str], opp_deck: list[str], seed: int, ticks: int):
    game = Game(my_deck, opp_deck, seed=seed, decision_ticks=ticks)
    opp = build_player(opp_spec)
    opp.start(game, 1)
    st.session_state.play = {
        "game": game, "opp": opp, "opp_name": opp_spec["name"], "seed": seed, "ticks": ticks,
        "decks": (my_deck, opp_deck), "step": 0, "rows": [], "t0": time.time(), "saved": None,
        "log": [], "opp_think": [],
    }


def _advance(P: dict, my_move_index: int | None) -> None:
    """Apply the human's move (None = forced wait) together with the opponent's, run one interval."""
    game: Game = P["game"]
    moves = [game.legal_moves(0), game.legal_moves(1)]
    text_h = game.describe(0, moves[0])
    text_o = game.describe(1, moves[1])
    if len(moves[1]) > 1:
        d = P["opp"].decide(game, 1, text_o, moves[1])
        game.consume_events(1)
    else:
        d = Decision(0, raw="(forced wait, not asked)")
    asked_h = my_move_index is not None
    if asked_h:
        game.consume_events(0)
    chosen = [moves[0][my_move_index or 0], moves[1][d.index]]
    left, _ = game.time_left_s()
    snap = [(p.elixir_milli / 1000, sum(p.tower_hp)) for p in game.state.players]
    res = game.step(chosen)
    for t, (dd, asked, txt) in enumerate(((Decision(chosen[0].index, raw="(human)"), asked_h, text_h), (d, len(moves[1]) > 1, text_o))):
        P["rows"].append({
            "step": P["step"], "team": t, "player": "human" if t == 0 else P["opp_name"], "time_left": round(left, 1),
            "elixir": snap[t][0], "my_towers": snap[t][1], "enemy_towers": snap[1 - t][1], "n_moves": len(moves[t]),
            "asked": int(asked), "move": chosen[t].label(), "result": res[t], "ok": int(dd.ok), "error": dd.error,
            "latency_s": round(dd.latency_s, 2), "tokens_in": dd.usage.get("in", 0), "tokens_out": dd.usage.get("out", 0),
            "cache_read": dd.usage.get("cache_read", 0), "cache_write": dd.usage.get("cache_write", 0),
            "raw": dd.raw, "state": txt if asked else "", "cost_usd": dd.usage.get("cost", 0.0)})
    if res[1] != "wait":
        P["log"].append(f"[{int(left) // 60}:{int(left) % 60:02d}] opponent {res[1]}")
        if d.raw and len(moves[1]) > 1 and not d.raw.startswith("("):
            P["opp_think"].append((f"{int(left) // 60}:{int(left) % 60:02d}", d.raw))
    if res[0] != "wait":
        P["log"].append(f"[{int(left) // 60}:{int(left) % 60:02d}] you {res[0]}")
    P["step"] += 1


def _fast_forward(P: dict, max_steps: int = 400) -> None:
    """Skip intervals where waiting is your only option (no elixir / opening lockout)."""
    game: Game = P["game"]
    n = 0
    while not game.over and len(game.legal_moves(0)) == 1 and n < max_steps:
        _advance(P, None)
        n += 1


def _save(P: dict, get_db) -> str:
    game: Game = P["game"]
    db = get_db()
    winner, crowns, towers, ticks, trace = game.finish()
    mid = P.setdefault("match_id", f"human__vs__{P['opp_name']}__{uuid.uuid4().hex}")
    (OUT_DIR / "replays").mkdir(parents=True, exist_ok=True)
    rp = OUT_DIR / "replays" / f"{mid}.msgpack"
    if trace is not None:
        save_trace(trace, rp)
    with db.transaction():
        jid = db.get_or_create_job("human-play", "", ["human"], [], P["ticks"], 0, "Games played by a human on the Play page")
        db.queue_matches(jid, [{"match_id": mid, "blue": "human", "red": P["opp_name"], "seed": P["seed"],
                                "deck": {"blue": P["decks"][0], "red": P["decks"][1]}}])
        db.match_started(jid, mid, "", str(rp))
        db.set_match_decks(jid, mid, *P["decks"])
        db.add_decisions([(jid, mid, r["step"], r["team"], r["player"], r["time_left"], r["elixir"], r["my_towers"],
                           r["enemy_towers"], r["n_moves"], r["asked"], r["move"], r["result"], r["ok"], r["error"],
                           r["latency_s"], r["tokens_in"], r["tokens_out"], r["cache_read"], r["cache_write"], r["raw"],
                           r["state"], r["cost_usd"]) for r in P["rows"]])
        stats = {"decisions": P["step"], "asked": sum(r["asked"] for r in P["rows"] if r["team"] == 0)}
        db.match_finished(jid, {"match_id": mid, "winner": int(winner), "crowns": crowns, "tower_hp": towers, "ticks": ticks,
                                "wall_s": round(time.time() - P["t0"], 1), "stats_blue": stats, "stats_red": {}})
        n = db.query("SELECT COUNT(*) AS n FROM matches WHERE job_id = ?", (jid,))[0]["n"]
        db.execute("UPDATE jobs SET total_matches = ?, status = 'done' WHERE id = ?", (n, jid))
    return mid


# ---------------------------------------------------------------- page
def page_play(root: Path, get_db) -> None:
    st.caption("You play blue (bottom) through exactly the interface the models get: every 2 s of game time you pick "
               "one move from the legal-move list, and the game pauses while you decide. Finished games are saved "
               "under the job **human-play**.")
    st.info("For a real-time game against the bots (no pausing, drag cards onto the arena), run "
            "`uv run python -m cr_arena.live` and open http://localhost:8600.")
    P = st.session_state.get("play")
    opps = opponents(root)
    if P is None or st.button("New game"):
        if P is not None:
            st.session_state.pop("play")
            st.rerun()
        with st.form("setup"):
            c1, c2, c3 = st.columns(3)
            opp = model_selectbox("Opponent", list(opps), target=c1, help="Models are called through their configured provider "
                                                               "(claude_cli = your Claude Code login).")
            decks = deck_options(get_db())
            mine = c2.selectbox("Your deck", list(decks))
            theirs = c3.selectbox("Opponent deck", ["same as mine"] + list(decks))
            c4, c5 = st.columns(2)
            seed = c4.number_input("Seed (shuffle)", 1, 10_000, 1)
            ticks = c5.select_slider("Decision interval (game time)", [20, 40, 60], value=40,
                                     format_func=lambda t: f"{t * 0.05:.0f} s" if t % 20 == 0 else str(t))
            for name, d in decks.items():
                st.caption(f"**{name}**: {', '.join(d)}")
            if st.form_submit_button("Start game", type="primary"):
                od = decks[mine] if theirs == "same as mine" else decks[theirs]
                with loading("Starting your game..."):
                    _start(opps[opp], decks[mine], od, int(seed), int(ticks))
                    _fast_forward(st.session_state.play)
                st.rerun()
        return

    game: Game = P["game"]
    s = game.state
    me, en = s.players[0], s.players[1]
    left, ot = game.time_left_s()
    board, side = st.columns([1, 1.25])
    with board:
        st.markdown(board_svg(game), unsafe_allow_html=True)
    with side:
        st.markdown(f"<b>You</b> (blue) vs {model_label(P['opp_name'])} (red)", unsafe_allow_html=True)
        m = st.columns(3)
        m[0].metric("Time left", f"{int(left) // 60}:{int(left) % 60:02d}" + (" OT" if ot else ""))
        m[1].metric("Crowns (you-opp)", f"{me.crowns}-{en.crowns}")
        m[2].metric("Your elixir", f"{me.elixir_milli / 1000:.1f}")
        st.progress(min(1.0, me.elixir_milli / 10000), text=None)

        if game.over:
            if P["saved"] is None:
                with loading("Saving game results..."):
                    P["saved"] = _save(P, get_db)
            w = s.winner
            msg = {0: "🏆 You win!", 1: f"{P['opp_name']} wins.", 2: "Draw."}.get(w, "Game over")
            st.subheader(f"{msg}  {me.crowns}-{en.crowns}")
            st.markdown(f"Saved as `{P['saved']}`. Open it under **Match** (job *human-play*) for the replay and the "
                        f"opponent's reasoning.")
            if st.button("Play again", type="primary"):
                st.session_state.pop("play")
                st.rerun()
        else:
            moves = game.legal_moves(0)
            hand = []
            for slot, cid in enumerate(me.hand):
                c = game.card_by_id.get(cid)
                if c:
                    hand.append(f"**{c.name}** ({me.hand_costs[slot] if len(me.hand_costs) == len(me.hand) else c.elixir})")
            st.markdown("Hand: " + " · ".join(hand) + f" · next: {game.card_name(me.next_card)}")
            ev = game.mem[0].events[-6:]
            if ev:
                st.caption("Since your last move: " + "; ".join(ev))
            st.markdown("**Your move**")
            choice = None
            if st.button("⏸ wait (save elixir)", width="stretch"):
                choice = 0
            by_card: dict[str, list] = {}
            for mv in moves[1:]:
                by_card.setdefault(f"{mv.card} ({mv.cost}, {mv.kind.lower()})", []).append(mv)
            for card, mvs in by_card.items():
                with st.expander(card, expanded=True):
                    cols = st.columns(3)
                    for i, mv in enumerate(mvs):
                        if cols[i % 3].button(mv.target, key=f"mv{P['step']}_{mv.index}", width="stretch"):
                            choice = mv.index
            if choice is not None:
                try:
                    with loading("Waiting for the opponent's move..."):
                        _advance(P, choice)
                        _fast_forward(P)
                except InfraError as exc:
                    st.error(f"Opponent model unreachable: {exc}")
                st.rerun()
        with st.expander("Game log", expanded=False):
            st.text("\n".join(P["log"][-40:]) or "nothing yet")
        if P["opp_think"]:
            with st.expander(f"{P['opp_name']}'s reasoning (last move)"):
                t, raw = P["opp_think"][-1]
                st.caption(t)
                st.text(raw)
