"""Turn-based bot-vs-bot duels: which bot is strongest when the clock stops for every decision.

    uv run python -m cr_arena.turn_duel --out runs/turn-duel/v1 --seeds 1 2 3

Games use the benchmark's own match loop (cr_arena.match.play_match): every 40 ticks both bots
pick from the same numbered move list the models get, plays land at once, and the game waits for
both answers, so thinking time is free. The planner plays through PlannerPlayer, its look-ahead
applied to the numbered moves. Every bot is deterministic for a given seed, so games can run in
parallel without changing results. Results append to results.jsonl and an interrupted run resumes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .bots import human_bot_specs
from .decks import CLASSIC_DECKS
from .live_duel import DEFAULT_DECKS, schedule, summarize
from .match import play_match
from .players import build_player

DECISION_TICKS = 40


def bot_specs(planner_workers: int = 0) -> dict[str, dict]:
    """The turn-based catalog bots plus the planner on the numbered menu."""
    specs = {"planner": {"name": "planner-bot", "type": "planner", "workers": planner_workers}}
    specs.update(human_bot_specs("turn-based"))
    return specs


def _play(job: tuple) -> dict:
    specs, case, out = job
    blue, red = build_player(specs[case["blue"]]), build_player(specs[case["red"]])
    for player in (blue, red):  # most bots do not time themselves; measure all of them the same way
        def timed(*a, _decide=player.decide):
            t0 = time.perf_counter()
            decision = _decide(*a)
            decision.latency_s = time.perf_counter() - t0
            return decision
        player.decide = timed
    try:
        r = play_match(blue, red, CLASSIC_DECKS[case["deck_blue"]], CLASSIC_DECKS[case["deck_red"]], case["seed"],
                       case["id"], Path(out), decision_ticks=DECISION_TICKS)
    finally:
        for p in (blue, red):
            if hasattr(p, "close"):
                p.close()
    think = [[], []]
    play_think = [[], []]
    for line in (Path(out) / "logs" / f"{case['id']}.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["raw"] == "(forced wait, not asked)":
            continue
        think[row["team"]].append(row["latency_s"])
        if not row["move"].lower().startswith("wait"):
            play_think[row["team"]].append(row["latency_s"])
    stats = []
    for team, key in enumerate(("stats_blue", "stats_red")):
        st = r[key]
        stats.append({"asked": st.get("asked", 0), "answered": st.get("asked", 0), "plays": st["plays"],
                      "discarded": 0, "illegal_or_unparsed": st["illegal_or_unparsed"],
                      "think_mean_s": round(sum(think[team]) / len(think[team]), 3) if think[team] else None,
                      "play_think_mean_s": (round(sum(play_think[team]) / len(play_think[team]), 3)
                                            if play_think[team] else None)})
    return {"winner": r["winner"], "crowns": r["crowns"], "tower_hp": r["tower_hp"], "ticks": r["ticks"],
            "wall_s": r["wall_s"], "stats": stats, "case": case}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--bots", nargs="+", help="bot IDs (default: planner, search, search-v2)")
    ap.add_argument("--decks", nargs="+", default=DEFAULT_DECKS, choices=CLASSIC_DECKS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--cross-decks", action="store_true", help="also play distinct deck assignments")
    ap.add_argument("--parallel", type=int, default=4, help="games at once (results do not depend on it)")
    args = ap.parse_args()

    specs = bot_specs()
    keys = args.bots or list(specs)
    if set(keys) - set(specs) or len(keys) < 2:
        ap.error(f"need two or more bots from {list(specs)}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = schedule(keys, args.decks, args.seeds, args.cross_decks)
    manifest = {"mode": "turn-based", "bots": {k: specs[k] for k in keys}, "decks": args.decks, "seeds": args.seeds,
                "cross_decks": args.cross_decks, "decision_ticks": DECISION_TICKS, "command_delay_ticks": 0,
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"])).hexdigest(),
                "machine": {"platform": platform.platform(), "cpus": os.cpu_count(),
                            "python": platform.python_version()},
                "cases": [c["id"] for c in cases]}
    path = out / "manifest.json"
    if path.exists():
        old = json.loads(path.read_text())
        if any(old.get(k) != json.loads(json.dumps(manifest[k])) for k in ("mode", "bots", "decks", "cross_decks")):
            raise SystemExit("output already holds a different run; choose a new --out")
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    results_path = out / "results.jsonl"
    results = [json.loads(line) for line in results_path.read_text().splitlines()] if results_path.exists() else []
    done = {r["case"]["id"] for r in results}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} games, {len(done)} already played, {len(todo)} to go", flush=True)
    with ProcessPoolExecutor(args.parallel) as pool:
        futures = [pool.submit(_play, (specs, c, str(out))) for c in todo]
        for i, f in enumerate(as_completed(futures), len(done) + 1):
            r = f.result()
            results.append(r)
            with results_path.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            summary = summarize(results, keys)
            (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            case, st = r["case"], r["stats"]
            who = {0: case["blue"], 1: case["red"], 2: "draw"}.get(r["winner"], "unfinished")
            print(f"{i}/{len(cases)} {case['id']}: {who} ({r['crowns'][0]}-{r['crowns'][1]}) in {r['wall_s']}s; "
                  f"think per play {st[0]['play_think_mean_s']}s/{st[1]['play_think_mean_s']}s; "
                  + ", ".join(f"{k} {summary['overall'][k]['score']}" for k in summary["ranking"]), flush=True)


if __name__ == "__main__":
    main()
