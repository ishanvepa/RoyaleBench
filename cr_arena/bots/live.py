"""Adapt bot implementations to snapshot requests from a live worker process."""
from ..game import Game
from .registry import build_bot


class LiveBot:
    def __init__(self, spec: dict, decks: list[list[str]], seed: int, team: int, delay: int):
        self.spec, self.team = spec, team
        self.planner = self.sim = self.bot = None
        if spec["type"] == "planner":
            from .planner import Planner

            opts = {k: spec[k] for k in ("horizon_s", "top_k", "margin", "two_ply", "elixir_hp", "prefilter", "three_ply", "answer_k") if k in spec}
            self.planner = Planner(decks, seed, team, delay=delay, workers=spec.get("workers", 0), **opts)
        elif spec["type"] == "search-v2":
            from .live_search_v2 import LiveSearchGame, LiveSearchV2

            self.sim = LiveSearchGame(*decks, seed=seed, record=False, command_delay_ticks=delay)
            self.bot = LiveSearchV2(**{k: v for k, v in spec.items() if k not in ("type", "enabled", "deck")})
            self.bot.start(self.sim, team)
        else:
            self.sim = Game(*decks, seed=seed, record=False, command_delay_ticks=delay)
            self.bot = build_bot(spec)
            self.bot.sim = self.sim  # preserve v1's existing private-worker behavior

    def act(self, root: bytes) -> tuple:
        if self.planner:
            play, raw = self.planner.act(root)
            return (play[1], play[2], play[3], raw) if play else (-1, 0, 0, raw)
        self.sim.engine.load_state(root)
        source = self.sim.state
        moves = self.sim.legal_moves(self.team)
        if len(moves) > 1:
            decision = self.bot.decide(self.sim, self.team, "", moves)
            move, raw = moves[decision.index], decision.raw
        else:
            move, raw = moves[0], ""
        answer = (move.slot, move.x, move.y, raw)
        if self.spec["type"] == "search-v2":
            answer += (source.tick, source.players[self.team].hand[move.slot] if move.slot >= 0 else -1)
        return answer

    def close(self):
        if self.planner:
            self.planner.close()
