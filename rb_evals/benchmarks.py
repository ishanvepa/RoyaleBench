"""Benchmarks we are drafting: Harbor task folders under benchmarks/<name>/, matched with Valkyrie datasets.

A folder ``benchmarks/<name>/`` is published as the Valkyrie dataset ``<org benchmark>/<name>``. Task
folders are found the way ``valkyrie dataset push`` finds them: any folder holding ``task.toml``, the folder
name being the task id. An optional ``benchmark.toml`` carries display metadata. Never add a
``dataset.toml`` there: Valkyrie treats that file as a digest lock that freezes the task list.
"""

from __future__ import annotations

import os
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import EvalsConfig
    from .protocol import ValkyrieAPI as Valkyrie

IGNORED_NAMES = frozenset({".git", ".DS_Store", "__pycache__"})
MAX_FILE_BYTES = 200_000
KINDS = ("eval", "smoke")


def _read_toml(path: Path) -> tuple[dict, str]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, f"{path.name}: {exc}"


@dataclass
class LocalTask:
    id: str
    path: Path
    config: dict = field(default_factory=dict)
    config_error: str = ""

    def _get(self, section: str, key: str, default=None):
        value = self.config.get(section, {})
        return value.get(key, default) if isinstance(value, dict) else default

    @property
    def name(self) -> str:
        return str(self._get("task", "name", "") or "")

    @property
    def description(self) -> str:
        return str(self._get("task", "description", "") or "")

    @property
    def category(self) -> str:
        return str(self._get("metadata", "category", "") or "")

    @property
    def difficulty(self) -> str:
        return str(self._get("metadata", "difficulty", "") or "")

    @property
    def agent_timeout_s(self) -> float | None:
        return self._get("agent", "timeout_sec")

    @property
    def verifier_timeout_s(self) -> float | None:
        return self._get("verifier", "timeout_sec")

    @property
    def resources(self) -> dict:
        env = self.config.get("environment", {})
        return {k: env[k] for k in ("cpus", "memory_mb", "storage_mb", "build_timeout_sec") if isinstance(env, dict) and k in env}

    def read(self, rel: str) -> str | None:
        """Text of a file inside the task folder, or None when it is missing or not text."""
        path = self.path / rel
        try:
            if not path.is_file():
                return None
            data = path.read_bytes()[: MAX_FILE_BYTES + 1]
        except OSError:
            return None
        text = data.decode("utf-8", errors="replace")
        return text[:MAX_FILE_BYTES] + "\n... (truncated)" if len(data) > MAX_FILE_BYTES else text

    @property
    def instruction(self) -> str:
        return self.read("instruction.md") or ""

    def files(self) -> list[tuple[str, int]]:
        out = []
        for directory, subdirs, names in os.walk(self.path):
            subdirs[:] = sorted(d for d in subdirs if d not in IGNORED_NAMES)
            for name in sorted(names):
                if name not in IGNORED_NAMES:
                    full = Path(directory) / name
                    out.append((full.relative_to(self.path).as_posix(), full.stat().st_size))
        return out


@dataclass
class LocalBenchmark:
    name: str
    path: Path
    title: str = ""
    description: str = ""
    kind: str = "eval"
    tasks: dict[str, LocalTask] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.title or self.name


def task_problems(task: LocalTask) -> list[str]:
    """Things that make a task ungradable or break it in a Linux sandbox. Advisory: the UI shows them before publishing."""
    problems = []
    if task.config_error:
        problems.append(f"task.toml is unreadable ({task.config_error})")
    if not task.instruction.strip():
        problems.append("instruction.md is missing or empty")
    tests = task.read("tests/test.sh")
    if tests is None:
        problems.append("tests/test.sh is missing, so nothing grades this task")
    elif "reward" not in tests:
        problems.append("tests/test.sh never writes /logs/verifier/reward.txt (or reward.json)")
    for rel in ("tests/test.sh", "solution/solve.sh", "environment/Dockerfile"):
        text = task.read(rel)
        if text and "\r\n" in text:
            problems.append(f"{rel} has Windows (CRLF) line endings; Linux sandboxes need LF")
    if not task.agent_timeout_s:
        problems.append("task.toml has no [agent] timeout_sec")
    return problems


def find_task_folders(root: Path) -> dict[str, Path]:
    """Task folders under ``root`` at any depth; nothing inside a task counts as another task."""
    folders: dict[str, Path] = {}
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in IGNORED_NAMES)
        path = Path(directory)
        if "task.toml" not in files or path == root:
            continue
        subdirs.clear()
        folders.setdefault(path.name, path)
    return dict(sorted(folders.items()))


