"""Bot against bot under live-play conditions (free placement, command delay, a decision every fraction
of a second), to measure a bot before a human has to.

    uv run python -m cr_arena.duel --a planner --b heuristic --games 12
    uv run python -m cr_arena.duel --a planner --b planner:prefilter=1 --games 12 --out runs/duel/prefilter

A spec is a kind (planner, search, heuristic, random) plus optional settings, e.g. planner:horizon_s=8,top_k=6.
Each pairing is played from both sides on every (deck, seed), so seat and deck luck cancel out. Every bot
here is deterministic and decides on a fixed tick schedule (thinking takes no game time), so a run repeats
exactly. With --out, finished games are appended to games.jsonl and a rerun skips them.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from multiprocessing import get_context
from pathlib import Path

from royalegym.protocol import DeployCommand, DeployStatus

from .decks import CLASSIC_DECKS
from .game import Game

LIVE_DELAY = 21


def _value(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return float(v)


def _parse(spec: str) -> tuple[str, dict]:
    kind, _, rest = spec.partition(":")
    opts = {}
    for kv in filter(None, rest.split(",")):
        k, _, v = kv.partition("=")
        opts[k] = _value(v)
    return kind, opts


class _Agent:
    """Wraps either bot family behind one call: act(game) -> DeployCommand | None."""

    def __init__(self, spec: str, decks, seed: int, team: int, delay: int):
        self.kind, opts = _parse(spec)
        self.team = team
        self.think_s, self.decisions = 0.0, 0
        if self.kind == "planner":
            from .bots.planner import Planner

            self.bot = Planner(decks, seed, team, delay=delay, **opts)
            self.every = 8
        else:
            from .players import build_player

            self.bot = build_player({"name": spec, "type": self.kind, **opts})
            self.bot.sim = Game(decks[0], decks[1], seed=seed, record=False, command_delay_ticks=delay)
            self.every = 20

    def act(self, game: Game) -> DeployCommand | None:
        t0 = time.perf_counter()
        try:
            return self._act(game)
        finally:
            self.think_s += time.perf_counter() - t0
            self.decisions += 1

    def _act(self, game: Game) -> DeployCommand | None:
        if self.kind == "planner":
            play, _note = self.bot.act(game.engine.save_state())
            return DeployCommand(*play) if play else None
        moves = game.legal_moves(self.team)
        if len(moves) == 1:
            return None
        mv = moves[self.bot.decide(game, self.team, "", moves).index]
        return DeployCommand(self.team, mv.slot, mv.x, mv.y) if mv.slot >= 0 else None


def play_one(job: tuple) -> dict:
    spec_blue, spec_red, deck, seed, delay = job
    decks = [CLASSIC_DECKS[deck], CLASSIC_DECKS[deck]]
    game = Game(decks[0], decks[1], seed=seed, record=False, command_delay_ticks=delay)
    agents = [_Agent(spec_blue, decks, seed, 0, delay), _Agent(spec_red, decks, seed, 1, delay)]
    plays, refused = [0, 0], [0, 0]
    t0 = time.time()
    while not game.over:
        tick = game.state.tick
        cmds = []
        for a in agents:
            if tick % a.every == (0 if a.team == 0 else a.every // 2):  # the two seats decide on different ticks
                c = a.act(game)
                if c:
                    cmds.append(c)
        for r in game.engine.step(cmds, 1) or []:
            if r.status == DeployStatus.OK:
                plays[r.team] += 1
            else:
                refused[r.team] += 1
    for a in agents:
        if hasattr(a.bot, "close"):
            a.bot.close()
    s = game.state
    hp = [[max(0, h) for h in p.tower_hp] for p in s.players]
    full = [[max(1, m) for m in p.tower_max_hp] for p in s.players]
    return {"blue": spec_blue, "red": spec_red, "deck": deck, "seed": seed, "delay": delay, "winner": int(s.winner),
            "crowns": [p.crowns for p in s.players], "towers": [sum(h) for h in hp],
            # share of its total tower hit points each side still has at the end
            "tower_frac": [round(sum(hp[t]) / sum(full[t]), 4) for t in (0, 1)],
            "ticks": s.tick, "plays": plays, "refused": refused,
            "think_ms": [round(1000 * a.think_s / max(1, a.decisions), 1) for a in agents],
            "secs": round(time.time() - t0)}


def summarize(games: list[dict], a: str, b: str) -> dict:
    """A's results against B. Games on the same (deck, seed) with seats swapped form one pair."""
    pairs: dict[tuple, list[tuple[float, float]]] = {}
    wins = draws = losses = crowns_a = crowns_b = 0
    for g in games:
        if {g["blue"], g["red"]} != {a, b}:
            continue
        i = 0 if g["blue"] == a else 1
        score = 0.5 if g["winner"] == 2 else float(g["winner"] == i)
        wins, draws, losses = wins + (score == 1), draws + (score == 0.5), losses + (score == 0)
        crowns_a, crowns_b = crowns_a + g["crowns"][i], crowns_b + g["crowns"][1 - i]
        margin = g["tower_frac"][i] - g["tower_frac"][1 - i]  # -1 .. 1, positive = A kept more of its towers
        pairs.setdefault((g["deck"], g["seed"]), []).append((score, margin))
    full = [v for v in pairs.values() if len(v) == 2]
    ps = [sum(s for s, _ in v) / 2 for v in full]
    pos, neg = sum(p > 0.5 for p in ps), sum(p < 0.5 for p in ps)
    n = pos + neg
    sign_p = sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n if n else 1.0
    margins = [m for v in pairs.values() for _, m in v]
    total = wins + draws + losses
    return {"a": a, "b": b, "games": total, "wins": wins, "draws": draws, "losses": losses,
            "score": round((wins + draws / 2) / total, 3) if total else None, "crowns": [crowns_a, crowns_b],
            "pairs": len(full), "pairs_won": pos, "pairs_lost": neg, "sign_test_p_one_sided": round(sign_p, 4),
            "mean_tower_margin": round(sum(margins) / len(margins), 3) if margins else None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--games", type=int, default=12, help="total games (rounded to a multiple of 2)")
    ap.add_argument("--decks", default="giant-beatdown,hog-2.6-cycle,lavaloon,pekka-bridge-spam,log-bait,golem-beatdown")
    ap.add_argument("--seed0", type=int, default=1, help="first seed (use a fresh range for held-out checks)")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--delay", type=int, default=LIVE_DELAY)
    ap.add_argument("--out", help="directory for games.jsonl and summary.json (resumable)")
    a = ap.parse_args()
    decks = a.decks.split(",")
    jobs = []
    for i in range(a.games // 2):
        deck, seed = decks[i % len(decks)], a.seed0 + i
        jobs += [(a.a, a.b, deck, seed, a.delay), (a.b, a.a, deck, seed, a.delay)]
    games: list[dict] = []
    log = None
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "games.jsonl"
        if path.exists():
            games = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        done = {(g["blue"], g["red"], g["deck"], g["seed"], g["delay"]) for g in games}
        jobs = [j for j in jobs if j not in done]
        log = path.open("a")
    with get_context("spawn").Pool(a.parallel) as pool:
        for r in pool.imap_unordered(play_one, jobs):
            games.append(r)
            if log:
                log.write(json.dumps(r) + "\n")
                log.flush()
            names = [r["blue"], r["red"]]
            who = "draw" if r["winner"] == 2 else names[r["winner"]]
            print(f"{r['deck']:<18} s{r['seed']:<3} {r['blue']} vs {r['red']}: {who}  {r['crowns']}  "
                  f"towers {r['tower_frac']}  think {r['think_ms']} ms  ({r['secs']} s)", flush=True)
    summary = summarize(games, a.a, a.b)
    if a.out:
        (Path(a.out) / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\n{a.a} vs {a.b}: {summary['wins']}W {summary['draws']}D {summary['losses']}L of {summary['games']} "
          f"(score {summary['score']}); crowns {summary['crowns'][0]}-{summary['crowns'][1]}; "
          f"pairs {summary['pairs_won']}-{summary['pairs_lost']} of {summary['pairs']} "
          f"(sign p={summary['sign_test_p_one_sided']}); mean tower margin {summary['mean_tower_margin']:+}")


if __name__ == "__main__":
    main()
