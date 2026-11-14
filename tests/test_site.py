"""Keep competition formats and recorded deck rules separate in results."""

import json
import tempfile
import unittest
from pathlib import Path

from cr_arena.db import DB
from cr_arena.site import build, result_runs
from dashboard.leaderboard import run_label


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = DB(Path(self.directory.name) / "arena.db")
        self.addCleanup(self.db.close)

    def run_with_game(self, name, players, deck):
        job = self.db.get_or_create_job(name, "", players, [1], 40, 1)
        self.db.execute("""INSERT INTO matches
            (job_id,match_id,blue,red,deck,status,winner,crowns,ticks,finished_at)
            VALUES (?, 'game', ?, ?, ?, 'done', 0, '[3,0]', 100, 1)""",
                        (job, players[0], players[1], json.dumps(deck)))
        return job

    def data(self, **kwargs):
        html = build(self.db, out=Path(self.directory.name) / "index.html", **kwargs).read_text(encoding="utf-8")
        return json.loads(html.split("const DATA = ", 1)[1].split(";\nconst LOGOS", 1)[0])

    def test_format_and_deck_rules_come_from_participants_and_games(self):
        self.run_with_game("not-a-classic-name", ["a", "b", "c"], [1, 2])
        self.run_with_game("classic-v2", ["x", "y"], {"blue": [1], "red": [2]})
        self.run_with_game("human-play", ["human", "bot"], [1, 2])
        runs = {r["name"]: r for r in result_runs(self.db)}
        self.assertNotIn("human-play", runs)
        self.assertEqual((runs["not-a-classic-name"]["format"], runs["not-a-classic-name"]["deck_rules"]),
                         ("round_robin", "Preset decks"))
        self.assertEqual((runs["classic-v2"]["format"], runs["classic-v2"]["deck_rules"]),
                         ("duel", "Model-built decks"))

    def test_selected_battle_excludes_other_runs(self):
        self.run_with_game("tournament", ["a", "b", "c"], [1, 2])
        self.run_with_game("battle", ["x", "y"], {"blue": [1], "red": [2]})
        tracks = self.data(job_name="battle")["tracks"]
        self.assertEqual(len(tracks), 1)
        track = next(iter(tracks.values()))
        self.assertEqual(track["format"], "duel")
        self.assertEqual({p["name"] for p in track["players"]}, {"x", "y"})
        self.assertEqual(len(track["games"]), 1)

    def test_same_run_cannot_be_counted_twice(self):
        self.run_with_game("single", ["a", "b", "c"], [1, 2])
        tracks = self.data(classic="single", build_job="single")["tracks"]
        self.assertEqual(len(tracks), 1)
        self.assertEqual(len(next(iter(tracks.values()))["games"]), 1)

    def test_empty_battle_label_does_not_claim_results_or_failure(self):
        run = {"name": "battle-empty", "scored_games": 0, "status": "running", "deck_rules": "Preset decks"}
        self.assertEqual(run_label(run), "battle-empty · No results · Running")
        run.update(status="stopped")
        self.assertEqual(run_label(run), "battle-empty · No results · Stopped")
        run.update(scored_games=1)
        self.assertEqual(run_label(run), "battle-empty · 1 finished game · Preset decks")


if __name__ == "__main__":
    unittest.main()
