"""Simple deterministic-rule and random opponents."""
import random

from ..player_types import Decision, Player

class RandomBot(Player):
    """Uniformly random legal move (including wait). Anchor of the rating scale."""

    def __init__(self, name: str = "random-bot", seed: int = 0):
        self.name = name
        self.rng = random.Random(seed)

    def decide(self, game, team, text, moves):
        return Decision(self.rng.choice(moves).index)


class HeuristicBot(Player):
    """A few readable rules: spell clusters, defend the threatened lane, attack at high elixir."""

    def __init__(self, name: str = "heuristic-bot", attack_elixir: float = 8.0):
        self.name = name
        self.attack_elixir = attack_elixir

    def decide(self, game, team, text, moves):
        s = game.state
        me = s.players[team]
        elixir = me.elixir_milli / 1000
        enemy_units = [e for e in s.entities if e.team != team and e.kind in (0, 1) and e.hp > 0]
        threats = []
        for e in enemy_units:
            tx, ty = game.own_tiles(team, e.x, e.y)
            if ty < 16.5:  # on our side of the river
                threats.append((ty, tx, e))
        threats.sort(key=lambda t: t[0])

        # 1. Spell a group of >= 3 enemy units close together.
        for m in moves:
            if m.kind == "SPELL" and m.target.startswith("on enemy"):
                tx, ty = game.own_tiles(team, m.x, m.y)
                near = sum(1 for e in enemy_units
                           if abs(game.own_tiles(team, e.x, e.y)[0] - tx) <= 2.5
                           and abs(game.own_tiles(team, e.x, e.y)[1] - ty) <= 2.5)
                if near >= 3:
                    return Decision(m.index)

        # 2. Defend: cheapest troop/building in front of the threatened lane's tower.
        if threats:
            lane = game.lane_of(threats[0][1])
            want = {"left": "in front of left tower", "right": "in front of right tower"}.get(lane, "center (between towers)")
            cands = [m for m in moves if m.kind in ("TROOP", "BUILDING") and m.target in (want, "center (between towers)")]
            if cands:
                return Decision(min(cands, key=lambda m: (m.cost, m.target != want)).index)

        # 3. Attack when elixir is high: most expensive troop at the bridge of the weaker enemy lane.
        if elixir >= self.attack_elixir:
            en = s.players[1 - team]
            lane = "left" if en.tower_hp[1] <= en.tower_hp[2] else "right"
            cands = [m for m in moves if m.kind == "TROOP" and m.target in (f"{lane} bridge", f"behind {lane} tower")]
            if cands:
                return Decision(max(cands, key=lambda m: (m.cost, m.target.endswith("tower"))).index)
        return Decision(0)
