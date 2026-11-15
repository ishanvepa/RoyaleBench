"""Append two clip-inspired defenses to the eight byte-frozen Tactics @5 tasks.

    python -m cr_arena.build_tactics_clips
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import tempfile
import tomllib

import tomli_w
from valkyrie.sdk.task_content import task_digest

from rb_evals.benchmarks import load_benchmark, task_problems
from .build_tactics import FOUNDATION_PROTOCOL, OUT
from .build_tactics_hog import SOURCE_DIGESTS as ORIGINAL_DIGESTS, config as hog_config, play
from .coordinate_benchmark import packaged_protocol_digest, RUNTIME, SOLUTION
from .royale_task import verify
from .telemetry import atomic_json, digest

SOURCE = "royalebench/royalebench-tactics@5"
SOURCE_DIGESTS = {**ORIGINAL_DIGESTS,
    "05-hog-body-block": "sha256:d349207ed4074ba42409a7a4ca3a6e8d367dea3bd6d9ec470755f13224a559ed"}
TASKS = ("06-mini-pekka-kite", "07-balloon-fireball")
EVIDENCE = Path("runs/tactics-clips")
VERSION = "2.3.0"


def configs():
    own = ["Skeletons", "Fireball", "Knight", "Archer", "Giant", "Minions", "Cannon", "Zap"]
    result = []
    for task, family, attacker, card, elixir, hp, damage, interval, title, url in (
        (TASKS[0], 6, "MiniPekka", "Skeletons", 1, 1, 0, 10,
         "One-elixir Mini P.E.K.K.A. defense", "https://www.tiktok.com/t/ZTPDWutTM/"),
        (TASKS[1], 7, "Balloon", "Fireball", 4, 241, 240, 20,
         "One-Fireball Balloon defense", "https://www.tiktok.com/t/ZTPD72qTU/"),
    ):
        cfg = deepcopy(hog_config())
        cfg.update(id=task, family=family, title=title, version=VERSION, seed=42,
                   decision_ticks=interval, agent_deck=own, player_deck_name="clip-defense",
                   source_clip=url, source_recreation="docs/tiktok_recreations.md",
                   capability="timing and inward kiting" if family == 6 else "timing and directional spell knockback")
        cfg["objective"] = (
            f"Keep all three crown towers alive for 16 seconds using exactly one {card} play "
            f"and no other card. Spend at most {elixir} elixir and take at most {damage} "
            "additional total crown-tower damage. "
            + ("Your left princess tower has 1 HP: any hit fails. " if family == 6 else
               "Your left princess tower has 241 HP. A Balloon attack destroys it; its 240-damage "
               "death bomb is allowed and must be included in the damage total. ")
            + "You may wait before playing. After your one accepted card play, or after 12 "
              "decisions, the referee resolves the remaining window as waits."
        )
        cfg["scenario"].update(order=own, start_tick=200, horizon_s=16, elixir=elixir,
            tower_hp=[[4824, hp, 3052], [4824, 3052, 3052]],
            units=[dict(card=attacker, team=1, x=3.5, y=20.5)],
            only_card=card, grading="one_spell", protect_slots=[0, 1, 2],
            spend_budget=elixir, damage_limit=damage, max_decisions=12)
        result.append(cfg)
    return result


def instruction(cfg):
    skeletons = cfg["family"] == 6
    attacker = "MiniPekka (Mini P.E.K.K.A., 1390 HP)" if skeletons else "Balloon (1676 HP)"
    card = cfg["scenario"]["only_card"]
    return f"""# RoyaleBench Tactics: {cfg['title']}

## Objective and score

{cfg['objective']}

Reward is 1 only for a completed, independently replayed sequence meeting every requirement;
otherwise 0. Damage is summed across all three of your crown towers over the full window,
including delayed explosions. Spending counts all accepted card plays. A chat response alone
does not complete the task. These are survival objectives, not full-match wins.

## Play

Run `cr` to inspect the current board and zero-based hand slots. Use `cr play SLOT X Y` to play
or `cr wait` to wait. Command shape only: `cr play 0 8.5 10.5`; choose your own timing and position.
Each decision advances **{'0.5 seconds' if skeletons else '1 second'}** of simulated time.
Thinking does not advance the clock. Only **{card}** may be played, exactly once. Other cards
are present in the hand but are unavailable for this scenario. After an accepted {card} play,
the referee resolves the rest of the 16 seconds automatically. If you have not played after
12 decisions, it finishes with waits; that fails. Continue until `GAME OVER`. Make each
decision yourself; do not write programs, scripts, or loops to choose or submit moves.
Missing or partial play scores zero.

Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32, your back edge at y=0. Coordinates
are rounded only to engine subtile precision, with no placement snapping by the referee.
Malformed syntax does not advance time. A well-formed illegal action (including another card,
invalid slot, unaffordable card, or illegal location) consumes one interval as a wait, spends
no elixir and reports its rejection. Attempts and accepted placements are independently replayed.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 42, blue seat, zero additional command delay. Card deployment timers and spell flight time
still apply. There are 170 seconds left in regulation, normal x1 elixir regeneration, and a
16-second scoring window. You start with {cfg['scenario']['elixir']} elixir. The elixir bar
regenerates to a maximum of 10; the one-card restriction and spending limit remain in force.

