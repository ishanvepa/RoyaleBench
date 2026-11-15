"""Placement geometry stays aligned with the engine, even before a card is playable."""

import unittest

import msgspec
from royalegym.action import PlacementOracle
from royalegym.protocol import DeployCommand, DeployStatus, EntityKind, ShuffleMode

from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK
from cr_arena.game import Game
from cr_arena.live import Session


def session_for(deck=DEFAULT_DECK, elixir=10000):
    session = Session.__new__(Session)
    session.game = game = Game(deck, deck, seed=2, record=False)
    game.engine.reset(2, msgspec.structs.replace(game.setup, elixir_milli=[elixir, elixir]))
    session.sub = game.sub
    session.placement = PlacementOracle(game.arena, game.engine.rules(), game.cards)
    session.mask_cache = {}
    return session


def troop_slot(session):
    game = session.game
    return next(i for i, cid in enumerate(game.state.players[0].hand)
                if game.kind_of(game.card_by_id[cid]) == 'TROOP')


def allowed(mask, x, y):
    cx, cy = int(x * mask['half']), int(y * mask['half'])
    return mask['m'][cy * mask['width'] + cx] == '1'


class PlacementTests(unittest.TestCase):
    def test_preloads_all_slots_then_reuses_masks_as_time_and_elixir_advance(self):
        session = session_for(elixir=0)
        initial = session.placement_updates(session.game.state)
        self.assertEqual([m['slot'] for m in initial], [0, 1, 2, 3])
        self.assertEqual([m['card'] for m in initial], list(session.game.state.players[0].hand))
        self.assertEqual(session.placement_updates(session.game.state), [])
        session.game.engine.step([], 200)
        self.assertEqual(session.placement_updates(session.game.state), [])

    def test_preloaded_geometry_updates_after_tower_destruction(self):
        session = session_for()
        game = session.game
        slot = troop_slot(session)
        before = {m['slot']: m for m in session.placement_updates(game.state)}
        hp = [list(player.tower_hp) for player in game.state.players]
        hp[0][1] = hp[1][1] = 0
        game.engine.reset(2, msgspec.structs.replace(game.setup, tower_hp=hp))
        updates = {m['slot']: m for m in session.placement_updates(game.state)}
        self.assertFalse(allowed(before[slot], 3.5, 6.5))
        self.assertTrue(allowed(updates[slot], 3.5, 6.5))
        self.assertFalse(allowed(before[slot], 14.25, 20.25))
        self.assertTrue(allowed(updates[slot], 14.25, 20.25))

    def test_preloaded_masks_track_pending_hand_rotation_and_building_geometry(self):
        session = session_for()
        game = session.game
        game.engine.set_command_delay_ticks(21)
        game.engine.reset(2, game.setup)
        game.engine.step([], 200)
        slot = troop_slot(session)
        before = {m['slot']: m for m in session.placement_updates(game.state)}
        command = DeployCommand(0, slot, 6 * game.sub, 10 * game.sub)
        self.assertEqual(game.engine.step([command], 1)[0].status, DeployStatus.OK)
        updates = {m['slot']: m for m in session.placement_updates(game.state)}
        self.assertEqual(updates[slot], session.mask(slot))
        game.engine.step([], 21)
        updates = {m['slot']: m for m in session.placement_updates(game.state)}
        self.assertEqual(updates[slot]['card'], game.state.players[0].hand[slot])
        self.assertNotEqual(updates[slot]['card'], before[slot]['card'])
        for mask in updates.values():
            self.assertEqual(mask, session.mask(mask['slot']))

        # A newly placed building changes spatial blockers without changing the hand.
        cannon = next(c.card_id for c in game.cards if c.name == 'Cannon')
        deck = [cannon] + [cid for cid in game.setup.decks[0] if cid != cannon]
        game.engine.reset(2, msgspec.structs.replace(game.setup, decks=[deck, deck], shuffle=ShuffleMode.NONE))
        game.engine.step([], 200)
        session.placement_updates(game.state)
        self.assertEqual(game.engine.step([DeployCommand(1, 0, 8 * game.sub, 22 * game.sub)], 1)[0].status, DeployStatus.OK)
        game.engine.step([], 21)
        changed = session.placement_updates(game.state)
        self.assertTrue(changed)
        for mask in changed:
            self.assertEqual(mask, session.mask(mask['slot']))

    def test_both_own_princess_footprints_are_blocked_without_expanding_the_edges(self):
        session = session_for()
        mask = session.mask(troop_slot(session))
        for tower in session.game.state.entities:
            if tower.team != 0 or tower.kind != EntityKind.PRINCESS_TOWER:
                continue
            x0, y0, x1, y1 = [v / session.sub for v in tower.footprint]
            for cy in range(int(y0 * 2) - 1, int(y1 * 2) + 1):
                for cx in range(int(x0 * 2) - 1, int(x1 * 2) + 1):
                    x, y = (cx + .5) / 2, (cy + .5) / 2
                    self.assertEqual(allowed(mask, x, y), not (x0 <= x < x1 and y0 <= y < y1),
                                     (tower.uid, x, y))

    def test_destroyed_own_princess_releases_its_footprint(self):
        session = session_for()
        game = session.game
        slot = troop_slot(session)
        self.assertFalse(allowed(session.mask(slot), 3.5, 6.5))
        hp = [list(player.tower_hp) for player in game.state.players]
        hp[0][1] = 0
        game.engine.reset(2, msgspec.structs.replace(game.setup, tower_hp=hp))
        mask = session.mask(slot)
        self.assertTrue(allowed(mask, 3.5, 6.5))
        self.assertFalse(allowed(mask, 14.5, 6.5))

    def test_spells_can_still_target_princess_towers(self):
        session = session_for()
        game = session.game
        slot = next(i for i, cid in enumerate(game.state.players[0].hand)
                    if game.card_by_id[cid].name == 'Fireball')
        mask = session.mask(slot)
        for x, y in [(3.5, 6.5), (14.5, 6.5), (3.5, 25.5), (14.5, 25.5)]:
            self.assertTrue(allowed(mask, x, y))

    def test_buildings_cannot_be_dropped_over_own_princess_towers(self):
        session = session_for()
        game = session.game
        cannon = next(c.card_id for c in game.cards if c.name == 'Cannon')
        deck = [cannon] + [cid for cid in game.setup.decks[0] if cid != cannon]
        game.engine.reset(2, msgspec.structs.replace(game.setup, decks=[deck, deck], shuffle=ShuffleMode.NONE))
        mask = session.mask(0)
        self.assertFalse(allowed(mask, 3.5, 6.5))
        self.assertFalse(allowed(mask, 14.5, 6.5))

    def test_king_exclusion_is_at_exact_half_tile_bounds(self):
        session = session_for()
        mask = session.mask(troop_slot(session))
        self.assertEqual((mask['width'], mask['height'], mask['half']), (36, 64, 2))
        self.assertEqual(len(mask['m']), 36 * 64)
        # Sample every half-cell in and immediately around the engine's king block.
        x0, y0, x1, y1 = [v / session.sub for v in session.game.arena.king_blocks[0]]
        for cy in range(int(y0 * 2) - 1, int(y1 * 2) + 1):
            for cx in range(int(x0 * 2) - 1, int(x1 * 2) + 1):
                x, y = (cx + .5) / 2, (cy + .5) / 2
                blocked = x0 <= x < x1 and y0 <= y < y1
                self.assertEqual(allowed(mask, x, y), not blocked, (x, y))

    def test_mask_is_stable_through_lockout_and_insufficient_elixir(self):
        session = session_for(elixir=0)
        game = session.game
        slot = troop_slot(session)
        original = game.engine.save_state()
        initial = session.mask(slot)
        self.assertEqual(game.engine.save_state(), original, 'mask must not mutate the battle')
        game.engine.step([], game.engine.rules().deploy_lockout_ticks)
        self.assertEqual(game.engine.check_deploy(DeployCommand(0, slot, 6 * game.sub, 10 * game.sub)),
                         DeployStatus.NOT_ENOUGH_ELIXIR)
        self.assertEqual(session.mask(slot)['m'], initial['m'])
        game.engine.step([], 600)
        self.assertEqual(session.mask(slot)['m'], initial['m'])

    def test_every_offered_half_cell_is_accepted_for_classic_deck_hands(self):
        for name, deck in CLASSIC_DECKS.items():
            session = session_for(deck)
            game = session.game
            game.engine.step([], 200)
            for slot in range(4):
                mask = session.mask(slot)
                for index, bit in enumerate(mask['m']):
                    if bit != '1':
                        continue
                    cy, cx = divmod(index, mask['width'])
                    command = DeployCommand(0, slot, int((cx + .5) / 2 * game.sub),
                                            int((cy + .5) / 2 * game.sub))
                    self.assertEqual(game.engine.check_deploy(command), DeployStatus.OK,
                                     (name, slot, cx, cy))

    def test_destroyed_princess_opens_only_its_lane(self):
        session = session_for()
        game = session.game
        slot = troop_slot(session)
        before = session.mask(slot)
        hp = [list(player.tower_hp) for player in game.state.players]
        hp[1][1] = 0  # Red's own-left princess is on Blue's right.
        game.engine.reset(2, msgspec.structs.replace(game.setup, tower_hp=hp))
        after = session.mask(slot)
        self.assertFalse(allowed(before, 14.25, 20.25))
        self.assertTrue(allowed(after, 14.25, 20.25))
        self.assertFalse(allowed(after, 3.75, 20.25))

    def test_invalid_or_empty_slot_has_no_eligible_cells(self):
        session = session_for()
        for slot in [-1, 4, 99]:
            self.assertEqual(set(session.mask(slot)['m']), {'0'})
