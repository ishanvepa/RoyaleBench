"""CSV persistence, ordering, browser identity, and leaderboard API behavior."""

import csv
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from cr_arena import live
from cr_arena.db import DB
from cr_arena.leaderboard import Leaderboard


class LeaderboardTests(unittest.TestCase):
    def test_persistence_names_ranking_ties_and_ignored_draws(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leaderboard.csv"
            board = Leaderboard(path)
            self.assertEqual(board.standings("a")["entries"], [])
            results = [("a", "Old name", 0), ("a", "Alice, the Great", 0), ("a", "Alice, the Great", 1),
                       ("b", "Bob", 0), ("b", "Bob", 0), ("c", "Charlie", 1),
                       ("d", "Dara", 0), ("d", "Dara", 0), ("e", "Eve", -1)]
            for index, (player, name, winner) in enumerate(results):
                board.record(str(index), player, name, winner)
            board = Leaderboard(path)  # A fresh server reads the same file.
            result = board.standings("a")
            self.assertEqual([p["name"] for p in result["entries"]], ["Bob", "Dara", "Alice, the Great", "Charlie"])
            self.assertEqual([p["rank"] for p in result["entries"]], [1, 1, 3, 4])
            self.assertEqual((result["you"]["wins"], result["you"]["losses"]), (2, 1))
            self.assertTrue(result["you"]["is_you"])
            self.assertNotIn("player_id", result["you"])
            limited = board.standings("a", limit=1)
            self.assertEqual(len(limited["entries"]), 1)
            self.assertEqual(limited["total"], 4)
            self.assertEqual(limited["you"]["rank"], 3)

    def test_simultaneous_completions_and_retries_are_not_lost_or_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Leaderboard(Path(tmp) / "leaderboard.csv")
            with ThreadPoolExecutor(max_workers=5) as workers:
                list(workers.map(lambda i: board.record(str(i % 20), "a", "Alice", i % 2), range(100)))
            you = board.standings("a")["you"]
            self.assertEqual((you["wins"], you["losses"]), (10, 10))
            with board.path.open(newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file))), 20)

    def test_cookie_identity_survives_refresh_and_server_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leaderboard.csv"
            with patch.object(live, "DB", lambda: DB(Path(tmp) / "arena.db")):
                with TestClient(live.create_app(public=True, leaderboard_path=path)) as client:
                    client.get("/")
                    player_id = client.cookies[live.PLAYER_COOKIE]
                    board = client.app.state.leaderboard
                    board.record("game-1", player_id, "Future player name", 0)
                    board.record("game-2", "another-player", "Rival", 1)
                    response = client.get("/leaderboard")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(response.json()["you"]["name"], "Future player name")
                    self.assertEqual(response.json()["you"]["wins"], 1)
                    self.assertEqual(client.cookies[live.PLAYER_COOKIE], player_id)
                    self.assertIn("HttpOnly", response.headers["set-cookie"])
                with TestClient(live.create_app(public=True, leaderboard_path=path)) as restarted:
                    restarted.cookies.set(live.PLAYER_COOKIE, player_id)
                    self.assertEqual(restarted.get("/leaderboard").json()["you"]["wins"], 1)

    def test_unavailable_csv_returns_retryable_error_and_cannot_accept_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(live, "DB", lambda: DB(Path(tmp) / "arena.db")):
                with TestClient(live.create_app(leaderboard_path=Path(tmp))) as client:
                    with self.assertLogs(live.log, level="ERROR"):
                        self.assertEqual(client.get("/leaderboard").status_code, 503)
                    self.assertEqual(client.post("/leaderboard", json={"wins": 999}).status_code, 405)


if __name__ == "__main__":
    unittest.main()
