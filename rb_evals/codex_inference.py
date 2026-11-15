"""Token-based cost for Codex runs, whose harness reports usage but never a dollar amount.

Codex writes ``"cost": null`` next to its token counts, so the price is derived here and persisted next to the
task output, like ``modal_inference`` does for Modal-hosted models.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# USD per million tokens, from the OpenAI rate card the team supplied on 2026-11-15 (see docs/evals_dashboard.md).
# Exact model IDs only: never apply another model's price. Cache writes are billed per retention window; the
# harness logs do not say which one Codex used, so the cheaper 30-minute write rate is applied (see RATE_NOTE).
RATE_VERSION = "openai-gpt6-rate-card-2026-11-15"
RATE_SOURCE = "OpenAI standard API rates supplied by the team"
RATE_NOTE = "cache writes priced at the 30-minute rate; the 12-hour rate is higher"
RATES = {  # input, cached input, cache write (30m), output
    "openai/gpt-6-astra": ("10.00", "1.00", "12.50", "50.00"),
    "openai/gpt-6.1-sol": ("2.00", "0.10", "2.50", "10.00"),
    "openai/gpt-6.1-terra": ("1.00", "0.05", "1.25", "5.00"),
    "openai/gpt-6-luna": ("0.10", "0.01", "0.125", "0.50"),
}
RESOURCE_KEYS = ("Input Tokens (Uncached)", "Input Tokens (Cached)", "Cache Write Tokens (30m)", "Output Tokens")
SCHEMA_VERSION = 1
FILENAME = "token_cost.json"


def _count(value) -> int | None:
    return value if type(value) is int and value >= 0 else None


def read_codex_metrics(root: Path) -> dict | None:
    """Priced metrics for a Codex task folder, or None when it is not a Codex task with a known price.

    Only applies to a ``metrics_total.json`` whose cost is null (a numeric cost from a harness always wins),
    sitting next to a ``summary.json`` that names a model in ``RATES``.
    """
    for path in sorted(root.rglob("metrics_total.json")):
        try:
            raw = path.read_bytes()
            data = json.loads(raw)
            model = json.loads((path.parent / "summary.json").read_text(encoding="utf-8"))["metadata"]["model"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("cost") is not None or model not in RATES:
            continue
        counts = [_count(data.get(k)) for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                                                "output_tokens")]
        base = {"cost": None, "cost_source": "unknown", "wall_s": data.get("wall_clock_duration"),
                "input_tokens": counts[0], "output_tokens": counts[3], "cache_read_tokens": counts[1],
                "cache_write_tokens": counts[2], "reasoning_tokens": _count(data.get("reasoning_output_tokens")),
                "cost_note": "Codex cost requires complete token usage; input must include cached and cache-write tokens."}
        # Input already contains the cached and cache-written tokens: charging all three would double count.
        if any(c is None for c in counts) or counts[1] + counts[2] > counts[0]:
            return base
        return _persist(root, model, base, counts, hashlib.sha256(raw).hexdigest())
    return None


def _persist(root: Path, model: str, base: dict, counts: list[int], digest: str) -> dict:
    path = root / FILENAME
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if not (isinstance(saved, dict) and saved.get("schema_version") == SCHEMA_VERSION
            and saved.get("metrics_sha256") == digest and saved.get("model") == model):
        uncached = counts[0] - counts[1] - counts[2]
        amounts = (uncached, counts[1], counts[2], counts[3])  # reasoning tokens are already inside output
        breakdown = {k: str(Decimal(n) * Decimal(rate) / Decimal(1_000_000))
                     for k, n, rate in zip(RESOURCE_KEYS, amounts, RATES[model])}
        saved = {"schema_version": SCHEMA_VERSION, "model": model, "metrics_sha256": digest,
                 "recorded_at": datetime.now(timezone.utc).isoformat(), "rate_version": RATE_VERSION,
                 "rate_source": RATE_SOURCE, "rate_note": RATE_NOTE,
                 "rates_usd_per_million": dict(zip(RESOURCE_KEYS, RATES[model])),
                 "usage": dict(zip(("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                                    "output_tokens"), counts)),
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
    return {**base, "cost": float(Decimal(saved["cost_usd"])), "cost_source": "codex_token_usage",
            "cost_note": (f"Calculated from Codex token usage at {saved['rate_version']} rates; "
                          f"{saved['rate_note']}; excludes infrastructure and invoice adjustments."),
            "inference_cost_usd_exact": saved["cost_usd"],
            "inference_pricing": {k: saved[k] for k in ("rate_version", "rate_source", "rate_note",
                                                        "rates_usd_per_million", "cost_by_resource_usd")}}
