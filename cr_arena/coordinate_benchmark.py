"""Build a separately versioned, locally calibrated coordinate pilot from frozen v1 states.

    uv run python -m cr_arena.coordinate_benchmark

No model API calls or publication. References are converted from frozen v1 traces,
then submitted and independently replayed through the coordinate protocol.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import shutil
import tempfile
import tomllib

from .build_tasks import REFEREE_FILES, ROOT, START_SERVER, SUDOERS, TEST_SH
from .build_v1 import instruction as menu_instruction, write
from .coordinate_task import MODE
from .royale_task import make_referee, read_log, verify
from .scenario_task import ScenarioReferee

TITLE = "RoyaleBench coordinates pilot"
VERSION = "1.0.0-coordinate.1"
# Coordinate releases are derived from the exact v1@1 inputs. Later v1 revisions
# can add telemetry without changing v3's provenance.
BASE = ROOT.parent / "data/royalebench-v1-source"
LEGACY_DATASET = ROOT.parent / "benchmarks/royalebench-v1"
OUT = ROOT.parent / "benchmarks/royalebench-coordinates"
EVIDENCE = ROOT.parent / "runs/royalebench-coordinates"
PILOT = ("01-immediate-lethal", "03-spell-placement", "08-cycle-to-lethal")
RUNTIME = list(dict.fromkeys(REFEREE_FILES + ["scenario_task.py", "coordinate_task.py", "bots/planner.py"]))


def protocol_digest(root=ROOT, client=None):
    """Digest a runtime tree, preserving the manifest's stable path labels."""
    root = Path(root)
    client = Path(client) if client is not None else root / "cr_client.py"
    h = hashlib.sha256()
    for name in RUNTIME + ["cr_client.py"]:
        h.update(name.encode())
        path = client if name == "cr_client.py" else root / name
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def packaged_protocol_digest(task):
    """Digest the immutable referee and client shipped with one task."""
    task = Path(task)
    return protocol_digest(task / "environment/referee", task / "environment/cr")


def config(name, *, title=TITLE, version=VERSION):
    cfg = json.loads((BASE / name / "tests/task.json").read_text())
    cfg.update(benchmark=title, version=version, action_mode=MODE)
    return cfg


def reference_actions(name):
    """Translate the actual frozen menu trace, including its original snapped coordinates."""
    cfg = json.loads((BASE / name / "tests/task.json").read_text())
    ref = ScenarioReferee(cfg)
    actions = {}
    for entry in read_log(BASE / name / "solution/reference.jsonl"):
        if (entry["decision"], entry["tick"]) != (ref.decision, ref.tick):
            raise ValueError("frozen reference does not match its state")
        move = ref.check_move(entry["move"])
        if move.label() != entry["label"]:
            raise ValueError("frozen reference does not match its menu")
        if move.slot < 0:
            action = {"cmd": "wait"}
        else:
            x, y = ref.game.own_tiles(0, move.x, move.y)
            action = dict(cmd="play", slot=move.slot, x=x, y=y)
        actions[ref.tick] = action
        ref.act(entry["move"])
    if not ref.over or not ref.success():
        raise ValueError("frozen reference no longer solves the scenario")
    return actions


def play(cfg, path, actions):
    ref = make_referee(cfg)
    entries = []
    while not ref.over:
        action = actions.get(ref.tick, {"cmd": "wait"})
        entries.append(ref.entry(action, 5.0))
        ref.act_action(action)
    write(path, "".join(json.dumps(e) + "\n" for e in entries))
    ref.opponent.close()
    return ref


def calibration_problem(cfg, row, reference):
    """Cache only exact, passing protocol/config/log evidence; never waive release checks."""
    if row.get("config_sha256") != hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest():
        return "configuration changed"
    if row.get("protocol_sha256") != protocol_digest():
        return "runtime changed"
    if row.get("reward") != 1 or row.get("integrity") != 1 or row.get("deterministic") is not True:
        return "reference validation failed"
    if row.get("negative_rewards") != dict(wait=0, empty=0, malformed=0):
        return "negative controls failed"
    if not reference.is_file() or hashlib.sha256(reference.read_bytes()).hexdigest() != row.get("reference_log_sha256"):
        return "reference log changed"
    return None


