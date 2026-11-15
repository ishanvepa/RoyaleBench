"""Append a calibrated Hog defense to the seven unchanged Tactics @3 packages.

    python -m cr_arena.build_tactics_hog
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tomllib

import tomli_w
from valkyrie.sdk.task_content import task_digest

from rb_evals.benchmarks import load_benchmark, task_problems
from .build_tactics import FOUNDATION_PROTOCOL, OUT
from .coordinate_benchmark import packaged_protocol_digest, RUNTIME, SOLUTION
from .royale_task import make_referee, verify
from .telemetry import atomic_json, digest

TASK = "05-hog-body-block"
EVIDENCE = Path("runs/tactics-hog-one-hit")
SOURCE_DIGESTS = {
    "01-timed-spell-a": "sha256:0e2579caba181db0a46561f1bf26d2783715cd77e92a4b36534ab5ac1d56aa79",
    "01-timed-spell-b": "sha256:88ed284092d6c1e3b203dc0a587c07dc4d3c2cb62288d893799eb8b83a5e73b8",
    "02-reserve-counter-a": "sha256:de2e93bb3a6483ae81950340b87e7228fdff1f3a081cd5e617220c41c991e9b9",
    "03-tower-race-a": "sha256:5f06f83b6c8d7b3535586c06ac806aa7f0cd4f305273f1c81e05f45824d6b028",
    "03-tower-race-b": "sha256:3e63725e4c80ca0cbbafa4f1c1fff40733cd4b375ad047c94516334828d2e277",
    "04-tower-trade-a": "sha256:e707547ce030dbdaa350936aede97bca180c4eb98f6f95d0261ebde27be4a3fc",
    "04-tower-trade-b": "sha256:154132631b6934320601057e344b48f97cdfe06120224c721ef572203eb6d81b",
}


def config():
    # Reuse the disclosed Planner settings and ordinary defend rubric.
    base = json.loads((OUT / "02-reserve-counter-a/tests/task.json").read_text())
    keys = ("planner", "agent_team", "opponent", "action_mode", "foundation_dataset")
    cfg = {key: deepcopy(base[key]) for key in keys}
    own = ["IceGolemite", "Skeletons", "HogRider", "Musketeer", "Cannon", "Fireball", "Log", "IceSpirits"]
    enemy = ["Golem", "ThreeMusketeers", "Pekka", "MegaKnight", "LavaHound", "Rocket", "Lightning", "RoyalRecruits"]
    cfg.update(id=TASK, family=5, title="One-hit Hog defense: three elixir to survive",
               difficulty="hard", benchmark="RoyaleBench Tactics", version="2.2.0", seed=1,
               decision_ticks=10, agent_deck=own, opponent_deck=enemy,
               player_deck_name="hog-cycle-defense", opponent_deck_name="expensive-reserve",
               control=False, source_clip="https://www.tiktok.com/@clashchallenger1/video/7704162569065352478",
               objective="Your left princess tower has 1 HP: a single Hog hit destroys it and fails the task. "
                         "You start with 3 elixir and may spend only 3 in total. "
                         "Keep all three crown towers alive for 16 seconds, take zero additional total "
                         "crown-tower damage, and spend at most 3 elixir. You may submit up to 8 decisions; "
                         "the referee then resolves the remaining time as waits.",
               scenario=dict(start_tick=200, horizon_s=16, elixir=3, opponent_elixir=0,
                             order=own, opponent_order=enemy,
                             tower_hp=[[4824, 1, 3052], [4824, 3052, 3052]],
                             units=[dict(card="HogRider", team=1, x=2.5, y=18.5)],
                             grading="defend", protect_slots=[0, 1, 2], spend_budget=3,
                             damage_limit=0, max_decisions=8))
    return cfg


def instruction(cfg):
    return f"""# RoyaleBench Tactics: {cfg['title']}

## Objective and score

{cfg['objective']}

Reward is 1 only for a completed, independently replayed sequence meeting every requirement;
otherwise 0. Damage includes all your crown towers. Spending includes all accepted card plays
after the starting state, even when elixir regenerates. Affordable overspending is allowed by the
engine and fails the objective. A chat response alone does not complete the task.

## Play

Run `cr` to inspect the board and zero-based hand slots. Run `cr play SLOT X Y` to deploy a card,
or `cr wait` to wait. Command shape only: `cr play 0 8.5 10.5`; choose your own card and position.
Each decision advances **0.5 seconds** of simulated time. Thinking does not advance the clock.
After eight decisions, the referee automatically resolves waits through the end of the window.
Continue until `GAME OVER`. Make each decision yourself; do not write programs, scripts, or loops
to choose or submit moves. Missing or partial play scores zero.

Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32. They are rounded only to engine subtile
precision, with no placement snapping. Malformed syntax does not advance time. A well-formed
illegal action (invalid slot, unaffordable card, or illegal location) consumes one interval as a
wait and reports its rejection. Accepted and rejected attempts are independently replayed.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 1, blue seat, zero additional command delay. Card deployment timers still apply.
There are 170 seconds left in regulation, normal x1 elixir regeneration, and a 16-second scoring
window. You start with **exactly 3 elixir, and only 3 may be spent over the entire defense**.
The engine's normal elixir bar still regenerates, but spending any of that beyond your three-elixir
allowance fails the task, even if the engine accepts the play. There is no valid extra-elixir rescue.
Your crown towers have HP: king 4824, **left princess 1**, right princess 3052.
One Hog hit destroys your left princess tower and fails the task. The opponent's towers have HP:
king 4824, left princess 3052, right princess 3052. All towers are alive, with zero crowns on both sides.

