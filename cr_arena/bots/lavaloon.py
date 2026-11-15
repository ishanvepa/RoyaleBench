"""Scripted Lavaloon player: a readable, deck-specific bot to play against and to benchmark against.

Deck: LavaHound, Balloon, MegaMinion, Minions, Tombstone, Arrows, Fireball, Zap.

Game plan, as rules (no search, no learning; only what a player can see on the board):
1. Spells: Zap / Arrows on a swarm, Fireball on a tight group of units.
2. Defend: when enemy units are across the river on our side, answer with Tombstone, then
   Mega Minion, then Minions, in front of the threatened lane (never the Lava Hound or Balloon).
3. Attack: Lava Hound behind the tower of the lane with the weaker enemy princess tower; Balloon
   follows once the hound is moving; Minions / Mega Minion behind it for support.
4. Otherwise wait and bank elixir (and cycle a cheap card if elixir is about to be wasted).

It is stateless (it reads the board each call), so it works the same whether it is asked every
2 s (tournament) or every 0.25 s (live play).
"""

from __future__ import annotations

from royalegym.protocol import EntityKind

from ..player_types import Decision, Player

_UNITS = (EntityKind.TROOP, EntityKind.BUILDING)


class LavaloonBot(Player):
    def __init__(self, name: str = "lavaloon-bot", attack_elixir: float = 7.0, bank_elixir: float = 9.5):
        self.name = name
        self.attack_elixir = attack_elixir  # elixir needed before it starts a push with the hound
        self.bank_elixir = bank_elixir  # cycle a cheap card above this so elixir is not wasted

    def decide(self, game, team, text, moves):
        s = game.state
        me, en = s.players[team], s.players[1 - team]
        elixir = me.elixir_milli / 1000
        units = [e for e in s.entities if e.hp > 0 and e.kind in _UNITS]
        mine = [(game.card_name(e.card_id), *game.own_tiles(team, e.x, e.y)) for e in units if e.team == team]
        foes = [game.own_tiles(team, e.x, e.y) for e in units if e.team != team]
        threats = sorted((ty, tx) for tx, ty in foes if ty < 15.5)  # across the river, on our side

        def mv(card: str, *targets: str):
            for t in targets:
                for m in moves:
                    if m.card == card and m.target == t:
                        return m
            return None

        def near(tx: float, ty: float, r: float) -> int:
            return sum(1 for fx, fy in foes if abs(fx - tx) <= r and abs(fy - ty) <= r)

        # 1. Spells on groups of enemy units.
        for card, radius, need in (("Zap", 2.5, 3), ("Arrows", 3.5, 4), ("Fireball", 2.5, 3)):
            best, best_n = None, 0
            for m in moves:
                if m.card == card and m.target.startswith("on enemy"):
                    n = near(*game.own_tiles(team, m.x, m.y), radius)
                    if n > best_n:
                        best, best_n = m, n
            if best is not None and best_n >= need:
                return Decision(best.index)

        # 2. Defend.
        if threats:
            ty, tx = threats[0]
            lane = game.lane_of(tx)
            front = {"left": "in front of left tower", "right": "in front of right tower"}.get(
                lane, "center (between towers)")
            have_tomb = any(c == "Tombstone" for c, _x, _y in mine)
            defenders = sum(1 for c, _x, y in mine if c in ("Minions", "MegaMinion", "Tombstone") and y < 16)
            if ty < 14 and defenders < 3:
                pick = (None if have_tomb else mv("Tombstone", "center (between towers)", front)) \
                    or mv("MegaMinion", front, "center (between towers)") \
                    or mv("Minions", front, "center (between towers)")
                if pick is not None:
                    return Decision(pick.index)

        # 3. Attack: pick the lane of the weaker enemy princess tower that still stands.
        # The enemy's slot 1 ("its left") stands on OUR right, so slot 1 -> right lane, slot 2 -> left lane.
        alive = [(en.tower_hp[i], "right" if i == 1 else "left") for i in (1, 2) if en.tower_hp[i] > 0]
        lane = min(alive)[1] if alive else "left"
        hound = [(x, y) for c, x, y in mine if c == "LavaHound"]
        balloon = [c for c, _x, _y in mine if c == "Balloon"]
        if hound:
            hx, hy = hound[0]
            push_lane = game.lane_of(hx)
            push_lane = push_lane if push_lane in ("left", "right") else lane
            if not balloon and elixir >= 5:
                where = (f"behind {push_lane} tower",) if hy < 9 else (f"in front of {push_lane} tower",
                                                                       f"{push_lane} bridge")
                m = mv("Balloon", *where)
                if m is not None:
                    return Decision(m.index)
            support = mv("MegaMinion", f"behind {push_lane} tower") or mv("Minions", f"behind {push_lane} tower")
            if support is not None and elixir >= 5 and not threats:
                return Decision(support.index)
        elif elixir >= self.attack_elixir and not (threats and threats[0][0] < 12):
            m = mv("LavaHound", f"behind {lane} tower")
            if m is not None:
                return Decision(m.index)

        # 4. Do not waste elixir at the cap.
        if elixir >= self.bank_elixir and not threats:
            m = mv("MegaMinion", f"behind {lane} tower") or mv("Minions", f"behind {lane} tower")
            if m is not None:
                return Decision(m.index)
        return Decision(0)
