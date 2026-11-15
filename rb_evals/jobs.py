"""Jobs: what the New job form submits, and how Valkyrie runs are presented as jobs.

One job is one Valkyrie run (one agent harness, one model, one benchmark selection). Valkyrie is the source
of truth: a job's name is the run's label and its id is the run id, so jobs started here or from a terminal
look the same.
"""

from __future__ import annotations

import re
import shlex
import time
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import EvalsConfig

ACTIVE_STATUSES = frozenset({"IN_PROGRESS", "STOPPING"})
RUN_PILL = {"IN_PROGRESS": "🔄 running", "STOPPING": "⏸ stopping", "STOPPED": "⏸ stopped",
            "FINISHED": "✅ finished", "ERROR": "❌ failed"}
TASK_ORDER = ["PENDING", "BUILDING", "IN_PROGRESS", "EVALUATING", "FINISHED", "ERROR", "STOPPED"]  # lifecycle order
# The order a monitor lists tasks in: what is happening now, then what went wrong, then the queue, then what is done.
TASK_SORT = ["IN_PROGRESS", "EVALUATING", "BUILDING", "ERROR", "STOPPED", "PENDING", "FINISHED"]
TASK_PILL = {"PENDING": "⏳ pending", "BUILDING": "🔨 building", "IN_PROGRESS": "🔄 running",
             "EVALUATING": "🧪 grading", "FINISHED": "✅ finished", "ERROR": "❌ error", "STOPPED": "⏸ stopped"}
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


@dataclass
class JobSpec:
    dataset: str  # dataset folder name, e.g. "smoke"
    revision: str  # published revision number or tag; resolve "latest" to a number for reproducible jobs
    agent: str
    model: str
    secret_name: str  # name of a Valkyrie secret holding the model provider's API key
    secret_env: str  # environment variable the harness reads that key from
    concurrency: int
    label: str
    task_ids: list[str] | None = None  # None = every task in the revision
    benchmark: str = "royalebench"
    provider: str = "modal"
    extra: dict = field(default_factory=dict)

    def validate(self, cfg: EvalsConfig, known_tasks: Collection[str] | None = None) -> None:
        """Raise ValueError with a message for the form when the job cannot be started."""
        if self.provider != "modal":
            raise ValueError("Jobs always run their sandboxes on Modal.")
        if not NAME_RE.fullmatch(self.dataset or ""):
            raise ValueError("Choose a benchmark.")
        if not (self.revision or "").strip():
            raise ValueError("Choose a published revision.")
        if not (self.agent or "").strip():
            raise ValueError("Choose a harness (agent).")
        model = (self.model or "").strip()
        if "/" not in model or model.startswith("/") or model.endswith("/"):
            raise ValueError("Model must be a Valkyrie model key such as anthropic/claude-sonnet-4-6.")
        if not (self.secret_name or "").strip() or not (self.secret_env or "").strip():
            raise ValueError("Choose the Valkyrie secret that holds the model API key.")
        if not 1 <= int(self.concurrency) <= cfg.max_concurrency:
            raise ValueError(f"Concurrency must be between 1 and {cfg.max_concurrency}.")
        if not (self.label or "").strip():
            raise ValueError("Give the job a name.")
        if self.task_ids is not None:
            if not self.task_ids:
                raise ValueError("Select at least one task, or run the whole benchmark.")
            if len(set(self.task_ids)) != len(self.task_ids):
                raise ValueError("Task selection contains duplicates.")
            unknown = sorted(set(self.task_ids) - set(known_tasks)) if known_tasks is not None else []
            if unknown:
                raise ValueError(f"Not in this revision: {', '.join(unknown)}")

    def task_count(self, known_tasks: Collection[str]) -> int:
        return len(self.task_ids) if self.task_ids is not None else len(known_tasks)

    def needs_confirmation(self, cfg: EvalsConfig, known_tasks: Collection[str]) -> bool:
        return self.task_count(known_tasks) > cfg.confirm_over_tasks

    def start_kwargs(self) -> dict:
        """Keyword arguments for ``Valkyrie.start_run``."""
        return {"benchmark": self.benchmark, "dataset": self.dataset, "ref": str(self.revision), "agent": self.agent,
                "model": self.model.strip(), "concurrency": int(self.concurrency),
                "task_ids": list(self.task_ids) if self.task_ids else None, "label": self.label.strip(),
                "provider": self.provider, "secrets": {self.secret_env: self.secret_name}}

    def cli_command(self) -> str:
        """The equivalent terminal command (secret *names* only), for reproducing or documenting the run."""
        parts = ["valkyrie", "run", "start", "--agent", self.agent,
                 "--dataset", f"{self.benchmark}/{self.dataset}@{self.revision}", "--model", self.model.strip(),
                 "--provider", self.provider, "-s", self.secret_env, self.secret_name,
                 "--concurrency", str(self.concurrency)]
        if self.task_ids:
            parts += ["--task-ids", ",".join(self.task_ids)]
        parts += ["--label", self.label.strip()]
        return " ".join(shlex.quote(p) for p in parts)


