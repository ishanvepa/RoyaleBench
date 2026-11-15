"""The Share Play Hog challenge runs at live speed and stops on the decisive event."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from royalegym.protocol import DeployCommand, DeployStatus
from starlette.testclient import TestClient

from cr_arena import live
from cr_arena.db import DB


def receive(ws, kind):
    for _ in range(5):
        message = ws.receive_json()
        if message["t"] == kind:
            return message
        if message["t"] in ("busy", "error", "invalid"):
            raise AssertionError(message)
    raise AssertionError(f"Did not receive {kind}")


class BenchmarkPlayTests(unittest.TestCase):
    def test_live_reference_stops_when_hog_dies(self):
        cfg = json.loads(live.BENCHMARK_TASK.read_text())
        challenge = live.LiveHogChallenge(cfg)
        self.assertEqual(challenge.game.state.tick, 190)
        self.assertEqual(challenge.game.state.players[0].elixir_milli, 3000)
        self.assertEqual(challenge.game.state.players[0].tower_hp[1], 1)
        self.assertFalse(challenge.hog_seen)
        while challenge.outcome is None:
            tick = challenge.game.state.tick
            commands = []
            if tick - challenge.hog_tick in live.HOG_REFERENCE:
                slot, x, y = live.HOG_REFERENCE[tick - challenge.hog_tick]
                commands = [DeployCommand(live.HUMAN, slot, round(x * challenge.game.sub),
                                          round(y * challenge.game.sub))]
            results = challenge.step(commands)
            self.assertTrue(all(r.status == DeployStatus.OK for r in results))
        self.assertEqual(challenge.outcome, "hog")
        self.assertEqual(challenge.game.state.tick, 359)
        self.assertEqual(challenge.spent, 3)
        self.assertEqual(challenge.damage, 0)
        self.assertTrue(challenge.success)

    def test_live_player_has_a_fixed_three_elixir_allowance(self):
        cfg = json.loads(live.BENCHMARK_TASK.read_text())
        session = live.BenchmarkSession(None, cfg, "player", None)
        try:
            with self.assertRaisesRegex(ValueError, "Only 3 elixir"):
                session.on_message({"t": "play", "slot": 2, "x": 2.5, "y": 12.5})
            session.on_message({"t": "play", "slot": 0, "x": 1.5, "y": 12.5})
            session.on_message({"t": "play", "slot": 1, "x": 3.5, "y": 12.5})
            with self.assertRaisesRegex(ValueError, "Only 3 elixir"):
                session.on_message({"t": "play", "slot": 1, "x": 3.5, "y": 12.5})
        finally:
            session.close()

    def test_websocket_advances_without_input_and_ends_when_tower_falls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(live, "OUT_DIR", root), patch.object(live, "DB", lambda: DB(root / "arena.db")):
                with TestClient(live.create_app(public=True, leaderboard_path=root / "leaderboard.csv")) as client:
                    with client.websocket_connect("/ws") as ws:
                        hello = receive(ws, "hello")
                        self.assertEqual(hello["benchmark"]["budget"], 3)
                        ws.send_json({"t": "start", "mode": "benchmark"})
                        init = receive(ws, "init")
                        self.assertEqual(init["mode"], "benchmark")
                        self.assertEqual(init["delay"], 0)
                        initial = receive(ws, "s")
                        self.assertEqual(initial["k"], 190)
                        self.assertEqual(initial["me"]["e"], 3000)
                        self.assertEqual(initial["benchmark"]["phase"], "incoming")
                        self.assertEqual(initial["benchmark"]["spent"], 0)
                        self.assertFalse(live.ACTIVE.copy().pop().challenge.hog_seen)
                        ticks = [initial["k"]]
                        for _ in range(150):
                            message = ws.receive_json()
                            if message["t"] == "over":
                                result = message
                                break
                            if message["t"] in ("busy", "error", "invalid"):
                                raise AssertionError(message)
                            if message["t"] == "s":
                                ticks.append(message["k"])
                                self.assertLessEqual(message["me"]["e"], 3000)
                        else:
                            self.fail("Live challenge did not finish")
                        self.assertIn(200, ticks)
                        self.assertGreater(ticks[-1], 300)
                        self.assertEqual(result["outcome"], "tower")
                        self.assertFalse(result["success"])
                        self.assertEqual(result["tower_damage"], 1)
                        self.assertEqual(result["spent"], 0)
                        self.assertTrue((root / "replays" / result["saved"]).is_file())
                        self.assertEqual(client.get("/leaderboard").json()["total"], 0)
                    resolution = client.get("/benchmark/resolution")
                    self.assertEqual(resolution.status_code, 200)
                    self.assertIn("IceGolemite at (1.5, 12.5)", resolution.text)
                    self.assertIn("Skeletons at (3.5, 12.5)", resolution.text)
                    self.assertIn("Challenge cleared: Hog defeated", resolution.text)


if __name__ == "__main__":
    unittest.main()
