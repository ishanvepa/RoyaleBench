"""Custom deck persistence, validation, and dashboard integration without model calls."""

import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from cr_arena.db import DB
from cr_arena.decks import CLASSIC_DECKS, DEFAULT_DECK, deck_options
from cr_arena.game import Game
from dashboard.battle import battle_plan, with_custom_deck

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

    def app(self, body):
        return AppTest.from_string(
            "from cr_arena.db import DB\n"
            f"db = DB({str(self.path)!r})\ntry:\n" + textwrap.indent(body, "    ") +
            "\nfinally:\n    db.close()", default_timeout=30).run()

    def test_builder_create_edit_validation_and_delete(self):
        app = self.app("from dashboard.decks import page_decks\npage_decks(lambda: db)")
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key="save_deck").disabled)
        app.text_input(key="deck_name").set_value("My cycle")
        app.multiselect(key="deck_cards").set_value(DEFAULT_DECK).run()
        app.button(key="save_deck").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.db.custom_decks()[0]["cards"], DEFAULT_DECK)
        self.assertEqual(app.selectbox(key="deck_editor").value, self.db.custom_decks()[0]["id"])
        app.text_input(key="deck_name").set_value("Renamed").run()
        app.button(key="save_deck").click().run()
        self.assertEqual(self.db.custom_decks()[0]["name"], "Renamed")
        app.multiselect(key="deck_cards").set_value(DEFAULT_DECK[:7]).run()
        self.assertTrue(app.button(key="save_deck").disabled)
        app.button(key="delete_deck").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.db.custom_decks(), [])

    def test_custom_deck_is_available_on_both_sides_of_human_game(self):
        self.db.save_custom_deck("Test", DEFAULT_DECK)
        app = self.app(f"from dashboard.play import page_play\nfrom pathlib import Path\npage_play(Path({str(ROOT)!r}), lambda: db)")
        self.assertFalse(app.exception)
        self.assertIn("Custom: Test", app.selectbox[1].options)
        self.assertIn("Custom: Test", app.selectbox[2].options)


if __name__ == "__main__":
    unittest.main()
