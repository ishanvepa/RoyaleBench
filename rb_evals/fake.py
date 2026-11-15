"""In-memory Valkyrie for tests, demos and UI development (``ROYALEBENCH_FAKE_VALKYRIE=1``).

It implements ``ValkyrieAPI`` without any network access or credentials. Local benchmarks under
``benchmarks/`` appear as published (revision 1, in sync), a few finished runs are pre-seeded, and a run
started through ``start_run`` walks its tasks through PENDING, BUILDING, IN_PROGRESS, EVALUATING and
FINISHED in real time, ``concurrency`` tasks at a time. The clock is injectable so tests are deterministic.

Behaviour switches by model name, so error paths can be exercised on demand: a model ending in ``-broken``
fails every task with an infrastructure error.
"""

from __future__ import annotations

import io
import json
import tarfile
import threading
import time
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .benchmarks import discover_local, local_digests
from .valkyrie import ValkyrieError

BUILD_S, RUN_S, EVAL_S = 1.5, 3.0, 1.0
TERMINAL = ("FINISHED", "ERROR", "STOPPED")
SECRET_NAMES = ["anthropic-api-key-demo", "openai-api-key-demo", "modal-credentials"]
AGENT_NAMES = ["claude_code-v1.0.0", "codex-v1.0.0", "mini_swe_agent"]
# A dataset that exists only on Valkyrie (no local folder), so "remote only" and multi-task leaderboards can be shown.
REMOTE_ONLY = "arena-lite"
REMOTE_TASKS = ["lane-defense", "elixir-trade", "spell-timing", "counter-push"]


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts is not None else None


def _crc(*parts: str) -> int:
    return zlib.crc32("|".join(parts).encode())


def _strength(model: str) -> float:
    name = model.lower()
    for key, value in (("opus", 0.85), ("sonnet", 0.7), ("gpt-5", 0.6), ("haiku", 0.4)):
        if key in name:
            return value
    return 0.5


@dataclass
class _Task:
    id: str
    start_at: float  # epoch seconds at which the task leaves PENDING
    reward: float
    cost: float
    error: str = ""
    category: str = ""
    stopped: bool = False


@dataclass
class _Run:
    id: str
    label: str | None
    agent: str
    model: str
    dataset: str
    revision: int
    concurrency: int
    user: str
    started_at: float
    tasks: list[_Task]
    secrets: dict[str, str]
    task_ids: list[str] | None = None
    stopped_at: float | None = None
    stop_requested: bool = False


@dataclass
class _Version:
    revision: int
    digests: dict[str, str]
    tags: list[str]
    created_at: float
    created_by: str


