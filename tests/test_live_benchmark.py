"""Share Play uses the published Hog task and exposes its validated resolution."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from cr_arena import live
from cr_arena.db import DB


def receive(ws, kind):
    for _ in range(4):
        message = ws.receive_json()
        if message["t"] == kind:
            return message
        if message["t"] in ("busy", "error", "invalid"):
            raise AssertionError(message)
    raise AssertionError(f"Did not receive {kind}")


class BenchmarkPlayTests(unittest.TestCase):
    def test_reference_and_failure_use_exact_task_without_leaderboard_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(live, "OUT_DIR", root), patch.object(live, "DB", lambda: DB(root / "arena.db")):
                with TestClient(live.create_app(public=True, leaderboard_path=root / "leaderboard.csv")) as client:
                    with client.websocket_connect("/ws") as ws:
                        hello = receive(ws, "hello")
                        self.assertEqual(hello["benchmark"]["budget"], 3)
                        self.assertEqual(hello["benchmark"]["decisions"], 8)
                        for winning in (True, False):
                            ws.send_json({"t": "start", "mode": "benchmark"})
                            init = receive(ws, "init")
                            self.assertEqual(init["mode"], "benchmark")
                            self.assertEqual(init["delay"], 0)
                            initial = receive(ws, "s")
                            self.assertEqual(initial["k"], 200)
                            self.assertEqual(initial["me"]["e"], 3000)
                            self.assertEqual(initial["benchmark"], {"decision": 0, "max_decisions": 8,
                                                                     "spent": 0, "budget": 3})
                            self.assertEqual(next(e[6] for e in initial["en"] if e[1] == 0 and e[10] == 1), 1)
                            self.assertEqual(live.ACTIVE.copy().pop().game.command_delay_ticks, 0)
                            for decision in range(8):
                                action = {"t": "wait"}
                                if winning and decision == 1:
                                    action = {"t": "play", "slot": 0, "x": 1.5, "y": 11.5}
                                if winning and decision == 2:
                                    action = {"t": "play", "slot": 1, "x": 3.5, "y": 13.5}
                                ws.send_json(action)
                                turn = receive(ws, "benchmark_turn")
                                self.assertTrue(turn["accepted"])
                                snap = receive(ws, "s")
                                self.assertEqual(snap["benchmark"]["decision"], decision + 1)
                            result = receive(ws, "over")
                            self.assertEqual(result["success"], winning)
                            self.assertEqual(result["spent"], 3 if winning else 0)
                            self.assertEqual(result["tower_damage"] == 0, winning)
                            self.assertTrue((root / "replays" / result["saved"]).is_file())
                            self.assertEqual(client.get("/leaderboard").json()["total"], 0)
                    resolution = client.get("/benchmark/resolution")
                    self.assertEqual(resolution.status_code, 200)
                    self.assertIn("Decision 2: Play IceGolemite", resolution.text)
                    self.assertIn("IceGolemite at (1.5, 11.5)", resolution.text)
                    self.assertIn("Challenge cleared: zero tower damage", resolution.text)


if __name__ == "__main__":
    unittest.main()
