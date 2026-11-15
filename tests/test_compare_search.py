import unittest

from cr_arena.compare_search import EngineMeter, summarize
from cr_arena.decks import DEFAULT_DECK
from cr_arena.game import Game


class ComparisonTests(unittest.TestCase):
    def test_meter_counts_simulation_across_restores(self):
        game = Game(DEFAULT_DECK, DEFAULT_DECK, 0, record=False)
        engine = EngineMeter(game.engine)
        root = engine.save_state()
        engine.step([], 40)
        engine.load_state(root)
        engine.step([], 20)
        self.assertEqual(engine.ticks, 60)
        self.assertEqual(engine.loads, 1)
        self.assertEqual(game.state.tick, 20)

    def test_uncertainty_uses_pairs_instead_of_independent_seats(self):
        results = []
        for pair in range(6):
            for seat in (0, 1):
                results.append({'blue': 'v2' if seat == 0 else 'v1', 'red': 'v1' if seat == 0 else 'v2',
                                'winner': seat, 'case': {'pair': str(pair), 'matchup': 'mirror'},
                                'decision_latency_s': {},
                                'stats_blue': {'illegal_or_unparsed': 0},
                                'stats_red': {'illegal_or_unparsed': 0}})
        report = summarize(results, 'v2')
        self.assertEqual(report['wins'], 12)
        self.assertEqual(report['completed_pairs'], 6)
        self.assertEqual(report['paired_sign_test_one_sided_p'], 1 / 64)
        # One pair split between the bots contributes no sign-test evidence.
        results[0]['winner'] = 1
        self.assertEqual(summarize(results[:2], 'v2')['paired_sign_test_one_sided_p'], 1)


if __name__ == '__main__':
    unittest.main()