class FakeValkyrie:
    def __init__(self, benchmarks_dir: Path | None = None, *, clock: Callable[[], float] = time.time,
                 user: str = "you@example.com", seed: bool = True, benchmark: str = "royalebench"):
        self.clock = clock
        self.user = user
        self.benchmark = benchmark
        self._lock = threading.RLock()
        self._runs: dict[str, _Run] = {}
        self._versions: dict[str, list[_Version]] = {}  # dataset -> versions, oldest first
        self._counter = 0
        now = clock()
        if benchmarks_dir is not None:
            for name, bench in discover_local(Path(benchmarks_dir)).items():
                self._versions[name] = [_Version(1, local_digests(bench), ["latest", "v1"], now - 86_400, "ci@example.com")]
        if seed:
            self._seed(now)

    # ------------------------------------------------------------------ seeding
    def _seed(self, now: float) -> None:
        self._versions[REMOTE_ONLY] = [_Version(1, {t: f"sha256:{_crc(t):064x}" for t in REMOTE_TASKS}, ["latest", "v1"],
                                                now - 172_800, "ben@example.com")]
        smoke = sorted(self._versions["smoke"][0].digests) if "smoke" in self._versions else []
        hour = 3600
        if smoke:
            self._seed_run("claude-smoke", "royalebench-connection-smoke", "claude_code-v1.0.0", "anthropic/claude-sonnet-4-6",
                           "smoke", smoke, now - 20 * hour)
            self._seed_run("gpt-smoke", "smoke-gpt-5", "codex-v1.0.0", "openai/gpt-5", "smoke", smoke, now - 18 * hour,
                           user="ben@example.com")
            self._seed_run("mini-smoke", "royalebench-mini-swe-smoke", "mini_swe_agent", "anthropic/claude-sonnet-4-6",
                           "smoke", smoke, now - 16 * hour, force_error=("Sandbox error: Dependency installation for contract "
                                                                         "mini_swe_agent failed with exit code 2", "agent"))
        for i, (agent, model, hours) in enumerate((("claude_code-v1.0.0", "anthropic/claude-opus-5-5", 12),
                                                   ("claude_code-v1.0.0", "anthropic/claude-sonnet-4-6", 10),
                                                   ("codex-v1.0.0", "openai/gpt-5", 8),
                                                   ("claude_code-v1.0.0", "anthropic/claude-haiku-5-5", 6))):
            self._seed_run(f"arena-{i}", f"arena-lite-{model.rpartition('/')[2]}", agent, model, REMOTE_ONLY,
                           REMOTE_TASKS, now - hours * hour, user="ishan@example.com" if i % 2 else "ben@example.com")

    def _seed_run(self, run_id: str, label: str, agent: str, model: str, dataset: str, tasks: list[str], started: float,
                  *, user: str | None = None, force_error: tuple[str, str] | None = None) -> None:
        run = self._make_run(run_id, label, agent, model, dataset, 1, tasks, 2, user or self.user, started,
                             secrets={"ANTHROPIC_API_KEY": "anthropic-api-key-demo"})
        if force_error:
            for task in run.tasks:
                task.error, task.category = force_error
        self._runs[run_id] = run

    def _make_run(self, run_id: str, label: str | None, agent: str, model: str, dataset: str, revision: int,
                  task_ids: list[str], concurrency: int, user: str, started: float, *, secrets: dict[str, str],
                  selected: list[str] | None = None) -> _Run:
        broken = model.endswith("-broken")
        tasks = []
        for i, task_id in enumerate(task_ids):
            solved = (_crc(model, task_id) % 100) / 100 < _strength(model)
            tasks.append(_Task(
                task_id, started + (i // max(1, concurrency)) * (BUILD_S + RUN_S + EVAL_S), 1.0 if solved else 0.0,
                round(0.01 + (_crc(task_id, model) % 400) / 10_000, 4),
                error="Sandbox lost connection to the agent" if broken else "", category="infrastructure" if broken else ""))
        return _Run(run_id, label, agent, model, dataset, revision, concurrency, user, started, tasks, dict(secrets),
                    task_ids=selected)

    # ------------------------------------------------------------------ time model
    def _status(self, task: _Task, now: float) -> str:
        if task.stopped:
            return "STOPPED"
        dt = now - task.start_at
        if dt < 0:
            return "PENDING"
        if dt < BUILD_S:
            return "BUILDING"
        if dt < BUILD_S + RUN_S:
            return "IN_PROGRESS"
        if task.error:
            return "ERROR"
        return "EVALUATING" if dt < BUILD_S + RUN_S + EVAL_S else "FINISHED"

    def _finished_at(self, task: _Task) -> float:
        return task.start_at + BUILD_S + RUN_S + (0 if task.error else EVAL_S)

    def _run_status(self, run: _Run, now: float) -> str:
        statuses = [self._status(t, now) for t in run.tasks]
        if any(s in ("PENDING", "BUILDING", "IN_PROGRESS", "EVALUATING") for s in statuses):
            return "STOPPING" if run.stop_requested else "IN_PROGRESS"
        if any(s == "STOPPED" for s in statuses):
            return "STOPPED"
        return "FINISHED" if "FINISHED" in statuses else "ERROR"

    def _counts(self, run: _Run, now: float) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in run.tasks:
            status = self._status(task, now)
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _row(self, run: _Run) -> dict:
        now = self.clock()
        status = self._run_status(run, now)
        counts = self._counts(run, now)
        terminal = sum(counts.get(s, 0) for s in TERMINAL)
        finished = [t for t in run.tasks if self._status(t, now) == "FINISHED"]
        done_at = max((self._finished_at(t) for t in run.tasks if self._status(t, now) in ("FINISHED", "ERROR")), default=None)
        score = 100 * sum(t.reward for t in finished) / len(finished) if status == "FINISHED" and finished else None
        error = None
        if status == "ERROR":
            error = f"No tasks were completed successfully. {len(run.tasks)}/{len(run.tasks)} tasks: {run.tasks[0].error}"
        return {"id": run.id, "name": self.benchmark, "agent_name": run.agent, "label": run.label, "model": run.model,
                "dataset": run.dataset, "started_by_email": run.user, "started_at": _iso(run.started_at),
                "finished_at": _iso(done_at) if status in ("FINISHED", "ERROR", "STOPPED") else None, "status": status,
                "total_tasks": len(run.tasks), "finished_tasks": terminal, "task_state_counts": counts,
                "final_score": score, "error_message": error}

    def _get(self, run_id: str) -> _Run:
        run = self._runs.get(run_id)
        if run is None:
            raise ValkyrieError(f"Not found on Valkyrie: run {run_id} not found", "not_found")
        return run

    # ------------------------------------------------------------------ ValkyrieAPI: environment
    def invalidate(self) -> None:
        return None

    def identity(self) -> dict:
        return {"organization": "fake-org", "email": self.user, "name": "Fake User", "credential": "login"}

    def providers(self) -> dict[str, str]:
        return {"modal": "modal-credentials"}

    def secret_names(self) -> list[str]:
        return list(SECRET_NAMES)

    def agent_names(self) -> list[str]:
        return list(AGENT_NAMES)

    def queue(self, run_id: str | None = None) -> dict:
        now = self.clock()
        summary = {"waiting": 0, "building": 0, "in_progress": 0, "evaluating": 0}
        out = {"summary": summary, "waiting": 0, "active": 0, "position": None}
        position = 0
        with self._lock:
            for run in self._runs.values():
                for task in run.tasks:
                    status = self._status(task, now)
                    key = {"PENDING": "waiting", "BUILDING": "building", "IN_PROGRESS": "in_progress",
                           "EVALUATING": "evaluating"}.get(status)
                    if key:
                        summary[key] += 1
                    if run_id and run.id == run_id:
                        if status == "PENDING":
                            out["waiting"] += 1
                            position += 1
                            out["position"] = out["position"] or position
                        elif key:
                            out["active"] += 1
        return out

    # ------------------------------------------------------------------ ValkyrieAPI: runs
    def list_runs(self, benchmark: str | None = None) -> list[dict]:
        with self._lock:
            rows = [self._row(r) for r in self._runs.values()]
        if benchmark and benchmark != self.benchmark:
            return []
        return sorted(rows, key=lambda r: r["started_at"], reverse=True)

    def run(self, run_id: str) -> dict:
        with self._lock:
            return self._row(self._get(run_id))

    def run_metadata(self, run_id: str) -> dict:
        run = self._get(run_id)
        refs = {env: f"valkyrie/tenants/fake/{name}" for env, name in run.secrets.items()}
        return {"benchmark_id": run.id, "benchmark_name": self.benchmark, "started_by_email": run.user,
                "benchmark_arguments": {
                    "contract": {"name": run.agent, "model": run.model, "secrets": refs, "kwargs": {"model": run.model}},
                    "concurrency": run.concurrency, "task_ids": run.task_ids, "slice_str": None, "dataset": run.dataset,
                    "dataset_version": {"id": f"{self.benchmark}/{run.dataset}@{run.revision}", "label": None},
                    "sandbox_provider": "modal"},
                "project": {"handle": "default", "name": "Default"}}

    def run_tasks(self, run_id: str) -> list[dict]:
        run, now = self._get(run_id), self.clock()
        out = []
        for task in sorted(run.tasks, key=lambda t: t.id):
            status = self._status(task, now)
            out.append({"id": f"{run.id}:{task.id}", "task_id": task.id, "status": status,
                        "started_at": _iso(max(task.start_at, run.started_at)) if status != "PENDING" else _iso(run.started_at),
                        "finished_at": _iso(self._finished_at(task)) if status in ("FINISHED", "ERROR") else None,
                        "error_message": task.error or None if status == "ERROR" else None,
                        "failure_category": task.category or None if status == "ERROR" else None})
        return out

    def _task(self, run: _Run, task_id: str) -> _Task:
        for task in run.tasks:
            if task.id == task_id:
                return task
        raise ValkyrieError(f"Not found on Valkyrie: task {task_id} not found in this run", "not_found")

    def _breakdown(self, task: _Task) -> dict:
        return {"sandbox_build_duration": BUILD_S, "agent_run_duration": RUN_S + (_crc(task.id) % 30) / 10,
                "evaluation_run_duration": EVAL_S, "sandbox_run_duration": BUILD_S + RUN_S + EVAL_S + 10}

    def _evaluation(self, task: _Task) -> dict:
        return {"task_id": task.id, "rewards": {"reward": task.reward},
                "verifier_result": {"rewards": {"reward": task.reward}},
                "metadata": {"reward_source": "/logs/verifier/reward.txt", "verifier_exit_code": 0,
                             "verifier_output": f"Verifier reward for {task.id}: {task.reward:g}\n"},
                "task_breakdown": self._breakdown(task)}

    def task(self, run_id: str, task_id: str) -> dict:
        run, now = self._get(run_id), self.clock()
        task = self._task(run, task_id)
        status = self._status(task, now)
        row = next(r for r in self.run_tasks(run_id) if r["task_id"] == task_id)
        out = {**row, "evaluation_result": None, "agent_caused_exit_reason": None, "task_breakdown": None}
        if status == "FINISHED":
            out["evaluation_result"] = self._evaluation(task)
            out["task_breakdown"] = self._breakdown(task)
        return out

    def results(self, run_id: str) -> dict:
        run, now = self._get(run_id), self.clock()
        row = self._row(run)
        done = [t for t in run.tasks if self._status(t, now) == "FINISHED"]
        failed = [t for t in run.tasks if self._status(t, now) == "ERROR"]
        durations = [self._breakdown(t) for t in done] or [{}]
        avg = lambda key: (sum(d.get(key, 0) for d in durations) / len(durations)) if done else None  # noqa: E731
        return {
            "benchmark_id": run.id, "benchmark_name": self.benchmark, "started_at": row["started_at"],
            "finished_at": row["finished_at"], "status": row["status"], "error_message": row["error_message"],
            "benchmark_arguments": self.run_metadata(run_id)["benchmark_arguments"], "tasks_stopped": None,
            "final_evaluation": ({"id": run.id, "org_id": "fake", "benchmark": run.id, "final_score": row["final_score"],
                                  "properties": {"total": len(run.tasks), "n_trials": len(done), "n_errors": len(failed)}}
                                 if row["final_score"] is not None else None),
            "average_task_breakdown": ({k: avg(k) for k in ("sandbox_build_duration", "agent_run_duration",
                                                            "evaluation_run_duration", "sandbox_run_duration")} if done else None),
            "evaluation_results": {t.id: self._evaluation(t) for t in done},
            "task_errors": {t.id: t.error for t in failed} or None,
            "task_failure_categories": {t.id: t.category for t in failed} or None,
        }

    def run_logs(self, run_id: str, *, task_id: str | None = None, query: str | None = None, limit: int = 500) -> list[dict]:
        run, now = self._get(run_id), self.clock()
        events = []
        for task in run.tasks:
            if task_id and task.id != task_id:
                continue
            status = self._status(task, now)
            steps = [(0.0, "sandbox build started"), (BUILD_S, "agent started"), (BUILD_S + RUN_S, "agent finished")]
            if not task.error:
                steps.append((BUILD_S + RUN_S, "verifier started"))
                steps.append((BUILD_S + RUN_S + EVAL_S, f"verifier reward {task.reward:g}"))
            else:
                steps.append((BUILD_S + RUN_S, f"error: {task.error}"))
            if status == "STOPPED":
                steps = [s for s in steps if task.start_at + s[0] <= (run.stopped_at or now)] + [(0.0, "task stopped")]
            for offset, message in steps:
                if task.start_at + offset <= now:
                    events.append({"timestamp": _iso(task.start_at + offset), "task_id": task.id, "message": message})
        events.sort(key=lambda e: e["timestamp"])
        if query:
            events = [e for e in events if query.lower() in e["message"].lower()]
        return events[-limit:]

    def run_errors(self, run_id: str) -> dict:
        tasks = {t["task_id"]: t["error_message"] for t in self.run_tasks(run_id) if t["error_message"]}
        return {"run": self.run(run_id)["error_message"], "tasks": tasks}

    # ------------------------------------------------------------------ ValkyrieAPI: run control
    def _resolve(self, dataset: str, ref: str) -> _Version:
        versions = self._versions.get(dataset)
        if not versions:
            raise ValkyrieError(f"Not found on Valkyrie: dataset {self.benchmark}/{dataset} not found", "not_found")
        for version in reversed(versions):
            if ref == "latest" and version is versions[-1] or ref == str(version.revision) or ref in version.tags:
                return version
        raise ValkyrieError(f"Not found on Valkyrie: version {ref!r} of {dataset} not found", "not_found")

    def start_run(self, *, benchmark: str, dataset: str, ref: str, agent: str, model: str, concurrency: int,
                  task_ids: Sequence[str] | None, label: str, provider: str, secrets: dict[str, str]) -> dict:
        version = self._resolve(dataset, ref)
        known = sorted(version.digests)
        chosen = list(task_ids) if task_ids else known
        missing = sorted(set(chosen) - set(known))
        if missing:
            raise ValkyrieError(f"Valkyrie rejected the request (422): unknown tasks {', '.join(missing)}", "rejected")
        if provider != "modal":
            raise ValkyrieError(f"Valkyrie rejected the request (422): unsupported provider {provider}", "rejected")
        with self._lock:
            self._counter += 1
            run_id = f"00000000-0000-4000-8000-{self._counter:012d}"
            now = self.clock()
            run = self._make_run(run_id, label, agent, model, dataset, version.revision, chosen, concurrency, self.user, now,
                                 secrets=secrets, selected=list(task_ids) if task_ids else None)
            self._runs[run_id] = run
        return {"run_id": run_id, "task_count": len(chosen),
                "dataset_version": {"id": f"{benchmark}/{dataset}@{version.revision}", "label": None},
                "warning": None, "started_at": _iso(now)}

    def stop_run(self, run_id: str, *, force: bool = False) -> str:
        with self._lock:
            run, now = self._get(run_id), self.clock()
            for task in run.tasks:
                if self._status(task, now) in ("PENDING", "BUILDING", "IN_PROGRESS", "EVALUATING"):
                    task.stopped = True
            run.stop_requested, run.stopped_at = False, now
        return "stopping"

    def _reschedule(self, run: _Run, tasks: list[_Task], now: float, concurrency: int | None) -> None:
        width = max(1, concurrency or run.concurrency)
        for i, task in enumerate(tasks):
            task.start_at = now + (i // width) * (BUILD_S + RUN_S + EVAL_S)
            task.stopped, task.error, task.category = False, "", ""

    def resume_run(self, run_id: str, *, concurrency: int | None = None) -> str:
        with self._lock:
            run, now = self._get(run_id), self.clock()
            self._reschedule(run, [t for t in run.tasks if t.stopped], now, concurrency)
        return "resumed"

    def retry_run(self, run_id: str, *, concurrency: int | None = None) -> str:
        with self._lock:
            run, now = self._get(run_id), self.clock()
            self._reschedule(run, [t for t in run.tasks if self._status(t, now) == "ERROR"], now, concurrency)
        return "retrying"

    def set_concurrency(self, run_id: str, concurrency: int) -> int:
        with self._lock:
            self._get(run_id).concurrency = concurrency
        return concurrency

    # ------------------------------------------------------------------ ValkyrieAPI: datasets
    def datasets(self, benchmark: str) -> list[dict]:
        out = []
        for name, versions in sorted(self._versions.items()):
            out.append({"name": name, "description": "", "created_by_email": versions[0].created_by,
                        "created_at": _iso(versions[0].created_at), "updated_at": _iso(versions[-1].created_at),
                        "archived_at": None, "benchmark": self.benchmark})
        return out

    def _version_row(self, dataset: str, v: _Version) -> dict:
        return {"benchmark": self.benchmark, "dataset": dataset, "revision": v.revision, "digest": f"sha256:{_crc(dataset, str(v.revision)):064x}",
                "task_count": len(v.digests), "tags": list(v.tags), "created_by_email": v.created_by, "created_at": _iso(v.created_at)}

    def dataset_versions(self, benchmark: str, dataset: str) -> list[dict]:
        if dataset not in self._versions:
            raise ValkyrieError(f"Not found on Valkyrie: dataset {dataset} not found", "not_found")
        return [self._version_row(dataset, v) for v in reversed(self._versions[dataset])]

    def dataset_tasks(self, benchmark: str, dataset: str, ref: str = "latest") -> list[dict]:
        version = self._resolve(dataset, ref)
        return [{"task_id": t, "digest": d, "size": 1024, "source_name": None} for t, d in sorted(version.digests.items())]

    def push_dataset(self, benchmark: str, dataset: str, folder: Path | str, tags: Sequence[str] = ()) -> dict:
        from valkyrie.sdk.task_content import task_digest

        from .benchmarks import find_task_folders

        folders = find_task_folders(Path(folder))
        if not folders:
            raise ValkyrieError("Valkyrie rejected the request: no task folders found", "rejected")
        digests = {task_id: task_digest(path) for task_id, path in folders.items()}
        with self._lock:
            versions = self._versions.setdefault(dataset, [])
            created = [] if versions else [f"{benchmark}/{dataset}"]
            latest = versions[-1] if versions else None
            stored = sorted(t for t, d in digests.items() if not latest or latest.digests.get(t) != d)
            if latest and latest.digests == digests:
                version = latest  # unchanged folder: Valkyrie returns the version it already made
            else:
                version = _Version((latest.revision + 1) if latest else 1, digests, ["latest"], self.clock(), self.user)
                for older in versions:
                    older.tags = [t for t in older.tags if t != "latest"]
                versions.append(version)
            for tag in tags:
                for other in versions:
                    other.tags = [t for t in other.tags if t != tag]
                version.tags.append(tag)
        row = self._version_row(dataset, version)
        return {"version": {**row, "metric_digest": None, "manifest": None}, "stored": stored if version is not latest else [],
                "created": created, "warnings": [], "left_out": {}}

    # ------------------------------------------------------------------ ValkyrieAPI: artifacts
    def download_artifact(self, run_id: str, path: str, dest: Path | str) -> Path:
        run, now = self._get(run_id), self.clock()
        task_id, _, name = path.partition("/")
        task = next((t for t in run.tasks if t.id == task_id), None)
        if task is None or name != "agent_output.tar.gz" or self._status(task, now) != "FINISHED":
            raise ValkyrieError("FileNotFoundError: No artifacts found at the requested path", "other")
        target = Path(dest) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        summary = {"metadata": {"task_id": task.id, "model": run.model, "agent": run.agent, "success": task.reward >= 1},
                   "task_prompt": f"(fake prompt for {task.id})",
                   "metrics": {"cost": task.cost, "wall_clock_duration": RUN_S, "input_tokens": 3 + _crc(task.id) % 20,
                               "output_tokens": 100 + _crc(task.id, "o") % 400, "cache_read_input_tokens": 20_000 + _crc(task.id, "c") % 30_000}}
        final = f"Worked through {task.id}; answer written." if task.reward >= 1 else f"Could not solve {task.id}."
        trajectory = [
            {"type": "system", "subtype": "init", "cwd": "/app", "model": run.model.rpartition("/")[2], "tools": ["Bash", "Write", "Read"]},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": f"Plan for {task.id}."}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "I will write the answer file."}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_1", "name": "Write",
                                                                             "input": {"file_path": "/app/answer.json", "content": "{}"}}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1",
                                                                      "content": "File created successfully at: /app/answer.json"}]}},
            {"type": "result", "subtype": "success", "result": final, "total_cost_usd": task.cost},
        ]
        files = {"logs/summary.json": json.dumps(summary), "logs/final_message.txt": final,
                 "logs/trajectory.jsonl": "\n".join(json.dumps(e) for e in trajectory)}
        with tarfile.open(target, "w:gz") as tar:
            for member, text in files.items():
                data = text.encode()
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return Path(dest)
