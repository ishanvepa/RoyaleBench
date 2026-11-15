"""Play one match between two players, logging every decision and saving a replay."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from royalegym.replay import save_trace

from .game import Game
from .players import Decision, Player


def play_match(blue: Player, red: Player, deck_blue: list[str], deck_red: list[str], seed: int,
               match_id: str, out_dir: Path, decision_ticks: int = 40, verbose: bool = False,
               on_step=None, record: bool = True) -> dict:
    """``on_step(rows)`` gets one dict per side after every decision interval (for the DB)."""
    out_dir = Path(out_dir)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    (out_dir / "replays").mkdir(parents=True, exist_ok=True)
    game = Game(deck_blue, deck_red, seed=seed, decision_ticks=decision_ticks, record=record)
    players = [blue, red]
    for team, p in enumerate(players):
        p.start(game, team)
    stats = [{"decisions": 0, "plays": 0, "errors": 0, "illegal_or_unparsed": 0, "latency_s": 0.0,
              "tokens_in": 0, "tokens_out": 0} for _ in players]
    t0 = time.time()
    log_path = out_dir / "logs" / f"{match_id}.jsonl"
    with log_path.open("w") as log, ThreadPoolExecutor(max_workers=2) as pool:
        step_no = 0
        while not game.over:
            moves = [game.legal_moves(t) for t in (0, 1)]
            texts = [game.describe(t, moves[t]) for t in (0, 1)]
            # Both players think at the same time on the same frozen state.
            # Only "wait" is legal (not enough elixir / opening lockout): don't spend an API call.
            futs = [None if len(moves[t]) == 1 else pool.submit(players[t].decide, game, t, texts[t], moves[t])
                    for t in (0, 1)]
            decisions = [Decision(0, raw="(forced wait, not asked)") if f is None else f.result() for f in futs]
            for t in (0, 1):
                if futs[t] is not None:
                    game.consume_events(t)
            chosen = [decisions[t].move or moves[t][decisions[t].index] for t in (0, 1)]
            left, _ = game.time_left_s()
            snap = [(p.elixir_milli / 1000, sum(p.tower_hp)) for p in game.state.players]
            results = game.step(chosen)
            rows = []
            for t in (0, 1):
                st, d = stats[t], decisions[t]
                st["decisions"] += 1
                st["asked"] = st.get("asked", 0) + int(futs[t] is not None)
                st["plays"] += int(chosen[t].slot >= 0 and results[t].startswith("played"))
                st["latency_s"] += d.latency_s
                st["tokens_in"] += d.usage.get("in", 0)
                st["tokens_out"] += d.usage.get("out", 0)
                st["cache_read"] = st.get("cache_read", 0) + d.usage.get("cache_read", 0)
                st["cache_write"] = st.get("cache_write", 0) + d.usage.get("cache_write", 0)
                st["cost_usd"] = round(st.get("cost_usd", 0.0) + d.usage.get("cost", 0.0), 6)
                if not d.ok:
                    st["errors" if d.error and not d.error.startswith(("no MOVE", "illegal")) else "illegal_or_unparsed"] += 1
                rows.append({
                    "step": step_no, "team": t, "player": players[t].name, "time_left": round(left, 1),
                    "elixir": snap[t][0], "my_towers": snap[t][1], "enemy_towers": snap[1 - t][1],
                    "n_moves": len(moves[t]), "asked": int(futs[t] is not None), "move": chosen[t].label(),
                    "result": results[t], "ok": int(d.ok), "error": d.error, "latency_s": round(d.latency_s, 2),
                    "tokens_in": d.usage.get("in", 0), "tokens_out": d.usage.get("out", 0),
                    "cache_read": d.usage.get("cache_read", 0), "cache_write": d.usage.get("cache_write", 0),
                    "cost_usd": d.usage.get("cost", 0.0), "raw": d.raw, "state": texts[t] if futs[t] is not None else "",
                })
                log.write(json.dumps({
                    "step": step_no, "time_left": round(left, 1), "team": t, "player": players[t].name,
                    "state": texts[t], "n_moves": len(moves[t]), "move": chosen[t].label(), "result": results[t],
                    "raw": d.raw, "ok": d.ok, "error": d.error, "latency_s": round(d.latency_s, 2), "usage": d.usage,
                    "diagnostics": d.diagnostics,
                }) + "\n")
            log.flush()
            if on_step:
                on_step(rows)
            if verbose:
                print(f"[{match_id}] {left:6.1f}s  blue: {results[0]:<45} red: {results[1]}")
            step_no += 1
    winner, crowns, towers, ticks, trace = game.finish()
    if trace is not None:
        save_trace(trace, out_dir / "replays" / f"{match_id}.msgpack")
    for st in stats:
        st["latency_s"] = round(st["latency_s"], 1)
    return {
        "match_id": match_id, "blue": blue.name, "red": red.name, "seed": seed,
        "deck_blue": deck_blue, "deck_red": deck_red, "winner": int(winner),  # 0 blue, 1 red, 2 draw
        "crowns": crowns, "tower_hp": towers, "ticks": ticks, "wall_s": round(time.time() - t0, 1),
        "stats_blue": stats[0], "stats_red": stats[1],
    }
