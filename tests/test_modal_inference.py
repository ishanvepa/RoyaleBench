import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from rb_evals.modal_inference import RATES
from rb_evals.results import ResultsCache, load_records, read_agent_metrics
from tests.helpers import ApiCase


MODEL = "openai/deepseek-v4.1-flash-1017"


def trajectory(model=MODEL):
    return {"trajectory_format": "mini-swe-agent-1.1", "info": {
        "config": {"model": {"model_name": model, "cost_tracking": "ignore_errors"}},
        "model_stats": {"api_calls": 1, "instance_cost": 0}}, "messages": [
            {"role": "assistant", "extra": {"response": {"id": "response-1", "usage": {
                "prompt_tokens": 8721, "completion_tokens": 371,
                "prompt_tokens_details": {"cached_tokens": 5376},
                "completion_tokens_details": {"reasoning_tokens": 100}}}}}]}


def save(root, data):
    root.mkdir(parents=True, exist_ok=True)
    (root / "trajectory.json").write_text(json.dumps(data), encoding="utf-8")
    # A summary fallback must not mask complete usage in the actual trajectory.
    (root / "summary.json").write_text('{"metrics": {"cost": 0}}', encoding="utf-8")


class ModalInferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_deepseek_matches_billed_token_subtotal_and_persists_exact_decimals(self):
        data = trajectory()
        # Several tool calls may store the same model response more than once.
        data["messages"].append(copy.deepcopy(data["messages"][0]))
        save(self.root, data)
        metrics = read_agent_metrics(self.root)
        self.assertEqual(metrics["cost"], 0.00123413)
        self.assertEqual(metrics["reported_cost"], 0)
        self.assertEqual(metrics["cost_source"], "modal_token_usage")
        saved = json.loads((self.root / "inference_cost.json").read_text())
        self.assertEqual(Decimal(saved["cost_usd"]), Decimal("0.00123413"))
        self.assertEqual({k: Decimal(v) for k, v in saved["cost_by_resource_usd"].items()}, {
            "Input Tokens (Uncached)": Decimal("0.00083625"),
            "Input Tokens (Cached)": Decimal("0.00002688"), "Output Tokens": Decimal("0.000371")})
        # Completion includes reasoning: it must not be charged a second time.
        self.assertEqual(saved["usage"]["output_tokens"], 371)
        before = (self.root / "inference_cost.json").read_bytes()
        with patch.dict(RATES, {MODEL: ("99", "99", "99")}):
            self.assertEqual(read_agent_metrics(self.root)["cost"], metrics["cost"])
        self.assertEqual((self.root / "inference_cost.json").read_bytes(), before)

    def test_all_four_exact_variants_have_the_verified_rates(self):
        for model, expected in ((MODEL, "0.00123413"),
                                ("openai/inkling-2-small", "0.00153578"),
                                ("openai/kimi-k3.1-pro", "0.0114752"),
                                ("openai/Qwen/Qwen3.8-2.4T-A95B", "0.01026")):
            with self.subTest(model=model):
                save(self.root, trajectory(model))
                self.assertEqual(Decimal(read_agent_metrics(self.root)["inference_cost_usd_exact"]), Decimal(expected))

    def test_incomplete_invalid_or_unaccounted_calls_are_unknown(self):
        for change in ("missing_cache", "missing_output", "bad_cache", "fractional", "extra_call", "no_calls",
                       "bad_total", "conflicting_duplicate"):
            with self.subTest(change=change):
                data = trajectory()
                usage = data["messages"][0]["extra"]["response"]["usage"]
                if change == "missing_cache":
                    del usage["prompt_tokens_details"]
                elif change == "missing_output":
                    del usage["completion_tokens"]
                elif change == "bad_cache":
                    usage["prompt_tokens_details"]["cached_tokens"] = 99999
                elif change == "fractional":
                    usage["completion_tokens"] = 1.5
                elif change == "extra_call":
                    data["info"]["model_stats"]["api_calls"] = 2
                elif change == "bad_total":
                    usage["total_tokens"] = 1
                elif change == "conflicting_duplicate":
                    duplicate = copy.deepcopy(data["messages"][0])
                    duplicate["extra"]["response"]["usage"]["completion_tokens"] += 1
                    data["messages"].append(duplicate)
                else:
                    del data["info"]["model_stats"]["api_calls"]
                save(self.root, data)
                self.assertIsNone(read_agent_metrics(self.root)["cost"])
                self.assertFalse((self.root / "inference_cost.json").exists())

    def test_replaced_trajectory_invalidates_the_saved_charge(self):
        data = trajectory()
        save(self.root, data)
        before = read_agent_metrics(self.root)
        data["messages"][0]["extra"]["response"]["usage"]["completion_tokens"] += 1
        save(self.root, data)
        after = read_agent_metrics(self.root)
        self.assertNotEqual(before["cost"], after["cost"])
        self.assertEqual(after["cost"], 0.00123513)
        del data["messages"][0]["extra"]["response"]["usage"]["completion_tokens"]
        save(self.root, data)
        self.assertIsNone(read_agent_metrics(self.root)["cost"])

    def test_unknown_model_is_not_priced_as_a_similar_variant(self):
        save(self.root, trajectory("openai/deepseek-v4.1-flash"))
        self.assertIsNone(read_agent_metrics(self.root)["cost"])


class ModalInferenceApiTests(ApiCase):
    def test_cached_tasks_roll_up_to_job_and_survive_restart_without_downloads(self):
        run_id = self.start(task_ids=["t1", "t2"], model=MODEL)
        self.advance(30)
        for task_id in ("t1", "t2"):
            folder = self.ctx.cache.task_dir(run_id, task_id)
            save(folder, trajectory())
            (folder / ".done").write_text("1")
        with patch.object(self.fake, "download_artifact", side_effect=AssertionError("must reuse cached usage")):
            for _ in range(2):
                self.ctx.cache = ResultsCache(self.ctx.cache.root)
                tasks = self.client.get(f"/api/evals/jobs/{run_id}/tasks").json()["tasks"]
                self.assertEqual([t["cost_usd"] for t in tasks], [0.00123413] * 2)
                job = self.client.get(f"/api/evals/jobs/{run_id}").json()["job"]
                self.assertEqual(job["cost_usd"], 0.00246826)
                self.assertEqual(job["cost_known"], 2)
                trace = self.client.get(f"/api/evals/jobs/{run_id}/tasks/t1/trace").json()
                self.assertEqual(trace["cost_source"], "modal_token_usage")
                self.assertEqual(Decimal(trace["inference_cost_usd_exact"]), Decimal("0.00123413"))
                self.assertEqual(trace["inference_pricing"]["rates_usd_per_million"]["Output Tokens"], "1.00")
                record = load_records(self.fake, self.ctx.cache, [self.fake.run(run_id)], fetch_costs=False)[0]
                self.assertEqual(sum(t["cost"] for t in record["tasks"]), job["cost_usd"])
