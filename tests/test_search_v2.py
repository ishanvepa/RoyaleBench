"""Real-engine checks for the benchmark search contract (no model calls)."""
import unittest

from royalegym.protocol import DeployCommand, DeployStatus

from cr_arena.decks import DEFAULT_DECK
from cr_arena.game import Game
from cr_arena.players import build_player
from cr_arena.search_v2 import SearchV2


def small_bot(**kwargs):
    return SearchV2(max_candidates=32, shortlist_size=6, screen_horizon_s=1.0,
                    horizon_s=2.25, budget_ticks=4000, max_rollouts=150, **kwargs)


class SearchV2Tests(unittest.TestCase):
    def game(self):
        g = Game(DEFAULT_DECK, DEFAULT_DECK, seed=11, record=False)
        g.engine.step([], 160)
        return g

    def test_private_state_repeatability_and_legal_mapping_both_seats(self):
        g = self.game()
        root = g.engine.save_state()
        for team, continuation in ((0, 'defensive'), (1, 'defensive'), (0, 'legacy'), (1, 'legacy')):
            bot = small_bot(seed=17, continuation_policy=continuation)
            moves = g.legal_moves(team)
            first = bot.decide(g, team, '', moves)
            self.assertIn('search-v2:', first.raw)
            self.assertEqual(first.diagnostics, bot.last_search)
            diagnostic = bot.last_search
            second = bot.decide(g, team, '', moves)
            self.assertEqual(first.index, second.index)
            self.assertEqual(diagnostic['scenarios'], bot.last_search['scenarios'])
            self.assertEqual(diagnostic['candidates'], bot.last_search['candidates'])
            self.assertEqual(g.engine.save_state(), root)
            self.assertLessEqual(diagnostic['simulated_ticks'], bot.budget_ticks)
            self.assertLessEqual(diagnostic['rollouts'], bot.max_rollouts)
            chosen = moves[first.index]
            if chosen.slot >= 0:
                self.assertEqual(g.engine.check_deploy(DeployCommand(team, chosen.slot, chosen.x, chosen.y)),
                                 DeployStatus.OK)
            self.assertTrue(any(c['index'] == 0 and c['samples'] > 0 for c in diagnostic['candidates']))

    def test_horizon_clamped_and_both_sides_redeploy(self):
        g = self.game()
        bot = small_bot()
        bot.start(g, 0)
        calls = []
        original = bot._policy
        def policy(game, team, kind, rng):
            calls.append((game.state.tick, team))
            return original(game, team, kind, rng)
        bot._policy = policy
        _, ticks = bot._rollout(g.engine.save_state(), 0, g.legal_moves(0)[0], 'aggressive', 3, 85)
        self.assertEqual(ticks, 85)
        self.assertEqual(calls, [(160, 1), (200, 0), (200, 1), (240, 0), (240, 1)])

    def test_reservation_survives_low_screen_score(self):
        g = self.game()
        # A real enemy deployment on the far bridge, advanced into our territory.
        enemy_moves = g.legal_moves(1)
        attacker = next(m for m in enemy_moves if m.kind == 'TROOP' and m.target == 'left bridge')
        g.engine.step([DeployCommand(1, attacker.slot, attacker.x, attacker.y)], 100)
        bot = small_bot()
        moves = g.legal_moves(0)
        scores = {m.index: (-1000 if m.target.startswith('in front') else 0) for m in moves}
        reservations = bot._reservations(g, 0, moves, scores)
        self.assertIn('tower-threat', reservations.values())
        bot.decide(g, 0, '', moves)
        for index, reason in bot.last_search['reservations'].items():
            candidate = next(c for c in bot.last_search['candidates'] if c['index'] == index)
            self.assertGreater(candidate['samples'], 0, reason)

    def test_air_defense_prevents_tower_loss_in_engine_trace(self):
        from cr_arena.search_tactics import probe
        report = probe('anti-air')
        self.assertEqual(report['outcomes']['wait']['tower_hp'][0][1], 0)
        self.assertGreater(report['outcomes']['v2']['tower_hp'][0][1], 0)
        self.assertIn('air-response', report['v2_search']['reservations'].values())

    def test_legacy_hog_probe_defends_and_counterattacks(self):
        import tomllib
        from pathlib import Path
        from cr_arena.search_tactics import probe
        config = tomllib.loads((Path(__file__).resolve().parents[1] / 'configs/search_v2_legacy.toml').read_text())
        spec = next(p for p in config['players'] if p['type'] == 'search-v2')
        outcomes = probe('urgent-defense', spec)['outcomes']
        self.assertLessEqual(outcomes['v2']['tower_damage_taken'], outcomes['v1']['tower_damage_taken'])
        self.assertGreaterEqual(outcomes['v2']['tower_damage_dealt'], outcomes['v1']['tower_damage_dealt'])
        self.assertGreater(outcomes['v2']['tower_damage_dealt'], outcomes['wait']['tower_damage_dealt'])

    def test_terminal_rollout_stops_without_work_and_scores_draw(self):
        from royalegym import MatchSetup
        from cr_arena.search_bot import evaluate, WIN
        g = self.game()
        g.engine.reset(11, MatchSetup(decks=g.setup.decks, start_tick=100000))
        g.engine.step([], 1)
        self.assertTrue(g.over)
        bot = small_bot()
        bot.start(g, 0)
        score, ticks = bot._rollout(g.engine.save_state(), 0, g.legal_moves(0)[0], 'patient', 1, 45)
        self.assertEqual(ticks, 0)
        self.assertEqual(score, evaluate(g, 0))
        self.assertEqual(score, 0)
        g.engine.reset(11, MatchSetup(decks=g.setup.decks, start_tick=100000,
                                     tower_hp=[[4824, 1000, 3052], [4824, 3052, 3052]]))
        g.engine.step([], 10000)
        self.assertTrue(g.over)
        self.assertEqual(evaluate(g, g.state.winner), WIN)
        self.assertEqual(evaluate(g, 1 - g.state.winner), -WIN)

    def test_configuration_rejects_partial_minimum_and_live_delay(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            SearchV2(budget_ticks=1).start(self.game(), 0)
        with self.assertRaisesRegex(ValueError, 'workers'):
            SearchV2(workers=2)
        with self.assertRaisesRegex(ValueError, 'zero command delay'):
            small_bot().start(Game(DEFAULT_DECK, DEFAULT_DECK, 0, record=False, command_delay_ticks=21), 0)
        self.assertIsInstance(build_player({'type': 'search-v2', 'name': 'candidate'}), SearchV2)


if __name__ == '__main__':
    unittest.main()
