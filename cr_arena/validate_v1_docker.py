"""Run protected v1 references through cr, restart, and fresh-container verification.

    python -m cr_arena.validate_v1_docker [--tasks 1 5]

No cloud resources or model keys are used. The common runtime image is built once;
each task supplies only its own private config, protected solution, and verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from .royalebench_v1 import protocol_digest


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
    name = f"royale-v1-{task.name}"
    dest = (out / task.name).resolve()
    dest.mkdir(parents=True, exist_ok=True)
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
        docker("exec", "-u", "player", name, "bash", "-c", "test ! -r /var/lib/royale/actions.jsonl")
        # A restart must retain the completed scenario and replay its authenticated log.
        docker("exec", name, "pkill", "-u", "referee", "-f", "cr_arena.royale_task")
        resumed = docker("exec", "-u", "player", name, "cr")
        if "GAME OVER: scenario SUCCESS" not in resumed:
            raise RuntimeError("restart lost the scenario: " + resumed)
        docker("cp", f"{name}:/var/lib/royale/actions.jsonl", dest / "actions.jsonl")
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
    result = dict(task=task.name, family=cfg["family"], reward=1, integrity=1,
                  protocol_sha256=protocol_digest(),
                  config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                  image=docker("image", "inspect", image, "--format", "{{.Id}}").strip(),
                  isolated=True, restart_verified=True, network="none", elapsed_s=round(time.perf_counter()-started, 3))
    (dest / "docker_validation.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", type=int, nargs="*")
    ap.add_argument("--benchmark", type=Path, default=Path("benchmarks/royalebench-v1"))
    ap.add_argument("--out", type=Path, default=Path("runs/royalebench-v1/docker"))
    args = ap.parse_args()
    manifest = json.loads((args.benchmark / "manifest.json").read_text())
    if manifest["protocol_sha256"] != protocol_digest():
        raise SystemExit("rebuild the dataset after the protocol change")
    tasks = [args.benchmark / name for name in manifest["runnable_tasks"]]
    tasks = [p for p in tasks if not args.tasks or int(p.name[:2]) in args.tasks]
    if not tasks:
        raise SystemExit("no matching runnable tasks")
    image = "royalebench-v1:validation"
    print("Building common v1 image...", flush=True)
    # Always build the same base task, including when validating a subset.
    docker("build", "--platform", "linux/amd64", "-t", image,
           args.benchmark / manifest["runnable_tasks"][0] / "environment")
    for task in tasks:
        validate(task, image, args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    image_id = docker("image", "inspect", image, "--format", "{{.Id}}").strip()
    configs = {name: hashlib.sha256(json.dumps(json.loads(
        (args.benchmark / name / "tests/task.json").read_text()), sort_keys=True).encode()).hexdigest()
        for name in manifest["runnable_tasks"]}
    results = [json.loads(p.read_text()) for p in sorted(args.out.glob("*/docker_validation.json"))]
    results = [r for r in results if r.get("protocol_sha256") == protocol_digest()
               and r.get("image") == image_id and r["task"] in configs
               and r.get("config_sha256") == configs[r["task"]]]
    (args.out / "validation.json").write_text(json.dumps(dict(protocol_sha256=protocol_digest(),
                         image=image_id,
                         tasks=results), indent=2)+"\n")


if __name__ == "__main__":
    main()
