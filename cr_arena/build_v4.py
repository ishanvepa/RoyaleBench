"""Build the focused v4 challenge set from validated v3 coordinate scenarios.

The v3 dataset remains frozen. Three scenarios reflect the threat across the
arena; two overtime positions vary enemy and own tower HP in sequence. References
and negative controls are replayed from each new state before packaging.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from functools import partial
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import shutil
import tomllib

import tomli_w

from .coordinate_benchmark import instruction, play, protocol_digest
from .royale_task import verify
from .telemetry import VERSION as CAPTURE_VERSION, digest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "benchmarks/royalebench-v3"
OUT = ROOT / "benchmarks/royalebench-v4"
EVIDENCE = ROOT / "runs/royalebench-v4"
TITLE = "RoyaleBench v4"
VERSION = "4.0.0"
VARIANTS = {
    "02-efficient-defense-mirror": ("02-efficient-defense", "mirror"),
    "04-tank-and-support-mirror": ("04-tank-and-support", "mirror"),
    "05-successive-threats-mirror": ("05-successive-threats", "mirror"),
    "08-cycle-to-lethal-plus": ("08-cycle-to-lethal", "extra-lethal"),
    "08-cycle-to-lethal-critical": ("08-cycle-to-lethal", "critical"),
}


def transform(name: str) -> tuple[dict, list[dict]]:
    source, variant = VARIANTS[name]
    cfg = json.loads((SOURCE / source / "tests/task.json").read_text())
    cfg = {key: value for key, value in cfg.items()
           if key not in ("task_id", "instruction_sha256", "rubric", "capture_schema_version", "resources")}
    suffix = {"mirror": "opposite lane", "extra-lethal": "two-hit lethal", "critical": "critical defense"}[variant]
    cfg.update(id=name, title=f"{cfg['title']} ({suffix})",
               benchmark=TITLE, version=VERSION)
    scenario = cfg["scenario"]
    if variant == "mirror":
        scenario["tower_hp"] = [[hp[0], hp[2], hp[1]] for hp in scenario["tower_hp"]]
        for unit in scenario["units"]:
            unit["x"] = 18 - unit["x"]
        if "scheduled_attack" in scenario:
            scenario["scheduled_attack"]["x"] = 18 - scenario["scheduled_attack"]["x"]
        cfg["objective"] = (cfg["objective"].replace("left", "@side@")
                            .replace("right", "left").replace("@side@", "right")
                            .replace("(3.5, 6.5)", "(14.5, 6.5)"))
        cfg["release_gate"] = "Mirrored reference wins; original-lane placement fails; replay and negative controls pass."
    else:
        scenario["tower_hp"][1][2] = 180
        if variant == "critical":
            scenario["tower_hp"][0][1] = 250
            cfg["release_gate"] = "A winning Cannon defense and a failing cheap-defense counterfactual must be replay-verified."
        else:
            cfg["release_gate"] = "A winning two-hit reference and a failing Fireball-only counterfactual must be replay-verified."

    entries = [json.loads(line) for line in (SOURCE / source / "solution/reference.jsonl").read_text().splitlines()]
    actions = [deepcopy(entry["action"]) for entry in entries]
    if variant == "mirror":
        if source == "05-successive-threats":
            # The v3 menu reference does not transfer to this lane. This
            # alternate sequence was replay-verified on the mirrored state.
            actions = [
                dict(cmd="play", slot=2, x=3.5, y=11.0),
                dict(cmd="wait"), dict(cmd="wait"),
                dict(cmd="play", slot=3, x=3.5, y=4.5),
                dict(cmd="wait"),
                dict(cmd="play", slot=0, x=14.5, y=11.5),
                dict(cmd="wait"),
                dict(cmd="play", slot=0, x=12.5, y=14.5),
                dict(cmd="wait"), dict(cmd="wait"),
            ]
        for action in actions:
            if action["cmd"] == "play":
                action["x"] = 18 - action["x"]
    elif variant == "extra-lethal":
        # Defend the Giant, damage the tower with Fireball, then use Log to
        # finish the remaining 21 HP before the Giant can destroy our tower.
        actions = [
            dict(cmd="play", slot=0, x=3.5, y=10.5),
            dict(cmd="play", slot=0, x=6.5, y=10.5),
            dict(cmd="play", slot=0, x=3.5, y=25.5),
            dict(cmd="play", slot=3, x=3.5, y=25.5),
        ]
    else:
        actions = [
            dict(cmd="play", slot=3, x=3.5, y=21.0),
            dict(cmd="play", slot=3, x=6.5, y=10.5),
            dict(cmd="play", slot=3, x=3.5, y=25.5),
        ]
    return cfg, actions


def run_actions(cfg: dict, path: Path, actions: list[dict]) -> dict:
    start = cfg["scenario"]["start_tick"]
    ticks = {start + 40 * i: action for i, action in enumerate(actions)}
    ref = play(cfg, path, ticks)
    report = verify(cfg, path, None)
    if report["rewards"]["integrity"] != 1:
        raise ValueError(f"{cfg['id']}: reference replay integrity failed")
    return report


def calibrate(name: str, evidence: Path) -> tuple[dict, dict]:
    cfg, actions = transform(name)
    dest = evidence / name
    dest.mkdir(parents=True, exist_ok=True)
    reference = dest / "reference.jsonl"
    cached_path = dest / "validation.json"
    config_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    if cached_path.is_file() and reference.is_file():
        cached = json.loads(cached_path.read_text())
        valid_cache = (cached.get("config_sha256") == config_hash
                       and cached.get("protocol_sha256") == protocol_digest()
                       and cached.get("reference_log_sha256") == hashlib.sha256(reference.read_bytes()).hexdigest()
                       and cached.get("reward") == cached.get("integrity") == 1
                       and cached.get("deterministic") is True
                       and cached.get("negative_rewards") == dict(wait=0, empty=0, malformed=0)
                       and cached.get("counterfactual_reward") == 0)
        if valid_cache:
            fresh = verify(cfg, reference, None)
            if fresh["rewards"]["reward"] == fresh["rewards"]["integrity"] == 1 and fresh["outcome"] == cached["reference_outcome"]:
                print(f"Revalidated cached reference: {name}", flush=True)
                return cfg, cached
    first = run_actions(cfg, reference, actions)
    second = verify(cfg, reference, None)
    if first != second or first["rewards"]["reward"] != 1:
        raise ValueError(f"{name}: winning deterministic reference required")
    waits = [dict(cmd="wait")] * len(actions)
    idle = run_actions(cfg, dest / "wait.jsonl", waits)
    (dest / "empty.jsonl").write_text("")
    (dest / "malformed.jsonl").write_text("not json\n")
    negatives = {"wait": idle["rewards"]["reward"]}
    for kind in ("empty", "malformed"):
        negatives[kind] = verify(cfg, dest / f"{kind}.jsonl", None)["rewards"]["reward"]
    if any(negatives.values()):
        raise ValueError(f"{name}: negative control scored positive")

    source, variant = VARIANTS[name]
    original = [json.loads(line)["action"] for line in
                (SOURCE / source / "solution/reference.jsonl").read_text().splitlines()]
    if name == "02-efficient-defense-mirror":
        # Centre placement can defend both lanes. Test the observed left-lane
        # shortcut rather than treating a transferable central defense as a failure.
        original = [dict(cmd="play", slot=0, x=6.5, y=10.5)]
    elif variant == "critical":
        original = [
            dict(cmd="play", slot=3, x=3.5, y=21.0),
            dict(cmd="play", slot=0, x=3.7, y=9.5),
            dict(cmd="play", slot=0, x=3.5, y=25.5),
        ]
    contrast = run_actions(cfg, dest / "counterfactual.jsonl", original)
    if contrast["rewards"]["reward"] != 0:
        raise ValueError(f"{name}: unchanged strategy also wins; lever is not discriminative")

    row = dict(task=name, source_task=source, transform=variant,
               reward=1, integrity=1, deterministic=True, negative_rewards=negatives,
               counterfactual_reward=0,
               config_sha256=config_hash,
               protocol_sha256=protocol_digest(),
               reference_log_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
               reference_outcome=first["outcome"])
    (dest / "validation.json").write_text(json.dumps(row, indent=2) + "\n")
    print(f"Calibrated {name}: reference=1, counterfactual=0, negatives=0", flush=True)
    return cfg, row


def build(out: Path = OUT, evidence: Path = EVIDENCE, *, jobs: int = 1) -> dict:
    out, evidence = Path(out).resolve(), Path(evidence).resolve()
    if not 1 <= jobs <= 4:
        raise ValueError("jobs must be 1 to 4")
    source_manifest = json.loads((SOURCE / "manifest.json").read_text())
    for package, pinned in source_manifest["dependencies"].items():
        if package_version(package) != pinned:
            raise ValueError(f"{package} must be {pinned}")
    names = tuple(VARIANTS)
    evidence.mkdir(parents=True, exist_ok=True)
    worker = partial(calibrate, evidence=evidence)
    if jobs == 1:
        calibrated = [worker(name) for name in names]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            calibrated = list(pool.map(worker, names))
    protocol = protocol_digest()
    if any(row["protocol_sha256"] != protocol for _, row in calibrated):
        raise ValueError("runtime changed during calibration")

    out.mkdir(parents=True, exist_ok=True)
    for cfg, row in calibrated:
        name = cfg["id"]
        source = SOURCE / row["source_task"]
        dest = out / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        task_instruction = instruction(cfg)
        packaged = dict(cfg, task_id=name, instruction_sha256=digest(task_instruction),
                        rubric="scenario-objective-coordinates-v1",
                        capture_schema_version=CAPTURE_VERSION,
                        resources=dict(agent_timeout_s=3600, verifier_timeout_s=600,
                                       cpus=1, memory_mb=2048, storage_mb=4096))
        for side in ("environment", "tests"):
            (dest / side / "task.json").write_text(json.dumps(packaged, indent=2) + "\n")
        (dest / "instruction.md").write_text(task_instruction)
        (dest / "solution/reference.jsonl").write_bytes((evidence / name / "reference.jsonl").read_bytes())
        task = tomllib.loads((source / "task.toml").read_text())
        task["task"].update(name=f"royalebench/v4-{name}",
                            description=f"{cfg['title']}. {cfg['objective']} | action_mode=coordinates-v1 | version={VERSION}")
        task["metadata"].update(dataset_version=VERSION, action_mode="coordinates-v1", difficulty="hard")
        (dest / "task.toml").write_text(tomli_w.dumps(task))

    manifest = dict(benchmark=TITLE, version=VERSION, action_mode="coordinates-v1",
                    capture_schema_version=CAPTURE_VERSION, protocol_sha256=protocol,
                    runnable_tasks=list(names), gated_tasks=[],
                    source_dataset="royalebench/royalebench-v3@2",
                    dependencies=source_manifest["dependencies"], tasks=[row for _, row in calibrated],
                    status="Local reference calibration; Docker and hosted model results recorded separately.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "benchmark.toml").write_text(tomli_w.dumps({"benchmark": dict(title=TITLE, kind="eval",
        description=f"{len(names)} replay-validated continuation challenges against Planner with coordinate actions.")}))
    (out / "README.md").write_text(
        f"# RoyaleBench v4\n\n{len(names)} focused continuation challenges from the v3 model comparison. "
        "See [the guide](../../docs/royalebench_v4.md). "
        "Regenerate with `uv run python -m cr_arena.build_v4`.\n")
    (evidence / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    build(args.out, args.evidence, jobs=args.jobs)


if __name__ == "__main__":
    main()
