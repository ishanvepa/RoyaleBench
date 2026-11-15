"""Planner candidates, shortlist and live start-up, and the live duel harness's bookkeeping."""
import unittest

from royalegym.protocol import DeployCommand, DeployStatus

from cr_arena.bots.live import LiveBot
from cr_arena.bots.planner import Planner
from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK
from cr_arena.duel import _parse, summarize

HOG = CLASSIC_DECKS["hog-2.6-cycle"]


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


class PlannerCandidateTests(unittest.TestCase):
    def test_pending_card_excludes_its_own_slot_not_slot_zero(self):
        planner = Planner([HOG, HOG], 1, 1, delay=21, workers=0)
        g, e = planner.g, planner.e
        e.step([], 200)  # past the opening lockout, with elixir to spare
        player = g.state.players[1]
        # Put the cheapest card that is not in slot 0 on its way (it lands 21 ticks later).
        slot = min(range(1, 4), key=lambda i: player.hand_costs[i])
        x, y = g.engine_point(1, 8.5, 9.5)
        result = e.step([DeployCommand(1, slot, x, y)], 1)
        self.assertEqual(result[0].status, DeployStatus.OK)
        self.assertTrue(g.state.players[1].pending)
        slots = {c[1] for c in planner.candidates(1)}
        self.assertNotIn(slot, slots, "a card on its way cannot be played again")
        self.assertIn(0, slots, "slot 0 is still playable while another card is pending")


class PlannerWarmTests(unittest.TestCase):
    def test_warm_starts_every_worker_and_first_decision_is_not_a_cold_start(self):
        planner = Planner([HOG, HOG], 1, 1, delay=21, workers=2)
        try:
            planner.warm()
            pids = set(planner.pool._processes)
            self.assertEqual(len(pids), 2)
            planner.e.step([], 200)
            planner.act(planner.e.save_state())
            self.assertEqual(set(planner.pool._processes), pids, "no new workers were spawned for the decision")
        finally:
            planner.pool.shutdown(wait=True, cancel_futures=True)

    def test_warm_without_a_pool_does_nothing(self):
        Planner([HOG, HOG], 1, 1, workers=0).warm()


if __name__ == "__main__":
    unittest.main()