The only troop on the starting board is an enemy **full-health HogRider (1697 HP) at (2.5, 18.5)**,
already active and approaching your left bridge. You have no troops or buildings deployed.
Your princess towers are centered at (3.5, 6.5) and (14.5, 6.5); the river is around y=15–17.
`cr` reports exact current unit positions, HP, tower HP, elixir, hand slots, and next card.

Starting hand, in slot order: {', '.join(cfg['scenario']['order'][:4])}.
Your exact subsequent draw queue: {', '.join(cfg['scenario']['order'][4:])}.
Deck: IceGolemite (Ice Golem, 2), Skeletons (1), HogRider (4), Musketeer (4), Cannon (3),
Fireball (4), Log (2), IceSpirits (Ice Spirit, 1). Played cards return to the back of the queue;
slots refill after the engine's normal delay. Elixir regenerates to a maximum of 10.

There are **no additional enemy deployments during the scoring window**. The fixed opponent is
the existing deterministic Planner (10-second horizon, three plies, top 4, 3 answers, margin 40,
elixir value 150 HP, quiet-score prefilter, workers=0), with privileged engine information.
It starts with zero elixir and a deck whose cheapest cards cost six, so it cannot afford a play
within 16 seconds at x1 regeneration. Its disclosed deck is {', '.join(cfg['opponent_deck'])}.

