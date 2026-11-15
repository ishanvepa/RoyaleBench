"""The planner bot as a turn-based player (tournament / duel harness).

Unlike the numbered-move players it places cards at exact spots, returning them as ``Decision.move``, and it
reads the true engine state (it knows the opponent's hand and elixir), so it is a reference opponent, not a
fair-information one. Live play builds the planner itself (see bots.live).
"""
from __future__ import annotations

import time

from ..game import Move
from ..player_types import Decision, Player


class PlannerPlayer(Player):
    def __init__(self, name: str = "planner-bot", workers: int = 0, **opts):
        self.name, self.workers, self.opts = name, workers, opts
        self.planner = None

    def start(self, game, team):
        from .planner import Planner

        self.planner = Planner(game.decks, game.seed, team, delay=game.command_delay_ticks,
                               workers=self.workers, **self.opts)

    def decide(self, game, team, text, moves):
        t0 = time.time()
        play, note = self.planner.act(game.engine.save_state())
        lat = time.time() - t0
        if play is None:
            return Decision(0, raw=f"wait. {note}", latency_s=lat)
        _t, slot, x, y = play
        p = game.state.players[team]
        card = game.card_by_id[p.hand[slot]]
        tx, ty = game.own_tiles(team, x, y)
        cost = p.hand_costs[slot] if len(p.hand_costs) == len(p.hand) else card.elixir
        mv = Move(0, slot, card.name, game.kind_of(card), cost, f"({tx:.1f}, {ty:.1f})", game.lane_of(tx), x, y)
        return Decision(0, move=mv, raw=note, latency_s=lat)
