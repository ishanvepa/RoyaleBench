"""Results of finished runs: per-task rewards, agent-reported cost, an on-disk cache, and the leaderboard.

Valkyrie's final results JSON has rewards, durations and errors but no cost. Cost is only in each task's
agent output (``<task>/agent_output.tar.gz``, whose ``logs/summary.json`` the Claude Code harness fills in),
so it is downloaded once per task and cached. Cost is the model usage the harness reports; Modal sandbox
charges are not included. Only FINISHED runs are cached for good: failed or stopped runs can be retried.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean

from .jobs import parse_ts
from .valkyrie import Valkyrie, ValkyrieError

SOLVED_AT = 1.0  # a task counts as solved ("won") at full reward
# Failures that say nothing about the model: excluded from the score and counted separately.
NOT_THE_MODELS_FAULT = frozenset({"infrastructure", "benchmark_service", "cancelled", "unknown"})


# ---------------------------------------------------------------------- parsing a results JSON
def run_info(results: dict) -> dict:
    """Who ran what, from a results JSON's launch arguments."""
    args = results.get("benchmark_arguments") or {}
    contract = args.get("contract") or {}
    version = (args.get("dataset_version") or {}).get("id") or ""  # "royalebench/smoke@1"
    name, _, revision = version.partition("@")
    return {"agent": contract.get("name") or "", "model": contract.get("model") or "",
            "dataset": args.get("dataset") or name.partition("/")[2], "revision": revision,
            "dataset_version": version, "concurrency": args.get("concurrency"),
            "task_ids": args.get("task_ids"), "slice": args.get("slice_str")}


def reward_of(entry: dict) -> float | None:
    rewards = entry.get("rewards") or {}
    if isinstance(rewards.get("reward"), (int, float)):
        return float(rewards["reward"])
    numbers = [float(v) for v in rewards.values() if isinstance(v, (int, float))]
    return numbers[0] if numbers else None


def task_results(results: dict) -> list[dict]:
    """One row per task: reward (None when it never got graded), durations, error, failure category."""
    evaluated = results.get("evaluation_results") or {}
    errors = results.get("task_errors") or {}
    categories = results.get("task_failure_categories") or {}
    rows = []
    for task_id in sorted(set(evaluated) | set(errors)):
        entry = evaluated.get(task_id) or {}
        breakdown = entry.get("task_breakdown") or {}
        reward = reward_of(entry)
        category = categories.get(task_id)
        rows.append({
            "task": task_id, "reward": reward, "solved": reward is not None and reward >= SOLVED_AT,
            "agent_s": breakdown.get("agent_run_duration"), "sandbox_s": breakdown.get("sandbox_run_duration"),
            "error": errors.get(task_id) or "", "failure_category": category or "",
            "verifier_output": (entry.get("metadata") or {}).get("verifier_output", ""),
            # Counts toward the model's score: graded, or failed on the agent side (scores 0).
            "counted": reward is not None or (category or "unknown") not in NOT_THE_MODELS_FAULT,
        })
    return rows


# ---------------------------------------------------------------------- agent output / cost
def read_agent_metrics(root: Path) -> dict | None:
    """Cost and token usage from an extracted agent output folder (``summary.json`` or ``metrics_total.json``)."""
    for name in ("summary.json", "metrics_total.json"):
        for path in sorted(root.rglob(name)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            metrics = data.get("metrics") if isinstance(data, dict) and isinstance(data.get("metrics"), dict) else data
            if isinstance(metrics, dict) and isinstance(metrics.get("cost"), (int, float)):
                return {"cost": float(metrics["cost"]), "input_tokens": metrics.get("input_tokens"),
                        "output_tokens": metrics.get("output_tokens"),
                        "cache_read_tokens": metrics.get("cache_read_input_tokens"),
                        "cache_write_tokens": metrics.get("cache_creation_input_tokens"),
                        "wall_s": metrics.get("wall_clock_duration")}
    return None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n... ({len(text) - limit} more characters)"


def _as_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):  # tool results are often a list of {type: text, text: ...} blocks
        return "\n".join(_as_text(v.get("text", v) if isinstance(v, dict) else v) for v in value)
    return json.dumps(value, ensure_ascii=False, indent=2) if value is not None else ""