def load_benchmark(path: Path) -> LocalBenchmark | None:
    folders = find_task_folders(path)
    if not folders:
        return None
    meta, error = _read_toml(path / "benchmark.toml") if (path / "benchmark.toml").is_file() else ({}, "")
    info = meta.get("benchmark", {}) if isinstance(meta.get("benchmark"), dict) else {}
    kind = info.get("kind", "eval")
    bench = LocalBenchmark(name=path.name, path=path, title=str(info.get("title", "")),
                           description=str(info.get("description", "")), kind=kind if kind in KINDS else "eval")
    if error:
        bench.errors.append(error)
    if kind not in KINDS:
        bench.errors.append(f"benchmark.toml: kind must be one of {', '.join(KINDS)}, got {kind!r}")
    for task_id, folder in folders.items():
        config, err = _read_toml(folder / "task.toml")
        bench.tasks[task_id] = LocalTask(task_id, folder, config, err)
        if err:
            bench.errors.append(f"{task_id}/{err}")
    return bench


def discover_local(benchmarks_dir: Path) -> dict[str, LocalBenchmark]:
    """Every benchmark folder that holds at least one task, by name."""
    out: dict[str, LocalBenchmark] = {}
    if not benchmarks_dir.is_dir():
        return out
    for child in sorted(benchmarks_dir.iterdir()):
        if child.is_dir() and not child.name.startswith((".", "_")) and child.name not in IGNORED_NAMES:
            bench = load_benchmark(child)
            if bench:
                out[bench.name] = bench
    return out


def local_digests(bench: LocalBenchmark) -> dict[str, str]:
    """Digest of every local task, computed exactly like ``dataset push`` does."""
    from valkyrie.sdk.task_content import task_digest

    return {task_id: task_digest(task.path) for task_id, task in bench.tasks.items()}


IN_SYNC, MODIFIED, NOT_PUBLISHED, PUBLISHED_ONLY = "in sync", "modified", "not published", "published only"


def sync_states(local: dict[str, str], published: dict[str, str]) -> dict[str, str]:
    """Per task: same digest, changed since publishing, never published, or only on Valkyrie."""
    states = {}
    for task_id in sorted(set(local) | set(published)):
        if task_id not in published:
            states[task_id] = NOT_PUBLISHED
        elif task_id not in local:
            states[task_id] = PUBLISHED_ONLY
        else:
            states[task_id] = IN_SYNC if local[task_id] == published[task_id] else MODIFIED
    return states


def benchmark_state(has_local: bool, versions: list[dict], states: dict[str, str]) -> str:
    """draft | published | modified (local differs from the latest published version) | remote only."""
    if not versions:
        return "draft"
    if not has_local:
        return "remote only"
    return "published" if all(s == IN_SYNC for s in states.values()) else "modified"


@dataclass
class BenchmarkInfo:
    name: str
    title: str
    description: str
    kind: str
    local: LocalBenchmark | None
    versions: list[dict] = field(default_factory=list)  # newest first
    task_states: dict[str, str] = field(default_factory=dict)
    state: str = "draft"

    @property
    def latest(self) -> dict | None:
        return self.versions[0] if self.versions else None

    @property
    def task_ids(self) -> list[str]:
        return sorted(self.local.tasks) if self.local else sorted(self.task_states)

    @property
    def tags(self) -> list[str]:
        return sorted({t for v in self.versions for t in v.get("tags", [])})


def collect_benchmarks(cfg: EvalsConfig, valkyrie: Valkyrie | None,
                       only: str | None = None) -> tuple[list[BenchmarkInfo], str | None]:
    """Local drafts merged with published datasets. Works offline: the second item is the Valkyrie error, if any.

    ``only`` restricts the (network-heavy) per-benchmark lookups to one benchmark name.
    """
    local = discover_local(cfg.benchmarks_dir)
    remote: dict[str, dict] = {}
    errors: list[str] = []
    if valkyrie is not None:
        try:
            remote = {d["name"]: d for d in valkyrie.datasets(cfg.benchmark) if not d.get("archived_at")}
        except Exception as exc:  # noqa: BLE001 - offline / signed out: still list the drafts
            errors.append(str(exc))

    def build(name: str) -> BenchmarkInfo:
        bench = local.get(name)
        versions: list[dict] = []
        states: dict[str, str] = {}
        if name in remote and valkyrie is not None:
            try:
                versions = valkyrie.dataset_versions(cfg.benchmark, name)
                if versions:
                    published = {t["task_id"]: t["digest"] for t in valkyrie.dataset_tasks(cfg.benchmark, name, str(versions[0]["revision"]))}
                    states = sync_states(local_digests(bench) if bench else {}, published)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        elif bench:
            states = {t: NOT_PUBLISHED for t in bench.tasks}
        title = bench.display_title if bench else name
        description = (bench.description if bench and bench.description else remote.get(name, {}).get("description", ""))
        return BenchmarkInfo(name, title, description, bench.kind if bench else "eval", bench, versions, states,
                             benchmark_state(bench is not None, versions, states))

    names = sorted(set(local) | set(remote))
    if only is not None:
        names = [n for n in names if n == only]
    with ThreadPoolExecutor(max_workers=4) as pool:
        infos = list(pool.map(build, names))
    return infos, (errors[0] if errors else None)
