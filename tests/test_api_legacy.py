"""The /api/legacy endpoints: results, overview, jobs, matches, replays, models, decks, play and battles.

    uv run python -m unittest tests.test_api_legacy -v
"""

import os
import subprocess
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from cr_arena.battles import BattleRun
from cr_arena.decks import CLASSIC_DECKS
from rb_server.app import create_app
from rb_server.context import ArenaHandle, build_context
from rb_server.processes import ManagedProcess
from rb_server.settings import Settings
from tests.helpers import ARENA_CONFIG, SAMPLE_REPLAY, ApiCase, seed_arena, write

L = "/api/legacy"
MOCK_CONFIG = Path(__file__).resolve().parent / "mock_config.toml"


class LegacyCase(ApiCase):
    def setUp(self):
        super().setUp()
        self.ids = seed_arena(self.db)
        config = write(Path(self.tmp.name) / "arena.toml", ARENA_CONFIG)
        patcher = patch.dict(os.environ, {"CR_ARENA_CONFIG": str(config)})
        patcher.start()
        self.addCleanup(patcher.stop)


class ResultsTests(LegacyCase):
    def test_runs_exclude_human_games_and_describe_their_format(self):
        runs = {r["name"]: r for r in self.client.get(f"{L}/results").json()["runs"]}
        self.assertEqual(set(runs), {"tourney", "battle-1"})
        self.assertEqual((runs["battle-1"]["format"], runs["battle-1"]["deck_rules"], runs["battle-1"]["scored_games"]), ("duel", "Model-built decks", 1))
        self.assertEqual((runs["tourney"]["format"], runs["tourney"]["scored_games"], runs["tourney"]["status"]), ("round_robin", 1, "running"))

    def test_results_of_a_run(self):
        r = self.client.get(f"{L}/results/tourney").json()
        self.assertEqual((r["name"], r["format"], r["running"], r["deck_rules"]), ("tourney", "round_robin", True, "Preset decks"))
        winner = r["players"][0]
        self.assertEqual((winner["rank"], winner["name"], winner["wins"], winner["losses"], winner["family"], winner["logo_url"]),
                         (1, "model-a", 1, 0, "claude", "/api/assets/logos/claude"))
        self.assertEqual((winner["crowns"], winner["crown_diff"], winner["three_crowns"], winner["as_blue"]), (3.0, 3, 1, [1, 0, 0]))
        self.assertTrue(winner["llm"])
        (game,) = r["games"]
        self.assertEqual((game["id"], game["winner"], game["crowns"], game["replay"], game["deck_kind"]), ("a-b__s1", 0, [3, 0], True, "preset"))
        self.assertEqual(self.client.get(f"{L}/results/battle-1").json()["games"][0]["deck_kind"], "built")

    def test_unknown_or_invalid_run_names(self):
        self.assertEqual(self.client.get(f"{L}/results/nope").status_code, 404)
        self.assertEqual(self.client.get(f"{L}/results/human-play").status_code, 404)  # human games never get standings
        self.assertEqual(self.client.get(f"{L}/results/-bad").status_code, 422)