def default_label(dataset: str, model: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    short = re.sub(r"[^A-Za-z0-9._-]+", "-", model.rpartition("/")[2]).strip("-") or "model"
    return f"{dataset}-{short}-{stamp}"


def default_secret(secrets: Collection[str], provider_prefix: str, preferred: str | None = None) -> str | None:
    """Pick a stored secret for a provider: the one named by $VALKYRIE_ANTHROPIC_SECRET-style preference,
    else the only/first one whose name mentions the provider."""
    if preferred and preferred in secrets:
        return preferred
    matches = sorted(s for s in secrets if provider_prefix.lower() in s.lower())
    return matches[0] if matches else None


# ---------------------------------------------------------------------- presenting runs
def parse_ts(value) -> datetime | None:
    """Valkyrie timestamps are ISO strings, sometimes without an offset (those are UTC)."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def duration_s(run: dict, now: float | None = None) -> float | None:
    started = parse_ts(run.get("started_at"))
    if started is None:
        return None
    finished = parse_ts(run.get("finished_at"))
    end = finished.timestamp() if finished else (now if now is not None else time.time())
    return max(0.0, end - started.timestamp())


def eta_seconds(run: dict, now: float | None = None) -> float | None:
    """Time left, from the pace so far; only meaningful while the run is active."""
    if run.get("status") not in ACTIVE_STATUSES:
        return None
    done, total = int(run.get("finished_tasks") or 0), int(run.get("total_tasks") or 0)
    elapsed = duration_s(run, now)
    if not done or not total or elapsed is None or done >= total:
        return None
    return elapsed / done * (total - done)


def job_row(run: dict, now: float | None = None) -> dict:
    """One flat record per run for tables."""
    total, done = int(run.get("total_tasks") or 0), int(run.get("finished_tasks") or 0)
    status = str(run.get("status") or "")
    return {
        "id": str(run["id"]),
        "job": run.get("label") or "(no label)",
        "status": status,
        "state": RUN_PILL.get(status, status),
        "benchmark": f"{run.get('name', '')}/{run.get('dataset', '')}",
        "dataset": run.get("dataset") or "",
        "model": run.get("model") or "",
        "harness": run.get("agent_name") or "",
        "done": done,
        "total": total,
        "progress": (done / total) if total else 0.0,
        "score": run.get("final_score"),
        "started_by": run.get("started_by_email") or "",
        "started_at": parse_ts(run.get("started_at")),
        "duration_s": duration_s(run, now),
        "error": run.get("error_message") or "",
        "task_state_counts": dict(run.get("task_state_counts") or {}),
    }


def task_rows(tasks: list[dict], now: float | None = None) -> list[dict]:
    """Flat per-task records from ``Valkyrie.run_tasks``."""
    rows = []
    for t in tasks:
        started, finished = parse_ts(t.get("started_at")), parse_ts(t.get("finished_at"))
        end = finished.timestamp() if finished else (now if now is not None else time.time())
        rows.append({
            "task": t["task_id"], "status": t.get("status", ""), "state": TASK_PILL.get(t.get("status", ""), t.get("status", "")),
            "category": t.get("failure_category") or "", "error": t.get("error_message") or "",
            "duration_s": (end - started.timestamp()) if started else None,
            "started_at": started, "finished_at": finished,
        })
    order = {s: i for i, s in enumerate(TASK_SORT)}
    return sorted(rows, key=lambda r: (order.get(r["status"], 99), r["task"]))
