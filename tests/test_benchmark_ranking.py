"""Task ranking uses completed attempts and the existing cost cache without downloads."""

import json
from unittest.mock import patch

from rb_evals import results as R
from tests.helpers import ApiCase, make_task, write
from tests.test_evals_backend import synthetic_results


class TaskRankingTests(ApiCase):
    URL = "/api/evals/benchmarks/alpha/ranking"

    def test_pools_attempts_and_averages_only_known_costs_excluding_infra_errors(self):
        run_ids = [self.start(task_ids=None), self.start(task_ids=None),
                   self.start(task_ids=["t1"]), self.start(task_ids=["t1"])]
        self.advance(30)
        self.start(task_ids=["t1"])  # active attempts do not enter the ranking
        raw = [
            synthetic_results({"t1": 1, "t2": 0}, errors={"t3": "network"},
                              categories={"t3": "infrastructure"}, dataset="alpha"),
            synthetic_results({"t1": 0, "t2": 1}, errors={"t3": "agent failed"},
                              categories={"t3": "agent"}, dataset="alpha", model="m/b", revision="2"),
            synthetic_results({"t1": 1}, dataset="alpha"),
            synthetic_results({"t1": 1}, dataset="alpha"),
        ]
        for run_id, data in zip(run_ids, raw):
            self.ctx.cache.save_results(run_id, data)
        for run_id, task, cost in [(run_ids[0], "t1", 0.3), (run_ids[1], "t1", 0),
                                   (run_ids[3], "t1", 0.6), (run_ids[0], "t2", 0.1),
                                   (run_ids[1], "t2", 0.5), (run_ids[0], "t3", 99)]:
            folder = self.ctx.cache.task_dir(run_id, task)
            write(folder / "metrics_total.json", json.dumps({"cost": cost}))
            write(folder / ".done", "1")
        make_task(self.benchmarks / "alpha" / "t4")  # current task with no attempts
        with patch.object(self.fake, "download_artifact", wraps=self.fake.download_artifact) as download:
            response = self.client.get(self.URL)
            self.assertEqual(response.status_code, 200, response.text)
            download.assert_not_called()
        body = response.json()
        self.assertEqual(body["runs_considered"], 4)
        self.assertEqual([r["task"] for r in body["rows"]], ["t3", "t2", "t1", "t4"])
        rows = {r["task"]: r for r in body["rows"]}
        self.assertEqual((rows["t1"]["attempts"], rows["t1"]["solved"], rows["t1"]["pass_rate"]), (4, 3, 0.75))
        self.assertEqual(rows["t1"]["cost_known"], 3)
        self.assertAlmostEqual(rows["t1"]["cost_per_task"], 0.3)  # zero counts, missing cost does not
        self.assertAlmostEqual(rows["t2"]["cost_per_task"], 0.3)
        self.assertEqual((rows["t3"]["attempts"], rows["t3"]["infra_errors"], rows["t3"]["pass_rate"]), (1, 1, 0))
        self.assertIsNone(rows["t3"]["cost_per_task"])  # infra's $99 never enters this average
        self.assertEqual((rows["t4"]["attempts"], rows["t4"]["cost_known"]), (0, 0))
        self.assertTrue(all(rows["t4"][key] is None for key in ("pass_rate", "cost_per_task", "rank")))

    def test_ties_share_ranks_and_unknown_costs_are_not_zero(self):
        rows = R.task_ranking([{"dataset": "alpha", "tasks": [
            {"task": task, "counted": True, "solved": solved, "cost": None}
            for task, solved in [("t1", True), ("t2", False), ("t3", False)]
        ]}], "alpha", ["t1", "t2", "t3", "untried"])
        self.assertEqual([(r["task"], r["rank"]) for r in rows], [("t2", 1), ("t3", 1), ("t1", 3), ("untried", None)])
        self.assertTrue(all(r["cost_per_task"] is None for r in rows))

    def test_empty_and_remote_only_benchmarks_and_unknown_name(self):
        body = self.client.get("/api/evals/benchmarks/draft/ranking").json()
        self.assertEqual((body["runs_considered"], body["costs_pending"]), (0, 0))
        self.assertEqual([(r["task"], r["attempts"], r["rank"]) for r in body["rows"]], [("d1", 0, None)])
        remote = self.client.get("/api/evals/benchmarks/arena-lite/ranking").json()
        self.assertEqual((remote["runs_considered"], len(remote["rows"])), (4, 4))
        self.assertTrue(all(r["attempts"] == 4 for r in remote["rows"]))
        self.assertEqual(self.client.get("/api/evals/benchmarks/missing/ranking").status_code, 404)
