"""Battle scheduling and launch isolation (no model calls). The web app's battle endpoints are tested in test_api_legacy."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cr_arena.battles import battle_plan, launch_battle

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

    def test_background_launch_snapshots_config_and_targets_the_given_database(self):
        with tempfile.TemporaryDirectory() as directory, patch("cr_arena.battles.subprocess.Popen") as popen:
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


if __name__ == "__main__":
    unittest.main()
