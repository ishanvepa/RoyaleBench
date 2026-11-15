"""Planner candidate generation and live start-up."""
import unittest

from royalegym.protocol import DeployCommand, DeployStatus

from cr_arena.bots.planner import Planner
from cr_arena.decks import CLASSIC_DECKS

HOG = CLASSIC_DECKS["hog-2.6-cycle"]


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
