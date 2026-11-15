"""Delayed, asynchronous human-play adapter for the frozen numbered search.

The fixed-budget benchmark stays deterministic. Live search adds a soft deadline:
finish screening and one full comparison, then stop at a completed-round boundary.
"""
from dataclasses import replace
import time

from ..game import Game
from .search_v2 import SearchV2


class LiveSearchGame(Game):
    def legal_moves(self, team):
        # A pending card must land before its hand slot can be considered again.
        player = self.state.players[team]
        # Native pending rows are [kind, card ID, x, y, ticks left, cost].
        pending_cards = {p[1] for p in player.pending if p[0] == 0}
        pending_slots = {i for i, card in enumerate(player.hand) if card in pending_cards}
        return [replace(m, index=i) for i, m in enumerate(
            m for m in super().legal_moves(team) if m.slot not in pending_slots)]


class LiveSearchV2(SearchV2):
    def __init__(self, *args, deadline_ms=1200, **kwargs):
        super().__init__(*args, **kwargs)
        if deadline_ms <= 0:
            raise ValueError("deadline_ms must be positive")
        self.deadline_ms = deadline_ms
        self.deadline = 0.0
        self.deadline_reached = False

    def start(self, game, team):
        self._initialize(game, game_class=LiveSearchGame, command_delay_ticks=game.command_delay_ticks)

    def _search_more(self):
        self.deadline_reached = time.perf_counter() >= self.deadline
        return not self.deadline_reached

    def decide(self, game, team, text, moves):
        self.deadline = time.perf_counter() + self.deadline_ms / 1000
        self.deadline_reached = False
        decision = super().decide(game, team, text, moves)
        decision.diagnostics.update(action_mode="numbered-live", deadline_ms=self.deadline_ms,
                                    deadline_reached=self.deadline_reached,
                                    budget_exhausted=not self.deadline_reached,
                                    command_delay_ticks=game.command_delay_ticks)
        return decision
