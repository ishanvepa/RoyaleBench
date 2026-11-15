"""Merge the published v5@1 and win@2 task packages without changing their bytes.

    uv run python -m cr_arena.build_v6
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import ZipFile

from valkyrie.sdk import ValkyrieClient
from valkyrie.sdk.task_content import task_digest

from rb_evals.benchmarks import load_benchmark, task_problems

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks/royalebench-v6"
EVIDENCE = ROOT / "runs/royalebench-v6"
CACHE = ROOT / "runs/recent/v6-sources"
SOURCES = (
    ("royalebench-v5", 1, "sha256:456914c198d4738959064c5e409944ac320fbe70b7404d6efb1304005a4d08cd", 10),
    ("royalebench-win", 2, "sha256:c1e42376f700f7cafdce9b34b359c32d81fc223eb7632cded5483937451a10a9", 4),
)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8", newline="\n")


def unpack(archive, target):
    with ZipFile(archive) as source:
        for item in source.infolist():
            relative = PurePosixPath(item.filename)
            if (relative.is_absolute() or ".." in relative.parts or "\\" in item.filename
                    or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError(f"unsafe archive member: {item.filename}")
        source.extractall(target)


async def fetch(sources_config=SOURCES, cache=CACHE):
    """Resolve immutable revisions; downloaded bytes must match service task digests."""
    sources, tasks, seen = [], [], set()
    limit = asyncio.Semaphore(4)
    async with ValkyrieClient() as client:
        for dataset, revision, expected, count in sources_config:
            version = await client.datasets.versions.get("royalebench", dataset, str(revision))
            if version.digest != expected or version.task_count != count or version.metric_digest is not None:
                raise ValueError(f"source revision or metric changed: {dataset}@{revision}")
            source = f"royalebench/{dataset}@{revision}"
            members = await client.datasets.versions.tasks("royalebench", dataset, str(revision))
            if len(members) != count:
                raise ValueError(f"incomplete source task list: {source}")
            sources.append(dict(dataset=source, digest=expected, task_count=count))

            async def download(member):
                async with limit:
                    archive = cache / dataset / f"{member.task_id}.zip"
                    if not archive.is_file():
                        await client.datasets.versions.download("royalebench", dataset, member.task_id,
                                                               archive, ref=str(revision))
                    return dict(task=member.task_id, source=source, digest=member.digest,
                                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                                archive=str(archive.relative_to(ROOT)).replace("\\", "/"))

            for member in members:
                if member.task_id in seen:
                    raise ValueError(f"duplicate task ID across sources: {member.task_id}")
                seen.add(member.task_id)
            tasks.extend(await asyncio.gather(*(download(member) for member in members)))
    return sources, tasks


def build():
    sources, members = asyncio.run(fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Validate everything in staging before adding any runnable output.
    with tempfile.TemporaryDirectory(prefix="v6-merge-", dir=CACHE) as temporary:
        staged = Path(temporary)
        rows = []
        for member in members:
            task = staged / member["task"]
            unpack(ROOT / member["archive"], task)
            if task_digest(task) != member["digest"]:
                raise ValueError(f"source content digest mismatch: {member['task']}")
            cfg = json.loads((task / "tests/task.json").read_text(encoding="utf-8"))
            if cfg != json.loads((task / "environment/task.json").read_text(encoding="utf-8")):
                raise ValueError(f"agent and verifier configurations differ: {task.name}")
            if cfg["id"] != task.name or cfg["action_mode"] != "coordinates-v1":
                raise ValueError(f"task identity or protocol mismatch: {task.name}")
            from .coordinate_benchmark import packaged_protocol_digest
            rows.append({**member, "grading": cfg["scenario"]["grading"],
                         "objective": cfg["objective"], "protocol_sha256": packaged_protocol_digest(task)})
        problems = {name: task_problems(task) for name, task in load_benchmark(staged).tasks.items()}
        if any(problems.values()):
            raise ValueError(problems)
        existing = {p.parent.name for p in OUT.glob("*/task.toml")}
        if existing - {r["task"] for r in rows}:
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
            assert task_digest(target) == row["digest"]
    manifest = dict(benchmark="RoyaleBench v6", version="6.0.0", sources=sources,
                    runnable_tasks=[r["task"] for r in rows], tasks=rows,
                    task_count=len(rows), task_packages_unchanged=True,
                    aggregation="Mean source-task binary reward across all 14 tasks; no source reweighting.",
                    grading="Preserve source objectives. The four win@2 tasks require terminal match wins; v5 includes defense and placement tasks.",
                    validation="See runs/royalebench-v6/checks.json; source scores are not v6 run results.")
    write_json(OUT / "manifest.json", manifest)
    write_json(EVIDENCE / "merge.json", manifest)
    (OUT / "benchmark.toml").write_text(
        '[benchmark]\ntitle = "RoyaleBench v6"\nkind = "eval"\n'
        'description = "14 unchanged tasks merged from v5@1 (10) and win@2 (4). Source objectives retained."\n',
        encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        "# RoyaleBench v6\n\n14 tasks: the exact union of `royalebench-v5@1` (10) and `royalebench-win@2` (4).\n"
        "Task IDs, files, instructions, runtime, references and grading are unchanged.\n"
        "The score is the mean binary source-task reward, so it is not an all-task match-win rate.\n"
        "See [the guide](../../docs/royalebench_v6.md) and `manifest.json` for provenance.\n"
        "Rebuild with `uv run python -m cr_arena.build_v6` (requires Valkyrie access).\n",
        encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps(dict(tasks=result["task_count"], sources=result["sources"], output=str(OUT)), indent=2))
