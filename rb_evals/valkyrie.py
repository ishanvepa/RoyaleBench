"""Synchronous facade over the Valkyrie SDK.

Every method opens a short-lived client (the same login as ``valkyrie login``), returns plain dicts and
lists, and raises ``ValkyrieError`` with a message fit to show in the UI. Returning plain data keeps the
API and the tests independent of SDK model classes, and lets tests swap in a fake client.

Read calls are memoised for a few seconds, one in-flight request per key, so many browser tabs polling the
same run share a single Valkyrie request; anything that changes state clears the memo.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from valkyrie.sdk import (
    FetchBenchmarksRequest,
    FetchTasksRequest,
    ValkyrieAPIError,
    ValkyrieClient,
    ValkyrieSDKError,
)
from valkyrie.sdk.models import HostedDataset

READ_TIMEOUT_S = 30.0  # a dashboard request should fail fast rather than hang on a dead network
PUSH_TIMEOUT_S = 600.0  # uploading task archives can legitimately take a while


class ValkyrieError(RuntimeError):
    """A Valkyrie call failed. ``kind`` is auth | network | not_found | rejected | other."""

    def __init__(self, message: str, kind: str = "other"):
        super().__init__(message)
        self.kind = kind


def describe_error(exc: BaseException) -> ValkyrieError:
    if isinstance(exc, ValkyrieAPIError):
        if exc.status_code == 401:
            return ValkyrieError("Not signed in to Valkyrie, or the login expired. Run `valkyrie login`, then reload.", "auth")
        detail = exc.detail
        if isinstance(detail, list):  # validation errors: [{loc, msg}, ...]
            detail = "; ".join(f"{(d.get('loc') or ['?'])[-1]}: {d.get('msg')}" for d in detail if isinstance(d, dict))
        if exc.status_code == 404:
            return ValkyrieError(f"Not found on Valkyrie: {detail}", "not_found")
        return ValkyrieError(f"Valkyrie rejected the request ({exc.status_code}): {detail}", "rejected")
    if isinstance(exc, (httpx.HTTPError, ConnectionError, TimeoutError)):
        return ValkyrieError(f"Cannot reach Valkyrie: {type(exc).__name__}: {exc}", "network")
    if isinstance(exc, ValkyrieSDKError):
        text = str(exc)
        if "login" in text.lower():
            return ValkyrieError(f"{text} Run `valkyrie login`, then reload.", "auth")
        return ValkyrieError(text, "rejected" if isinstance(exc, ValueError) else "other")
    return ValkyrieError(f"{type(exc).__name__}: {exc}")


def _uuid(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except (ValueError, AttributeError, TypeError):
        raise ValkyrieError(f"Not a valid run id: {run_id!r}", "not_found") from None


def run_sync(make: Callable[[], Awaitable[Any]]) -> Any:
    """asyncio.run that also works when the calling thread already has an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(make())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make())).result()


class TTLCache:
    """Time-limited memo with one in-flight computation per key. Failures are never cached."""

    def __init__(self) -> None:
        self._items: dict[Any, tuple[float, Any]] = {}
        self._locks: dict[Any, threading.Lock] = {}
        self._lock = threading.Lock()

    def _hit(self, key: Any) -> tuple[bool, Any]:
        with self._lock:
            item = self._items.get(key)
            if item and item[0] > time.monotonic():
                return True, item[1]
        return False, None

    def get_or_set(self, key: Any, ttl: float, make: Callable[[], Any]) -> Any:
        found, value = self._hit(key)
        if found:
            return value
        with self._lock:
            gate = self._locks.setdefault(key, threading.Lock())
        with gate:  # a second caller waits here, then finds the first caller's result
            found, value = self._hit(key)
            if found:
                return value
            value = make()
            with self._lock:
                self._items[key] = (time.monotonic() + ttl, value)
            return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


def _dump(model: Any) -> Any:
    return model.model_dump(mode="json") if hasattr(model, "model_dump") else model


