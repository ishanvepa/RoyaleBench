"""Process-level settings, read from the environment once at start-up."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"  # local by default: start/stop/publish spend organisation credits
    port: int = 8000
    fake_valkyrie: bool = False  # in-memory Valkyrie: no network, no credentials, no cost
    static_dir: Path = ROOT / "web" / "dist"
    evals_config: Path | None = None  # evals.toml override
    benchmarks_dir: Path | None = None
    cache_dir: Path | None = None
    arena_db: str | None = None  # SQLite path or Postgres URL for the legacy arena pages

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            host=env.get("ROYALEBENCH_HOST", cls.host),
            port=int(env.get("ROYALEBENCH_PORT", cls.port)),
            fake_valkyrie=_truthy(env.get("ROYALEBENCH_FAKE_VALKYRIE")),
            static_dir=Path(env["ROYALEBENCH_STATIC_DIR"]) if env.get("ROYALEBENCH_STATIC_DIR") else cls.static_dir,
            evals_config=Path(env["ROYALEBENCH_EVALS_CONFIG"]) if env.get("ROYALEBENCH_EVALS_CONFIG") else None,
            benchmarks_dir=Path(env["ROYALEBENCH_BENCHMARKS_DIR"]) if env.get("ROYALEBENCH_BENCHMARKS_DIR") else None,
            cache_dir=Path(env["ROYALEBENCH_CACHE_DIR"]) if env.get("ROYALEBENCH_CACHE_DIR") else None,
            arena_db=env.get("ROYALEBENCH_ARENA_DB") or None,
        )
