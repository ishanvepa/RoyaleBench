"""Live bot-vs-bot duels: which human-play bot is strongest in real time.

    uv run python -m cr_arena.live_duel --out runs/live-duel/v1 --seeds 1 2

Each game runs the live server's own loop: the engine at its real speed (20 ticks a second),
each bot thinking in its own process on snapshots, asked at most every 0.25 s of game time,
plays landing COMMAND_DELAY_TICKS later, and Search v2's stale answers discarded by the same
check the live server uses. Thinking time is therefore part of strength, as it is against a human.

Every pairing of the catalog's live bots plays every deck with seats swapped. Games run one at a
time so that the bots do not share the machine with other games. Results append to results.jsonl
and an interrupted run resumes where it stopped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

from royalegym.protocol import DeployStatus
from royalegym.replay import save_trace

from .bots import human_bot_specs
from .decks import CLASSIC_DECKS
from .game import Game
from .live import BOT_EVERY_TICKS, COMMAND_DELAY_TICKS, _bot_worker, bot_answer_command

DEFAULT_DECKS = ["giant-beatdown", "hog-2.6-cycle", "lavaloon"]
READY_TIMEOUT_S = 120


def play_live(specs: list[dict], decks: list[list[str]], seed: int, delay: int = COMMAND_DELAY_TICKS,
              replay: Path | None = None, max_ticks: int | None = None) -> dict:
    """One real-time game between two live bots. specs[0] plays blue (team 0)."""
    game = Game(decks[0], decks[1], seed=seed, record=replay is not None, command_delay_ticks=delay)
    e = game.engine
    ctx = mp.get_context("spawn")
    conns, procs = [], []
    stats = [{"asked": 0, "answered": 0, "waits": 0, "sent": 0, "accepted": 0, "refused": 0, "discarded": 0,
              "think_s": [], "play_think_s": []} for _ in specs]
    pool = ThreadPoolExecutor(2)
    try:
        for team, spec in enumerate(specs):
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_bot_worker, args=(child, decks, seed, spec, delay, team), daemon=False)
            proc.start()
            child.close()
            conns.append(parent)
            procs.append(proc)
        for team, conn in enumerate(conns):  # both start thinking on the same clock
            if not conn.poll(READY_TIMEOUT_S):
                raise RuntimeError(f"{specs[team]['name']} did not start")
            conn.recv()
        busy, asked_tick, asked_at = [False, False], [-10_000, -10_000], [0.0, 0.0]
        tick_s = game.state.tick_ms / 1000
        t0 = due = time.perf_counter()
        lag_resets = 0
        max_behind = 0.0
        while not game.over and (max_ticks is None or game.state.tick < max_ticks):
            cmds = []
            for team, conn in enumerate(conns):
                if busy[team] and conn.poll():
                    answer = conn.recv()
                    busy[team] = False
                    st = stats[team]
                    st["answered"] += 1
                    took = time.perf_counter() - asked_at[team]
                    st["think_s"].append(took)
                    command, raw = bot_answer_command(game, answer, team)
                    if command is not None:
                        cmds.append(command)
                        st["sent"] += 1
                        st["play_think_s"].append(took)
                    elif "(discarded" in raw:
                        st["discarded"] += 1
                    else:
                        st["waits"] += 1
            tick = game.state.tick
            res = e.step(cmds, 1)
            if game.recorder:
                game.recorder.record_step(tick, 1, list(cmds), res)
                game.recorder.record_frame(e)
            for r in res:
                stats[r.team]["accepted" if r.status == DeployStatus.OK else "refused"] += 1
            for team, conn in enumerate(conns):
                if not busy[team] and tick - asked_tick[team] >= BOT_EVERY_TICKS:
                    pool.submit(conn.send, e.save_state())  # a pipe write can block: keep it off the clock
                    busy[team], asked_tick[team], asked_at[team] = True, tick, time.perf_counter()
                    stats[team]["asked"] += 1
            due += tick_s
            wait = due - time.perf_counter()
            max_behind = max(max_behind, -wait)
            if wait < -0.25:  # same rule as the live server: never sprint to catch up
                due = time.perf_counter()
                lag_resets += 1
            elif wait > 0:
                time.sleep(wait)
        wall = time.perf_counter() - t0
    finally:
        for conn in conns:
            try:
                conn.send(None)
            except (OSError, ValueError):
                pass
        for proc in procs:
            proc.join(timeout=5)
            if proc.is_alive():
                proc.terminate()
        for conn in conns:
            conn.close()
        pool.shutdown(wait=False)
    winner, crowns, towers, ticks, trace = game.finish()
    if replay is not None and trace is not None:
        replay.parent.mkdir(parents=True, exist_ok=True)
        save_trace(trace, replay)
    for st in stats:
        think = sorted(st.pop("think_s"))
        st["think_mean_s"] = round(sum(think) / len(think), 3) if think else None
        st["think_p95_s"] = round(think[min(len(think) - 1, int(0.95 * len(think)))], 3) if think else None
        plays = st.pop("play_think_s")
        st["play_think_mean_s"] = round(sum(plays) / len(plays), 3) if plays else None
    return {"winner": int(winner), "crowns": crowns, "tower_hp": towers, "ticks": ticks,
            "wall_s": round(wall, 1), "clock_lag_resets": lag_resets, "max_behind_s": round(max_behind, 3),
            "stats": stats}


def schedule(bot_keys: list[str], decks: list[str], seeds: list[int], cross: bool) -> list[dict]:
    matchups = [(d, d) for d in decks] + ([(a, b) for a in decks for b in decks if a != b] if cross else [])
    cases = []
    for a, b in combinations(bot_keys, 2):
        for da, db in matchups:
            for seed in seeds:
                pair = f"{a}__vs__{b}__{da}__{db}__s{seed}"
                cases.append({"id": f"{pair}__swap0", "pair": pair, "blue": a, "red": b,
                              "deck_blue": da, "deck_red": db, "seed": seed})
                cases.append({"id": f"{pair}__swap1", "pair": pair, "blue": b, "red": a,
                              "deck_blue": db, "deck_red": da, "seed": seed})
    return cases


def score(result: dict, key: str) -> float:
    seat = 0 if result["case"]["blue"] == key else 1
    return 0.5 if result["winner"] == 2 else float(result["winner"] == seat)


def summarize(results: list[dict], bot_keys: list[str]) -> dict:
    overall = {k: {"games": 0, "points": 0.0, "wins": 0, "draws": 0, "losses": 0, "crowns_for": 0,
                   "crowns_against": 0} for k in bot_keys}
    head = {}
    think = {k: [] for k in bot_keys}
    play_think = {k: [] for k in bot_keys}
    discarded = {k: [0, 0] for k in bot_keys}
    for r in results:
        if r["winner"] not in (0, 1, 2):
            continue  # stopped early by --max-ticks
        case = r["case"]
        for team, key in enumerate((case["blue"], case["red"])):
            s = score(r, key)
            o = overall[key]
            o["games"] += 1
            o["points"] += s
            o["wins" if s == 1 else "draws" if s == 0.5 else "losses"] += 1
            o["crowns_for"] += r["crowns"][team]
            o["crowns_against"] += r["crowns"][1 - team]
            st = r["stats"][team]
            if st["think_mean_s"] is not None:
                think[key].append(st["think_mean_s"])
            if st.get("play_think_mean_s") is not None:
                play_think[key].append(st["play_think_mean_s"])
            discarded[key][0] += st["discarded"]
            discarded[key][1] += st["answered"]
        a, b = sorted((case["blue"], case["red"]), key=bot_keys.index)
        h = head.setdefault(f"{a} vs {b}", {"games": 0, a: 0.0, b: 0.0, "pairs": {}})
        h["games"] += 1
        h[a] += score(r, a)
        h[b] += score(r, b)
        h["pairs"].setdefault(case["pair"], []).append(score(r, a))
    for name, h in head.items():
        a, b = name.split(" vs ")
        pairs = [sum(v) / 2 for v in h.pop("pairs").values() if len(v) == 2]
        pos, neg = sum(v > 0.5 for v in pairs), sum(v < 0.5 for v in pairs)
        n = pos + neg
        # two-sided exact sign test over seat-swapped pairs that were not split
        tail = sum(math.comb(n, k) for k in range(max(pos, neg), n + 1)) / 2 ** n if n else 1.0
        h.update({"complete_pairs": len(pairs), f"pairs_won_{a}": pos, f"pairs_won_{b}": neg,
                  "pairs_split": len(pairs) - n, "sign_test_two_sided_p": min(1.0, 2 * tail)})
    for k, o in overall.items():
        o["score"] = round(o["points"] / o["games"], 3) if o["games"] else None
        o["mean_think_s"] = round(sum(think[k]) / len(think[k]), 3) if think[k] else None
        o["mean_play_think_s"] = round(sum(play_think[k]) / len(play_think[k]), 3) if play_think[k] else None
        o["discarded_share"] = round(discarded[k][0] / discarded[k][1], 3) if discarded[k][1] else None
    ranking = sorted(bot_keys, key=lambda k: -(overall[k]["score"] or 0))
    return {"games": sum(o["games"] for o in overall.values()) // 2, "ranking": ranking, "overall": overall, "head_to_head": head}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--bots", nargs="+", help="catalog IDs (default: every live bot)")
    ap.add_argument("--decks", nargs="+", default=DEFAULT_DECKS, choices=CLASSIC_DECKS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--cross-decks", action="store_true", help="also play distinct deck assignments")
    ap.add_argument("--planner-workers", type=int, default=8,
                    help="planner pool size; the live server gives a lone game 8")
    ap.add_argument("--max-ticks", type=int, help="stop each game early (smoke tests only)")
    args = ap.parse_args()

    specs = human_bot_specs("live")
    keys = args.bots or list(specs)
    unknown = set(keys) - set(specs)
    if unknown or len(keys) < 2:
        ap.error(f"need two or more live bots from {list(specs)}")
    for k in keys:
        if specs[k]["type"] == "planner":
            specs[k] = {**specs[k], "workers": args.planner_workers}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = schedule(keys, args.decks, args.seeds, args.cross_decks)
    manifest = {"bots": {k: specs[k] for k in keys}, "decks": args.decks, "seeds": args.seeds,
                "cross_decks": args.cross_decks, "command_delay_ticks": COMMAND_DELAY_TICKS,
                "bot_every_ticks": BOT_EVERY_TICKS, "max_ticks": args.max_ticks,
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"])).hexdigest(),
                "machine": {"platform": platform.platform(), "cpus": os.cpu_count(),
                            "python": platform.python_version()},
                "cases": [c["id"] for c in cases]}
    path = out / "manifest.json"
    if path.exists():
        old = json.loads(path.read_text())
        same = {"bots", "decks", "cross_decks", "command_delay_ticks", "bot_every_ticks", "max_ticks"}
        if any(old.get(k) != json.loads(json.dumps(manifest[k])) for k in same):
            raise SystemExit("output already holds a different run; choose a new --out")
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    results_path = out / "results.jsonl"
    results = [json.loads(line) for line in results_path.read_text().splitlines()] if results_path.exists() else []
    done = {r["case"]["id"] for r in results}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} games, {len(done)} already played; about {len(todo) * 4} min to go", flush=True)
    for i, case in enumerate(todo, len(done) + 1):
        r = play_live([specs[case["blue"]], specs[case["red"]]],
                      [CLASSIC_DECKS[case["deck_blue"]], CLASSIC_DECKS[case["deck_red"]]], case["seed"],
                      replay=out / "replays" / f"{case['id']}.msgpack", max_ticks=args.max_ticks)
        r["case"] = case
        results.append(r)
        with results_path.open("a") as f:
            f.write(json.dumps(r) + "\n")
        summary = summarize(results, keys)
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        who = {0: case["blue"], 1: case["red"], 2: "draw"}.get(r["winner"], "unfinished")
        st = r["stats"]
        print(f"{i}/{len(cases)} {case['id']}: {who} ({r['crowns'][0]}-{r['crowns'][1]}) in {r['wall_s']}s; "
              f"think per play {st[0]['play_think_mean_s']}s/{st[1]['play_think_mean_s']}s; lag resets {r['clock_lag_resets']}; "
              + ", ".join(f"{k} {summary['overall'][k]['score']}" for k in summary["ranking"]), flush=True)


if __name__ == "__main__":
    main()
