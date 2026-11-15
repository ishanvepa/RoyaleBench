"""Extend the immutable v8 release with three unchanged published Tactics tasks.

    uv run python -m cr_arena.build_v9
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from valkyrie.sdk import ValkyrieClient
from valkyrie.sdk.task_content import task_digest

from rb_evals.benchmarks import load_benchmark, task_problems
from .build_v6 import fetch, unpack, write_json
from .coordinate_benchmark import packaged_protocol_digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks/royalebench-v9"
EVIDENCE = ROOT / "runs/royalebench-v9"
CACHE = ROOT / "runs/recent/v9-sources"
BASE = ("royalebench-v8", 1, "sha256:e5807bda20b03468993ef75b0eeb4f881f7e70fe0a674be977888d5502f979b2", 18)
TACTICS = ("royalebench-tactics", 6, "sha256:5d9869332560e7ee325d975c6fca3340f75c69bb43f43a2f83f49775de424c37", 10)
ADDITIONS = {
    "05-hog-body-block": "sha256:d349207ed4074ba42409a7a4ca3a6e8d367dea3bd6d9ec470755f13224a559ed",
    "06-mini-pekka-kite": "sha256:9531bc33a497ef30fbe8f577d494db0d8471031eca300270e26f190a706169ee",
    "07-balloon-fireball": "sha256:9826da994607ef95f00a9f0c6f51a0af1bd0589cf3a221c78650591713659be6",
}
HOG_RUN = "f186e6ff-11df-4612-be6a-205298ba1b8a"


async def source_members():
    sources, members = await fetch((BASE,), CACHE)
    dataset, revision, expected, count = TACTICS
    async with ValkyrieClient() as client:
        version = await client.datasets.versions.get("royalebench", dataset, str(revision))
        if version.digest != expected or version.task_count != count or version.metric_digest is not None:
            raise ValueError("Pinned Tactics revision changed")
        published = await client.datasets.versions.tasks("royalebench", dataset, str(revision))
        selected = {r.task_id: r for r in published if r.task_id in ADDITIONS}
        if len(published) != count or set(selected) != set(ADDITIONS):
            raise ValueError("Incomplete Tactics source membership")
        # The supplied job used @5. Check its Hog package is identical to @6's.
        earlier = await client.datasets.versions.tasks("royalebench", dataset, "5")
        hog = next((r for r in earlier if r.task_id == "05-hog-body-block"), None)
        if hog is None or hog.digest != ADDITIONS["05-hog-body-block"]:
            raise ValueError("The requested Hog run's source package changed")
        source = f"royalebench/{dataset}@{revision}"
        sources.append(dict(dataset=source, digest=expected, task_count=count,
                            selected_tasks=list(ADDITIONS), selected_count=3))
        for name, digest in ADDITIONS.items():
            if selected[name].digest != digest:
                raise ValueError(f"Unexpected Tactics package: {name}")
            archive = CACHE / dataset / f"{name}.zip"
            if not archive.is_file():
                await client.datasets.versions.download("royalebench", dataset, name, archive, ref=str(revision))
            members.append(dict(task=name, source=source, digest=digest,
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                archive=archive.relative_to(ROOT).as_posix()))
    return sources, members


def build():
    sources, members = asyncio.run(source_members())
    if len(members) != 21 or len({r["task"] for r in members}) != 21:
        raise ValueError("v9 must contain the 18 v8 tasks plus exactly three distinct additions")
    with tempfile.TemporaryDirectory(prefix="v9-merge-", dir=CACHE) as temporary:
        staged, rows = Path(temporary), []
        for member in members:
            task = staged / member["task"]
            unpack(ROOT / member["archive"], task)
            if task_digest(task) != member["digest"]:
                raise ValueError(f"Source package mismatch: {task.name}")
            cfg = json.loads((task / "tests/task.json").read_text())
            if cfg != json.loads((task / "environment/task.json").read_text()):
                raise ValueError(f"Agent/verifier configuration mismatch: {task.name}")
            if cfg["id"] != task.name or cfg["action_mode"] != "coordinates-v1":
                raise ValueError(f"Task identity/protocol mismatch: {task.name}")
            rows.append({**member, "grading": cfg["scenario"]["grading"],
                "objective": cfg["objective"], "protocol_sha256": packaged_protocol_digest(task)})
        benchmark = load_benchmark(staged)
        problems = {n: task_problems(t) for n, t in benchmark.tasks.items() if task_problems(t)}
        if len(benchmark.tasks) != 21 or problems:
            raise ValueError(problems or "Incomplete staged dataset")
        if OUT.is_symlink() or {p.parent.name for p in OUT.glob("*/task.toml")} - {r["task"] for r in rows}:
            raise ValueError("Refusing to replace unexpected output")
        for row in rows:
            target = OUT / row["task"]
            if target.exists() and (target.is_symlink() or task_digest(target) != row["digest"]):
                raise ValueError(f"Refusing to overwrite changed task: {target.name}")
        OUT.mkdir(parents=True, exist_ok=True)
        for row in rows:
            target = OUT / row["task"]
            if not target.exists(): shutil.copytree(staged / row["task"], target)
            if task_digest(target) != row["digest"]: raise ValueError(target.name)
    manifest = dict(benchmark="RoyaleBench v9", version="9.0.0", sources=sources,
        runnable_tasks=[r["task"] for r in rows], tasks=rows, task_count=21,
        task_packages_unchanged=True, base_dataset="royalebench/royalebench-v8@1",
        requested_hog_run=dict(run_id=HOG_RUN, dataset="royalebench/royalebench-tactics@5",
                               task="05-hog-body-block", digest=ADDITIONS["05-hog-body-block"]),
        aggregation="Mean binary source-task reward across all 21 tasks; no source reweighting.",
        grading="Preserve all v8 objectives and add three Tactics defense objectives. This is objective success, not an all-task match-win rate.",
        validation="See runs/royalebench-v9/checks.json and resolution-check.json. Source model scores are not v9 run results.")
    write_json(OUT / "manifest.json", manifest)
    write_json(EVIDENCE / "merge.json", manifest)
    (OUT / "benchmark.toml").write_text(
        '[benchmark]\ntitle = "RoyaleBench v9"\nkind = "eval"\n'
        'description = "21 unchanged tasks: all 18 v8@1 tasks plus Hog body-block, Mini P.E.K.K.A. kite and Balloon Fireball defenses."\n')
    (OUT / "README.md").write_text(
        "# RoyaleBench v9\n\nAll 18 `royalebench-v8@1` tasks plus three unchanged `royalebench-tactics@6` defenses.\n"
        "The Hog package is identical to the linked Tactics @5 pilot. Source task IDs, instructions, resources, references and grading are preserved.\n"
        "Score: mean binary objective reward across all 21 tasks.\n"
        "See [the guide](../../docs/royalebench_v9.md) and `manifest.json` for provenance.\n"
        "Build: `uv run python -m cr_arena.build_v9`. Prepare Watch resolution: `uv run python -m cr_arena.validate_v9`.\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps(dict(tasks=result["task_count"], sources=result["sources"]), indent=2))
