"""What each player is shown and offered matches what the engine does (review findings 3-8)."""

import unittest

import msgspec
from royalegym.protocol import DeployCommand, EntityKind, SpawnSpec

from cr_arena.game import Game, Move
from cr_arena.live import Session
from cr_arena.players import SYSTEM_PROMPT

FILLER = ["Knight", "Archer", "Musketeer", "Giant", "Cannon", "Minions"]


def game_with(blue_extra, red_extra, spawns=(), start_tick=0, tower_hp=None, delay=0, need=None):
    """A game set up as asked; with ``need=(team, card)``, the first seed dealing that card."""
    for seed in range(1, 60):
        game = _game_with(blue_extra, red_extra, spawns, start_tick, tower_hp, delay, seed)
        if need is None or slot_of(game, *need) is not None:
            return game
    raise AssertionError(f"no seed deals {need}")


def _game_with(blue_extra, red_extra, spawns, start_tick, tower_hp, delay, seed):
    blue = (list(blue_extra) + [c for c in FILLER if c not in blue_extra])[:8]
    red = (list(red_extra) + [c for c in FILLER if c not in red_extra])[:8]
    blue += [c for c in ("Fireball", "Zap", "Log") if c not in blue][: 8 - len(blue)]
    red += [c for c in ("Fireball", "Zap", "Log") if c not in red][: 8 - len(red)]
    game = Game(blue, red, seed=seed, record=False, command_delay_ticks=delay)
    ids = {c.name: c.card_id for c in game.cards}
    setup = msgspec.structs.replace(
        game.setup, elixir_milli=[10000, 10000], start_tick=start_tick, tower_hp=tower_hp,
        spawns=[SpawnSpec(team, ids[name], *game.engine_point(team, x, y)) for team, name, x, y in spawns])
    game.setup = setup
    game.engine.reset(seed, setup)
    lockout = game.engine.rules().deploy_lockout_ticks
    if lockout and not start_tick:
        game.engine.step([], lockout)  # no play is accepted before this
    game.mem = [type(m)() for m in game.mem]
    game._update_memory()
    for m in game.mem:
        m.events.clear()
    return game


def slot_of(game, team, name):
    hand = game.state.players[team].hand
    for slot, cid in enumerate(hand):
        if game.card_name(cid) == name:
            return slot
    return None


class SpellTargets(unittest.TestCase):
    def test_rage_can_be_cast_on_an_own_unit_and_at_fixed_zones(self):
        game = game_with(["Rage"], [], spawns=[(0, "Knight", 9.0, 12.0)], need=(0, "Rage"))
        slot = slot_of(game, 0, "Rage")
        targets = [m.target for m in game.legal_moves(0) if m.slot == slot]
        self.assertTrue(any(t.startswith("on your Knight") for t in targets), targets)
        self.assertIn("left bridge", targets)
        self.assertIn("enemy side, left lane", targets)


class EnemyPlaysAreSeen(unittest.TestCase):
    def test_an_instant_enemy_zap_is_reported_to_the_other_player(self):
        game = game_with([], ["Zap"], need=(1, "Zap"))
        slot = slot_of(game, 1, "Zap")
        zap = next(m for m in game.legal_moves(1) if m.slot == slot and m.target.startswith("enemy king"))
        wait = Move(0, -1, "wait", "WAIT", 0, "-", "-")
        game.step([wait, zap])
        self.assertIn("Zap", game.mem[0].enemy_cards_seen)
        self.assertTrue(any(ev.startswith("enemy cast Zap") for ev in game.mem[0].events), game.mem[0].events)
        self.assertIn("enemy cast Zap", game.describe(0, game.legal_moves(0)))


class TowerNames(unittest.TestCase):
    def test_enemy_towers_are_named_from_the_observers_side(self):
        for team in (0, 1):
            game = game_with([], [])
            for e in game.state.entities:
                if e.team == team or e.kind != EntityKind.PRINCESS_TOWER:
                    continue
                tx, _ = game.own_tiles(team, e.x, e.y)
                name = game.tower_name(team, e)
                self.assertEqual(name, "left princess tower" if tx < 9 else "right princess tower")
            # the hp listed as the enemy's LEFT tower is the one on the observer's left
            hp = [[3000, 1000, 2000], [3000, 1000, 2000]]
            game = game_with([], [], tower_hp=hp)
            text = game.describe(team, game.legal_moves(team))
            enemy_line = next(line for line in text.splitlines() if line.startswith("ENEMY TOWERS"))
            left = next(e for e in game.state.entities if e.team != team and e.kind == EntityKind.PRINCESS_TOWER
                        and game.own_tiles(team, e.x, e.y)[0] < 9)
            self.assertIn(f"left princess tower {left.hp}/", enemy_line)


class Tiebreak(unittest.TestCase):
    def test_prompt_states_the_tower_hp_tiebreak(self):
        self.assertNotIn("still tied after overtime = draw", SYSTEM_PROMPT)
        self.assertIn("weakest standing tower", SYSTEM_PROMPT)

    def test_clock_never_goes_negative_and_no_play_is_offered_in_the_drain(self):
        probe = game_with([], [])
        s = probe.state
        end = s.regular_ticks + s.overtime_ticks
        game = game_with([], [], start_tick=end + 20, tower_hp=[[3000, 2000, 2000], [3000, 2100, 2100]])
        if game.over:
            self.skipTest("engine ended the match at once")
        left, _ = game.time_left_s()
        self.assertEqual(left, 0)
        self.assertEqual([m.slot for m in game.legal_moves(0)], [-1])
        self.assertIn("TIME LEFT: 0:00 (TIEBREAK", game.describe(0, game.legal_moves(0)))


class ShieldsAndStatus(unittest.TestCase):
    def test_dark_prince_shield_is_described_and_sent_to_the_page(self):
        game = game_with([], [], spawns=[(0, "DarkPrince", 9.0, 10.0)])
        prince = next(e for e in game.state.entities if game.card_name(e.card_id) == "DarkPrince")
        if prince.shield <= 0:
            self.skipTest("engine reports no shield")
        self.assertIn(f"+ shield {prince.shield}", game.describe(0, game.legal_moves(0)))
        session = Session.__new__(Session)
        session.game, session.sub, session.paused = game, game.sub, False
        row = next(r for r in session.snapshot()["en"] if r[0] == prince.uid)
        self.assertEqual(row[15], prince.shield)


class LivePending(unittest.TestCase):
    def test_pending_play_marks_the_slot_that_was_played(self):
        game = game_with([], [], delay=21)
        session = Session.__new__(Session)
        session.game, session.sub, session.paused = game, game.sub, False
        hand = game.state.players[0].hand
        slot = next(i for i in (3, 2, 1) if game.kind_of(game.card_by_id[hand[i]]) != "SPELL")
        mv = next(m for m in game.legal_moves(0) if m.slot == slot)
        game.engine.step([DeployCommand(0, slot, mv.x, mv.y)], 1)
        pend = session.snapshot()["me"]["pend"]
        self.assertEqual([p[0] for p in pend], [slot])
        self.assertEqual(pend[0][1], hand[slot])


if __name__ == "__main__":
    unittest.main()
