"""Verify each unchanged v6 task using its own packaged runtime image.

    uv run python -m cr_arena.validate_v6_docker --jobs 4
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
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


def validate_task(item):
    member, image = item
    task = OUT / member["task"]
    if task_digest(task) != member["digest"]:
        raise ValueError(f"task changed before verification: {task.name}")
    result = validate(task, image, EVIDENCE / "docker")
    negative = {}
    for name, payload in (("empty", ""), ("malformed", "not json\n"), ("wrong-type", "[]\n")):
        dest = (EVIDENCE / "docker" / task.name / "controls" / name).resolve()
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
    write_json(EVIDENCE / "docker" / task.name / "v6_validation.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text())
    groups = defaultdict(list)
    for member in manifest["tasks"]:
        groups[environment_digest(OUT / member["task"])].append(member)
    work, images = [], []
    for signature, members in groups.items():
        image = f"royalebench-v6:validation-{signature[:12]}"
        print(f"Building source runtime image for {len(members)} tasks: {image}", flush=True)
        docker("build", "--platform", "linux/amd64", "-t", image,
               OUT / members[0]["task"] / "environment")
        images.append(dict(environment_sha256=signature, image=image,
                           image_digest=docker("image", "inspect", image, "--format", "{{.Id}}").strip()))
        work.extend((member, image) for member in members)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(validate_task, work))
    write_json(EVIDENCE / "docker/validation.json", dict(task_count=len(results),
               images=images, tasks=results, source_packages_unchanged=True,
               all_negative_controls_zero=True))


if __name__ == "__main__":
    main()