def calibrate(name, evidence, *, title=TITLE, version=VERSION, reuse=False):
    start_protocol = protocol_digest()
    cfg = config(name, title=title, version=version)
    dest = evidence / name
    reference = dest / "reference.jsonl"
    if reuse and (dest / "validation.json").is_file():
        row = json.loads((dest / "validation.json").read_text())
        if not calibration_problem(cfg, row, reference):
            # Recheck the actual reference even when reusing expensive negative-control evidence.
            report = verify(cfg, reference, None)
            if report["rewards"]["reward"] == report["rewards"]["integrity"] == 1 and report["outcome"] == row["reference_outcome"]:
                print(f"Revalidated cached reference: {name}", flush=True)
                return cfg, row
    ref = play(cfg, reference, reference_actions(name))
    first, second = verify(cfg, reference, None), verify(cfg, reference, None)
    idle = play(cfg, dest / "wait.jsonl", {})
    write(dest / "empty.jsonl", "")
    write(dest / "malformed.jsonl", "not json\n")
    negative = {n: verify(cfg, dest / f"{n}.jsonl", None)["rewards"]["reward"]
                for n in ("wait", "empty", "malformed")}
    if first["rewards"]["reward"] != 1 or first != second or any(negative.values()):
        raise ValueError(f"coordinate calibration failed: {name}")
    if protocol_digest() != start_protocol:
        raise ValueError("runtime sources changed during calibration; retry sequentially")
    evidence_row = dict(task=name, reward=1, integrity=first["rewards"]["integrity"],
                        deterministic=True, negative_rewards=negative,
                        config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                        protocol_sha256=start_protocol,
                        reference_log_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                        reference_outcome=ref.outcome(), decisions=ref.decision,
                        menu_baseline_reward=1, frontier_model_runs=[])
    write(dest / "validation.json", json.dumps(evidence_row, indent=2) + "\n")
    print(f"Calibrated {name}: reward=1, deterministic replay, negative controls=0", flush=True)
    return cfg, evidence_row


SOLUTION = '''"""Protected coordinate reference; never installed in the player environment."""
import json
import subprocess
from pathlib import Path

subprocess.check_output(["cr"], text=True)
for line in Path("/solution/reference.jsonl").read_text().splitlines():
    a = json.loads(line)["action"]
    args = ["wait"] if a["cmd"] == "wait" else ["play", str(a["slot"]), str(a["x"]), str(a["y"])]
    text = subprocess.check_output(["cr", *args], text=True)
if "GAME OVER: scenario SUCCESS" not in text:
    raise SystemExit(text)
print(text)
'''


def instruction(cfg):
    # Retain the exact fixed state, mechanics, deck statistics, and disclosures.
    tail = menu_instruction(cfg).split("## Fixed starting state\n", 1)[1]
    tail = tail.replace("visible events, and legal placements", "visible events, and your hand")
    tail = tail.replace("Legal moves are re-numbered after every decision.", "")
    return f'''# {cfg['benchmark']}: {cfg['title']}

## Objective and score

{cfg['objective']}

Reward is 1 only for a completed, independently replayed sequence meeting the objective; otherwise 0.
A chat response alone does not complete the task. Damage means additional damage to all your crown
towers after the starting state. Spending includes all accepted plays, even as elixir regenerates.
Spending and lane budgets are checked by the verifier; overspending is possible and fails the objective.
Any stated card restriction or maximum decision count still applies.

## Play

Run `cr` to inspect the board and zero-based hand slots (0, 1, 2, 3).
Run `cr play SLOT X Y` to deploy that slot at tile coordinates, or `cr wait` to wait.
For command shape only: `cr play 0 8.5 10.5`. Choose your own card and position.
Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32. They are rounded only to engine
subtile precision, never snapped to a nearby legal placement. There is no numbered action menu.
Malformed commands do not advance time. A well-formed illegal play (bad slot, empty slot,
unaffordable card, illegal location, or unavailable card) consumes one interval as a wait and
reports its rejection. Accepted commands and rejected attempts are replayed by the verifier.
Both players choose from the same frozen state. Each interval advances up to 2 seconds; thinking
does not advance time. Continue until `GAME OVER`. Submit each decision yourself; do not write
programs, scripts, or loops to choose or submit moves. Missing or partial play scores zero.
After the task's maximum decision count, or its single allowed spell, the referee resolves waits.

Planner is unchanged: deterministic 10-second, three-ply search, top 4 candidates, 3 answers,
margin 40, elixir value 150 HP, quiet-score prefilter, no worker processes. It generates its own
coordinate candidates and sees the true engine state, including your hand and elixir. You see
your own hand/elixir, the board, visible events, and next card. Its deck is disclosed below;
its hand, queue and elixir remain hidden unless inferable from history.

## Fixed starting state
{tail}'''


