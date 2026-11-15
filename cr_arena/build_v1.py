"""Package calibrated RoyaleBench v1 tasks in the Harbor format.

    python -m cr_arena.validate_v1
    python -m cr_arena.build_v1

Only locally validated tasks enter the runnable dataset. All proposed scenarios,
including gated ones, are recorded in manifest.json and candidates/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from .build_tasks import DOCKERFILE, REFEREE_FILES, ROOT, START_SERVER, SUDOERS, TEST_SH, ROYALEGYM, ROYALESIM, task_toml
from .royalebench_v1 import TITLE, VERSION, catalog, protocol_digest
from .scenario_task import ScenarioReferee
from .royale_task import verify
from .telemetry import VERSION as CAPTURE_VERSION, digest

OUT = Path("benchmarks/royalebench-v1")
EVIDENCE = Path("runs/royalebench-v1")

SOLUTION_DRIVER = '''"""Replay a protected reference through exactly the agent's cr socket interface."""
import json
import subprocess
from pathlib import Path

def call(*args):
    return subprocess.check_output(["cr", *args], text=True)

text = call()
for line in Path("/solution/reference.jsonl").read_text().splitlines():
    entry = json.loads(line)
    if entry["label"] not in text.splitlines():
        raise SystemExit("reference no longer matches the legal menu")
    text = call("act", str(entry["move"]))
if "GAME OVER: scenario SUCCESS" not in text:
    raise SystemExit(text)
print(text)
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if path.suffix == ".sh" or path.name in {"cr", "royale-start-server"}:
        path.chmod(0o755)


def json_text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def instruction(cfg):
    ref = ScenarioReferee(cfg)
    g, s = ref.game, cfg["scenario"]
    elapsed, overtime = g.time_left_s()
    extra = ""
    if s.get("disclose_queue"):
        extra += "\nYour exact draw queue after the starting four cards: " + ", ".join(s["order"][4:]) + ".\n"
    if "verified_fireball_crown_damage" in s:
        extra += f"\nA Fireball deals {s['verified_fireball_crown_damage']} crown-tower damage in this simulator (verified at build time).\n"
    if s.get("scheduled_attack"):
        extra += ("\nThe scheduled GoblinBarrel is guaranteed, costs the opponent 3 elixir, and is reserved in its hand "
                  "until elapsed 6.0 seconds. Planner chooses every other opponent play.\n")
    if s.get("visible_history"):
        extra += "\nVisible enemy deployment history (times relative to this start):\n" + "\n".join(s["visible_history"]) + "\n"
    return f'''# {TITLE}: {cfg['title']}

## Objective and score

{cfg['objective']}

Reward is binary: 1 if the objective is met after you finish the scenario, 0 otherwise.
Only decisions submitted with `cr act N` count. A chat response alone does not complete the task.
Missing or partial play receives 0. The referee may advance forced waits automatically.
Spending limits are hard constraints on the legal menu and include all your cards played after this start.
Tower damage means the sum of additional damage to all your crown towers from this starting state.

## Play

Run `cr` to inspect the board and numbered legal moves. Run `cr act N` to submit one move.
Move 0 is wait. Both players choose from the same state; each interval advances up to 2.0 seconds.
The game pauses while you think. Continue until `cr` prints `GAME OVER`.
Make each decision yourself; do not write programs, scripts, or loops to choose or submit moves.
The model is evaluated on decisions through this menu. The opponent can use arbitrary legal placements.

The fixed opponent is **planner-bot**: a deterministic 10-second search, best-reply analysis
and a third ply answering the 3 worst replies, top 4 candidates with the quiet-score prefilter,
margin 40, elixir value 150 HP, and no worker processes. It sees the true engine state, including your
hand and elixir. You see only your own hand and elixir, the board, visible events, and the next card.
The opponent's deck is disclosed below; its hand and draw queue are hidden unless inferable from history.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed {cfg['seed']}, blue seat, zero command delay. Time remaining: {elapsed:.0f} seconds in
{'overtime' if overtime else 'regulation'}; elixir multiplier x{g.state.elixir_rate}.
The scoring window is at most {s['horizon_s']} seconds and ends earlier if the match ends.
Your starting hand: {', '.join(s['order'][:4])}. Starting elixir: {s['elixir']}.
`cr` provides exact tower HP, current unit HP/positions, visible events, and legal placements.
{extra}
Coordinates are in tiles from your perspective: x 0-18 from left to right, y 0-32 from your back
edge to the enemy's. The river is near y 15-16; your princess towers are near (3.5, 6.5) and
(14.5, 6.5), the enemy's near y 25.5. Legal moves are re-numbered after every decision.

## Match rules

Princess tower destroyed = one crown; king destroyed = instant win. A regulation crown lead wins
when regulation ends. Tied crowns enter overtime, where the next destroyed tower wins.
At the final overtime deadline a crown tie is broken by total remaining crown-tower HP, then seed
parity. For fixed defense windows the stated survival/damage objective determines the score.
Elixir regenerates (maximum 10), faster in the final minute and overtime. Played cards return to the
back of the eight-card queue; a hand slot refills after the engine's normal refill delay.

## Decks

Your deck: {cfg['player_deck_name']} (average {sum(c.elixir for c in g.cards if c.name in cfg['agent_deck'])/8:.2f} elixir).
{g.deck_summary(0)}

Opponent deck: {cfg['opponent_deck_name']} (average {sum(c.elixir for c in g.cards if c.name in cfg['opponent_deck'])/8:.2f} elixir).
{g.deck_summary(1)}
'''