Princess towers destroyed award one crown; losing the king ends the match. For this task, survival,
zero additional crown-tower damage, and the spending limit determine success after the full window.
"""


def play(cfg, path, actions):
    ref = make_referee(cfg)
    entries = []
    try:
        while not ref.over:
            action = actions.get(ref.decision, {"cmd": "wait"})
            entries.append(ref.entry(action, 5.0))
            ref.act_action(action)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(e) + "\n" for e in entries))
        return ref.outcome()
    finally:
        ref.opponent.close()


def validate(cfg, out):
    """Calibrate references, timing/placement ablations, and authenticated-log failures."""
    ice = dict(cmd="play", slot=0, x=1.5, y=11.5)
    skeletons = dict(cmd="play", slot=1, x=3.5, y=13.5)
    cases = {
        "reference": {1: ice, 2: skeletons},
        "wait": {},
        "ice-only": {1: ice},
        "skeletons-only": {2: skeletons},
        "one-tile-lower": {1: ice, 2: dict(skeletons, y=12.5)},
        "both-half-second-earlier": {0: ice, 1: skeletons},
        "overspend": {6: dict(cmd="play", slot=2, x=14.5, y=13.5)},
        "rejected-placement": {1: dict(ice, x=-1)},
        "previous-opus-policy": {0: dict(ice, x=3.5, y=12),
                                 2: dict(skeletons, y=13)},
    }
    dest = out / TASK
    rows = {}
    for name, actions in cases.items():
        path = dest / f"{name}.jsonl"
        outcome = play(cfg, path, actions)
        a, b = verify(cfg, path, None), verify(cfg, path, None)
        expected = int(name == "reference")
        if a != b or a["rewards"]["reward"] != expected or a["rewards"]["integrity"] != 1:
            raise ValueError(f"Calibration failed: {name}: {a}")
        if outcome["opponent_plays"]:
            raise ValueError("Unexpected opposing deployment")
        if name in {"wait", "one-tile-lower", "previous-opus-policy"} and outcome["crowns_against"] != 1:
            raise ValueError(f"The first Hog hit must cost a tower: {name}")
        rows[name] = dict(reward=expected, deterministic=True, outcome=outcome)
    for name, content in (("empty", ""), ("malformed", "not json\n"),
                          ("wrong-schema", '{"action": []}\n')):
        path = dest / f"{name}.jsonl"
        path.write_text(content)
        report = verify(cfg, path, None)
        if report["rewards"]["reward"] != 0:
            raise ValueError(f"Bad log rewarded: {name}")
        rows[name] = dict(reward=0)
    report = dict(task=TASK, config_sha256=digest(cfg), cases=rows,
                  reference_log_sha256=hashlib.sha256((dest / "reference.jsonl").read_bytes()).hexdigest())
    atomic_json(dest / "validation.json", report)
    return report


def build(out=OUT, evidence=EVIDENCE):
    out, evidence = Path(out), Path(evidence)
    if out.is_symlink():
        raise ValueError("Refusing to replace a symlink")
    unknown = {p.parent.name for p in out.glob("*/task.toml")} - {*SOURCE_DIGESTS, TASK}
    if unknown:
        raise ValueError(f"Output contains unrelated tasks: {sorted(unknown)}")
    for name, expected in SOURCE_DIGESTS.items():
        if task_digest(OUT / name) != expected:
            raise ValueError(f"Published Tactics @3 source changed: {name}")
    cfg = config()
    validation = validate(cfg, evidence)
    template = OUT / "01-timed-spell-a"
    if packaged_protocol_digest(template) != FOUNDATION_PROTOCOL:
        raise ValueError("Frozen coordinate runtime changed")
    # Gameplay files must match the source used for local calibration. Keep the frozen viewer too.
    for name in RUNTIME:
        if name not in {"replay.py", "replay.html"}:
            if (Path(__file__).parent / name).read_bytes() != (template / "environment/referee" / name).read_bytes():
                raise ValueError(f"Local gameplay differs from the published runtime: {name}")
    with tempfile.TemporaryDirectory(prefix="tactics-hog-") as temporary:
        stage = Path(temporary)
        task = stage / TASK
        shutil.copytree(template, task)
        text = instruction(cfg)
        packaged = dict(cfg, task_id=TASK, instruction_sha256=digest(text),
                        rubric="scenario-objective-coordinates-v1", capture_schema_version="1.0",
                        resources={"agent_timeout_s": 3600, "verifier_timeout_s": 600,
                                   "cpus": 1, "memory_mb": 2048, "storage_mb": 4096})
        for relative in ("environment/task.json", "tests/task.json"):
            atomic_json(task / relative, packaged)
        (task / "instruction.md").write_text(text)
        (task / "solution/replay_reference.py").write_text(SOLUTION)
        shutil.copyfile(evidence / TASK / "reference.jsonl", task / "solution/reference.jsonl")
        config_toml = tomllib.loads((task / "task.toml").read_text())
        config_toml["task"].update(name=f"royalebench/tactics-{TASK}", description=cfg["objective"])
        config_toml["metadata"].update(difficulty="hard", deck=cfg["player_deck_name"], seed=1,
                                       decision_ticks=10, dataset_version=cfg["version"], family=5,
                                       opponent_deck=cfg["opponent_deck_name"])
        (task / "task.toml").write_text(tomli_w.dumps(config_toml))
        problems = task_problems(load_benchmark(stage).tasks[TASK])
        if problems or packaged_protocol_digest(task) != FOUNDATION_PROTOCOL:
            raise ValueError(problems or "New task changed the runtime")
        out.mkdir(parents=True, exist_ok=True)
        if out.resolve() != OUT.resolve():
            for name in SOURCE_DIGESTS:
                target = out / name
                if target.exists() and task_digest(target) != SOURCE_DIGESTS[name]:
                    raise ValueError(f"Refusing to overwrite {target}")
                shutil.copytree(OUT / name, target, dirs_exist_ok=True)
        target = out / TASK
        if target.is_symlink():
            raise ValueError("Refusing to replace a symlink")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(task, target)
    old = json.loads((OUT / "manifest.json").read_text())
    manifest = dict(old, version=cfg["version"], runnable_tasks=[*SOURCE_DIGESTS, TASK],
                    source_dataset="royalebench/royalebench-tactics@3",
                    source_task_digests=SOURCE_DIGESTS, task_count=8,
                    status="Seven unchanged @3 tasks plus a one-HP-tower, three-elixir Hog defense; hosted checks recorded separately.")
    manifest["tasks"] = [r for r in old["tasks"] if r["id"] != TASK] + [dict(
        id=TASK, family=5, status="local-validated", reason=None, validation=validation)]
    atomic_json(out / "manifest.json", manifest)
    if out.resolve() != OUT.resolve():
        shutil.copyfile(OUT / "benchmark.toml", out / "benchmark.toml")
    (out / "README.md").write_text("# RoyaleBench Tactics\n\nEight coordinate tasks: the seven unchanged @3 packages plus a one-HP-tower Hog defense with three starting elixir and a three-elixir total spending limit.\nSee [the guide](../../docs/tactics.md). Rebuild with `python -m cr_arena.build_tactics_hog`.\n")
    for name, expected in SOURCE_DIGESTS.items():
        if task_digest(out / name) != expected:
            raise ValueError(f"Source task changed during build: {name}")
    atomic_json(evidence / "build.json", dict(source_dataset="royalebench/royalebench-tactics@3",
                protocol_sha256=FOUNDATION_PROTOCOL, source_task_digests=SOURCE_DIGESTS,
                new_task=TASK, new_task_digest=task_digest(out / TASK), task_count=8))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    build(args.out, args.evidence)
    print(f"Built eight tasks under {args.out}")


if __name__ == "__main__":
    main()
