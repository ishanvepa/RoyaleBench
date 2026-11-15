"""Deck-strength snapshots and ranking, without network or credentials."""

import unittest

from cr_arena.deck_strength import latest, ranking, wilson
from cr_arena.decks import CLASSIC_DECKS


def row(deck, win_rate, battles, captured="2026-01-01"):
    return {"deck": deck, "captured": captured, "win_rate": win_rate, "battles": battles}


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


if __name__ == "__main__":
    unittest.main()
