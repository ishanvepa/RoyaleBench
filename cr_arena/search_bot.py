"""Search bot: the reference ("Stockfish") player.

It uses the SAME numbered move list the language models get. At each decision it tries every
legal move on a copy of the game: save the engine state, play the move together with a sampled
opponent reply, simulate the next few seconds with a fast playout policy for both sides, score
the position, restore. The move with the best average score is played.

Strength knobs (like Stockfish levels): rollouts per move and look-ahead horizon.

Information: v1 searches the true engine state, so its simulations know the opponent's hand,
elixir and card cycle (an omniscient reference). See `docs` in the README for the plan to
determinize this (sample the hidden hand from unseen cards).
"""

from __future__ import annotations

import random

from royalegym.protocol import DeployCommand, EntityKind

from .game import Game, Move
from .players import Decision, HeuristicBot, Player

WIN = 100_000.0


def evaluate(game: Game, team: int) -> float:
    """Position score from `team`'s point of view (higher is better)."""
    s = game.state
    if s.game_over:
        return 0.0 if s.winner == 2 else (WIN if s.winner == team else -WIN)
    me, en = s.players[team], s.players[1 - team]
    v = 2000.0 * (me.crowns - en.crowns)
    # tower damage: princess towers (a crown each) and the king tower (3 crowns)
    for side, sign in ((en, 1.0), (me, -1.0)):
        for i in range(3):
            lost = 1.0 - side.tower_hp[i] / side.tower_max_hp[i] if side.tower_max_hp[i] else 0.0
            v += sign * (1500.0 if i == 0 else 900.0) * lost
    v += 25.0 * (me.elixir_milli - en.elixir_milli) / 1000.0
    # units on the board, worth their elixir share x remaining hp; attackers count more the deeper they are
    for e in s.entities:
        if e.hp <= 0 or e.kind not in (EntityKind.TROOP, EntityKind.BUILDING):
            continue
        card = game.card_by_id.get(e.card_id)
        cost = (card.elixir / max(1, card.count)) if card else 1.0
        val = 45.0 * cost * (e.hp / e.max_hp if e.max_hp else 0.0)
        _, ty = game.own_tiles(team, e.x, e.y)  # 0 = my back edge, 32 = enemy back edge
        if e.team == team:
            v += val * (1.0 + 0.6 * max(0.0, ty - 16.0) / 16.0)
        else:
            v -= val * (1.0 + 0.6 * max(0.0, 16.0 - ty) / 16.0)
    return v


class SearchBot(Player):
    def __init__(self, name: str = "search-bot", rollouts: int = 4, horizon_s: float = 12.0, seed: int = 0,
                 p_heuristic: float = 0.6, p_wait: float = 0.25):
        self.name = name
        self.rollouts = rollouts
        self.horizon_s = horizon_s
        self.rng = random.Random(seed)
        self.p_heuristic = p_heuristic
        self.p_wait = p_wait
        self.policy_bot = HeuristicBot("playout")
        self.sim: Game | None = None

    def start(self, game, team):
        # A private engine to search on: the real game is shared with the opponent's thread, so it is
        # only ever read (save_state), never stepped, by the search.
        self.sim = Game(game.decks[0], game.decks[1], seed=game.seed, decision_ticks=game.decision_ticks, record=False)

    # fast playout policy: mostly the heuristic, sometimes wait, sometimes a random legal move
    def _policy(self, game: Game, team: int, rng: random.Random) -> Move:
        moves = game.legal_moves(team)
        if len(moves) == 1:
            return moves[0]
        r = rng.random()
        if r < self.p_heuristic:
            return moves[self.policy_bot.decide(game, team, "", moves).index]
        if r < self.p_heuristic + self.p_wait:
            return moves[0]
        return rng.choice(moves[1:])

    @staticmethod
    def _cmds(*pairs: tuple[int, Move]) -> list:
        return [DeployCommand(t, m.slot, m.x, m.y) for t, m in pairs if m.slot >= 0]

    def decide(self, game, team, text, moves):
        if len(moves) == 1:
            return Decision(0)
        if self.sim is None:
            self.start(game, team)
        root = game.engine.save_state()
        h0 = game.engine.state_hash()
        game = self.sim  # everything below runs on the private copy
        e = game.engine
        e.load_state(root)
        assert e.state_hash() == h0, "private copy must match the real game"
        dt = game.decision_ticks
        horizon = int(self.horizon_s * 1000 / game.state.tick_ms)
        seeds = [self.rng.randrange(1 << 30) for _ in range(self.rollouts)]  # common random numbers across moves
        scores = []
        for mv in moves:
            total = 0.0
            for sd in seeds:
                rng = random.Random(sd)
                e.load_state(root)
                opp = self._policy(game, 1 - team, rng)
                e.step(self._cmds((team, mv), (1 - team, opp)), dt)
                t = dt
                while t < horizon and not game.state.game_over:
                    a, b = self._policy(game, team, rng), self._policy(game, 1 - team, rng)
                    e.step(self._cmds((team, a), (1 - team, b)), dt)
                    t += dt
                total += evaluate(game, team)
            scores.append(total / len(seeds))
        best = max(range(len(moves)), key=lambda i: scores[i])
        top = sorted(range(len(moves)), key=lambda i: -scores[i])[:3]
        raw = "search: " + "; ".join(f"{moves[i].label()} = {scores[i]:.0f}" for i in top)
        return Decision(best, raw=raw)
