import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch
from decimal import Decimal
from pathlib import Path

from rb_evals.config import ModelPreset
from rb_evals.modal_billing import ModalBilling
from rb_evals.results import read_agent_metrics
from tests.helpers import ApiCase


class ModalBillingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 11, 14, 18, 35, tzinfo=timezone.utc)
        self.models = tuple(ModelPreset(m, modal_app=f"ep-{m}") for m in ("qwen", "inkling", "deepseek"))
        self.calls = []
        self.amount = Decimal("0.123456789")

    def fetch(self, start, end, models):
        self.calls.append((start, end))
        return "workspace", {m.id: f"ap-{m.id}" for m in models}, [
            dict(object_id="ap-qwen", description="qwen", environment_name="main", interval_start=start,
                 cost=self.amount, cost_by_resource={"H100": self.amount}),
            dict(object_id="ap-deepseek", description="deepseek", environment_name="main", interval_start=start,
                 cost=Decimal("0")),
            dict(object_id="ap-other", description="other", environment_name="main", interval_start=start,
                 cost=Decimal("999"))]

    def service(self, **kwargs):
        return ModalBilling(self.root, self.models, fetch=kwargs.get("fetch", self.fetch), now=lambda: self.now)

    def test_sync_is_idempotent_and_survives_restart_without_network(self):
        billing = self.service()
        self.assertTrue(billing.sync())
        self.assertTrue(billing.sync())
        view = self.service(fetch=lambda *a: self.fail("should read from disk")).view()
        self.assertAlmostEqual(view["cost_usd"], float(self.amount))
        by = {m["model"]: m for m in view["models"]}
        self.assertEqual(by["qwen"]["cost_usd"], float(self.amount))
        self.assertEqual(by["deepseek"]["cost_usd"], 0)
        self.assertIsNone(by["inkling"]["cost_usd"])
        raw = json.loads((self.root / "workspace-2026-11.json").read_text())
        self.assertEqual(raw["rows"][0]["cost_usd"], str(self.amount))
        start, end = self.calls[-1]
        self.assertEqual((start.day, start.hour, end.hour, end.minute), (1, 0, 17, 0))

    def test_revised_bill_replaces_previous_total_and_failure_retains_data(self):
        billing = self.service()
        billing.sync()
        self.amount = Decimal("0.25")
        billing.sync()
        def fail(*args):
            raise PermissionError("secret must never be displayed")
        failed = self.service(fetch=fail)
        self.assertFalse(failed.sync())
        view = failed.view()
        self.assertEqual(view["cost_usd"], 0.25)
        self.assertIn("PermissionError", view["error"])
        self.assertNotIn("secret", view["error"])

    def test_shared_app_is_counted_once_in_total(self):
        shared = (ModelPreset("a", modal_app="ep-qwen"), ModelPreset("b", modal_app="ep-qwen"))
        def fetch(*args):
            workspace, _, rows = self.fetch(*args)
            return workspace, {"a": "ap-qwen", "b": "ap-qwen"}, rows
        billing = ModalBilling(self.root, shared, fetch=fetch, now=lambda: self.now)
        billing.sync()
        self.assertEqual(billing.view()["cost_usd"], float(self.amount))

    def test_changed_app_mapping_does_not_reuse_old_bill(self):
        billing = self.service()
        billing.sync()
        billing.models = (ModelPreset("qwen", modal_app="ep-other-qwen"),)
        self.assertIsNone(billing.view()["cost_usd"])
        self.assertIsNone(billing.view()["models"][0]["cost_usd"])
        self.assertIn("mapping changed", billing.view()["models"][0]["error"])

    def test_month_boundary_queries_last_complete_billing_period(self):
        self.now = datetime(2026, 12, 1, 0, 20, tzinfo=timezone.utc)
        self.service().sync()
        start, end = self.calls[-1]
        self.assertEqual((start.month, start.day, start.hour, end.month, end.day, end.hour), (11, 1, 0, 11, 30, 23))

    def test_sdk_month_request_uses_contiguous_seven_day_windows(self):
        @dataclass
        class Row:
            cost: Decimal
        report = Mock(side_effect=lambda **kwargs: [Row(Decimal("1"))])
        workspace = SimpleNamespace(name="workspace", hydrate=Mock(), billing=SimpleNamespace(report=report))
        sdk = SimpleNamespace(Workspace=SimpleNamespace(from_context=lambda: workspace),
            App=SimpleNamespace(lookup=Mock(return_value=SimpleNamespace(app_id="ap-qwen"))))
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        end = datetime(2026, 11, 30, 23, tzinfo=timezone.utc)
        with patch.dict("sys.modules", {"modal": sdk}):
            _, _, rows = ModalBilling._fetch(start, end, self.models)
        self.assertEqual(len(rows), 5)
        cursor = start
        for call in report.call_args_list:
            self.assertEqual(call.kwargs["start"], cursor)
            self.assertLessEqual(call.kwargs["end"] - cursor, timedelta(days=7))
            self.assertEqual(call.kwargs["resolution"], "h")
            cursor = call.kwargs["end"]
        self.assertEqual(cursor, end)


