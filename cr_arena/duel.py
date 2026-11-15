"""Bot against bot under live-play conditions (free placement, command delay, a decision every fraction
of a second), to measure a bot before a human has to.

    uv run python -m cr_arena.duel --a planner --b search --games 12
    uv run python -m cr_arena.duel --a planner --b planner:two_ply=0 --games 12

A spec is a kind (planner, search, heuristic, random) plus optional settings, e.g. planner:horizon_s=8,top_k=6.
Each pairing is played from both sides on every deck, so seat and deck luck cancel out.
"""

from __future__ import annotations

import argparse
import time
from multiprocessing import get_context

from royalegym.protocol import DeployCommand

from .decks import CLASSIC_DECKS
from .game import Game

LIVE_DELAY = 21


def _parse(spec: str) -> tuple[str, dict]:
    kind, _, rest = spec.partition(":")
    opts = {}
    for kv in filter(None, rest.split(",")):
        k, _, v = kv.partition("=")
        opts[k] = float(v) if "." in v else int(v)
    return kind, opts


class _Agent:
    """Wraps either bot family behind one call: act(game) -> DeployCommand | None."""

    def __init__(self, spec: str, decks, seed: int, team: int, delay: int):
        self.kind, opts = _parse(spec)
        self.team = team
        if self.kind == "planner":
            from .bots.planner import Planner

            opts = {k: (bool(v) if k == "two_ply" else v) for k, v in opts.items()}
            self.bot = Planner(decks, seed, team, delay=delay, **opts)
            self.every = 8
        else:
            from .players import build_player

            self.bot = build_player({"name": spec, "type": self.kind, **opts})
            self.bot.sim = Game(decks[0], decks[1], seed=seed, record=False, command_delay_ticks=delay)
            self.every = 20

    def act(self, game: Game) -> DeployCommand | None:
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
    t0 = time.time()
    while not game.over:
        tick = game.state.tick
        cmds = []
        for a in agents:
            if tick % a.every == (0 if a.team == 0 else a.every // 2):  # the two seats decide on different ticks
                c = a.act(game)
                if c:
                    cmds.append(c)
        game.engine.step(cmds, 1)
    s = game.state
    return {"blue": spec_blue, "red": spec_red, "deck": deck, "seed": seed, "winner": int(s.winner),
            "crowns": [p.crowns for p in s.players], "towers": [sum(p.tower_hp) for p in s.players],
            "secs": round(time.time() - t0)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--games", type=int, default=12, help="total games (rounded to a multiple of 2)")
    ap.add_argument("--decks", default="giant-beatdown,hog-2.6-cycle,lavaloon,pekka-bridge-spam,log-bait,golem-beatdown")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--delay", type=int, default=LIVE_DELAY)
    a = ap.parse_args()
    decks = a.decks.split(",")
    jobs = []
    for i in range(a.games // 2):
        deck, seed = decks[i % len(decks)], 1 + i
        jobs += [(a.a, a.b, deck, seed, a.delay), (a.b, a.a, deck, seed, a.delay)]
    score = {a.a: 0.0, a.b: 0.0}
    wins = {a.a: 0, a.b: 0, "draw": 0}
    crowns = {a.a: 0, a.b: 0}
    with get_context("spawn").Pool(a.parallel) as pool:
        for r in pool.imap_unordered(play_one, jobs):
            names = [r["blue"], r["red"]]
            who = "draw" if r["winner"] == 2 else names[r["winner"]]
            wins[who] += 1
            for i, n in enumerate(names):
                crowns[n] += r["crowns"][i]
                score[n] += 0.5 if r["winner"] == 2 else float(r["winner"] == i)
            print(f"{r['deck']:<18} s{r['seed']:<3} {r['blue']} vs {r['red']}: {who}  {r['crowns']}  ({r['secs']} s)", flush=True)
    n = len(jobs)
    print(f"\n{a.a}: {wins[a.a]} wins, {wins['draw']} draws, {wins[a.b]} losses out of {n} "
          f"(score {score[a.a]:.1f}/{n}); crowns {crowns[a.a]}-{crowns[a.b]}")


if __name__ == "__main__":
    main()