def build(out=OUT, evidence=EVIDENCE, *, names=PILOT, title=TITLE, version=VERSION,
          guide="coordinate_harness.md", task_prefix="coordinates-", command="cr_arena.coordinate_benchmark",
          reuse=False, jobs=1, include_candidates=False):
    import tomli_w

    out, evidence = Path(out).resolve(), Path(evidence).resolve()
    protected = (BASE.resolve(), LEGACY_DATASET.resolve())
    if any(out == path or path in out.parents for path in protected):
        raise ValueError("the frozen v1 dataset cannot be overwritten")
    if not 1 <= jobs <= 4:
        raise ValueError("jobs must be between 1 and 4")
    released = json.loads((BASE / "manifest.json").read_text())["runnable_tasks"]
    if not names or len(set(names)) != len(names) or set(names) - set(released):
        raise ValueError("only released v1 scenarios may be promoted")
    expected = json.loads((BASE / "manifest.json").read_text())["dependencies"]
    for package, pinned in expected.items():
        if package_version(package) != pinned:
            raise ValueError(f"{package} must be {pinned} to match the frozen v1 engine")
    start_protocol = protocol_digest()
    # Validate everything before replacing any generated task.
    calibrator = partial(calibrate, evidence=evidence, title=title, version=version, reuse=reuse)
    if jobs == 1:
        calibrated = [calibrator(name) for name in names]
    else:
        # Isolated engines, disjoint task evidence directories, one parent publishing the manifest.
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            calibrated = list(pool.map(calibrator, names))
    if any(row["protocol_sha256"] != start_protocol for _, row in calibrated):
        raise ValueError("runtime sources changed between task calibrations")
    out.mkdir(parents=True, exist_ok=True)
    for cfg, row in calibrated:
        name = cfg["id"]
        with tempfile.TemporaryDirectory(prefix="royale-coordinates-") as tmp:
            d = Path(tmp) / name
            for source in RUNTIME:
                write(d / "environment/referee" / source, (ROOT / source).read_text())
            for relative, text in {
                "environment/Dockerfile": (BASE / name / "environment/Dockerfile").read_text(),
                "environment/cr": (ROOT / "cr_client.py").read_text(),
                "environment/royale-start-server": START_SERVER,
                "environment/sudoers": SUDOERS,
                "environment/task.json": json.dumps(cfg, indent=2) + "\n",
                "tests/task.json": json.dumps(cfg, indent=2) + "\n",
                "tests/test.sh": TEST_SH,
                "instruction.md": instruction(cfg),
                "solution/solve.sh": "#!/bin/bash\nset -euo pipefail\npython3 /solution/replay_reference.py\n",
                "solution/replay_reference.py": SOLUTION,
                "solution/reference.jsonl": (evidence / name / "reference.jsonl").read_text(),
            }.items():
                write(d / relative, text)
            task = tomllib.loads((BASE / name / "task.toml").read_text())
            task["task"].update(name=f"royalebench/{task_prefix}{name}",
                                description=f"{cfg['title']}. {cfg['objective']} | action_mode={MODE} | version={version}")
            task["metadata"].update(dataset_version=version, action_mode=MODE)
            write(d / "task.toml", tomli_w.dumps(task))
            if (out / name).is_symlink():
                raise ValueError("refusing to replace symlink")
            if (out / name).exists():
                shutil.rmtree(out / name)
            shutil.copytree(d, out / name)
    if protocol_digest() != start_protocol:
        raise ValueError("runtime sources changed during packaging; rebuild before running")
    gated = []
    if include_candidates:
        for path in sorted((BASE / "candidates").glob("*.json")):
            candidate = json.loads(path.read_text())
            candidate.update(benchmark=title, version=version, action_mode=MODE)
            write(out / "candidates" / path.name, json.dumps(candidate, indent=2) + "\n")
            gated.append(dict(id=candidate["id"], family=candidate["family"],
                              reason="Gated in frozen v1; coordinate release gate is not validated.",
                              release_gate=candidate.get("release_gate")))
    manifest = dict(benchmark=title, version=version, action_mode=MODE,
                    protocol_sha256=start_protocol, runnable_tasks=list(names), gated_tasks=gated,
                    source_dataset="royalebench/royalebench-v1@1",
                    dependencies={p: package_version(p) for p in ("royalegym", "royalesim", "msgspec")},
                    tasks=[row for _, row in calibrated],
                    status="Local reference calibration only; Docker and model runs tracked separately.")
    write(out / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    write(out / "benchmark.toml", tomli_w.dumps({"benchmark": dict(title=title, kind="eval",
          description=f"{len(names)} continuation scenarios against Planner with direct coordinate actions and paused text observations. Model calibration tracked separately.")}))
    write(out / "README.md", f"# {title}\n\n"
          f"{len(names)} reference-validated scenarios from frozen v1 with direct coordinate actions.\n"
          f"See [the guide](../../docs/{guide}) for protocol, validation, and limitations.\n"
          f"Regenerate with `uv run python -m {command}`.\n")
    write(evidence / "validation.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    build(args.out, args.evidence)


if __name__ == "__main__":
    main()
