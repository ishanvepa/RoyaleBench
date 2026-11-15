"""Deck-strength snapshots, matchups and rankings, without network or credentials."""

import unittest

from cr_arena.deck_strength import latest, load_matchups, ranking, wilson, within_set
from cr_arena.decks import CLASSIC_DECKS


def row(deck, win_rate, battles, captured="2026-01-01"):
    return {"deck": deck, "captured": captured, "win_rate": win_rate, "battles": battles}


def matchup(deck, opponent, win_rate, battles=10_000):
    return {"deck": deck, "opponent": opponent, "captured": "2026-01-01", "win_rate": win_rate, "battles": battles}


class DeckStrengthTests(unittest.TestCase):
    def test_snapshot_covers_every_classic_deck(self):
        self.assertEqual(set(latest()), set(CLASSIC_DECKS))

    def test_wilson_interval(self):
        low, high = wilson(0.5, 100)
        self.assertAlmostEqual(low, 0.4038, places=3)
        self.assertAlmostEqual(high, 0.5962, places=3)

    def test_ranking_uses_newest_snapshot_groups_overlapping_decks_into_tiers_and_puts_empty_decks_last(self):
        ranked = ranking([row("a", 0.55, 10_000), row("b", 0.52, 10_000), row("c", 0.515, 10_000),
                          row("d", 0.40, 10_000), row("e", 0.50, 0), row("d", 0.10, 10_000, "2025-01-01")])
        self.assertEqual([e["deck"] for e in ranked], ["a", "b", "c", "d", "e"])
        self.assertEqual([e["rank"] for e in ranked], [1, 2, 3, 4, None])
        self.assertEqual([e["tier"] for e in ranked], [1, 2, 2, 3, None])  # b and c overlap; d is the newer 0.40 row

    def test_a_small_sample_cannot_outrank_a_large_one_on_luck(self):
        ranked = ranking([row("tiny", 0.60, 20), row("big", 0.50, 100_000)])
        self.assertEqual([e["deck"] for e in ranked], ["big", "tiny"])

    def test_matchups_cover_every_ordered_pair_and_the_two_directions_agree(self):
        rows = load_matchups()
        self.assertEqual({(r["deck"], r["opponent"]) for r in rows},
                         {(a, b) for a in CLASSIC_DECKS for b in CLASSIC_DECKS if a != b})
        rate = {(r["deck"], r["opponent"]): r["win_rate"] for r in rows}
        for (a, b), w in rate.items():  # a pair is the same battles seen from both decks' pages
            self.assertAlmostEqual(w + rate[(b, a)], 1.0, delta=0.005, msg=f"{a} vs {b}")

    def test_within_set_ranks_by_mean_head_to_head_win_rate(self):
        ranked = within_set([matchup("a", "b", .60), matchup("b", "a", .40), matchup("b", "c", .60),
                             matchup("c", "b", .40), matchup("c", "a", .55), matchup("a", "c", .45)])
        self.assertEqual([e["deck"] for e in ranked], ["a", "b", "c"])
        self.assertAlmostEqual(ranked[0]["win_rate"], 0.525)  # a: mean of 0.60 vs b and 0.45 vs c
        self.assertEqual([e["tier"] for e in ranked], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