Your crown towers have HP: king 4824, left princess {cfg['scenario']['tower_hp'][0][1]}, right
princess 3052. The opponent's towers have HP: king 4824, left princess 3052, right princess 3052.
All six towers are alive and both sides have zero crowns. Your princess towers are centered at
(3.5, 6.5) and (14.5, 6.5); the river is around y=15–17.

The only troop on the starting board is an enemy **full-health {attacker} at (3.5, 20.5)**,
already active and approaching your left bridge. You have no deployed troops or buildings.
`cr` reports current unit positions and HP, tower HP, elixir, hand slots, and next card.

Starting hand in slot order: Skeletons (1 elixir), Fireball (4), Knight (3), Archer (3).
Subsequent draw queue: Giant (5), Minions (3), Cannon (3), Zap (2).
The spell restriction is {'not applicable: only Skeletons is available' if skeletons else 'exactly one Fireball; no other card is available'}.

There are **no additional enemy deployments during this window**. The fixed opponent is the
existing deterministic Planner (10-second horizon, three plies, top 4, 3 answers, margin 40,
elixir value 150 HP, quiet-score prefilter, workers=0), with privileged engine information.
It starts with zero elixir and a deck whose cheapest cards cost six, so it cannot afford a play
within 16 seconds at x1 regeneration. Its deck is {', '.join(cfg['opponent_deck'])}.
Losing a princess awards the opponent a crown; losing your king ends the match.
"""


def cases(cfg):
    small = cfg["family"] == 6
    action = dict(cmd="play", slot=0 if small else 1, x=7.5 if small else 3.5,
                  y=13.5 if small else 7.5)
    when = 6 if small else 10
    return {
        "reference": {when: action}, "wait": {}, "immediate": {0: action},
        "mistimed": {when + 1 if small else when - 1: action},
        "misplaced": {when: dict(action, x=6.5 if small else 8.5)},
        "rejected-placement": {when: dict(action, x=-1)},
        "wrong-card": {when: dict(action, slot=1 if small else 0)},
    }


def validate(cfg, evidence):
    dest = evidence / cfg["id"]
    dest.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name, actions in cases(cfg).items():
        path = dest / f"{name}.jsonl"
        outcome = play(cfg, path, actions)
        report = verify(cfg, path, None)
        expected = int(name == "reference")
        if report["rewards"]["reward"] != expected or report["rewards"]["integrity"] != 1:
            raise ValueError(f"Calibration failed: {cfg['id']}/{name}: {report}")
        if outcome["opponent_plays"] or outcome["elapsed_s"] != 16:
            raise ValueError(f"Unexpected deployment or truncated window: {cfg['id']}/{name}")
        if name == "reference":
            repeated = verify(cfg, path, None)
            if report != repeated or outcome["spent_elixir"] != cfg["scenario"]["spend_budget"]:
                raise ValueError("Reference must be deterministic and use the stated card budget")
        rows[name] = dict(reward=expected, integrity=1, outcome=outcome)
    valid = (dest / "reference.jsonl").read_text().splitlines()
    tampered = json.loads(valid[-1]); tampered["state_hash"] = "invalid"
    bad_logs = {
        "empty": "", "malformed": "not json\n", "wrong-schema": '{"action": []}\n',
        "wrong-type": '[]\n', "partial": valid[0] + "\n",
        "tampered": "\n".join([*valid[:-1], json.dumps(tampered)]) + "\n",
    }
    for name, content in bad_logs.items():
        path = dest / f"{name}.jsonl"; path.write_text(content)
        report = verify(cfg, path, None)
        if report["rewards"]["reward"] != 0:
            raise ValueError(f"Bad log rewarded: {cfg['id']}/{name}")
        rows[name] = dict(reward=0, completed=report["completed"], integrity=report["rewards"]["integrity"])
    row = dict(task=cfg["id"], config_sha256=digest(cfg), cases=rows, reference_deterministic=True,
               reference_log_sha256=hashlib.sha256((dest / "reference.jsonl").read_bytes()).hexdigest())
    atomic_json(dest / "validation.json", row)
    return row


def build(out=OUT, evidence=EVIDENCE):
    out, evidence = Path(out), Path(evidence)
    protected = [Path("benchmarks") / name for name in ("royalebench-v1", "royalebench-v3", "royalebench-coordinates")]
    if any(out.resolve() == p.resolve() or p.resolve() in out.resolve().parents for p in protected):
        raise ValueError("Cannot overwrite a foundation dataset")
    if out.is_symlink() or (out.exists() and not (out / "manifest.json").is_file()):
        raise ValueError("Refusing to replace an unrecognized dataset directory")
    unknown = {p.parent.name for p in out.glob("*/task.toml")} - {*SOURCE_DIGESTS, *TASKS}
    if unknown:
        raise ValueError(f"Output contains unrelated tasks: {sorted(unknown)}")
    for name, expected in SOURCE_DIGESTS.items():
        if task_digest(OUT / name) != expected:
            raise ValueError(f"Published @5 source changed: {name}")
    template = OUT / "05-hog-body-block"
    if packaged_protocol_digest(template) != FOUNDATION_PROTOCOL:
        raise ValueError("Frozen coordinate runtime changed")
    for name in RUNTIME:
        if name not in {"replay.py", "replay.html"} and (Path(__file__).parent / name).read_bytes() != (template / "environment/referee" / name).read_bytes():
            raise ValueError(f"Local gameplay differs from packaged calibration runtime: {name}")
    rows, config_list = [], configs()
    for cfg in config_list:
        validation = validate(cfg, evidence)
        with tempfile.TemporaryDirectory(prefix="tactics-clips-") as temporary:
            stage = Path(temporary); task = stage / cfg["id"]
            shutil.copytree(template, task)
            text = instruction(cfg)
            packaged = dict(cfg, task_id=cfg["id"], instruction_sha256=digest(text),
                rubric="scenario-objective-coordinates-v1", capture_schema_version="1.0",
                resources={"agent_timeout_s": 3600, "verifier_timeout_s": 600,
                           "cpus": 1, "memory_mb": 2048, "storage_mb": 4096})
            for relative in ("environment/task.json", "tests/task.json"):
                atomic_json(task / relative, packaged)
            (task / "instruction.md").write_text(text)
            (task / "solution/replay_reference.py").write_text(SOLUTION)
            shutil.copyfile(evidence / cfg["id"] / "reference.jsonl", task / "solution/reference.jsonl")
            toml = tomllib.loads((task / "task.toml").read_text())
            toml["task"].update(name=f"royalebench/tactics-{cfg['id']}", description=cfg["objective"])
            toml["metadata"].update(difficulty="hard", deck=cfg["player_deck_name"], seed=42,
                decision_ticks=cfg["decision_ticks"], dataset_version=VERSION, family=cfg["family"])
            (task / "task.toml").write_text(tomli_w.dumps(toml))
            problems = task_problems(load_benchmark(stage).tasks[cfg["id"]])
            if problems or packaged_protocol_digest(task) != FOUNDATION_PROTOCOL:
                raise ValueError(problems or "New task changed the frozen runtime")
            out.mkdir(parents=True, exist_ok=True)
            target = out / cfg["id"]
            if target.is_symlink():
                raise ValueError("Refusing to replace a symlink")
            if target.exists(): shutil.rmtree(target)
            shutil.copytree(task, target)
        rows.append(dict(id=cfg["id"], family=cfg["family"], status="local-validated", reason=None, validation=validation))
        print(f"Built {cfg['id']}; reference 1, all {len(validation['cases'])-1} controls 0", flush=True)
    old = json.loads((OUT / "manifest.json").read_text())
    if out.resolve() != OUT.resolve():
        for name, expected in SOURCE_DIGESTS.items():
            target = out / name
            if target.exists() and task_digest(target) != expected:
                raise ValueError(f"Refusing to overwrite {target}")
            shutil.copytree(OUT / name, target, dirs_exist_ok=True)
        shutil.copyfile(OUT / "benchmark.toml", out / "benchmark.toml")
    manifest = dict(old, version=VERSION, runnable_tasks=[*SOURCE_DIGESTS, *TASKS], task_count=10,
        source_dataset=SOURCE, source_task_digests=SOURCE_DIGESTS,
        tasks=[r for r in old["tasks"] if r["id"] not in TASKS] + rows,
        status="Eight unchanged @5 tasks plus two locally validated clip-inspired defenses; hosted validation recorded separately.")
    atomic_json(out / "manifest.json", manifest)
    (out / "README.md").write_text("# RoyaleBench Tactics\n\nTen coordinate tasks: eight unchanged @5 packages plus one-elixir Mini P.E.K.K.A. kiting and a one-Fireball Balloon defense.\nSee [the guide](../../docs/tactics.md). Rebuild with `python -m cr_arena.build_tactics_clips`.\n")
    for name, expected in SOURCE_DIGESTS.items():
        if task_digest(out / name) != expected: raise ValueError(f"Source task changed during build: {name}")
    atomic_json(evidence / "build.json", dict(source_dataset=SOURCE, protocol_sha256=FOUNDATION_PROTOCOL,
        source_task_digests=SOURCE_DIGESTS, new_task_digests={t: task_digest(out / t) for t in TASKS},
        task_count=10, dependencies={p: version(p) for p in ("royalegym", "royalesim", "msgspec")}))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args(); build(args.out, args.evidence)


if __name__ == "__main__": main()
