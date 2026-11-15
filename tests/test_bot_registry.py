"""Shared bot catalog/factory behavior across benchmark and human-play paths."""
import tempfile
import unittest
from pathlib import Path

from cr_arena.bots import build_bot, human_bot_specs
from cr_arena.bots.baselines import HeuristicBot, RandomBot
from cr_arena.bots.live import LiveBot
from cr_arena.bots.planner import Planner, PlannerPlayer
from cr_arena.bots.search import SearchBot
from cr_arena.bots.search_v2 import SearchV2
from cr_arena.decks import DEFAULT_DECK
from cr_arena.game import Game
from cr_arena.players import build_player


class BotRegistryTests(unittest.TestCase):
    def test_factory_keeps_existing_types_and_legacy_imports(self):
        from cr_arena.players import HeuristicBot as OldHeuristic, RandomBot as OldRandom
        from cr_arena.search_bot import SearchBot as OldSearch
        from cr_arena.search_v2 import SearchV2 as OldV2
        from cr_arena.planner_bot import Planner as OldPlanner
        from cr_arena.live_search_v2 import LiveSearchV2 as OldLive
        from cr_arena.bots.live_search_v2 import LiveSearchV2
        self.assertEqual((OldHeuristic, OldRandom, OldSearch, OldV2, OldPlanner, OldLive),
                         (HeuristicBot, RandomBot, SearchBot, SearchV2, Planner, LiveSearchV2))
        for kind, cls in [('random', RandomBot), ('heuristic', HeuristicBot),
                          ('search', SearchBot), ('search-v2', SearchV2)]:
            self.assertIsInstance(build_player({'type': kind, 'name': kind}), cls)
        with self.assertRaisesRegex(ValueError, 'unknown bot type'):
            build_bot({'type': 'typo', 'name': 'bad'})

    def test_catalog_modes_order_and_fresh_presets(self):
        self.assertEqual(list(human_bot_specs('live')), ['planner', 'search', 'search-v2'])
        self.assertEqual(list(human_bot_specs('turn-based')), ['search', 'search-v2'])
        first = human_bot_specs('live')
        first['search-v2']['opponent_mix'].clear()
        self.assertEqual(human_bot_specs('live')['search-v2']['opponent_mix'],
                         ['legacy', 'aggressive', 'patient'])

    def test_new_catalog_entry_needs_no_selector_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bots.toml'
            path.write_text('[bots.practice]\nmodes=["live", "turn-based"]\n'
                            'name="practice-bot"\ntype="heuristic"\nattack_elixir=7.0\n')
            for mode in ('live', 'turn-based'):
                spec = human_bot_specs(mode, path)['practice']
                self.assertNotIn('modes', spec)
                self.assertEqual(build_bot(spec).attack_elixir, 7)

    def test_catalog_rejects_bad_modes_and_missing_or_ambiguous_presets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bots.toml'
            with self.assertRaisesRegex(ValueError, 'unknown human-play mode'):
                human_bot_specs('typo', path)
            path.write_text('[bots.bad]\nmodes=["typo"]\n')
            with self.assertRaisesRegex(ValueError, 'unknown human-play mode'):
                human_bot_specs('live', path)
            path.write_text('[bots.bad]\nmodes=["live"]\npreset="preset.toml"\npreset_player="missing"\n')
            preset = Path(directory) / 'preset.toml'
            preset.write_text('players=[]\n')
            with self.assertRaisesRegex(ValueError, 'exactly one player'):
                human_bot_specs('live', path)
            preset.write_text('[[players]]\nname="missing"\ntype="search"\n'
                              '[[players]]\nname="missing"\ntype="search"\n')
            with self.assertRaisesRegex(ValueError, 'exactly one player'):
                human_bot_specs('live', path)

    def test_v1_live_adapter_still_returns_legal_legacy_answer(self):
        game = Game(DEFAULT_DECK, DEFAULT_DECK, 11, record=False, command_delay_ticks=21)
        game.engine.step([], 160)
        bot = LiveBot({'type': 'search', 'name': 'search-bot', 'rollouts': 1, 'horizon_s': 2},
                      game.decks, game.seed, 1, 21)
        try:
            answer = bot.act(game.engine.save_state())
            self.assertEqual(len(answer), 4)
            self.assertIn(answer[:3], [(m.slot, m.x, m.y) for m in game.legal_moves(1)])
        finally:
            bot.close()

    def test_planner_turn_based_picks_a_numbered_move_deterministically(self):
        self.assertIsInstance(build_player({'type': 'planner', 'name': 'planner-bot', 'workers': 0}), PlannerPlayer)
        choices = []
        for _ in range(2):
            game = Game(DEFAULT_DECK, DEFAULT_DECK, 11, record=False)
            game.engine.step([], 160)
            bot = build_bot({'type': 'planner', 'name': 'planner-bot', 'horizon_s': 4.0})
            bot.start(game, 1)
            moves = game.legal_moves(1)
            self.assertGreater(len(moves), 1)
            root = game.engine.save_state()
            decision = bot.decide(game, 1, '', moves)
            bot.close()
            self.assertEqual(game.engine.save_state(), root, 'the real game must not be stepped')
            self.assertIn(decision.index, range(len(moves)))
            self.assertTrue(decision.raw.startswith('planner:'))
            choices.append((decision.index, decision.raw))
        self.assertEqual(choices[0], choices[1])

    def test_planner_process_pool_still_works_after_module_move(self):
        planner = Planner([DEFAULT_DECK, DEFAULT_DECK], 11, 1, delay=21, horizon_s=1, workers=1)
        workers = []
        try:
            planner.g.engine.step([], 160)
            root = planner.e.save_state()
            scores = planner._map('rollout', root, [None] * 4)
            self.assertEqual(scores, [planner.rollout(root, None, planner.horizon)] * 4)
            workers = list(planner.pool._processes.values())
        finally:
            # Production close is asynchronous; drain the test-owned pool before
            # asserting worker exit so suite scheduling cannot race the assertion.
            planner.pool.shutdown(wait=True, cancel_futures=True)
            planner.close()
            for worker in workers:
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