class MiniMetricsTests(unittest.TestCase):
    def write(self, root, *, cost=0, mode="ignore_errors", missing=False):
        message = {"role": "assistant", "extra": {"response": {"id": "one", "usage": {
            "prompt_tokens": 100, "completion_tokens": 20,
            "prompt_tokens_details": {"cached_tokens": 60},
            "completion_tokens_details": {"reasoning_tokens": 5}}}}}
        data = {"trajectory_format": "mini-swe-agent-1.1", "info": {
            "model_stats": {"instance_cost": cost, "api_calls": 1},
            "config": {"model": {"cost_tracking": mode}}}, "messages": [message, message]}
        if missing:
            data["messages"] = [{"role": "assistant"}]
        (root / "summary.json").write_text('{"agent": "mini_swe_agent"}')
        (root / "trajectory.json").write_text(json.dumps(data))

    def test_unknown_price_preserves_usage_without_false_zero_or_duplicate_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root)
            metrics = read_agent_metrics(root)
            self.assertIsNone(metrics["cost"])
            self.assertEqual(metrics["reported_cost"], 0)
            self.assertEqual([metrics[k] for k in ("input_tokens", "output_tokens", "cache_read_tokens", "reasoning_tokens")],
                             [100, 20, 60, 5])
            self.assertEqual(metrics["cost_source"], "unknown")
            self.write(root, cost=0.25)
            self.assertEqual(read_agent_metrics(root)["cost"], 0.25)

    def test_missing_usage_is_not_zero_and_known_zero_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, mode="default", missing=True)
            self.assertEqual(read_agent_metrics(root)["cost"], 0)
            self.assertIsNone(read_agent_metrics(root)["input_tokens"])


class BillingApiTests(ApiCase):
    def test_persisted_compute_is_exposed_separately_from_task_api_costs(self):
        billing = self.ctx.billing
        billing.models = (ModelPreset("openai/qwen", modal_app="ep-qwen"),)
        billing.now = lambda: datetime(2026, 11, 14, 18, tzinfo=timezone.utc)
        billing.fetch = lambda start, end, models: ("workspace", {"openai/qwen": "ap-qwen"}, [dict(
            object_id="ap-qwen", description="qwen", environment_name="main", interval_start=start, cost=Decimal("2.5"))])
        self.assertTrue(billing.sync())
        response = self.client.get("/api/evals/modal-billing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cost_usd"], 2.5)
        self.assertEqual(response.json()["models"][0]["object_id"], "ap-qwen")
        self.assertIsNone(self.client.get("/api/evals/jobs/claude-smoke").json()["job"]["cost_usd"])
