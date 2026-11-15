"""Merge all published v6@1 and v7@1 tasks, preserving their exact packages.

    uv run python -m cr_arena.build_v8
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import tempfile

from valkyrie.sdk.task_content import task_digest

from rb_evals.benchmarks import load_benchmark, task_problems

from .build_v6 import fetch, unpack, write_json
from .coordinate_benchmark import packaged_protocol_digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks/royalebench-v8"
EVIDENCE = ROOT / "runs/royalebench-v8"
CACHE = ROOT / "runs/recent/v8-sources"
SOURCES = (
    ("royalebench-v6", 1, "sha256:813f00528a075f38acf4c8af9614da226de739e6a3d67e6e95be78b290e3fdf9", 14),
    ("royalebench-v7", 1, "sha256:8cc4ceee579bdb878039229758ca2aea57660509c5a5ccec439d44bf8f9fe3b3", 4),
)


def build():
    sources, members = asyncio.run(fetch(SOURCES, CACHE))
    CACHE.mkdir(parents=True, exist_ok=True)
    # Validate the complete source union before creating runnable output.
    with tempfile.TemporaryDirectory(prefix="v8-merge-", dir=CACHE) as temporary:
        staged = Path(temporary)
        rows = []
        for member in members:
            task = staged / member["task"]
            unpack(ROOT / member["archive"], task)
            if task_digest(task) != member["digest"]:
                raise ValueError(f"source content digest mismatch: {task.name}")
            cfg = json.loads((task / "tests/task.json").read_text(encoding="utf-8"))
            if cfg != json.loads((task / "environment/task.json").read_text(encoding="utf-8")):
                raise ValueError(f"agent and verifier configurations differ: {task.name}")
            if cfg["id"] != task.name or cfg["action_mode"] != "coordinates-v1":
                raise ValueError(f"task identity or protocol mismatch: {task.name}")
            rows.append({**member, "grading": cfg["scenario"]["grading"],
                         "objective": cfg["objective"], "protocol_sha256": packaged_protocol_digest(task)})
        benchmark = load_benchmark(staged)
        if len(benchmark.tasks) != 18:
            raise ValueError("expected exactly 18 source tasks")
        problems = {name: task_problems(task) for name, task in benchmark.tasks.items()}
        if any(problems.values()):
            raise ValueError(problems)
        expected = {r["task"] for r in rows}
        if {p.parent.name for p in OUT.glob("*/task.toml")} - expected:
            raise ValueError("output contains tasks outside the pinned source union")
        for row in rows:
            target = OUT / row["task"]
            if target.exists() and (target.is_symlink() or task_digest(target) != row["digest"]):
                raise ValueError(f"refusing to overwrite changed task: {target}")
        OUT.mkdir(parents=True, exist_ok=True)
        for row in rows:
            target = OUT / row["task"]
            if not target.exists():
                shutil.copytree(staged / row["task"], target)
            if task_digest(target) != row["digest"]:
                raise ValueError(f"copied task digest mismatch: {target.name}")
    manifest = dict(benchmark="RoyaleBench v8", version="8.0.0", sources=sources,
        runnable_tasks=[r["task"] for r in rows], tasks=rows, task_count=len(rows),
        task_packages_unchanged=True,
        aggregation="Mean source-task binary reward across all 18 tasks; no source reweighting.",
        grading="Preserve source objectives: 12 terminal-match-win tasks and six other v6 objectives. The four v7 tasks require a crown before their shorter windows end.",
        validation="See runs/royalebench-v8/checks.json. Source model scores are not new v8 run results.")
    write_json(OUT / "manifest.json", manifest)
    write_json(EVIDENCE / "merge.json", manifest)
    (OUT / "benchmark.toml").write_text(
        '[benchmark]\ntitle = "RoyaleBench v8"\nkind = "eval"\n'
        'description = "18 unchanged tasks: all 14 v6@1 tasks plus the four harder v7@1 continuations. Source grading retained."\n',
        encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        "# RoyaleBench v8\n\n18 tasks: the exact union of `royalebench-v6@1` (14) and `royalebench-v7@1` (4).\n"
        "Task IDs, instructions, runtime, references and grading retain their source bytes.\n"
        "Score: mean binary source-task reward; this is an objective success rate.\n"
        "See [the guide](../../docs/royalebench_v8.md) and `manifest.json` for provenance.\n"
        "Rebuild with `uv run python -m cr_arena.build_v8` (requires Valkyrie access).\n",
        encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps(dict(tasks=result["task_count"], sources=result["sources"], output=str(OUT)), indent=2))