def release_problem(cfg, evidence):
    if not evidence:
        return "Local reference validation has not run."
    digest = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    if evidence.get("config_sha256") != digest:
        return "Validation is stale for the current scenario configuration."
    if evidence.get("protocol_sha256") != protocol_digest():
        return "Validation is stale for the current engine adapter/referee/Planner code."
    if evidence.get("reference_reward") != 1 or not evidence.get("deterministic"):
        return "Reference has not won with deterministic replay."
    if evidence.get("wait_success") or evidence.get("empty_reward") != 0 or evidence.get("malformed_reward") != 0:
        return "Negative control failed."
    if cfg["release_gate"] and not evidence.get("release_gate_passed"):
        return cfg["release_gate"]
    return None


def build(out=OUT, evidence_dir=EVIDENCE):
    for package, expected in [("royalegym", ROYALEGYM), ("royalesim", ROYALESIM)]:
        if version(package) != expected:
            raise RuntimeError(f"{package} must be {expected} to match the pinned task image")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Delete only known generated task folders, after checking their absolute parent.
    for old in out.iterdir():
        if old.is_dir() and (old / "task.toml").is_file():
            if old.resolve().parent != out or old.is_symlink():
                raise ValueError(f"refusing to replace unexpected path {old}")
            shutil.rmtree(old)
    write(out / "benchmark.toml", f'''# Generated by python -m cr_arena.build_v1
[benchmark]
title = "{TITLE}"
description = "Mid-match strategic continuations against Planner. Binary scenario objectives, fixed engine state, isolated referee, replay grading. Locally calibrated; frontier-model calibration pending."
kind = "eval"
''')
    entries, names = [], []
    configs = catalog()
    for cfg in configs:
        evidence_path = evidence_dir / cfg["id"] / "validation.json"
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else None
        problem = release_problem(cfg, evidence)
        reference_text = ""
        if evidence:
            log = evidence_dir / cfg["id"] / "reference.jsonl"
            reference_bytes = log.read_bytes() if log.exists() else b""
            if hashlib.sha256(reference_bytes).hexdigest() != evidence.get("reference_log_sha256"):
                problem = "Reference action log is missing or does not match validation."
            elif not problem:
                print(f"Replaying protected reference: {cfg['id']}", flush=True)
                # Verify an immutable copy and package exactly those bytes. This also catches
                # mixed evidence left by accidentally overlapping calibration processes.
                with tempfile.TemporaryDirectory(prefix="royale-v1-build-") as tmp:
                    staged = Path(tmp) / "reference.jsonl"
                    staged.write_bytes(reference_bytes)
                    report = verify(cfg, staged, None)
                if report["rewards"]["reward"] != 1 or report["outcome"] != evidence["reference_outcome"]:
                    problem = "Reference replay disagrees with its validation evidence."
                reference_text = reference_bytes.decode("utf-8")
        entries.append(dict(id=cfg["id"], family=cfg["family"], title=cfg["title"],
                            status="gated" if problem else "local-validated", reason=problem,
                            csv_win_rate=cfg["csv_win_rate"], validation=evidence))
        if problem:
            write(out / "candidates" / (cfg["id"] + ".json"), json_text(cfg))
            continue
        (out / "candidates" / (cfg["id"] + ".json")).unlink(missing_ok=True)
        names.append(cfg["id"])
        d = out / cfg["id"]
        env = d / "environment"
        for name in REFEREE_FILES + ["scenario_task.py", "bots/planner.py"]:
            # Explicit files only: no tests, solutions, credentials, or calibration results.
            write(env / "referee" / name, (ROOT / name).read_text(encoding="utf-8"))
        task_instruction = instruction(cfg)
        packaged_config = dict(cfg, task_id=cfg["id"], instruction_sha256=digest(task_instruction),
                               rubric="scenario-objective-v1", capture_schema_version=CAPTURE_VERSION,
                               resources={"agent_timeout_s": 3600, "verifier_timeout_s": 600,
                                          "cpus": 1, "memory_mb": 2048, "storage_mb": 4096})
        write(env / "task.json", json_text(packaged_config))
        write(d / "tests/task.json", json_text(packaged_config))
        dockerfile = DOCKERFILE.replace("FROM python:3.12-slim-bookworm", "FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df")
        pins = " ".join(f"{p}=={version(p)}" for p in ["numpy", "gymnasium", "pettingzoo", "msgspec", "cloudpickle", "typing-extensions", "farama-notifications"])
        dockerfile = dockerfile.replace("royalesim==0.1.48", "royalesim==0.1.48 " + pins)
        dockerfile = dockerfile.replace("WORKDIR /app", "ENV PYTHONHASHSEED=0 LANG=C.UTF-8 LC_ALL=C.UTF-8\nWORKDIR /app")
        write(env / "Dockerfile", dockerfile)
        write(env / "cr", (ROOT / "cr_client.py").read_text(encoding="utf-8"))
        write(env / "royale-start-server", START_SERVER)
        write(env / "sudoers", SUDOERS)
        write(d / "tests/test.sh", TEST_SH)
        write(d / "instruction.md", task_instruction)
        toml = task_toml(cfg["id"], cfg["seed"], 0, 0)
        # Reuse the isolation/resource protocol, replacing match-specific metadata.
        lines = toml.splitlines()
        replacements = {"description =": "description = " + json.dumps(f"{cfg['title']}. {cfg['objective']} | opponent=planner-bot | seed={cfg['seed']} | version={VERSION}"),
                        "category =": 'category = "clash-royale-continuation"',
                        "difficulty =": f'difficulty = "{cfg["difficulty"]}"',
                        "opponent =": 'opponent = "planner"',
                        "deck =": f'deck = "{cfg["player_deck_name"]}"'}
        for i, line in enumerate(lines):
            for key, value in replacements.items():
                if line.startswith(key):
                    lines[i] = value
        toml = "\n".join(lines) + "\n"
        metadata = (f'dataset_version = "{VERSION}"\nfamily = {cfg["family"]}\n'
                    f'opponent_deck = "{cfg["opponent_deck_name"]}"\n'
                    f'control = {str(cfg["family"] == 1).lower()}\n')
        toml = toml.replace('[agent]\n', metadata + '\n[agent]\n')
        # Harness installation needs public access during setup; constrain actual play.
        # Harbor's agent policy applies to agent.run(), not agent.setup().
        toml = toml.replace('[environment]\n', '[environment]\nnetwork_mode = "public"\n')
        toml = toml.replace('[agent]\n', '[agent]\nnetwork_mode = "allowlist"\nallowed_hosts = ["api.anthropic.com", "api.openai.com", "openrouter.ai", "ishanvepa171--ep-qwen3-8-2-4t-a95b-server.us-west.modal.direct", "ishanvepa171--ep-inkling-2-small-server.us-west.modal.direct"]\n')
        toml = toml.replace('[verifier]\n', '[verifier]\nnetwork_mode = "no-network"\n')
        # A busy Planner continuation is replayed in the verifier; give it measured headroom.
        toml = toml.replace("timeout_sec = 300.0", "timeout_sec = 600.0")
        write(d / "task.toml", toml)
        write(d / "solution/solve.sh", "#!/bin/bash\nset -euo pipefail\npython3 /solution/replay_reference.py\n")
        write(d / "solution/replay_reference.py", SOLUTION_DRIVER)
        write(d / "solution/reference.jsonl", reference_text)
    manifest = dict(benchmark=TITLE, version=VERSION, capture_schema_version=CAPTURE_VERSION,
                    opponent="planner", planner=configs[0]["planner"],
                    protocol_sha256=protocol_digest(),
                    dependencies={p: version(p) for p in ["royalegym", "royalesim", "msgspec"]},
                    runnable_tasks=names, tasks=entries,
                    aggregation="Mean binary reward across runnable tasks. Also report per-family means; paired variants share a family.",
                    status="Local validation only; Docker/Modal and frontier-model validation tracked separately.")
    write(out / "manifest.json", json_text(manifest))
    write(out / "README.md", f'''# {TITLE}

Generated Harbor dataset: **{len(names)} runnable variants**, all against **planner-bot**.
Read [the benchmark guide](../../docs/royalebench_v1.md) for scenarios, scores, validation and launch commands.

The [manifest](manifest.json) records every proposed variant, its validation evidence and release status.
Candidates without a passing reference and release gate remain in `candidates/`, outside the runnable task list.
Regenerate with `python -m cr_arena.build_v1`; edit the source specifications, not these task folders.
''')
    print(f"Built {TITLE}: {len(names)} runnable tasks, {len(entries)-len(names)} gated variants at {out}")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = ap.parse_args()
    build(args.out, args.evidence)


if __name__ == "__main__":
    main()