class JobTests(LegacyCase):
    def test_overview_and_job_list(self):
        ov = self.client.get(f"{L}/overview").json()
        self.assertEqual((ov["totals"]["jobs"], ov["totals"]["running_jobs"], ov["totals"]["matches_done"], ov["totals"]["matches_total"]), (3, 1, 2, 4))
        row = next(j for j in ov["jobs"] if j["name"] == "tourney")
        self.assertEqual((row["done"], row["total"], row["running"], row["notes"], row["players"]), (1, 3, 1, "a note", ["model-a", "model-b", "bot"]))
        names = [j["name"] for j in self.client.get(f"{L}/jobs").json()["jobs"]]
        self.assertEqual(set(names), {"tourney", "battle-1", "human-play"})

    def test_job_report_has_every_tab_with_providers_attached(self):
        r = self.client.get(f"{L}/jobs/tourney").json()
        self.assertEqual((r["status"], r["done"], r["total"], r["anchor"], r["decision_ticks"]), ("running", 1, 3, "bot", 40))
        self.assertEqual([(s["rank"], s["player"], s["wins"], s["family"]) for s in r["standings"]], [(1, "model-a", 1, "claude"), (2, "model-b", 0, "gpt")])
        self.assertEqual(r["win_table"][0]["player"], "model-a")
        self.assertEqual({e["ending"]: e["matches"] for e in r["endings"]}["3-crown knockout"], 1)
        self.assertEqual({m["player"] for m in r["metrics"]}, {"model-a", "model-b"})
        self.assertEqual(r["metrics"][0]["family"], "claude")
        self.assertIn("[[players]]", r["config_toml"])
        self.assertEqual(self.client.get(f"{L}/jobs/nope").status_code, 404)

    def test_matches_filter_and_paginate(self):
        everything = self.client.get(f"{L}/jobs/tourney/matches").json()
        self.assertEqual((everything["total"], everything["players"]), (3, ["bot", "model-a", "model-b"]))
        done = self.client.get(f"{L}/jobs/tourney/matches", params={"status": "done"}).json()["matches"]
        self.assertEqual([(m["match_id"], m["winner"], m["ending"], m["errors_blue"], m["has_replay"]) for m in done],
                         [("a-b__s1", "model-a", "3-crown knockout", 3, True)])
        by_bot = self.client.get(f"{L}/jobs/tourney/matches", params={"player": "bot"}).json()["matches"]
        self.assertEqual({m["match_id"] for m in by_bot}, {"b-bot__s1", "a-bot__s1"})
        page = self.client.get(f"{L}/jobs/tourney/matches", params={"page": 2, "page_size": 2}).json()
        self.assertEqual((len(page["matches"]), page["total"], page["page"]), (1, 3, 2))
        self.assertEqual(self.client.get(f"{L}/jobs/tourney/matches", params={"page_size": 500}).status_code, 422)

    def test_match_report_and_on_demand_decision_detail(self):
        r = self.client.get(f"{L}/jobs/tourney/matches/a-b__s1").json()
        self.assertEqual((r["blue"], r["winner"], r["crowns"], r["deck"], r["decks"], r["decision_seconds"], r["has_replay"]),
                         ("model-a", "model-a", [3, 0], ["x"], None, 2.0, True))
        self.assertEqual(len(r["decisions"]), 6)
        first = r["decisions"][0]
        self.assertEqual((first["step"], first["team"], first["asked"], first["ok"], first["time_elapsed_s"]), (0, 0, True, True, 0.0))
        self.assertNotIn("state", first)
        detail = self.client.get(f"{L}/jobs/tourney/matches/a-b__s1/decisions/0/0").json()
        self.assertEqual(detail, {"state": "THE BOARD", "raw": "I will wait.\nMOVE: 0"})
        self.assertEqual(self.client.get(f"{L}/jobs/tourney/matches/a-b__s1/decisions/99/0").status_code, 404)
        self.assertEqual(self.client.get(f"{L}/jobs/tourney/matches/nope").status_code, 404)
        built = self.client.get(f"{L}/jobs/tourney/matches/b-bot__s1").json()
        self.assertEqual(built["decks"], {"blue": ["x"], "red": ["y"]})


class ReplayTests(LegacyCase):
    def test_a_saved_replay_is_served_as_a_sandboxed_page(self):
        self.assertTrue(SAMPLE_REPLAY.exists(), "the repository ships sample replays")
        r = self.client.get(f"{L}/jobs/tourney/matches/a-b__s1/replay")
        self.assertEqual(r.status_code, 200, r.text[:200])
        self.assertTrue(r.headers["content-type"].startswith("text/html"))
        self.assertEqual(r.headers["content-security-policy"], "sandbox allow-scripts")  # the viewer runs script: confine it
        self.assertIn("<html", r.text.lower())

    def test_matches_without_a_replay_explain_why(self):
        running = self.client.get(f"{L}/jobs/tourney/matches/b-bot__s1/replay")
        self.assertEqual(running.status_code, 404)
        self.assertIn("saved when a match finishes", running.json()["error"]["message"])
        finished = self.client.get(f"{L}/jobs/battle-1/matches/x__vs__y__s1/replay")
        self.assertEqual(finished.status_code, 404)
        self.assertIn("replays_per_pair", finished.json()["error"]["message"])


