"""Planner candidate shortlist and the live duel harness's bookkeeping."""
import unittest

from cr_arena.bots.live import LiveBot
from cr_arena.bots.planner import Planner
from cr_arena.decks import DEFAULT_DECK
from cr_arena.duel import _parse, summarize


class PlannerShortlistTests(unittest.TestCase):
    def setUp(self):
        self.planner = Planner([DEFAULT_DECK, DEFAULT_DECK], 3, 1, delay=21, horizon_s=1, top_k=2, prefilter=False)

    def test_shortlist_keeps_plays_that_do_not_yet_beat_waiting(self):
        # (score, (team, slot, x, y)), best first; every score is far below any waiting margin.
        scored = [(-10.0, (1, 0, 1, 1)), (-11.0, (1, 0, 2, 2)), (-50.0, (1, 1, 3, 3)),
                  (-60.0, (1, 1, 4, 4)), (-70.0, (1, 2, 5, 5))]
        top = self.planner.shortlist(list(scored))
        # top_k by score, then the best spot of each card not already represented
        self.assertEqual([c for _v, c in top], [(1, 0, 1, 1), (1, 0, 2, 2), (1, 1, 3, 3), (1, 2, 5, 5)])

    def test_both_modes_return_a_legal_play_or_wait(self):
        for prefilter in (True, False):
            planner = Planner([DEFAULT_DECK, DEFAULT_DECK], 3, 1, delay=21, horizon_s=1, prefilter=prefilter)
            planner.g.engine.step([], 160)
            root = planner.e.save_state()
            play, _note = planner.act(root)
            if play is not None:
                planner.e.load_state(root)
                self.assertIn(play, planner.candidates(1))

    def test_answering_the_reply_never_scores_below_leaving_it_unanswered(self):
        # Answering includes "do nothing", so the third ply can only raise the worst-reply score.
        two = Planner([DEFAULT_DECK, DEFAULT_DECK], 3, 1, delay=21, horizon_s=4, three_ply=False)
        three = Planner([DEFAULT_DECK, DEFAULT_DECK], 3, 1, delay=21, horizon_s=4, three_ply=True, answer_k=2)
        two.g.engine.step([], 160)
        root = two.e.save_state()
        self.assertGreaterEqual(three.after_reply(root, None), two.after_reply(root, None))

    def test_live_bot_passes_planner_settings(self):
        bot = LiveBot({"type": "planner", "prefilter": False, "top_k": 3}, [DEFAULT_DECK, DEFAULT_DECK], 3, 1, 21)
        self.assertEqual((bot.planner.prefilter, bot.planner.top_k), (False, 3))
        self.assertEqual(bot.planner.args["prefilter"], False)  # worker processes get the same setting


class DuelSummaryTests(unittest.TestCase):
    def test_spec_values(self):
        self.assertEqual(_parse("planner:prefilter=false,top_k=6,margin=40.5"),
                         ("planner", {"prefilter": False, "top_k": 6, "margin": 40.5}))

    def test_pairs_swap_seats_on_the_same_deck_and_seed(self):
        def game(blue, red, deck, seed, winner, frac):
            return {"blue": blue, "red": red, "deck": deck, "seed": seed, "winner": winner,
                    "crowns": [1, 0] if winner == 0 else [0, 1], "tower_frac": frac}
        games = [game("A", "B", "d", 1, 0, [1.0, 0.5]), game("B", "A", "d", 1, 1, [0.6, 1.0]),  # A wins both
                 game("A", "B", "d", 2, 1, [0.5, 0.9]), game("B", "A", "d", 2, 1, [0.8, 0.7]),  # split
                 game("A", "C", "d", 1, 0, [1.0, 0.0])]  # other pairing: ignored
        s = summarize(games, "A", "B")
        self.assertEqual((s["games"], s["wins"], s["losses"], s["pairs"], s["pairs_won"], s["pairs_lost"]),
                         (4, 3, 1, 2, 1, 0))
        self.assertEqual(s["sign_test_p_one_sided"], 0.5)
        self.assertAlmostEqual(s["mean_tower_margin"], (0.5 + 0.4 - 0.4 - 0.1) / 4, places=3)


if __name__ == "__main__":
    unittest.main()
