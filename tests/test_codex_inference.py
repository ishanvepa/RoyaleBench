import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from rb_evals.codex_inference import RATES
from rb_evals.results import read_agent_metrics

MODEL = "openai/gpt-6.1-sol"
USAGE = {"cost": None, "wall_clock_duration": 23.52, "input_tokens": 111758, "cached_input_tokens": 94326,
         "cache_write_input_tokens": 17411, "output_tokens": 308, "reasoning_output_tokens": 24}


def save(root, metrics=USAGE, model=MODEL):
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "metrics_total.json").write_text(json.dumps(metrics), encoding="utf-8")
    (logs / "summary.json").write_text(json.dumps({"metadata": {"model": model}, "metrics": metrics}), encoding="utf-8")


class CodexCostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_prices_each_token_class_once_and_persists_the_breakdown(self):
        save(self.root)
        metrics = read_agent_metrics(self.root)
        # 21 uncached @2 + 94,326 cached @0.10 + 17,411 written @2.50 + 308 output @10 (reasoning is inside output)
        self.assertEqual(Decimal(metrics["inference_cost_usd_exact"]), Decimal("0.0560821"))
        self.assertEqual(metrics["cost"], 0.0560821)
        self.assertEqual(metrics["cost_source"], "codex_token_usage")
        self.assertEqual((metrics["input_tokens"], metrics["output_tokens"], metrics["cache_write_tokens"]),
                         (111758, 308, 17411))
        saved = json.loads((self.root / "token_cost.json").read_text())
        self.assertEqual(Decimal(saved["cost_by_resource_usd"]["Cache Write Tokens (30m)"]), Decimal("0.0435275"))

    def test_saved_rates_are_reused_not_repriced(self):
        save(self.root)
        first = read_agent_metrics(self.root)["cost"]
        before = (self.root / "token_cost.json").read_bytes()
        with patch.dict(RATES, {MODEL: ("99", "99", "99", "99")}):
            self.assertEqual(read_agent_metrics(self.root)["cost"], first)
        self.assertEqual((self.root / "token_cost.json").read_bytes(), before)

    def test_every_gpt6_model_is_priced(self):
        for model in RATES:
            with self.subTest(model=model):
                root = self.root / model.split("/")[1]
                save(root, model=model)
                self.assertGreater(read_agent_metrics(root)["cost"], 0)

    def test_unknown_model_or_inconsistent_usage_stays_unknown(self):
        save(self.root / "other", model="openai/gpt-unpriced")
        self.assertIsNone(read_agent_metrics(self.root / "other"))  # no price: nothing to report, nothing invented
        # Cached + written tokens exceeding the input total would double count: refuse to guess.
        save(self.root / "bad", {**USAGE, "cache_write_input_tokens": 50000})
        bad = read_agent_metrics(self.root / "bad")
        self.assertIsNone(bad["cost"])
        self.assertFalse((self.root / "bad" / "token_cost.json").exists())

    def test_harness_reported_cost_is_never_overridden(self):
        save(self.root, {**USAGE, "cost": 1.25})
        self.assertEqual(read_agent_metrics(self.root)["cost"], 1.25)
        self.assertFalse((self.root / "token_cost.json").exists())


if __name__ == "__main__":
    unittest.main()