def normalize_trajectory(events: list[dict], *, max_steps: int = 300, max_text: int = 4000) -> list[dict]:
    """Turn an agent trajectory into a flat list of steps: {kind, title, text, time}.

    Understands the Claude Code stream format (system/assistant/user/result events whose message content is a
    list of thinking, text, tool_use and tool_result blocks); anything else becomes an ``other`` step with a
    JSON preview so no harness is ever dropped silently.
    """
    steps: list[dict] = []
    tool_names: dict[str, str] = {}  # tool_use id -> tool name, so a result can say which tool produced it

    def add(kind: str, title: str, text: str, when, tool: str | None = None) -> None:
        steps.append({"kind": kind, "title": title, "text": _clip(text, max_text), "time": when, "tool": tool})

    for event in events:
        if not isinstance(event, dict):
            add("other", "event", str(event), None)
            continue
        kind, when = event.get("type"), event.get("timestamp")
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        content = message.get("content")
        if kind == "system":
            tools = event.get("tools") or []
            add("system", "Session started", f"model {event.get('model', '?')} · cwd {event.get('cwd', '?')} · {len(tools)} tools", when)
        elif kind in ("assistant", "user") and isinstance(content, list):
            for block in content:
                btype = block.get("type") if isinstance(block, dict) else None
                if btype == "thinking":
                    add("thinking", "Thinking", block.get("thinking") or "(reasoning not recorded)", when)
                elif btype == "text":
                    add("text", "Assistant" if kind == "assistant" else "User", block.get("text", ""), when)
                elif btype == "tool_use":
                    inputs = block.get("input") or {}
                    detail = inputs.get("command") or inputs.get("file_path") or ""
                    body = json.dumps(inputs, ensure_ascii=False, indent=2) if not detail else (
                        f"{detail}\n\n{inputs['content']}" if "content" in inputs else str(detail))
                    name = str(block.get("name") or "?")
                    if block.get("id"):
                        tool_names[str(block["id"])] = name
                    add("tool_use", f"Tool: {name}", body, when, tool=name)
                elif btype == "tool_result":
                    name = tool_names.get(str(block.get("tool_use_id")))
                    add("tool_result", f"Tool result: {name}" if name else "Tool result", _as_text(block.get("content")), when, tool=name)
                else:
                    add("other", f"{kind} block", json.dumps(block, ensure_ascii=False)[:max_text], when)
        elif kind in ("assistant", "user") and isinstance(content, str):
            add("text", "Assistant" if kind == "assistant" else "User", content, when)
        elif kind == "result":
            add("result", f"Result ({event.get('subtype', 'done')})", _as_text(event.get("result")), when)
        else:
            add("other", str(kind or "event"), json.dumps(event, ensure_ascii=False)[:max_text], when)
        if len(steps) >= max_steps:
            break
    return steps


def read_trace(root: Path, max_steps: int = 300) -> dict:
    """What the agent said and did, from an extracted agent output folder."""

    def first(name: str) -> Path | None:
        return next(iter(sorted(root.rglob(name))), None)

    out: dict = {"final_message": "", "steps": [], "steps_total": 0, "metrics": read_agent_metrics(root)}
    final = first("final_message.txt")
    if final:
        out["final_message"] = final.read_text(encoding="utf-8", errors="replace")
    trajectory = first("trajectory.jsonl")
    if trajectory:
        events = []
        for line in trajectory.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    events.append({"type": "unparsed", "raw": line[:500]})
        out["steps_total"] = len(events)
        out["steps"] = normalize_trajectory(events, max_steps=max_steps)
    return out