class ModelsTests(LegacyCase):
    def test_models_overview(self):
        self.db.execute("INSERT INTO model_checks VALUES (?, ?, ?, ?, ?, ?, ?)", ("model-a", "anthropic", "claude-x", 1, 1.2, "ok", 1000.0))
        r = self.client.get(f"{L}/models").json()
        self.assertEqual(r["config_name"], "arena.toml")
        rows = {m["name"]: m for m in r["models"]}
        self.assertEqual((rows["model-a"]["family"], rows["model-a"]["logo_url"], rows["model-a"]["key_env"], rows["model-a"]["check_ok"]),
                         ("claude", "/api/assets/logos/claude", "ANTHROPIC_API_KEY", True))
        self.assertEqual((rows["bot"]["family"], rows["bot"]["logo_url"], rows["bot"]["key_ok"]), ("bot", None, None))

    def test_a_check_runs_in_the_background_once_at_a_time(self):
        log = Path(self.tmp.name) / "check.log"
        log.write_text("OK   model-a   1.2s\n")
        proc = SimpleNamespace(poll=lambda: None)
        started = ManagedProcess("model-check", proc, log)
        with patch("rb_server.services.legacy.spawn", return_value=started) as spawn:
            first = self.client.post(f"{L}/models/check")
            self.assertEqual((first.status_code, first.json()["state"]), (200, "running"))
            args = spawn.call_args.args[1]
            self.assertEqual(args[:2], ["-m", "cr_arena.check_models"])
            self.assertEqual(self.client.post(f"{L}/models/check").status_code, 409)  # already running
        self.assertIn("OK   model-a", self.client.get(f"{L}/models/check").json()["output"])
        proc.poll = lambda: 0
        self.assertEqual(self.client.get(f"{L}/models/check").json()["state"], "done")
        proc.poll = lambda: 1
        self.assertEqual(self.client.get(f"{L}/models/check").json()["state"], "failed")

    def test_no_check_has_run_yet(self):
        self.assertEqual(self.client.get(f"{L}/models/check").json()["state"], "idle")


