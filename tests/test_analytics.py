"""Arena analytics: win tables, endings, head to head, per-model metrics and the Job/Match report data.

    uv run python -m unittest tests.test_analytics -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from cr_arena import analytics as A
from cr_arena.db import DB

CONFIG = """
[tournament]
decision_ticks = 40
anchor = "bot"
[[players]]
name = "model-a"
provider = "anthropic"
model = "claude-x"
price_in = 3
price_out = 15
[[players]]
name = "model-b"
provider = "openai"
model = "gpt-x"
[[players]]
name = "bot"
type = "random"
"""


def match(blue, red, winner, crowns, ticks=3000, mid="m"):
    return {"match_id": mid, "blue": blue, "red": red, "winner": winner, "crowns": json.dumps(crowns), "ticks": ticks}


class PureLogicTests(unittest.TestCase):
    def test_endings(self):
        self.assertEqual(A.ending(match("a", "b", 0, [3, 0], 900)), "3-crown knockout")
        self.assertEqual(A.ending(match("a", "b", 0, [2, 1], 3600)), "more crowns at full time")
        self.assertEqual(A.ending(match("a", "b", 2, [1, 1], 3600)), "draw")
        self.assertEqual(A.ending(match("a", "b", 1, [1, 2], 4800)), "overtime crown")
        self.assertEqual(A.ending(match("a", "b", 0, [1, 1], 6000)), "tower-HP tiebreak")
        self.assertEqual(A.ending(match("a", "b", 2, [1, 1], 6000)), "draw")
        self.assertEqual(A.ending({"crowns": None, "ticks": None, "winner": 2}), "draw")

    def results(self):
        return [match("a", "b", 0, [3, 0], 900, "1"), match("b", "a", 0, [2, 1], 3600, "2"), match("a", "c", 2, [1, 1], 3600, "3"),
                match("c", "a", 1, [0, 1], 5000, "4")]

    def test_win_table_counts_every_way_a_game_can_end(self):
        rows = {r["player"]: r for r in A.win_table(self.results())}
        a = rows["a"]
        self.assertEqual((a["games"], a["wins"], a["draws"], a["losses"]), (4, 2, 1, 1))
        self.assertEqual((a["three_crown_wins"], a["won_in_overtime"], a["wins_as_blue"], a["wins_as_red"]), (1, 1, 1, 1))
        self.assertEqual((a["crowns_for"], a["crowns_against"], a["avg_crowns"]), (6, 3, 1.5))
        self.assertAlmostEqual(a["win_rate"], 0.5)
        self.assertEqual(rows["b"]["won_at_full_time"], 1)
        self.assertEqual(A.win_table(self.results())[0]["player"], "a")  # best win rate first
        self.assertEqual(A.win_table([]), [])

    def test_ending_counts_follow_the_fixed_order(self):
        counts = A.ending_counts(self.results())
        self.assertEqual([c["ending"] for c in counts], A.ENDING_ORDER)
        self.assertEqual({c["ending"]: c["matches"] for c in counts}, {"3-crown knockout": 1, "more crowns at full time": 1,
                                                                      "overtime crown": 1, "tower-HP tiebreak": 0, "draw": 1})

    def test_head_to_head_scores_a_draw_as_half_a_point_from_both_sides(self):
        cells = {(c["player"], c["opponent"]): c for c in A.head_to_head(self.results())}
        self.assertEqual((cells[("a", "b")]["points"], cells[("a", "b")]["games"]), (1.0, 2))  # won as blue, lost as red
        self.assertEqual(cells[("a", "c")]["points"], 1.5)  # a draw (0.5) and a win as red (1.0)
        self.assertEqual(cells[("c", "a")]["points"], 0.5)
        self.assertAlmostEqual(cells[("b", "a")]["score"], 0.5)

    def test_jl_tolerates_null_json_and_decoded_values(self):
        self.assertEqual(A.jl(None, []), [])
        self.assertEqual(A.jl("", {}), {})
        self.assertEqual(A.jl("[1, 2]"), [1, 2])
        self.assertEqual(A.jl([1]), [1])


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = DB(Path(self.tmp.name) / "arena.db")
        self.addCleanup(self.db.close)
        self.job_id = self.db.get_or_create_job("tourney", CONFIG, ["model-a", "model-b", "bot"], [1], 40, 3, "a note")
        self.db.set_job_status(self.job_id, "running")
        self.db.queue_matches(self.job_id, [
            {"match_id": "a-b", "blue": "model-a", "red": "model-b", "seed": 1, "deck": ["x"]},
            {"match_id": "b-bot", "blue": "model-b", "red": "bot", "seed": 1, "deck": {"blue": ["x"], "red": ["y"]}},
            {"match_id": "a-bot", "blue": "model-a", "red": "bot", "seed": 1, "deck": ["x"]},
        ])
        self.db.match_started(self.job_id, "a-b", "log", "replay.msgpack")
        self.db.match_finished(self.job_id, {"match_id": "a-b", "winner": 0, "crowns": [3, 0], "tower_hp": [], "ticks": 900, "wall_s": 12.0,
                                             "stats_blue": {"errors": 1, "illegal_or_unparsed": 2}, "stats_red": {}})
        self.db.match_started(self.job_id, "b-bot", "log", "")  # still running
        self.job = A.get_job(self.db, "tourney")

    def decision(self, match_id, step, team, player, **kw):
        base = dict(time_left=170.0 - step, elixir=5.0, my_towers=3000, enemy_towers=3000, n_moves=4, asked=1, move="wait",
                    result="wait", ok=1, error="", latency_s=1.5, tokens_in=1000, tokens_out=100, cache_read=0, cache_write=0,
                    raw="MOVE: 0", state="board text", cost_usd=0.0)
        base.update(kw)
        self.db.add_decisions([(self.job_id, match_id, step, team, player, base["time_left"], base["elixir"], base["my_towers"],
                                base["enemy_towers"], base["n_moves"], base["asked"], base["move"], base["result"], base["ok"],
                                base["error"], base["latency_s"], base["tokens_in"], base["tokens_out"], base["cache_read"],
                                base["cache_write"], base["raw"], base["state"], base["cost_usd"])])

    def test_player_metrics_classify_errors_and_estimate_cost(self):
        self.decision("a-b", 0, 0, "model-a")
        self.decision("a-b", 1, 0, "model-a", ok=0, error="TimeoutError: slow", result="wait", latency_s=3.5)
        self.decision("a-b", 2, 0, "model-a", ok=0, error="no MOVE line", result="wait")
        self.decision("a-b", 3, 0, "model-a", ok=0, error="illegal move 9", result="wait")
        self.decision("a-b", 4, 0, "model-a", asked=0, tokens_in=0, tokens_out=0, latency_s=0.0, move="wait", result="played Knight")
        self.decision("a-b", 0, 1, "bot", tokens_in=0, tokens_out=0, latency_s=0.0)
        metrics = {m["player"]: m for m in A.player_metrics(self.db, self.job_id, A.prices(self.db, {"players": []}))}
        a = metrics["model-a"]
        self.assertEqual((a["decisions"], a["asked"], a["api_errors"], a["bad_replies"], a["plays"]), (5, 4, 1, 2, 1))
        self.assertAlmostEqual(a["error_rate"], 0.25)
        self.assertAlmostEqual(a["bad_reply_rate"], 0.5)
        self.assertAlmostEqual(a["avg_latency_s"], (1.5 + 3.5 + 1.5 + 1.5) / 4)
        self.assertAlmostEqual(a["est_cost_usd"], (4000 * 3 + 400 * 15) / 1e6)  # priced from the job's own config
        bot = metrics["bot"]
        self.assertIsNone(bot["avg_latency_s"])  # bots make no API calls: those columns do not apply
        self.assertIsNone(bot["tokens_in"])
        self.assertEqual(bot["est_cost_usd"], 0.0)

    def test_reported_cost_beats_a_price_estimate(self):
        self.decision("a-b", 0, 0, "model-a", cost_usd=0.5)
        (a,) = [m for m in A.player_metrics(self.db, self.job_id) if m["player"] == "model-a"]
        self.assertEqual(a["est_cost_usd"], 0.5)

    def test_overview_totals_and_rows(self):
        self.decision("a-b", 0, 0, "model-a")
        self.db.get_or_create_job("done-job", "", ["x"], [1], 40, 0)
        ov = A.overview(self.db, now=self.job["started_at"] + 100)
        self.assertEqual((ov["totals"]["jobs"], ov["totals"]["running_jobs"], ov["totals"]["matches_done"], ov["totals"]["matches_total"]), (2, 1, 1, 3))
        self.assertEqual(ov["totals"]["decisions"], 1)
        row = next(r for r in ov["jobs"] if r["name"] == "tourney")
        self.assertEqual((row["done"], row["total"], row["running"], row["queued"], row["notes"]), (1, 3, 1, 1, "a note"))
        self.assertAlmostEqual(row["progress"], 1 / 3)
        self.assertAlmostEqual(row["elapsed_s"], 100)
        self.assertAlmostEqual(row["eta_s"], 200)  # 1 of 3 done after 100 s
        self.assertEqual(row["players"], ["model-a", "model-b", "bot"])

    def test_job_report_collects_every_tab(self):
        report = A.job_report(self.db, self.job)
        self.assertEqual((report["done"], report["anchor"], report["decision_ticks"]), (1, "bot", 40))
        self.assertEqual([s["player"] for s in report["standings"]], ["model-a", "model-b"])
        self.assertEqual(report["standings"][0]["rank"], 1)
        self.assertEqual(report["llm_players"], ["model-a", "model-b"])
        self.assertEqual({e["ending"]: e["matches"] for e in report["endings"]}["3-crown knockout"], 1)
        self.assertIn("[[players]]", report["config_toml"])

    def test_matches_filter_paginate_and_show_live_progress(self):
        self.decision("b-bot", 0, 0, "model-b", time_left=120.0)
        self.decision("b-bot", 1, 0, "model-b", time_left=118.0)
        allm = A.job_matches(self.db, self.job)
        self.assertEqual((allm["total"], allm["players"]), (3, ["bot", "model-a", "model-b"]))
        by = {m["match_id"]: m for m in allm["matches"]}
        self.assertEqual((by["a-b"]["winner"], by["a-b"]["crowns"], by["a-b"]["ending"], by["a-b"]["errors_blue"], by["a-b"]["has_replay"]),
                         ("model-a", [3, 0], "3-crown knockout", 3, True))
        self.assertEqual(by["b-bot"]["time_left_s"], 118.0)
        self.assertIsNone(by["b-bot"]["winner"])
        self.assertEqual([m["match_id"] for m in A.job_matches(self.db, self.job, status=["done"])["matches"]], ["a-b"])
        self.assertEqual({m["match_id"] for m in A.job_matches(self.db, self.job, player="bot")["matches"]}, {"b-bot", "a-bot"})
        page2 = A.job_matches(self.db, self.job, page=2, page_size=2)
        self.assertEqual((len(page2["matches"]), page2["total"]), (1, 3))

    def test_match_report_and_on_demand_detail(self):
        self.decision("a-b", 0, 0, "model-a", state="THE BOARD", raw="I will wait.\nMOVE: 0")
        self.decision("a-b", 0, 1, "model-b")
        report = A.match_report(self.db, self.job, "a-b")
        self.assertEqual((report["blue"], report["winner"], report["deck"], report["decks"], report["decision_seconds"]),
                         ("model-a", "model-a", ["x"], None, 2.0))
        first = report["decisions"][0]
        self.assertEqual((first["step"], first["team"], first["asked"], first["ok"]), (0, 0, True, True))
        self.assertNotIn("state", first)  # the (large) board text is fetched on demand
        self.assertEqual(A.decision_detail(self.db, self.job, "a-b", 0, 0), {"state": "THE BOARD", "raw": "I will wait.\nMOVE: 0"})
        self.assertIsNone(A.decision_detail(self.db, self.job, "a-b", 99, 0))
        self.assertIsNone(A.match_report(self.db, self.job, "nope"))
        self.assertEqual(A.match_report(self.db, self.job, "b-bot")["status"], "running")

    def test_built_decks_are_reported_per_side(self):
        self.db.set_match_decks(self.job_id, "a-b", ["p"], ["q"])
        report = A.match_report(self.db, self.job, "a-b")
        self.assertEqual((report["decks"], report["deck"]), ({"blue": ["p"], "red": ["q"]}, None))

    def test_models_overview_combines_config_checks_and_record(self):
        # Explicit timestamps: two checks inserted in the same clock tick would have no defined order.
        self.db.execute("INSERT INTO model_checks VALUES (?, ?, ?, ?, ?, ?, ?)", ("model-a", "anthropic", "claude-x", 1, 1.2, "ok", 1000.0))
        self.db.execute("INSERT INTO model_checks VALUES (?, ?, ?, ?, ?, ?, ?)", ("model-a", "anthropic", "claude-x", 0, 9.0, "later failure", 2000.0))
        rows = {r["name"]: r for r in A.models_overview(self.db, A.load_arena_config_text(CONFIG))}
        a = rows["model-a"]
        self.assertEqual((a["family"], a["provider"], a["key_env"], a["check_ok"], a["check_detail"]), ("claude", "anthropic", "ANTHROPIC_API_KEY", False, "later failure"))
        self.assertEqual((a["games"], a["wins"], a["price_in"]), (1, 1, 3))
        self.assertEqual((rows["bot"]["family"], rows["bot"]["key_ok"], rows["bot"]["check_ok"]), ("bot", None, None))


if __name__ == "__main__":
    unittest.main()
