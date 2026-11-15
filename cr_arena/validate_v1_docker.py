"""Run protected v1 references through cr, restart, and fresh-container verification.

    python -m cr_arena.validate_v1_docker [--tasks 1 5]

No cloud resources or model keys are used. The common runtime image is built once;
each task supplies only its own private config, protected solution, and verifier.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from royalegym import RustEngine
from royalegym.replay import load_trace, verify_trace

from .royalebench_v1 import protocol_digest


def protocol_for(cfg, task=None):
    if cfg.get("action_mode") == "coordinates-v1":
        from .coordinate_benchmark import packaged_protocol_digest, protocol_digest as coordinate_digest
        return packaged_protocol_digest(task) if task is not None else coordinate_digest()
    return protocol_digest()


def docker(*args):
    p = subprocess.run(["docker", *map(str, args)], text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"docker {' '.join(map(str, args[:3]))}: {p.stdout}\n{p.stderr}")
    return p.stdout


def mount(source, target, readonly=True):
    return f"type=bind,source={Path(source).resolve()},target={target}" + (",readonly" if readonly else "")


def validate(task, image, out):
    started = time.perf_counter()
    cfg = json.loads((task / "tests/task.json").read_text())
    name = f"{task.parent.name}-{task.name}"
    dest = (out / task.name).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    # docker cp nests into an existing directory; replace only this generated export.
    shutil.rmtree(dest / "carried", ignore_errors=True)
    private_cfg = mount(task / "environment/task.json", "/opt/referee/task.json")
    docker("run", "-d", "--name", name, "--network", "none", "--mount", private_cfg,
           "--mount", mount(task / "solution", "/solution"), image, "sleep", "infinity")
    try:
        # The oracle mount is supplied only for validation, never to a model run.
        docker("exec", "-u", "player", name, "bash", "-c",
               "test ! -r /opt/referee/task.json && test ! -x /opt/referee/venv/bin/python && "
               "! sudo -n -u root true 2>/dev/null")
        text = docker("exec", "-u", "player", name, "bash", "/solution/solve.sh")
        if "GAME OVER: scenario SUCCESS" not in text:
            raise RuntimeError(text)
        docker("exec", "-u", "player", name, "bash", "-c",
               "test ! -r /var/lib/royale/actions.jsonl && "
               "test ! -r /var/lib/royale/capture/observations.jsonl && "
               "test ! -r /var/lib/royale/replay.msgpack")
        docker("cp", f"{name}:/var/lib/royale/replay.msgpack", dest / "before_restart.msgpack")
        # A restart must retain the completed scenario and replay its authenticated log.
        docker("exec", name, "pkill", "-u", "referee", "-f", "cr_arena.royale_task")
        resumed = docker("exec", "-u", "player", name, "cr")
        if "GAME OVER: scenario SUCCESS" not in resumed:
            raise RuntimeError("restart lost the scenario: " + resumed)
        docker("cp", f"{name}:/var/lib/royale/actions.jsonl", dest / "actions.jsonl")
        docker("cp", f"{name}:/var/lib/royale", dest / "carried")
    finally:
        docker("rm", "-f", name)
    output = docker("run", "--rm", "--network", "none", "--mount", private_cfg,
                    "--mount", mount(task / "tests", "/tests"),
                    "--mount", mount(dest / "actions.jsonl", "/var/lib/royale/actions.jsonl"),
                    "--mount", mount(dest, "/logs/verifier", readonly=False),
                    image, "bash", "/tests/test.sh")
    report = json.loads((dest / "match_report.json").read_text())
    if report["rewards"]["reward"] != 1 or report["rewards"]["integrity"] != 1:
        raise RuntimeError(json.dumps(report))
    before = load_trace(dest / "before_restart.msgpack")
    carried = load_trace(dest / "carried/replay.msgpack")
    verified = load_trace(dest / "replay.msgpack")
    hashes = lambda trace: [(f.tick, f.state_hash) for f in trace.frames]
    if hashes(before) != hashes(carried) or hashes(carried) != hashes(verified):
        raise RuntimeError("carried, restarted and independently verified frames differ")
    for trace in (carried, verified):
        problems = verify_trace(trace, RustEngine())
        if problems:
            raise RuntimeError(str(problems[:3]))
    capture = json.loads((dest / "carried/capture/manifest.json").read_text())
    if capture["capture_errors"] or capture["status"] != "completed":
        raise RuntimeError("incomplete carried capture: " + json.dumps(capture))
    for table in ("observations", "commands", "states", "events", "matches"):
        if not (dest / f"carried/capture/{table}.jsonl").stat().st_size:
            raise RuntimeError(f"empty carried {table}")
    result = dict(task=task.name, family=cfg["family"], reward=1, integrity=1,
                  protocol_sha256=protocol_for(cfg, task),
                  config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                  image=docker("image", "inspect", image, "--format", "{{.Id}}").strip(),
                  isolated=True, restart_verified=True, capture_complete=True,
                  trace_frames=len(carried.frames), replay_hashes_verified=True,
                  capture_schema_version=capture["schema_version"],
                  network="none", elapsed_s=round(time.perf_counter()-started, 3))
    (dest / "docker_validation.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)
    return result


def main(default_benchmark=Path("benchmarks/royalebench-v1")):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", type=int, nargs="*")
    ap.add_argument("--benchmark", type=Path, default=default_benchmark)
    ap.add_argument("--jobs", type=int, choices=range(1, 5), default=1,
                    help="independent validation containers (default: sequential)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    manifest = json.loads((args.benchmark / "manifest.json").read_text())
    first_cfg = json.loads((args.benchmark / manifest["runnable_tasks"][0] / "tests/task.json").read_text())
    first_task = args.benchmark / manifest["runnable_tasks"][0]
    current_protocol = protocol_for(first_cfg, first_task)
    args.out = args.out or Path("runs") / args.benchmark.name / "docker"
    if manifest["protocol_sha256"] != current_protocol:
        raise SystemExit("rebuild the dataset after the protocol change")
    tasks = [args.benchmark / name for name in manifest["runnable_tasks"]]
    if first_cfg.get("action_mode") == "coordinates-v1":
        for task in tasks:
            cfg = json.loads((task / "tests/task.json").read_text())
            if protocol_for(cfg, task) != current_protocol:
                raise SystemExit("coordinate tasks must ship one common protocol")
    tasks = [p for p in tasks if not args.tasks or int(p.name[:2]) in args.tasks]
    if not tasks:
        raise SystemExit("no matching runnable tasks")
    image = f"{args.benchmark.name}:validation"
    print(f"Building common {args.benchmark.name} image...", flush=True)
    # Always build the same base task, including when validating a subset.
    docker("build", "--platform", "linux/amd64", "-t", image,
           args.benchmark / manifest["runnable_tasks"][0] / "environment")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(partial(validate, image=image, out=args.out), tasks))
    args.out.mkdir(parents=True, exist_ok=True)
    image_id = docker("image", "inspect", image, "--format", "{{.Id}}").strip()
    configs = {name: hashlib.sha256(json.dumps(json.loads(
        (args.benchmark / name / "tests/task.json").read_text()), sort_keys=True).encode()).hexdigest()
        for name in manifest["runnable_tasks"]}
    results = [json.loads(p.read_text()) for p in sorted(args.out.glob("*/docker_validation.json"))]
    results = [r for r in results if r.get("protocol_sha256") == current_protocol
               and r.get("image") == image_id and r["task"] in configs
               and r.get("config_sha256") == configs[r["task"]]]
    (args.out / "validation.json").write_text(json.dumps(dict(protocol_sha256=current_protocol,
                         image=image_id,
                         tasks=results), indent=2)+"\n")


if __name__ == "__main__":
    main()