class DeckTests(LegacyCase):
    def cards(self):
        return list(CLASSIC_DECKS["giant-beatdown"])

    def test_lists_presets_and_the_card_pool(self):
        r = self.client.get(f"{L}/decks").json()
        keys = [d["key"] for d in r["decks"]]
        self.assertEqual(keys, list(CLASSIC_DECKS))
        giant = next(d for d in r["decks"] if d["key"] == "giant-beatdown")
        self.assertEqual((giant["preset"], giant["id"], giant["avg_elixir"]), (True, None, 3.38))
        card = next(c for c in r["cards"] if c["name"] == "Fireball")
        self.assertEqual((card["kind"], card["elixir"]), ("Spell", 4))
        self.assertGreater(len(r["cards"]), 50)

    def test_save_edit_and_delete_a_deck(self):
        created = self.client.post(f"{L}/decks", json={"name": " My deck ", "cards": self.cards()})
        self.assertEqual(created.status_code, 201, created.text)
        deck = created.json()
        self.assertEqual((deck["name"], deck["preset"], deck["key"].startswith("custom:"), deck["cards"]), ("My deck", False, True, self.cards()))
        self.assertIn(deck["key"], [d["key"] for d in self.client.get(f"{L}/decks").json()["decks"]])

        replacement = list(CLASSIC_DECKS["lavaloon"])
        edited = self.client.put(f"{L}/decks/{deck['id']}", json={"name": "Edited", "cards": replacement}).json()
        self.assertEqual((edited["name"], edited["cards"], edited["id"]), ("Edited", replacement, deck["id"]))

        self.assertEqual(self.client.delete(f"{L}/decks/{deck['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"{L}/decks/{deck['id']}").status_code, 404)
        self.assertEqual(self.client.put(f"{L}/decks/{deck['id']}", json={"name": "x", "cards": replacement}).status_code, 404)

    def test_invalid_decks_report_the_offending_field_and_change_nothing(self):
        ok = self.client.post(f"{L}/decks", json={"name": "Original", "cards": self.cards()}).json()
        cases = [({"name": "Bad", "cards": self.cards()[:7]}, "cards"), ({"name": "Bad", "cards": ["Knight"] * 8}, "cards"),
                 ({"name": "Bad", "cards": self.cards()[:7] + ["MissingCard"]}, "cards"), ({"name": "Original", "cards": self.cards()}, "name")]
        for body, field in cases:
            r = self.client.post(f"{L}/decks", json=body)
            self.assertEqual((r.status_code, r.json()["error"]["code"], r.json()["error"]["detail"][0]["field"]), (422, "validation_error", field), body)
        self.assertEqual(self.client.post(f"{L}/decks", json={"name": "", "cards": self.cards()}).status_code, 422)
        saved = [d for d in self.client.get(f"{L}/decks").json()["decks"] if not d["preset"]]
        self.assertEqual([d["id"] for d in saved], [ok["id"]])


class PlayTests(LegacyCase):
    def setUp(self):
        super().setUp()
        bots = {"random-bot": {"name": "random-bot", "type": "random", "seed": 3}}
        patcher = patch("rb_server.services.play.opponents", return_value=bots)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self, **overrides):
        body = {"opponent": "random-bot", "deck": "giant-beatdown", "seed": 1, "ticks": 40, **overrides}
        r = self.client.post(f"{L}/play/games", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_options(self):
        r = self.client.get(f"{L}/play/options").json()
        self.assertEqual([(o["name"], o["kind"], o["family"]) for o in r["opponents"]], [("random-bot", "bot", "bot")])
        self.assertEqual(r["tick_choices"], [20, 40, 60])
        self.assertEqual(len(r["decks"]), len(CLASSIC_DECKS))

    def test_a_new_game_describes_the_board_the_hand_and_the_legal_moves(self):
        g = self.start()
        self.assertEqual((g["over"], g["winner"], g["opponent"], g["crowns"], g["overtime"]), (False, None, "random-bot", [0, 0], False))
        self.assertEqual(len(g["hand"]), 4)
        self.assertEqual({h["name"] for h in g["hand"]} <= set(CLASSIC_DECKS["giant-beatdown"]), True)
        towers = [e for e in g["entities"] if e["kind"] in ("king", "princess")]
        self.assertEqual((len(towers), sum(1 for t in towers if t["team"] == 0)), (6, 3))
        self.assertTrue(all(0 <= e["x"] <= 18 and 0 <= e["y"] <= 32 for e in g["entities"]))
        wait = g["moves"][0]
        self.assertEqual((wait["index"], wait["slot"], wait["kind"], wait["x"]), (0, -1, "WAIT", None))
        plays = [m for m in g["moves"] if m["slot"] >= 0]
        self.assertTrue(plays and all(m["x"] is not None and m["cost"] <= g["elixir"] for m in plays))
        self.assertEqual(len(g["zones"]), 8)

    def test_playing_a_move_advances_the_game_and_logs_it(self):
        g = self.start()
        move = next(m for m in g["moves"] if m["slot"] >= 0)
        after = self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": move["index"]})
        self.assertEqual(after.status_code, 200, after.text)
        after = after.json()
        self.assertGreater(after["step"], g["step"])
        self.assertTrue(any(f"you played {move['card']}" in line for line in after["log"]), after["log"])
        self.assertEqual(self.client.get(f"{L}/play/games/{g['id']}").json()["step"], after["step"])  # the server holds the game

    def test_an_illegal_move_is_refused_and_the_game_is_unchanged(self):
        g = self.start()
        r = self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": 999})
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "validation_error"))
        self.assertEqual(self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": -1}).status_code, 422)
        self.assertEqual(self.client.get(f"{L}/play/games/{g['id']}").json()["step"], g["step"])

    def test_bad_starts(self):
        for body, field in (({"opponent": "nobody"}, "opponent"), ({"deck": "no-such-deck"}, "deck"), ({"opponent_deck": "custom:zzz"}, "opponent_deck"), ({"ticks": 33}, "ticks")):
            r = self.client.post(f"{L}/play/games", json={"opponent": "random-bot", "deck": "giant-beatdown", **body})
            self.assertEqual((r.status_code, r.json()["error"]["detail"][0]["field"]), (422, field), body)
        self.assertEqual(self.client.post(f"{L}/play/games", json={"opponent": "random-bot", "deck": "giant-beatdown", "seed": 0}).status_code, 422)

    def test_an_abandoned_or_unknown_game_is_gone(self):
        g = self.start()
        self.assertEqual(self.client.delete(f"{L}/play/games/{g['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"{L}/play/games/{g['id']}").status_code, 404)
        self.assertEqual(self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": 0}).status_code, 404)

    def test_games_in_progress_are_capped(self):
        self.ctx.plays.max_sessions = 2
        first, second = self.start(), self.start()
        r = self.client.post(f"{L}/play/games", json={"opponent": "random-bot", "deck": "giant-beatdown"})
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "conflict"))
        self.client.delete(f"{L}/play/games/{first['id']}")
        self.assertEqual(self.client.post(f"{L}/play/games", json={"opponent": "random-bot", "deck": "giant-beatdown"}).status_code, 201)
        self.assertEqual(self.client.get(f"{L}/play/games/{second['id']}").status_code, 200)

    def test_a_finished_game_is_saved_with_its_replay_and_shows_up_under_jobs(self):
        g = self.start(ticks=60)
        deadline = time.time() + 120
        while not g["over"] and time.time() < deadline:
            r = self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": 0})  # always wait: the game still runs to the end
            self.assertEqual(r.status_code, 200, r.text)
            g = r.json()
        self.assertTrue(g["over"])
        self.assertIn(g["winner"], (0, 1, 2))
        self.assertTrue(g["saved_as"] and g["saved_as"].startswith("human__vs__random-bot__"), g)
        self.assertIsNone(g["save_error"])
        self.assertEqual(self.client.post(f"{L}/play/games/{g['id']}/move", json={"index": 0}).status_code, 409)
        matches = self.client.get(f"{L}/jobs/human-play/matches").json()["matches"]
        self.assertEqual([(m["match_id"], m["blue"], m["red"], m["status"]) for m in matches], [(g["saved_as"], "human", "random-bot", "done")])
        report = self.client.get(f"{L}/jobs/human-play/matches/{g['saved_as']}").json()
        self.assertGreater(len(report["decisions"]), 10)
        self.assertTrue(report["has_replay"])


class BattleTests(LegacyCase):
    def test_options_list_only_models(self):
        r = self.client.get(f"{L}/battles/options").json()
        self.assertEqual([p["name"] for p in r["players"]], ["model-a", "model-b"])  # the bot is not offered
        self.assertEqual((r["max_parallel"], r["config_name"]), (6, "arena.toml"))

    def test_preview_counts_games_or_says_why_not(self):
        ok = self.client.post(f"{L}/battles/preview", json={"players": ["model-a", "model-b"], "mode": "mirror"}).json()
        self.assertEqual((ok["valid"], ok["games"], ok["error"]), (True, 2, None))  # one seed, both sides
        bad = self.client.post(f"{L}/battles/preview", json={"players": ["model-a", "bot"], "mode": "mirror"}).json()
        self.assertEqual((bad["valid"], bad["error"]), (False, "Choose two different enabled models."))
        self.assertEqual(self.client.post(f"{L}/battles/preview", json={"players": ["a"], "mode": "mirror"}).status_code, 422)
        self.assertEqual(self.client.post(f"{L}/battles/preview", json={"players": ["model-a", "model-b"], "mode": "chaos"}).status_code, 422)

    def test_a_custom_deck_is_snapshotted_into_the_runner_config(self):
        deck = self.client.post(f"{L}/decks", json={"name": "Mine", "cards": list(CLASSIC_DECKS["lavaloon"])}).json()
        launched = {}

        def fake_launch(root, config_text, names, mode, parallel, db_target):
            launched.update(config=config_text, names=names, mode=mode, parallel=parallel)
            log = Path(self.tmp.name) / "runner.log"
            log.write_text("[1/2] done\n")
            return BattleRun("battle-20261114-000000-abcd1234", SimpleNamespace(poll=lambda: None), log)

        with patch("rb_server.services.battles.launch_battle", side_effect=fake_launch):
            r = self.client.post(f"{L}/battles", json={"players": ["model-a", "model-b"], "mode": "mirror", "deck": deck["key"], "parallel": 2})
        self.assertEqual(r.status_code, 201, r.text)
        out = r.json()
        self.assertEqual((out["name"], out["state"], out["players"], out["job_exists"]), ("battle-20261114-000000-abcd1234", "running", ["model-a", "model-b"], False))
        self.assertIn("Lava" if "Lava" in str(CLASSIC_DECKS["lavaloon"]) else "LavaHound", launched["config"])
        self.assertEqual((launched["names"], launched["mode"], launched["parallel"]), (["model-a", "model-b"], "mirror", 2))
        status = self.client.get(f"{L}/battles/battle-20261114-000000-abcd1234").json()
        self.assertEqual((status["state"], "[1/2] done" in status["output"]), ("running", True))
        listed = self.client.get(f"{L}/battles").json()["battles"]
        self.assertEqual([b["name"] for b in listed], ["battle-20261114-000000-abcd1234"])
        self.assertEqual(listed[0]["output"], "")  # the list stays small; the log comes with the status

    def test_invalid_battles_never_launch(self):
        with patch("rb_server.services.battles.launch_battle", side_effect=AssertionError("must not launch")):
            r = self.client.post(f"{L}/battles", json={"players": ["model-a", "model-a"], "mode": "mirror"})
            self.assertEqual(r.status_code, 422)
            r = self.client.post(f"{L}/battles", json={"players": ["model-a", "model-b"], "mode": "mirror", "deck": "custom:missing"})
            self.assertEqual((r.status_code, r.json()["error"]["detail"][0]["field"]), (422, "deck"))
            self.assertEqual(self.client.post(f"{L}/battles", json={"players": ["model-a", "model-b"], "parallel": 9}).status_code, 422)

    def test_a_finished_battle_reports_its_exit_and_links_to_its_job(self):
        log = Path(self.tmp.name) / "r.log"
        log.write_text("runner failed")
        proc = SimpleNamespace(poll=lambda: 1)
        self.ctx.processes.add(BattleRun("battle-1", proc, log))  # "battle-1" is also a seeded job
        r = self.client.get(f"{L}/battles/battle-1").json()
        self.assertEqual((r["state"], r["exit_code"], r["job_exists"], r["output"]), ("failed", 1, True, "runner failed"))
        self.assertEqual(self.client.get(f"{L}/battles/battle-unknown").status_code, 404)

    def test_a_database_url_never_goes_on_a_command_line(self):
        from cr_arena.battles import launch_battle

        with patch("cr_arena.battles.subprocess.Popen") as popen:
            launch_battle(Path(self.tmp.name), ARENA_CONFIG, ["model-a", "model-b"], "mirror", 1, "postgresql://user:secret@host/db")
        command = popen.call_args.args[0]
        self.assertNotIn("--db", command)
        self.assertFalse(any("secret" in str(part) for part in command))
        self.assertEqual(popen.call_args.kwargs["env"]["DATABASE_URL"], "postgresql://user:secret@host/db")


class ReadOnlyLegacyTests(LegacyCase):
    read_only = True

    def test_everything_that_changes_state_or_spends_credits_is_refused(self):
        calls = [("post", f"{L}/models/check", None), ("post", f"{L}/decks", {"name": "x", "cards": list(CLASSIC_DECKS["lavaloon"])}),
                 ("put", f"{L}/decks/abc", {"name": "x", "cards": list(CLASSIC_DECKS["lavaloon"])}), ("delete", f"{L}/decks/abc", None),
                 ("post", f"{L}/play/games", {"opponent": "search-bot", "deck": "giant-beatdown"}),
                 ("post", f"{L}/play/games/abc/move", {"index": 0}),
                 ("post", f"{L}/battles", {"players": ["model-a", "model-b"]})]
        for method, url, body in calls:
            r = self.client.request(method, url, json=body)
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (403, "read_only"), url)
        self.assertEqual(self.client.get(f"{L}/overview").status_code, 200)
        self.assertEqual(self.client.get(f"{L}/battles/options").status_code, 200)


class DatabaseUnavailableTests(unittest.TestCase):
    def test_legacy_pages_report_an_unreachable_database_without_breaking_evals(self):
        tmp = Path(__import__("tempfile").mkdtemp())
        settings = Settings(static_dir=tmp / "none", arena_db="postgresql://nobody:x@127.0.0.1:1/none")
        ctx = build_context(settings, valkyrie=__import__("rb_evals.fake", fromlist=["FakeValkyrie"]).FakeValkyrie(seed=False))
        ctx.arena = ArenaHandle(settings.arena_db)
        client = TestClient(create_app(settings, ctx=ctx), headers={"x-rb-client": "web"})
        self.addCleanup(client.close)
        r = client.get(f"{L}/overview")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (503, "database_unavailable"))
        self.assertEqual(client.get("/api/evals/environment").status_code, 200)  # the Evals area never needed it


if __name__ == "__main__":
    unittest.main()
