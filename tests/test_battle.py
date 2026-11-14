"""Battle scheduling, launch isolation, and Streamlit interaction checks (no model calls)."""

import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.battle import battle_plan, launch_battle

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "tests/mock_config.toml").read_text()
MODELS = ["mock-llm-a", "mock-llm-b"]


class BattleTests(unittest.TestCase):
    def test_schedule_excludes_other_players_and_swaps_sides(self):
        plan = battle_plan(CONFIG, MODELS, "mirror")
        self.assertEqual(len(plan), 4)
        self.assertEqual({(p["blue"], p["red"]) for p in plan},
                         {(MODELS[0], MODELS[1]), (MODELS[1], MODELS[0])})
        self.assertEqual({p["seed"] for p in plan}, {1, 2})

    def test_rejects_invalid_selection_before_launching(self):
        for names in ([MODELS[0]] * 2, ["unknown", MODELS[1]], ["random-bot", MODELS[1]]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                battle_plan(CONFIG, names, "mirror")
        with self.assertRaises(ValueError):
            battle_plan(CONFIG.replace("seeds = [1, 2]", "seeds = []"), MODELS, "build")

    def test_background_launch_snapshots_config_and_targets_dashboard_database(self):
        with tempfile.TemporaryDirectory() as directory, patch("dashboard.battle.subprocess.Popen") as popen:
            root = Path(directory)
            run = launch_battle(root, CONFIG, MODELS, "build", 2, "test.db")
            command = popen.call_args.args[0]
            self.assertEqual(command[command.index("--players") + 1], ",".join(MODELS))
            self.assertEqual(command[command.index("--db") + 1], "test.db")
            self.assertEqual(command[command.index("--deck-mode") + 1], "build")
            self.assertEqual(Path(command[command.index("--config") + 1]).read_text(), CONFIG)
            self.assertEqual(popen.call_args.kwargs["cwd"], root)
            self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
            self.assertIs(run.process, popen.return_value)
            run.log_path.write_text("runner failed")
            self.assertEqual(run.log_tail(), "runner failed")
            other = launch_battle(root, CONFIG, MODELS, "mirror", 1, "test.db")
            self.assertNotEqual(run.name, other.name)

    def test_dashboard_battle_page_can_launch_without_blocking(self):
        from streamlit.testing.v1 import AppTest
        from cr_arena.db import DB
        from cr_arena.decks import DEFAULT_DECK

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        db = DB(Path(temporary.name) / "arena.db")
        self.addCleanup(db.close)
        db.save_custom_deck("Battle test", DEFAULT_DECK)
        with patch("cr_arena.db.DB", return_value=db):
            directory = temporary.name
            with patch.dict(os.environ, {"DATABASE_URL": "", "CR_ARENA_DB": str(Path(directory) / "arena.db"),
                                         "CR_ARENA_CONFIG": str(ROOT / "tests/mock_config.toml")}):
                app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30)
                app.query_params["page"] = "Battle"
                app.run()
                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.query_params["page"], "Play")
                self.assertEqual([tab.label for tab in app.tabs[:7]],
                                 ["Leaderboard", "Play", "Decks", "Overview", "Job", "Match", "Models"])
                self.assertEqual(len(app.sidebar), 0)
                self.assertEqual(app.radio(key="play_mode").value, "Model vs model")
                self.assertEqual(app.selectbox[0].value, MODELS[0])
                self.assertEqual(app.selectbox[1].value, MODELS[1])
                self.assertIn("4 games", app.info[0].value)
                app.selectbox(key="battle_deck").set_value("Custom: Battle test").run()
                with patch("dashboard.battle.launch_battle") as launch:
                    launch.return_value.process.poll.return_value = None
                    launch.return_value.name = "battle-test"
                    launch.return_value.log_tail.return_value = "Starting"
                    app.button(key="start_battle").click().run()
                    self.assertEqual(list(app.exception), [])
                    launch.assert_called_once()
                    self.assertEqual(tomllib.loads(launch.call_args.args[1])["decks"], {"list": [DEFAULT_DECK]})
                    self.assertTrue(app.button(key="start_battle").disabled)
                    app.radio(key="play_mode").set_value("You vs model").run()
                    self.assertEqual(list(app.exception), [])
                    self.assertEqual(app.selectbox[0].label, "Opponent")
                    self.assertTrue(any(form.label == "Start game" for form in app.button))
                    app.radio(key="play_mode").set_value("Model vs model").run()
                    self.assertEqual(list(app.exception), [])
                    self.assertTrue(app.button(key="start_battle").disabled)
                    launch.assert_called_once()
                    app.button(key="refresh_battle").click().run()
                    launch.assert_called_once()
                    launch.return_value.process.poll.return_value = 1
                    app.button(key="refresh_battle").click().run()
                    self.assertEqual(list(app.exception), [])
                    self.assertTrue(any("exited with code 1" in error.value for error in app.error))


if __name__ == "__main__":
    unittest.main()
