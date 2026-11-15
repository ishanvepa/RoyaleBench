"""Hard, tower-winning continuations informed by the v6 run audit.

    uv run python -m cr_arena.build_v7 --explore --jobs 4
    uv run python -m cr_arena.build_v7 --calibrate --build --jobs 4

Exploration is not release validation. No model calls or publication occur here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from importlib.metadata import version
import json
from pathlib import Path
import tomllib

from .bots.planner import Planner
from .build_v1 import write
from .coordinate_benchmark import BASE, ROOT, package_task, protocol_digest
from .decks import CLASSIC_DECKS
from .royale_task import make_referee, verify
from .royalebench_v1 import PLANNER, unit
from .telemetry import digest
from .win_benchmark import instruction as win_instruction

TITLE = "RoyaleBench v7"
VERSION = "7.0.0"
OUT = ROOT.parent / "benchmarks/royalebench-v7"
EVIDENCE = ROOT.parent / "runs/royalebench-v7"


def catalog():
    rows = []

    def add(number, slug, title, player, enemy, order, units, own_hp, enemy_hp,
            elixir, opponent_elixir, window, capability, failure, **scenario):
        rows.append(dict(
            id=f"{number:02d}-{slug}", family=number, title=title, difficulty="hard",
            benchmark=TITLE, version=VERSION, seed=1700 + number, agent_team=0,
            agent_deck=list(CLASSIC_DECKS[player]), opponent_deck=list(CLASSIC_DECKS[enemy]),
            player_deck_name=player, opponent_deck_name=enemy, csv_win_rate=None,
            opponent="planner", planner=deepcopy(PLANNER), decision_ticks=40,
            action_mode="coordinates-v1", release_gate=None,
            objective=f"Win the actual match by destroying an enemy crown tower within the next {window} seconds. "
                      "The position starts with 60 seconds of overtime remaining. The scoring window ends before "
                      "the overtime HP tiebreak: survival, an HP lead, and an unfinished match receive zero credit.",
            capability=capability, expected_failure=failure,
            scenario=dict(start_tick=4800, horizon_s=window, elixir=elixir,
                          opponent_elixir=opponent_elixir, order=order,
                          opponent_order=list(CLASSIC_DECKS[enemy]), units=units,
                          grading="win", tower_hp=[[4824, *own_hp], [4824, 3052, enemy_hp]],
                          disclose_queue=True, **scenario)))

    add(1, "critical-cycle-conversion", "Convert a critical defense into sustained damage",
        "hog-2.6-cycle", "giant-beatdown",
        ["IceSpirits", "Skeletons", "IceGolemite", "Log", "Cannon", "Fireball", "HogRider", "Musketeer"],
        [unit("Giant", 3.5, 12, hp=2500)], (250, 3052), 900, 7, 0, 28,
        "Preserve a critical tower while cycling into repeated win-condition damage",
        "Reuse a loose building pull or spend defensive control on premature tower damage")
    add(2, "second-wave-air-race", "Win an air race through a reserved second wave",
        "giant-beatdown", "lavaloon",
        ["Minions", "Fireball", "Knight", "Cannon", "Giant", "Archer", "Musketeer", "Zap"],
        [unit("Giant", 3.5, 20, team=0), unit("Balloon", 3.5, 10), unit("Minions", 3.5, 22)],
        (400, 3052), 1800, 9, 3, 30,
        "Allocate air defense and offensive support through a disclosed second Minions wave",
        "Use the old single-building race without preserving an answer to the second wave",
        scheduled_attack=dict(card="Minions", after_s=4, x=3.5, y=22))
    add(3, "supported-tank-conversion", "Convert a supported-tank defense into a crown",
        "log-bait", "giant-beatdown",
        ["InfernoTower", "Knight", "GoblinGang", "Log", "Rocket", "Princess", "IceSpirits", "GoblinBarrel"],
        [unit("Giant", 3.5, 15.5), unit("Musketeer", 3.5, 19.5)],
        (700, 3052), 1600, 10, 0, 36,
        "Separate tank and support, then convert surviving defenders and spell cycles into lethal",
        "Spend all regenerated elixir on defense or stop with an HP lead that earns no reward")
    add(4, "split-lane-conversion", "Defend ground and air in opposite lanes, then connect",
        "hog-2.6-cycle", "lavaloon",
        ["Cannon", "Musketeer", "IceSpirits", "HogRider", "IceGolemite", "Skeletons", "Fireball", "Log"],
        [unit("Giant", 3.5, 15), unit("Balloon", 14.5, 13, hp=1200)],
        (600, 600), 900, 8, 0, 32,
        "Allocate different counters across two lanes and preserve enough tempo for a Hog conversion",
        "Overdefend one lane, lose the other tower, or fail to turn the defense into damage")
    # A legal custom eight-card deck containing both members of the opening wave.
    rows[-1]["opponent_deck"] = ["Giant" if c == "LavaHound" else c for c in rows[-1]["opponent_deck"]]
    rows[-1]["scenario"]["opponent_order"] = list(rows[-1]["opponent_deck"])
    rows[-1]["opponent_deck_name"] = "giant-balloon"
    return rows


# Private reference policy: this module is never included in an agent environment.
OPENINGS = {
    1: [("IceSpirits", 3.5, 10), ("Cannon", 7, 11.5), ("Fireball", 3.5, 25.5),
        ("HogRider", 3.5, 15), ("Log", 4.982, 8.623), ("IceSpirits", 4.495, 9.766)],
    2: [("Cannon", 3.5, 13.5), ("Fireball", 3.5, 23), ("Minions", 3.5, 10.5),
        ("Musketeer", 3.5, 15), ("Zap", 3.5, 24), ("Archer", 3.5, 15)],
    3: [("InfernoTower", 3.5, 10.5), ("Knight", 3.5, 13.5),
        ("Rocket", 3.5, 25.5), ("Log", 3.5, 22), None],
    4: [("Musketeer", 14.5, 12), ("IceSpirits", 14.5, 10), ("Cannon", 7, 11.5),
        ("Skeletons", 5, 11), ("HogRider", 3.5, 15)],
}


def play(cfg, path, policy="reference"):
    ref = make_referee(cfg)
    planner = Planner(ref.game.decks, cfg["seed"], 0, **cfg["planner"]) if policy == "reference" else None
    entries = []
    try:
        while not ref.over:
            action = dict(cmd="wait")
            if planner:
                opening = OPENINGS[cfg["family"]]
                if ref.decision < len(opening) and opening[ref.decision] is not None:
                    card, x, y = opening[ref.decision]
                    slot = next(i for i, cid in enumerate(ref.game.state.players[0].hand)
                                if ref.game.card_name(cid) == card)
                    action = dict(cmd="play", slot=slot, x=x, y=y)
                elif ref.decision >= len(opening):
                    chosen, _ = planner.act(ref.game.engine.save_state())
                    if chosen:
                        _, slot, x, y = chosen
                        x, y = ref.game.own_tiles(0, x, y)
                        action = dict(cmd="play", slot=slot, x=x, y=y)
            elif policy in ("spell-rush", "bridge-rush"):
                moves = [m for m in ref.game.legal_moves(0) if m.slot >= 0]
                spells = [m for m in moves if m.card in ("Fireball", "Rocket", "Log", "Zap")
                          and m.target == "enemy left princess tower"]
                attacks = [m for m in moves if m.card in ("HogRider", "Giant", "GoblinBarrel")]
                choices = (spells if policy == "spell-rush" else attacks) or sorted(moves, key=lambda m: (m.cost, m.index))
                if choices:
                    m = choices[0]
                    x, y = ref.game.own_tiles(0, m.x, m.y)
                    action = dict(cmd="play", slot=m.slot, x=x, y=y)
            entries.append(ref.entry(action, 5.0))
            ref.act_action(action)
            if planner:
                print(f"{cfg['id']}: decision {ref.decision}, elapsed {(ref.tick-ref.start_tick)/20:.2f}s", flush=True)
        write(path, "".join(json.dumps(e) + "\n" for e in entries))
        return ref.outcome()
    finally:
        if planner:
            planner.close()
        ref.opponent.close()


def explore(cfg):
    path = EVIDENCE / "exploration" / cfg["id"] / "reference.jsonl"
    outcome = play(cfg, path)
    write(path.with_name("outcome.json"), json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(dict(task=cfg["id"], result=outcome["result"], elapsed_s=outcome["elapsed_s"],
                          plays=outcome["plays"], opponent_plays=len(outcome["opponent_plays"]))), flush=True)


def calibrate(cfg):
    protocol = protocol_digest()
    dest = EVIDENCE / cfg["id"]
    explored = EVIDENCE / "exploration" / cfg["id"] / "reference.jsonl"
    reference = dest / "reference.jsonl"
    # Authenticate cached actions against the current exact state; stale hashes fail.
    source = next((p for p in (reference, explored) if p.exists()
                   and verify(cfg, p, None)["rewards"]["reward"] == 1), None)
    if source is None:
        play(cfg, reference)
    elif source != reference:
        write(reference, source.read_text())
    first, second = verify(cfg, reference, None), verify(cfg, reference, None)
    if first != second or first["rewards"]["reward"] != 1 or first["rewards"]["integrity"] != 1:
        raise ValueError(f"{cfg['id']}: no deterministic winning reference")
    if first["outcome"]["crowns_for"] < 1 or first["outcome"]["ticks"] >= 6000:
        raise ValueError("reference must take a crown before the overtime tiebreak")
    negative = {}
    for policy in ("wait", "spell-rush", "bridge-rush"):
        path = dest / f"{policy}.jsonl"
        play(cfg, path, policy)
        negative[policy] = verify(cfg, path, None)["rewards"]["reward"]
    for name, content in (("empty", ""), ("malformed", "not json\n"), ("wrong-type", "[]\n"),
                          ("partial", reference.read_text().splitlines()[0] + "\n")):
        path = dest / f"{name}.jsonl"
        write(path, content)
        negative[name] = verify(cfg, path, None)["rewards"]["reward"]
    if any(negative.values()) or protocol_digest() != protocol:
        raise ValueError(f"{cfg['id']}: controls or runtime changed: {negative}")
    row = dict(task=cfg["id"], config_sha256=digest(cfg), protocol_sha256=protocol,
               reference_log_sha256=digest(reference.read_text()), reward=1, integrity=1,
               deterministic=True, negative_rewards=negative, reference_outcome=first["outcome"],
               decisions=first["decisions_applied"], frontier_model_runs=[],
               reference_policy="private explicit opening followed by privileged Planner; log proves solvability")
    write(dest / "validation.json", json.dumps(row, indent=2) + "\n")
    print(f"Validated {cfg['id']}: crown win, deterministic replay, 7 controls zero", flush=True)
    return row


def instruction(cfg):
    text = win_instruction(cfg)
    # A deliberately shorter window, rather than changed rules, excludes HP-tiebreak wins.
    text = text.replace("if it produces an actual win at the overtime deadline. A seed-parity tiebreak is part of the engine rules.",
                        "if it produces a completed match win. This scoring window ends before the overtime deadline; "
                        "the HP/seed tiebreak cannot award success here.")
    return text


def build():
    import tomli_w
    configs, rows = catalog(), []
    protocol = protocol_digest()
    for package, expected in json.loads((BASE / "manifest.json").read_text())["dependencies"].items():
        if version(package) != expected:
            raise ValueError(f"{package} must be {expected}")
    unexpected = {p.parent.name for p in OUT.glob("*/task.toml")} - {c["id"] for c in configs}
    if unexpected:
        raise ValueError(f"unexpected existing tasks: {sorted(unexpected)}")
    # Check the whole cohort before writing any task.
    for cfg in configs:
        dest = EVIDENCE / cfg["id"]
        row = json.loads((dest / "validation.json").read_text())
        if (row["config_sha256"] != digest(cfg) or row["protocol_sha256"] != protocol
                or row["reference_log_sha256"] != digest((dest / "reference.jsonl").read_text())
                or row["reward"] != 1 or row["integrity"] != 1 or row["deterministic"] is not True
                or set(row["negative_rewards"]) != {"wait", "spell-rush", "bridge-rush", "empty", "malformed", "wrong-type", "partial"}
                or any(row["negative_rewards"].values())):
            raise ValueError(f"stale or failing calibration: {cfg['id']}")
        report = verify(cfg, dest / "reference.jsonl", None)
        if report["rewards"]["reward"] != 1 or report["outcome"] != row["reference_outcome"]:
            raise ValueError(f"winning reference changed: {cfg['id']}")
        rows.append(row)
    template = BASE / "08-cycle-to-lethal"
    for cfg in configs:
        package_task(cfg, OUT, EVIDENCE, template, task_prefix="v7-", task_instruction=instruction(cfg),
                     rubric="binary-crown-win-coordinates-v1")
        path = OUT / cfg["id"] / "task.toml"
        task = tomllib.loads(path.read_text())
        task["task"]["description"] = (f"{cfg['capability']}. time_left=60s overtime | "
            f"window={cfg['scenario']['horizon_s']}s | player={cfg['player_deck_name']} | "
            f"opponent_deck={cfg['opponent_deck_name']} | opponent=planner | seed={cfg['seed']} | "
            "scoring=completed crown win before window ends")
        task["metadata"].update(difficulty="hard", family=cfg["family"], seed=cfg["seed"],
            deck=cfg["player_deck_name"], opponent_deck=cfg["opponent_deck_name"], control=False)
        write(path, tomli_w.dumps(task))
    if protocol_digest() != protocol:
        raise ValueError("runtime changed during packaging")
    manifest = dict(benchmark=TITLE, version=VERSION, action_mode="coordinates-v1",
        rubric="binary-crown-win-coordinates-v1", protocol_sha256=protocol,
        runnable_tasks=[c["id"] for c in configs],
        dependencies={p: version(p) for p in ("royalegym", "royalesim", "msgspec")}, tasks=rows,
        aggregation="Mean binary completed-match win reward; all tasks equally weighted.",
        status="Local validation complete; container and hosted evidence recorded separately.")
    write(OUT / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    write(EVIDENCE / "validation.json", json.dumps(manifest, indent=2) + "\n")
    write(OUT / "benchmark.toml", tomli_w.dumps({"benchmark": dict(title=TITLE, kind="eval",
          description=f"{len(configs)} hard continuations requiring a tower-winning conversion before overtime tiebreak.")}))
    write(OUT / "README.md", "# RoyaleBench v7\n\nHard tower-winning continuations against Planner.\n"
          "See [design, validation and calibration](../../docs/royalebench_v7.md).\n"
          "Build with `uv run python -m cr_arena.build_v7 --calibrate --build --jobs 4`.\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--explore", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--tasks", nargs="*", type=int)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
    for enabled, operation in ((args.explore, explore), (args.calibrate, calibrate)):
        if enabled:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                list(pool.map(operation, configs))
    if args.build:
        build()


if __name__ == "__main__":
    main()
