"""Settings for the Evals dashboard, read from evals.toml at the repository root."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "evals.toml"

# API-key variables for the common model providers; anything else is derived from the provider prefix.
PROVIDER_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


@dataclass(frozen=True)
class ModelPreset:
    id: str  # Valkyrie model key, e.g. anthropic/claude-sonnet-4-6
    secret_env: str = ""  # variable the harness reads the API key from


@dataclass(frozen=True)
class EvalsConfig:
    benchmark: str = "royalebench"
    provider: str = "modal"
    default_agent: str = "claude_code-v1.0.0"
    default_concurrency: int = 1
    max_concurrency: int = 10
    confirm_over_tasks: int = 5
    models: tuple[ModelPreset, ...] = ()
    benchmarks_dir: Path = ROOT / "benchmarks"
    cache_dir: Path = ROOT / "runs" / "evals"
    # Start / stop / publish spend organisation credits with this server's Valkyrie login.
    read_only: bool = False

    def dataset_ref(self, name: str) -> str:
        return f"{self.benchmark}/{name}"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def load_config(path: Path | str | None = None) -> EvalsConfig:
    """Read evals.toml (defaults when it is missing); ROYALEBENCH_EVALS_READONLY=1 forces read-only mode."""
    path = Path(path) if path else CONFIG_PATH
    data: dict = {}
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    v = data.get("valkyrie", {})
    defaults = EvalsConfig()
    models = tuple(ModelPreset(m["id"], m.get("secret_env", "")) for m in data.get("models", []) if m.get("id"))
    return EvalsConfig(
        benchmark=v.get("benchmark", defaults.benchmark),
        provider=v.get("provider", defaults.provider),
        default_agent=v.get("default_agent", defaults.default_agent),
        default_concurrency=int(v.get("default_concurrency", defaults.default_concurrency)),
        max_concurrency=int(v.get("max_concurrency", defaults.max_concurrency)),
        confirm_over_tasks=int(v.get("confirm_over_tasks", defaults.confirm_over_tasks)),
        models=models,
        read_only=_truthy(os.environ.get("ROYALEBENCH_EVALS_READONLY")),
    )


def secret_env_for(model_id: str, presets: tuple[ModelPreset, ...] = ()) -> str:
    """Environment variable the harness reads this model's API key from."""
    for preset in presets:
        if preset.id == model_id and preset.secret_env:
            return preset.secret_env
    prefix = model_id.partition("/")[0].strip().lower()
    if prefix in PROVIDER_KEY_ENV:
        return PROVIDER_KEY_ENV[prefix]
    cleaned = "".join(c if c.isalnum() else "_" for c in prefix).upper() or "MODEL"
    return f"{cleaned}_API_KEY"
