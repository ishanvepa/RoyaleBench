"""Verify merged tasks using each task's own packaged runtime image.

    uv run python -m cr_arena.validate_v6_docker --jobs 4
    uv run python -m cr_arena.validate_v6_docker --benchmark benchmarks/royalebench-v8 --jobs 4
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path

from valkyrie.sdk.task_content import task_digest

from .build_v6 import OUT, EVIDENCE, write_json
from .validate_v1_docker import docker, mount, validate


def environment_digest(task):
    """Separate images whenever any installed runtime or bootstrap file differs."""
    root = task / "environment"
    files = [(p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted(root.rglob("*")) if p.is_file() and p.name != "task.json"]
    return hashlib.sha256(json.dumps(files).encode()).hexdigest()


def validate_task(item, *, benchmark=OUT, evidence=EVIDENCE):
    member, image = item
    task = benchmark / member["task"]
    if task_digest(task) != member["digest"]:
        raise ValueError(f"task changed before verification: {task.name}")
    result = validate(task, image, evidence / "docker")
    negative = {}
    for name, payload in (("empty", ""), ("malformed", "not json\n"), ("wrong-type", "[]\n")):
        dest = (evidence / "docker" / task.name / "controls" / name).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        log = dest / "input.jsonl"
        log.write_text(payload, encoding="utf-8", newline="\n")
        docker("run", "--rm", "--network", "none",
               "--mount", mount(task / "environment/task.json", "/opt/referee/task.json"),
               "--mount", mount(task / "tests", "/tests"),
               "--mount", mount(log, "/var/lib/royale/actions.jsonl"),
               "--mount", mount(dest, "/logs/verifier", readonly=False),
               image, "bash", "/tests/test.sh")
        report = json.loads((dest / "match_report.json").read_text())
        negative[name] = report["rewards"]["reward"]
    if any(negative.values()):
        raise ValueError(f"negative control received credit: {task.name}: {negative}")
    if task_digest(task) != member["digest"]:
        raise ValueError(f"task changed during verification: {task.name}")
    result.update(source=member["source"], task_digest=member["digest"],
                  negative_rewards=negative)
    label = benchmark.name.removeprefix("royalebench-")
    write_json(evidence / "docker" / task.name / f"{label}_validation.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--benchmark", type=Path, default=OUT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--resume", action="store_true", help="reuse complete checks for unchanged packages and images")
    args = parser.parse_args()
    benchmark = args.benchmark
    evidence = args.out or Path("runs") / benchmark.name
    manifest = json.loads((benchmark / "manifest.json").read_text())
    groups = defaultdict(list)
    for member in manifest["tasks"]:
        groups[environment_digest(benchmark / member["task"])].append(member)
    work, images, results = [], [], []
    for signature, members in groups.items():
        image = f"{benchmark.name}:validation-{signature[:12]}"
        print(f"Building source runtime image for {len(members)} tasks: {image}", flush=True)
        docker("build", "--platform", "linux/amd64", "-t", image,
               benchmark / members[0]["task"] / "environment")
        image_digest = docker("image", "inspect", image, "--format", "{{.Id}}").strip()
        images.append(dict(environment_sha256=signature, image=image, image_digest=image_digest))
        for member in members:
            previous = evidence / "docker" / member["task"] / f"{benchmark.name.removeprefix('royalebench-')}_validation.json"
            row = json.loads(previous.read_text()) if args.resume and previous.exists() else {}
            if (row.get("task_digest") == member["digest"] == task_digest(benchmark / member["task"])
                    and row.get("image") == image_digest and row.get("source") == member["source"]
                    and row.get("reward") == row.get("integrity") == 1
                    and all(row.get(k) is True for k in ("isolated", "restart_verified", "capture_complete", "replay_hashes_verified"))
                    and row.get("negative_rewards") == {"empty": 0, "malformed": 0, "wrong-type": 0}
                    and all((previous.parent / p).is_file() for p in ("replay.msgpack", "actions.jsonl", "carried/capture/manifest.json"))):
                results.append(row)
                print(f"Reusing passing checks: {member['task']}", flush=True)
            else:
                work.append((member, image))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results.extend(pool.map(partial(validate_task, benchmark=benchmark, evidence=evidence), work))
    order = {r["task"]: i for i, r in enumerate(manifest["tasks"])}
    results.sort(key=lambda r: order[r["task"]])
    write_json(evidence / "docker/validation.json", dict(task_count=len(results),
               images=images, tasks=results, source_packages_unchanged=True,
               all_negative_controls_zero=True))


if __name__ == "__main__":
    main()