class Valkyrie:
    """What the dashboard needs from Valkyrie. ``client_factory`` exists so tests can inject a fake client."""

    def __init__(self, client_factory: Callable[[], Any] | None = None):
        self._custom_factory = client_factory
        self._cache = TTLCache()

    # ------------------------------------------------------------------ plumbing
    def _client(self, timeout: float) -> Any:
        return self._custom_factory() if self._custom_factory else ValkyrieClient(timeout=timeout)

    def _call(self, op: Callable[[Any], Awaitable[Any]], *, key: Any = None, ttl: float = 0,
              timeout: float = READ_TIMEOUT_S) -> Any:
        def go() -> Any:
            async def main() -> Any:
                async with self._client(timeout) as client:
                    return await op(client)

            try:
                return run_sync(main)
            except ValkyrieError:
                raise
            except Exception as exc:  # noqa: BLE001 - everything becomes a UI-safe message
                raise describe_error(exc) from exc

        if key is None or ttl <= 0:
            return go()
        return self._cache.get_or_set(key, ttl, go)

    def _mutate(self, op: Callable[[Any], Awaitable[Any]], *, timeout: float = READ_TIMEOUT_S) -> Any:
        try:
            return self._call(op, timeout=timeout)
        finally:
            self._cache.clear()

    def invalidate(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------ account / environment
    def identity(self) -> dict:
        async def op(c):
            return _dump(await c.account.identity())

        return self._call(op, key="identity", ttl=60)

    def providers(self) -> dict[str, str]:
        async def op(c):
            return dict((await c.providers.list()).providers)

        return self._call(op, key="providers", ttl=60)

    def secret_names(self) -> list[str]:
        async def op(c):
            return sorted(s.name for s in (await c.secrets.list()).secrets)

        return self._call(op, key="secrets", ttl=30)

    def agent_names(self) -> list[str]:
        async def op(c):
            return sorted(a.name for a in (await c.agents.list()).agents)

        return self._call(op, key="agents", ttl=60)

    def queue(self, run_id: str | None = None) -> dict:
        """Scheduler summary; with ``run_id`` also that run's queued/active task counts and best position."""

        async def op(c):
            o = await c.scheduler.overview()
            out = {"summary": _dump(o.summary), "waiting": 0, "active": 0, "position": None}
            if run_id:
                waiting = [w for w in o.waiting_entries if str(w.benchmark_uuid) == run_id]
                out["waiting"] = len(waiting)
                out["active"] = sum(1 for a in o.active_entries if str(a.benchmark_uuid) == run_id)
                out["position"] = min((w.position for w in waiting), default=None)
            return out

        return self._call(op, key=("queue", run_id), ttl=3)

    # ------------------------------------------------------------------ runs
    def list_runs(self, benchmark: str | None = None) -> list[dict]:
        async def op(c):
            request = FetchBenchmarksRequest(benchmark_name=[benchmark] if benchmark else None, limit=200)
            return [_dump(row) async for row in c.runs.iter(request)]

        return self._call(op, key=("runs", benchmark), ttl=5)

    def run(self, run_id: str) -> dict:
        """One run, in the same shape as a ``list_runs`` row (label and dataset included)."""
        rid = _uuid(run_id)

        async def op(c):
            single, fetched = await asyncio.gather(c.benchmarks.fetch(rid), c.runs.fetch(rid))
            data = _dump(single)
            data["label"] = fetched.label
            return data

        base = self._call(op, key=("run", run_id), ttl=3)
        args = self.run_metadata(run_id).get("benchmark_arguments") or {}
        return {**base, "dataset": args.get("dataset") or ""}

    def run_metadata(self, run_id: str) -> dict:
        """What the run was launched with: agent contract (secret references), dataset version, concurrency."""
        rid = _uuid(run_id)

        async def op(c):
            return _dump(await c.runs.metadata(rid))

        return self._call(op, key=("meta", run_id), ttl=30)

    def run_tasks(self, run_id: str) -> list[dict]:
        rid = _uuid(run_id)

        async def op(c):
            request = FetchTasksRequest.model_validate({"limit": 500, "sort": "task_id", "sort_dir": "asc"})
            return [_dump(t) async for t in c.benchmarks.iter_tasks(rid, request)]

        return self._call(op, key=("tasks", run_id), ttl=3)

    def task(self, run_id: str, task_id: str) -> dict:
        rid = _uuid(run_id)

        async def op(c):
            return _dump(await c.benchmarks.task(rid, task_id))

        return self._call(op, key=("task", run_id, task_id), ttl=5)

    def results(self, run_id: str) -> dict:
        """Final results JSON of a run (per-task rewards, durations, errors, launch arguments)."""
        rid = _uuid(run_id)

        async def op(c):
            return _dump(await c.runs.results(rid))

        return self._call(op)

    def run_logs(self, run_id: str, *, task_id: str | None = None, query: str | None = None, limit: int = 500) -> list[dict]:
        """Newest ``limit`` log lines, oldest first."""
        rid = _uuid(run_id)

        async def op(c):
            if task_id:
                page = await c.logs.page_task(rid, task_id, query=query or None, limit=1000)
            else:
                page = await c.logs.page_run(rid, query=query or None, limit=1000)
            events = [{"timestamp": e.timestamp.isoformat(), "task_id": e.task_id, "message": e.message} for e in page.events]
            return events[-limit:]

        return self._call(op, key=("logs", run_id, task_id, query, limit), ttl=3)

    def run_errors(self, run_id: str) -> dict:
        """Run-level error message and per-task error messages."""
        run = self.run(run_id)
        tasks = [t for t in self.run_tasks(run_id) if t.get("error_message")]
        return {"run": run.get("error_message"), "tasks": {t["task_id"]: t["error_message"] for t in tasks}}

    # ------------------------------------------------------------------ run control
    def start_run(self, *, benchmark: str, dataset: str, ref: str, agent: str, model: str, concurrency: int,
                  task_ids: Sequence[str] | None, label: str, provider: str, secrets: dict[str, str]) -> dict:
        async def op(c):
            response = await c.datasets.start_run(
                agent, HostedDataset(benchmark=benchmark, dataset=dataset, ref=ref), benchmark=benchmark,
                model=model, concurrency=concurrency, task_ids=list(task_ids) if task_ids else None,
                label=label, provider=provider, secrets=secrets)
            return {"run_id": str(response.benchmark_id), "task_count": response.task_count,
                    "dataset_version": _dump(response.dataset_version),
                    "warning": response.dataset_version_warning, "started_at": response.started_at.isoformat()}

        return self._mutate(op)

    def stop_run(self, run_id: str, *, force: bool = False) -> str:
        rid = _uuid(run_id)

        async def op(c):
            return (await c.runs.stop(rid, force=force)).status

        return self._mutate(op)

    def resume_run(self, run_id: str, *, concurrency: int | None = None) -> str:
        rid = _uuid(run_id)

        async def op(c):
            return (await c.runs.resume(rid, concurrency=concurrency)).status

        return self._mutate(op)

    def retry_run(self, run_id: str, *, concurrency: int | None = None) -> str:
        rid = _uuid(run_id)

        async def op(c):
            return (await c.runs.retry(rid, concurrency=concurrency)).status

        return self._mutate(op)

    def set_concurrency(self, run_id: str, concurrency: int) -> int:
        rid = _uuid(run_id)

        async def op(c):
            return (await c.runs.update_concurrency(rid, concurrency=concurrency)).concurrency

        return self._mutate(op)

    # ------------------------------------------------------------------ datasets
    def datasets(self, benchmark: str) -> list[dict]:
        async def op(c):
            return [_dump(d) for d in (await c.datasets.list(benchmark)).datasets]

        return self._call(op, key=("datasets", benchmark), ttl=30)

    def dataset_versions(self, benchmark: str, dataset: str) -> list[dict]:
        """Published versions, newest first."""

        async def op(c):
            return [_dump(v) for v in (await c.datasets.versions.list(benchmark, dataset)).versions]

        return self._call(op, key=("versions", benchmark, dataset), ttl=30)

    def dataset_tasks(self, benchmark: str, dataset: str, ref: str = "latest") -> list[dict]:
        async def op(c):
            return [_dump(t) for t in await c.datasets.versions.tasks(benchmark, dataset, ref)]

        return self._call(op, key=("dtasks", benchmark, dataset, ref), ttl=30)

    def push_dataset(self, benchmark: str, dataset: str, folder: Path | str, tags: Sequence[str] = ()) -> dict:
        """Publish a folder of task folders as a new dataset version (unchanged folders reuse the old one)."""
        notes: dict[str, Any] = {"stored": [], "created": [], "warnings": [], "left_out": {}}

        async def op(c):
            version = await c.datasets.push(
                benchmark, dataset, folder, tags=list(tags),
                on_stored=lambda task, _blob: notes["stored"].append(task),
                on_created=lambda name: notes["created"].append(name),
                on_left_out=lambda task, left: notes["left_out"].__setitem__(task, left),
                on_warning=notes["warnings"].append)
            return {"version": _dump(version), **notes}

        return self._mutate(op, timeout=PUSH_TIMEOUT_S)

    # ------------------------------------------------------------------ artifacts
    def download_artifact(self, run_id: str, path: str, dest: Path | str) -> Path:
        """Download a run artifact (a file or a folder) to ``dest/<path>``. ``dest`` must not exist yet."""
        rid = _uuid(run_id)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        async def op(c):
            return await c.artifacts.download(rid, dest, path=path)

        return self._call(op, timeout=PUSH_TIMEOUT_S)
