"""Custom deck persistence, validation, and battle config snapshots without model calls.
The deck endpoints and the web app's deck builder are tested in test_api_legacy and the web app's own tests."""

import tempfile
import tomllib
import unittest
from pathlib import Path

from cr_arena.battles import battle_plan, with_custom_deck
from cr_arena.db import DB
from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK, deck_options
from cr_arena.game import Game

ROOT = Path(__file__).resolve().parents[1]


class CustomDeckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "arena.db"
        self.db = DB(self.path)
        self.addCleanup(self.db.close)

    def test_save_edit_reopen_delete_and_preserve_presets(self):
        deck_id = self.db.save_custom_deck(" My deck ", DEFAULT_DECK)
        other = DB(self.path)
        try:
            self.assertEqual(other.custom_decks()[0]["name"], "My deck")
            self.assertEqual(deck_options(other)["Custom: My deck"], DEFAULT_DECK)
        finally:
            other.close()
        replacement = CLASSIC_DECKS["lavaloon"]
        self.assertEqual(self.db.save_custom_deck("Edited", replacement, deck_id), deck_id)
        self.assertEqual(self.db.custom_decks()[0]["cards"], replacement)
        game = Game(replacement, DEFAULT_DECK, seed=1, record=False)
        self.assertEqual(game.decks[0], replacement)
        self.db.delete_custom_deck(deck_id)
        self.assertEqual(deck_options(self.db), CLASSIC_DECKS)

    def test_invalid_decks_and_duplicate_names_do_not_change_saved_decks(self):
        deck_id = self.db.save_custom_deck("Original", DEFAULT_DECK)
        for cards in (DEFAULT_DECK[:7], DEFAULT_DECK + ["Tesla"], ["Knight"] * 8,
                      DEFAULT_DECK[:7] + ["MissingCard"]):
            with self.subTest(cards=cards), self.assertRaises(ValueError):
                self.db.save_custom_deck("Invalid", cards)
        for name in ("", "   ", "x" * 81, "Original"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.db.save_custom_deck(name, DEFAULT_DECK)
        with self.assertRaises(ValueError):
            self.db.save_custom_deck("Missing", DEFAULT_DECK, "missing")
        self.assertEqual(len(self.db.custom_decks()), 1)
        self.assertEqual(self.db.custom_decks()[0]["id"], deck_id)

    def test_battle_snapshot_uses_custom_cards_with_original_seeds(self):
        config = (ROOT / "tests/mock_config.toml").read_text()
        updated = with_custom_deck(config, DEFAULT_DECK)
        self.assertEqual(tomllib.loads(updated)["decks"], {"list": [DEFAULT_DECK]})
        plan = battle_plan(updated, ["mock-llm-a", "mock-llm-b"], "mirror")
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(match["deck"] == DEFAULT_DECK for match in plan))
        preset_config = (ROOT / "config.toml").read_text()
        replaced = tomllib.loads(with_custom_deck(preset_config, DEFAULT_DECK))
        self.assertEqual(replaced["decks"], {"list": [DEFAULT_DECK]})
        self.assertEqual(replaced["players"], tomllib.loads(preset_config)["players"])


if __name__ == "__main__":
    unittest.main()