class ResultsCache:
    """runs/evals/<run_id>/results.json and runs/evals/<run_id>/tasks/<task>/ (extracted agent output)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    @staticmethod
    def _safe(name: str) -> str:
        """One path segment: ids come from URLs and Valkyrie, so never let them climb out of the cache."""
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return "_" + cleaned if not cleaned.strip(".") else cleaned

    def _run(self, run_id: str) -> Path:
        return self.root / self._safe(run_id)

    def results(self, run_id: str) -> dict | None:
        path = self._run(run_id) / "results.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        except (OSError, ValueError):
            return None

    def save_results(self, run_id: str, results: dict) -> None:
        folder = self._run(run_id)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / "results.json.tmp"
        tmp.write_text(json.dumps(results), encoding="utf-8")
        os.replace(tmp, folder / "results.json")

    def task_dir(self, run_id: str, task_id: str) -> Path:
        return self._run(run_id) / "tasks" / self._safe(task_id)

    def replay_dir(self, run_id: str, task_id: str) -> Path:
        # Separate from agent output: trace/cost downloads replace the entire task_dir.
        return self._run(run_id) / "replays" / self._safe(task_id)

    def has_task(self, run_id: str, task_id: str) -> bool:
        return (self.task_dir(run_id, task_id) / ".done").exists()


def fetch_task_files(valkyrie: Valkyrie, cache: ResultsCache, run_id: str, task_id: str, *, final: bool) -> Path | None:
    """Download and extract a task's agent output; the folder, or None when the task has no output.

    ``final`` (the run is FINISHED) persists the result in the cache; otherwise it is refetched each time.
    Transient failures (network, auth) raise ``ValkyrieError`` so they are never remembered as "no output".
    """
    folder = cache.task_dir(run_id, task_id)
    if final and cache.has_task(run_id, task_id):
        return folder if any(p.name != ".done" for p in folder.iterdir()) else None
    with tempfile.TemporaryDirectory(prefix="rb_evals_") as tmp:
        try:
            downloaded = valkyrie.download_artifact(run_id, f"{task_id}/agent_output.tar.gz", Path(tmp) / "dl")
        except ValkyrieError as exc:
            if exc.kind in ("network", "auth"):
                raise
            return None  # the task produced no agent output (it errored before the agent ran)
        tarball = next(iter(Path(downloaded).rglob("agent_output.tar.gz")), None)
        if tarball is None:
            return None
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tarball) as tar:
            tar.extractall(folder, filter="data")
    if final:
        (folder / ".done").write_text("1")
    return folder


def task_metrics(valkyrie: Valkyrie, cache: ResultsCache, run_id: str, task_id: str, *, final: bool = True,
                 download: bool = True) -> dict | None:
    """Agent-reported cost and tokens for one task; None when unknown, or not downloaded and ``download`` is off."""
    folder = cache.task_dir(run_id, task_id)
    if not (final and cache.has_task(run_id, task_id)):
        if not download:
            return None
        if fetch_task_files(valkyrie, cache, run_id, task_id, final=final) is None:
            if final:  # remember there is nothing to read, so the leaderboard does not retry forever
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ".done").write_text("1")
            return None
    return read_agent_metrics(folder) if folder.exists() else None


# ---------------------------------------------------------------------- loading many runs
def load_records(valkyrie: Valkyrie, cache: ResultsCache, runs: Iterable[dict], *, fetch_costs: bool,
                 workers: int = 4, on_progress: Callable[[int, int], None] | None = None) -> list[dict]:
    """A record per FINISHED run: run-list fields + launch info + task rows (with cost when known)."""
    finished = [r for r in runs if r.get("status") == "FINISHED"]

    def load(run: dict) -> dict | None:
        run_id = str(run["id"])
        results = cache.results(run_id)
        if results is None:
            try:
                results = valkyrie.results(run_id)
            except ValkyrieError:
                return None
            cache.save_results(run_id, results)
        info = run_info(results)
        tasks = task_results(results)
        for t in tasks:
            t["cost"] = None
            t["tokens_out"] = None
        return {"run_id": run_id, "label": run.get("label") or "", "status": run.get("status"),
                "started_at": parse_ts(run.get("started_at")), "started_by": run.get("started_by_email") or "",
                "final_score": run.get("final_score"), "tasks": tasks, "revision": info["revision"],
                "concurrency": info["concurrency"],
                "agent": info["agent"] or run.get("agent_name") or "",
                "model": info["model"] or run.get("model") or "",
                "dataset": info["dataset"] or run.get("dataset") or ""}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = [r for r in pool.map(load, finished) if r]

    jobs = [(r, t) for r in records for t in r["tasks"]]

    def attach(item: tuple[dict, dict]) -> None:
        record, task = item
        try:
            metrics = task_metrics(valkyrie, cache, record["run_id"], task["task"], final=True, download=fetch_costs)
        except ValkyrieError:  # transient: leave the cost blank, try again on the next refresh
            return
        if metrics:
            task["cost"], task["tokens_out"] = metrics["cost"], metrics.get("output_tokens")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, _ in enumerate(pool.map(attach, jobs), 1):
            if on_progress:
                on_progress(n, len(jobs))
    return records


def uncached_task_count(cache: ResultsCache, runs: Iterable[dict]) -> int:
    """How many task outputs a cost refresh would still download for these (finished) runs."""
    total = 0
    for run in runs:
        if run.get("status") != "FINISHED":
            continue
        run_id = str(run["id"])
        results = cache.results(run_id)
        if results is None:  # results not cached yet: assume every task still needs its output
            total += int(run.get("total_tasks") or 0)
        else:
            total += sum(1 for t in task_results(results) if not cache.has_task(run_id, t["task"]))
    return total


# ---------------------------------------------------------------------- leaderboard
def leaderboard(records: Iterable[dict]) -> list[dict]:
    """Rows per (model, harness), pooled over the given finished-run records, best score first."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        groups.setdefault((record["model"], record["agent"]), []).append(record)
    rows = []
    for (model, agent), recs in groups.items():
        tasks = [t for r in recs for t in r["tasks"]]
        counted = [t for t in tasks if t["counted"]]
        graded = [t for t in counted if t["reward"] is not None]
        costs = [t["cost"] for t in counted if t["cost"] is not None]
        times = [t["agent_s"] for t in counted if t["agent_s"] is not None]
        solved = sum(1 for t in counted if t["solved"])
        rows.append({
            "model": model, "harness": agent, "runs": len(recs), "tasks_run": len(counted), "solved": solved,
            "pass_rate": solved / len(counted) if counted else None,
            "score": 100 * mean((t["reward"] or 0.0) for t in counted) if counted else None,
            "agent_failures": len(counted) - len(graded),
            "infra_errors": len(tasks) - len(counted),
            "avg_agent_s": mean(times) if times else None,
            "cost_usd": sum(costs) if costs else None,
            "cost_per_task": sum(costs) / len(costs) if costs else None,
            "cost_known": len(costs),
            "last_run": max((r["started_at"] for r in recs if r["started_at"]), default=None),
        })
    rows.sort(key=lambda r: (-(r["score"] if r["score"] is not None else -1), -r["solved"], r["model"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def task_history(records: Iterable[dict], dataset: str, task_id: str) -> list[dict]:
    """Every finished run's result for one task of a benchmark, newest run first."""
    rows = []
    for record in records:
        if record["dataset"] != dataset:
            continue
        for t in record["tasks"]:
            if t["task"] == task_id:
                rows.append({"run_id": record["run_id"], "job": record["label"], "model": record["model"],
                             "harness": record["agent"], "revision": record["revision"], "reward": t["reward"],
                             "solved": t["solved"], "agent_s": t["agent_s"], "cost": t["cost"], "error": t["error"],
                             "failure_category": t["failure_category"], "started_at": record["started_at"]})
    rows.sort(key=lambda r: r["started_at"].timestamp() if r["started_at"] else 0, reverse=True)
    return rows
