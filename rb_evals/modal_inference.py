"""Reproducible task inference charges from Modal-reported usage and verified rates."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Verified against Workspace.from_context().billing.rates() on 2026-11-15.
# Exact preset IDs only: never apply another provider's or model variant's price.
# USD per million tokens: uncached input, cached input, total completion.
# These models charge reasoning at the completion rate; completion already includes it.
RATE_VERSION = "modal-workspace-2026-11-15"
RATE_SOURCE = "modal.Workspace.from_context().billing.rates()"
RATES = {
    "openai/Qwen/Qwen3.8-2.4T-A95B": ("2.00", "0.25", "6.00"),
    "openai/inkling-2-small": ("0.30", "0.03", "1.00"),
    "openai/deepseek-v4.1-flash-1017": ("0.25", "0.005", "1.00"),
    "openai/kimi-k3.1-pro": ("2.00", "0.20", "10.00"),
}
USAGE_KEYS = ("input_tokens", "cache_read_tokens", "output_tokens")
RESOURCE_KEYS = ("Input Tokens (Uncached)", "Input Tokens (Cached)", "Output Tokens")


def record_inference_cost(root: Path, model: str, metrics: dict, trajectory_sha256: str) -> dict:
    """Attach and atomically persist a charge; reuse its original rates on later reads."""
    if model not in RATES:
        return metrics
    metrics = {**metrics, "cost": None, "cost_source": "unknown",
               "cost_note": "Modal inference cost requires complete token usage and matching API-call counts."}
    usage = {k: metrics.get(k) for k in USAGE_KEYS}
    if (not metrics.get("usage_complete") or any(type(v) is not int or v < 0 for v in usage.values())
            or usage["cache_read_tokens"] > usage["input_tokens"]):
        return metrics
    path = root / "inference_cost.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if not (isinstance(saved, dict) and saved.get("schema_version") == 1
            and saved.get("trajectory_sha256") == trajectory_sha256 and saved.get("model") == model):
        amounts = (usage["input_tokens"] - usage["cache_read_tokens"],
                   usage["cache_read_tokens"], usage["output_tokens"])
        breakdown = {k: str(Decimal(n) * Decimal(rate) / Decimal(1_000_000))
                     for k, n, rate in zip(RESOURCE_KEYS, amounts, RATES[model])}
        saved = {"schema_version": 1, "model": model, "trajectory_sha256": trajectory_sha256,
                 "recorded_at": datetime.now(timezone.utc).isoformat(),
                 "rate_version": RATE_VERSION, "rate_source": RATE_SOURCE,
                 "rates_usd_per_million": dict(zip(RESOURCE_KEYS, RATES[model])),
                 "usage": usage, "api_calls": metrics["api_calls"],
                 "cost_by_resource_usd": breakdown,
                 "cost_usd": str(sum((Decimal(v) for v in breakdown.values()), Decimal(0)))}
        # Independent dashboard requests can discover the same cached task together.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, delete=False) as handle:
            tmp = Path(handle.name)
            json.dump(saved, handle, allow_nan=False)
        try:
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return {**metrics, "cost": float(Decimal(saved["cost_usd"])), "cost_source": "modal_token_usage",
            "cost_note": ("Modal inference tokens only, calculated from complete response usage at "
                          f"{saved['rate_version']} rates; excludes infrastructure and invoice adjustments."),
            "inference_cost_usd_exact": saved["cost_usd"],
            "inference_pricing": {k: saved[k] for k in ("rate_version", "rate_source", "rates_usd_per_million",
                                                        "cost_by_resource_usd")}}
