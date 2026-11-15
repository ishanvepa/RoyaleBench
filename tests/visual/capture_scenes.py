"""Record real classic-deck battle frames for indicator screenshots.

Each of the seven classic decks plays one game against the next deck with a live-style
command delay, so plays wait on the board before landing. From each game we keep the
most crowded frame, preferring frames that show stuns and pending plays. The output feeds
tests/visual/scenes.html; it is a visual check aid, not used by the benchmark.

Run with: uv run python -m tests.visual.capture_scenes [out.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from royalegym.action import PlacementOracle

from cr_arena.bots.baselines import HeuristicBot
from cr_arena.decks import CLASSIC_DECKS
from cr_arena.live import Session

DELAY = 21  # the live client's command delay, in ticks


def snapshot_session(game) -> Session:
    s = Session.__new__(Session)
    s.game, s.sub, s.delay, s.seed, s.paused = game, game.sub, DELAY, game.seed, False
    s.bot_spec, s.deck_names = {"name": "heuristic"}, ("", "")
    s.player_name = 'Test player'
    s.placement = PlacementOracle(game.arena, game.engine.rules(), game.cards)
    s.mask_cache = {}
    return s


def score(snap: dict) -> float:
    units = [e for e in snap["en"] if e[2] in (0, 1)]
    stunned = sum(1 for e in snap["en"] if e[13] > 0)
    damaged = sum(1 for e in units if e[6] < e[7])
    return len(units) + 6 * min(stunned, 3) + 4 * min(len(snap["me"]["pend"]), 1) + 0.5 * damaged


def record(blue: str, red: str, seed: int) -> dict:
    from cr_arena.game import Game

    game = Game(CLASSIC_DECKS[blue], CLASSIC_DECKS[red], seed=seed, record=False,
                decision_ticks=8, command_delay_ticks=DELAY)
    sess, bots = snapshot_session(game), [HeuristicBot(attack_elixir=6.5), HeuristicBot(attack_elixir=6.5)]
    best, prev = None, None
    while not game.over and game.state.tick < 3600:
        moves = [game.legal_moves(t) for t in (0, 1)]
        game.step([m[bots[t].decide(game, t, "", m).index] for t, m in enumerate(moves)])
        snap = sess.snapshot()
        if prev is not None and (best is None or score(snap) > best[0]):
            best = (score(snap), prev, snap)
        prev = snap
    init = sess.init_msg()
    return {"decks": [blue, red], "seed": seed, "cards": init["cards"], "arena": init["arena"],
            "delay": DELAY, "a": best[1], "b": best[2]}


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/indicator_scenes.json")
    names = list(CLASSIC_DECKS)
    scenes = [record(n, names[(i + 1) % len(names)], seed=11 + i) for i, n in enumerate(names)]
    out.write_text(json.dumps(scenes))
    for sc in scenes:
        b = sc["b"]
        print(sc["decks"], "tick", b["k"], "entities", len(b["en"]),
              "stunned", sum(e[13] > 0 for e in b["en"]), "pending", len(b["me"]["pend"]))


if __name__ == "__main__":
    main()
