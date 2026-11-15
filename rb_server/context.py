"""Everything a request handler needs, built once at start-up and held on ``app.state.ctx``."""

from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from cr_arena.db import DB
from rb_evals.config import EvalsConfig, load_config
from rb_evals.protocol import ValkyrieAPI
from rb_evals.results import ResultsCache
from rb_evals.valkyrie import TTLCache, Valkyrie

from .errors import ApiError
from .play_sessions import PlaySessions
from .processes import ProcessRegistry
from .settings import Settings


class TaskResultCache:
    """Per-task Valkyrie results, kept in memory once the task is finished (they never change again)."""

    def __init__(self, max_items: int = 5000):
        self._items: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()
        self.max_items = max_items

    def get_many(self, run_id: str, task_ids: list[str], fetch: Callable[[str], dict], workers: int = 8) -> dict[str, dict]:
        """Details for the given finished tasks; tasks whose lookup fails are left out, never raised."""
        with self._lock:
            found = {t: self._items[(run_id, t)] for t in task_ids if (run_id, t) in self._items}
        missing = [t for t in task_ids if t not in found]
        if missing:
            def one(task_id: str) -> tuple[str, dict | None]:
                try:
                    return task_id, fetch(task_id)
                except Exception:  # noqa: BLE001 - one bad task must not hide the rest of the table
                    return task_id, None

            with ThreadPoolExecutor(max_workers=min(workers, len(missing))) as pool:
                fetched = list(pool.map(one, missing))
            with self._lock:
                if len(self._items) + len(fetched) > self.max_items:
                    self._items.clear()
                for task_id, detail in fetched:
                    if detail is not None:
                        self._items[(run_id, task_id)] = detail
                        found[task_id] = detail
        return found


@dataclass
class CostsState:
    state: str = "idle"  # idle | running | done | error
    done: int = 0
    total: int = 0
    error: str | None = None


class CostsJob:
    """At most one background download of task cost data at a time (the leaderboard polls its progress)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = CostsState()

    def status(self) -> CostsState:
        with self._lock:
            return dataclasses.replace(self._state)

    def start(self, work: Callable[[Callable[[int, int], None]], None]) -> bool:
        """Run ``work(progress)`` on a thread. False when a download is already running."""
        with self._lock:
            if self._state.state == "running":
                return False
            self._state = CostsState("running")

        def progress(done: int, total: int) -> None:
            with self._lock:
                self._state.done, self._state.total = done, total

        def runner() -> None:
            try:
                work(progress)
                with self._lock:
                    self._state.state = "done"
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._state.state, self._state.error = "error", f"{type(exc).__name__}: {exc}"

        threading.Thread(target=runner, name="rb-costs", daemon=True).start()
        return True


class ArenaHandle:
    """The legacy arena database, opened on first use so the Evals pages never depend on it being reachable."""

    def __init__(self, target: str | None = None, db: DB | None = None):
        self._target = target
        self._db = db
        self._lock = threading.Lock()

    def get(self) -> DB:
        if self._db is None:
            with self._lock:
                if self._db is None:
                    try:
                        self._db = DB(self._target)
                    except Exception as exc:  # noqa: BLE001 - a bad URL, a down database, a missing driver
                        raise ApiError(503, "database_unavailable", f"Cannot open the arena database: {type(exc).__name__}: {exc}") from exc
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None


@dataclass
class AppContext:
    settings: Settings
    cfg: EvalsConfig
    valkyrie: ValkyrieAPI
    cache: ResultsCache
    fake: bool = False
    now: Callable[[], float] = time.time  # the fake Valkyrie has its own clock, and durations must use the same one
    task_results: TaskResultCache = field(default_factory=TaskResultCache)
    costs: CostsJob = field(default_factory=CostsJob)
    arena: ArenaHandle = field(default_factory=ArenaHandle)
    processes: ProcessRegistry = field(default_factory=ProcessRegistry)
    plays: PlaySessions = field(default_factory=PlaySessions)
    memo: TTLCache = field(default_factory=TTLCache)  # short-lived memo for read endpoints that polling pages hit often

    def db(self) -> DB:
        return self.arena.get()


def build_context(settings: Settings, *, valkyrie: ValkyrieAPI | None = None, cfg: EvalsConfig | None = None) -> AppContext:
    cfg = cfg or load_config(settings.evals_config)
    if settings.benchmarks_dir:
        cfg = dataclasses.replace(cfg, benchmarks_dir=Path(settings.benchmarks_dir))
    if settings.cache_dir:
        cfg = dataclasses.replace(cfg, cache_dir=Path(settings.cache_dir))
    fake = valkyrie is None and settings.fake_valkyrie
    if fake:
        from rb_evals.fake import FakeValkyrie

        valkyrie = FakeValkyrie(cfg.benchmarks_dir, benchmark=cfg.benchmark)
        if not settings.cache_dir:  # simulated results must never mix with the real run cache
            cfg = dataclasses.replace(cfg, cache_dir=cfg.cache_dir.parent / "evals-fake")
    valkyrie = valkyrie or Valkyrie()
    return AppContext(settings, cfg, valkyrie, ResultsCache(cfg.cache_dir), fake=fake, now=getattr(valkyrie, "clock", time.time),
                      arena=ArenaHandle(settings.arena_db))
