"""Prepare exact-package validated reference replays for every v9 resolution.

Reuse v8's passing Docker evidence only after checking package/config/protocol
identity, replaying every engine frame, and confirming the reference commands.
Missing or mismatched evidence is freshly validated in the task's own image.
The three additions receive fresh Docker references and invalid-input controls.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path
import shutil

from royalegym import RustEngine
from royalegym.replay import load_trace, verify_trace
from valkyrie.sdk.task_content import task_digest

from .build_v6 import write_json
from .build_v9 import ROOT, OUT, EVIDENCE
from .coordinate_benchmark import packaged_protocol_digest
from .scenario_task import setup_for
from .validate_v1_docker import docker
from .validate_v6_docker import environment_digest, validate_task


def inherited_reference(member, benchmark=OUT, source_root=ROOT / "runs/royalebench-v8"):
    task = benchmark / member["task"]
    manifest = json.loads((source_root / "docker/validation.json").read_text())
    row = next(r for r in manifest["tasks"] if r["task"] == task.name)
    cfg = json.loads((task / "tests/task.json").read_text())
    cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    protocol = packaged_protocol_digest(task)
    if not (task_digest(task) == member["digest"] == row.get("task_digest")
            and cfg_hash == row.get("config_sha256") and protocol == row.get("protocol_sha256")
            and row.get("reward") == row.get("integrity") == 1
            and all(row.get(k) is True for k in ("isolated", "restart_verified", "capture_complete", "replay_hashes_verified"))
            and row.get("negative_rewards") == {"empty": 0, "malformed": 0, "wrong-type": 0}):
        raise ValueError("Source validation does not match the exact v9 package")
    source = source_root / "docker" / task.name
    replay, actions = source / "replay.msgpack", source / "actions.jsonl"
    trace = load_trace(replay)
    if trace.header.setup != setup_for(cfg) or trace.header.seed != cfg["seed"] or trace.result is None:
        raise ValueError("Source replay does not match the task's starting state")
    # Bind the authenticated passing log to the protected reference shipped with the package.
    logged = [json.loads(l)["action"] for l in actions.read_text().splitlines() if l.strip()]
    expected = [json.loads(l)["action"] for l in (task / "solution/reference.jsonl").read_text().splitlines() if l.strip()]
    if logged != expected:
        raise ValueError("Source run did not execute this package's reference commands")
    errors = verify_trace(trace, RustEngine())
    if errors:
        raise ValueError(f"Source replay diverged: {errors[:2]}")
    return dict(row, source=member["source"], task_digest=member["digest"],
                inherited_validation=str((source / "v8_validation.json").relative_to(ROOT)),
                inheritance_checks=dict(package_digest=True, configuration=True, protocol=True,
                                        initial_setup=True, reference_commands=True, all_frame_hashes=True)), source


def export_resolution_manifests(rows, evidence=EVIDENCE):
    """Also export one manifest per runtime for dashboards predating mixed cohorts."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["protocol_sha256"]].append(row)
    for protocol, members in groups.items():
        folder = evidence / f"docker-runtime-{protocol[:12]}"
        for row in members:
            source = evidence / "docker" / row["task"] / "replay.msgpack"
            target = folder / row["task"] / "replay.msgpack"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        write_json(folder / "validation.json", dict(protocol_sha256=protocol, task_count=len(members), tasks=members))


def validate(jobs=3, reuse_v8=True):
    manifest = json.loads((OUT / "manifest.json").read_text())
    rows, pending, reused = [], [], []
    for member in manifest["tasks"]:
        if task_digest(OUT / member["task"]) != member["digest"]:
            raise ValueError(f"v9 package changed: {member['task']}")
        if reuse_v8 and member["source"] == "royalebench/royalebench-v8@1":
            try:
                row, source = inherited_reference(member)
            except (OSError, ValueError, KeyError, StopIteration) as exc:
                print(f"Fresh Docker validation needed: {member['task']}: {exc}", flush=True)
            else:
                target = EVIDENCE / "docker" / member["task"]
                target.mkdir(parents=True, exist_ok=True)
                for name in ("replay.msgpack", "actions.jsonl", "match_report.json"):
                    shutil.copyfile(source / name, target / name)
                row["replay_sha256"] = hashlib.sha256((target / "replay.msgpack").read_bytes()).hexdigest()
                write_json(target / "v9_validation.json", row)
                rows.append(row); reused.append(member["task"])
                print(f"Verified unchanged v8 reference: {member['task']}", flush=True)
                continue
        pending.append(member)
    groups = defaultdict(list)
    for member in pending:
        groups[environment_digest(OUT / member["task"])].append(member)
    work = []
    for signature, members in groups.items():
        image = f"royalebench-v9:validation-{signature[:12]}"
        print(f"Building runtime for {len(members)} fresh references: {image}", flush=True)
        docker("build", "--platform", "linux/amd64", "-t", image, OUT / members[0]["task"] / "environment")
        work.extend((member, image) for member in members)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows.extend(pool.map(partial(validate_task, benchmark=OUT, evidence=EVIDENCE), work))
    order = {r["task"]: i for i, r in enumerate(manifest["tasks"])}
    rows.sort(key=lambda r: order[r["task"]])
    if len(rows) != 21 or any(r["reward"] != 1 or r["integrity"] != 1 for r in rows):
        raise ValueError("Every v9 task must have a passing validated reference")
    for row in rows:
        row["replay_sha256"] = hashlib.sha256((EVIDENCE / "docker" / row["task"] / "replay.msgpack").read_bytes()).hexdigest()
    write_json(EVIDENCE / "docker/validation.json", dict(task_count=21, tasks=rows,
        source_packages_unchanged=True, all_negative_controls_zero=True,
        inherited_after_full_replay_verification=reused,
        fresh_docker_tasks=[r["task"] for r in pending]))
    export_resolution_manifests(rows)
    from rb_evals.resolutions import resolution_replay
    checks = []
    for row in rows:
        result = resolution_replay(OUT / row["task"], EVIDENCE)
        if not result.get("available") or 'aria-label="Timeline"' not in result["html"]:
            raise ValueError(f"Resolution unavailable: {row['task']}")
        checks.append(dict(task=row["task"], available=True, protocol_sha256=row["protocol_sha256"],
                           replay_sha256=row["replay_sha256"], html_bytes=len(result["html"].encode())))
    write_json(EVIDENCE / "resolution-check.json", dict(task_count=21, available=21, tasks=checks))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=3)
    parser.add_argument("--fresh", action="store_true", help="re-run all 21 protected Docker references")
    args = parser.parse_args()
    validate(jobs=args.jobs, reuse_v8=not args.fresh)
