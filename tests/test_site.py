"""Keep competition formats and recorded deck rules separate in results."""

import json
import tempfile
import unittest
from pathlib import Path

from cr_arena.db import DB
from cr_arena.site import _family, build, result_runs


class ResultsTests(unittest.TestCase):
    def test_model_family_takes_priority_over_compatible_provider(self):
        for model, family in (
            ("openai/Qwen3.8-2.4T-A95B", "qwen"),
            ("openai/inkling-2-small", "inkling"),
            ("openai/deepseek-v4.1-flash-1017", "deepseek"),
            ("openai/kimi-k3.1-pro", "kimi"),
            ("moonshotai/Kimi-K2", "kimi"),
            ("moonshot-v1-8k", "kimi"),
            ("thinkingmachines/inkling-2-small", "inkling"),
            ("QwQ-32B", "qwen"),
            ("openai/gpt-5", "gpt"),
            ("anthropic/custom-model", "claude"),
        ):
            with self.subTest(model=model):
                self.assertEqual(_family(model, True), family)
        self.assertEqual(_family("inkling-bot", False), "bot")

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

    def test_replay_links_point_at_the_web_app_match_page(self):
        out = Path(self.directory.name) / "site.html"
        build(self.db, out=out, dashboard_url="http://example.test")
        html = out.read_text(encoding="utf-8")
        self.assertIn("${DATA.dashboard}/legacy/matches/${encodeURIComponent(g.job)}/${encodeURIComponent(g.id)}", html)
        self.assertNotIn("?page=Match", html)  # the Streamlit address scheme is gone
        self.assertIn("http://example.test", html)


if __name__ == "__main__":
    unittest.main()
