"""Win-only strategic continuations; calibration and packaging are kept separate.

    uv run python -m cr_arena.win_benchmark --calibrate
    uv run python -m cr_arena.win_benchmark --build
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from importlib.metadata import version
from functools import lru_cache
import json
from pathlib import Path
import shutil
import tomllib

from .bots.planner import Planner
from .build_v1 import write
from .coordinate_benchmark import (BASE, ROOT, RUNTIME, SOLUTION, instruction as coordinate_instruction,
                                   protocol_digest)
from .royale_task import make_referee, verify
from .royalebench_v1 import PLANNER, unit
from .decks import CLASSIC_DECKS
from .telemetry import VERSION as CAPTURE_VERSION, digest

TITLE = "RoyaleBench Win"
VERSION = "1.0.0"
OUT = ROOT.parent / "benchmarks/royalebench-win"
EVIDENCE = ROOT.parent / "runs/royalebench-win"


@lru_cache(maxsize=1)
def spell_crown_damage():
    """Disclose measured mechanics so damage planning does not test version trivia."""
    from royalegym import RustEngine, deck_ids
    from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode
    from .game import Game
    cards = list(RustEngine().cards())
    result = {}
    for card, deck_name in (("Fireball", "giant-beatdown"), ("Zap", "giant-beatdown"),
                            ("Log", "log-bait"), ("Rocket", "log-bait")):
        order = [card] + [c for c in CLASSIC_DECKS[deck_name] if c != card]
        setup = MatchSetup(decks=[deck_ids(order, cards)] * 2, shuffle=ShuffleMode.NONE,
                           start_tick=3600, elixir_milli=[10000, 0])
        game = Game(order, order, 0, record=False, setup=setup)
        before = game.state.players[1].tower_hp[2]
        x, y = game.engine_point(0, 3.5, 25.5)
        game.engine.step([DeployCommand(0, 0, x, y)], 120)
        result[card] = before - game.state.players[1].tower_hp[2]
        if result[card] <= 0:
            raise ValueError(f"crown damage probe failed: {card}")
    return result


def catalog():
    """Short, forced overtime conversions; every position needs more than one spell."""
    rows = []

    def add(number, slug, title, player, enemy, hand, units, own_hp, enemy_hp,
            elixir=8, opponent_elixir=0, left=24, capability="", failure=""):
        order = hand + [c for c in CLASSIC_DECKS[player] if c not in hand]
        rows.append(dict(
            id=f"{number:02d}-{slug}", family=number, title=title, difficulty="hard",
            benchmark=TITLE, version=VERSION, seed=700 + number, agent_team=0,
            agent_deck=list(CLASSIC_DECKS[player]), opponent_deck=list(CLASSIC_DECKS[enemy]),
            player_deck_name=player, opponent_deck_name=enemy, csv_win_rate=None,
            opponent="planner", planner=deepcopy(PLANNER), decision_ticks=40,
            action_mode="coordinates-v1", release_gate=None,
            objective=f"Win the actual match within the remaining {left} seconds of overtime. "
                      "Surviving, dealing damage, or leading on HP before the match ends earns no credit.",
            capability=capability, expected_failure=failure,
            scenario=dict(start_tick=6000-left*20, horizon_s=left, elixir=elixir,
                          opponent_elixir=opponent_elixir, order=order,
                          opponent_order=list(CLASSIC_DECKS[enemy]), units=units,
                          grading="win", tower_hp=[[4824, own_hp, 3052], [4824, 3052, enemy_hp]],
                          disclose_queue=True)))

    add(1, "cycle-and-connect", "Cycle, defend, and connect a win condition",
        "hog-2.6-cycle", "giant-beatdown", ["IceSpirits", "Skeletons", "IceGolemite", "Log"],
        [unit("Giant", 3.5, 12)], 700, 450, elixir=7, left=18,
        capability="Plan damage beyond the first spell while maintaining a building pull",
        failure="Cast Fireball without arranging the remaining damage before the Giant connects")
    rows[-1]["scenario"]["order"] = ["IceSpirits", "Skeletons", "IceGolemite", "Log", "Cannon", "Fireball", "HogRider", "Musketeer"]
    add(2, "sustained-tower-race", "Sustain a tower race beyond the first defense",
        "giant-beatdown", "lavaloon", ["Minions", "Fireball", "Knight", "Cannon"],
        [unit("Giant", 3.5, 20, team=0), unit("Musketeer", 3.5, 18, team=0),
         unit("Balloon", 3.5, 10), unit("Minions", 3.5, 22)], 305, 3052, elixir=7, left=30,
        capability="Buy enough defensive time while preserving a counterpush and allocating spells",
        failure="Treat one building or one offensive spell as a complete winning plan")
    add(3, "bait-damage-sequence", "Defend a supported tank and sequence finishing damage",
        "log-bait", "giant-beatdown", ["InfernoTower", "Knight", "GoblinGang", "Log"],
        [unit("Giant", 3.5, 15.5), unit("Musketeer", 3.5, 19.5)], 1068, 1000,
        elixir=10, left=24,
        capability="Convert tank/support defense into a multi-card lethal sequence",
        failure="Stabilize the board but run out of time or elixir before the finishing cycle")
    rows[-1]["scenario"]["order"] = ["InfernoTower", "Knight", "GoblinGang", "Log", "Rocket", "Princess", "IceSpirits", "GoblinBarrel"]
    critical = deepcopy(rows[0])
    critical.update(id="04-critical-cycle-and-connect", family=4,
                    title="Cycle and connect with a critical-health tower",
                    capability="Sustain a precise building pull and defensive spell timing until a Hog connects",
                    expected_failure="Reuse a placement that allows a tower hit, or spend Log on tower damage instead of controlling the Giant")
    # A paired HP intervention: retain seed, decks, hand, enemy state and time.
    critical["scenario"]["tower_hp"][0][1] = 250
    rows.append(critical)
    return rows


def play(cfg, path, policy="planner"):
    """Privileged search proves solvability; it is never exposed in the player image."""
    ref = make_referee(cfg)
    planner = Planner(ref.game.decks, cfg["seed"], 0, **cfg["planner"]) if policy == "planner" else None
    entries = []
    try:
        while not ref.over:
            action = {"cmd": "wait"}
            if planner:
                openings = {
                    1: [("Log", 3.5, 22), ("Cannon", 6, 10.5), ("Fireball", 3.5, 25.5),
                        ("HogRider", 3.5, 15), ("IceSpirits", 3.5, 10.5)],
                    2: [("Cannon", 3.5, 13.5), ("Fireball", 3.5, 23), ("Minions", 3.5, 10.5)],
                    3: [("InfernoTower", 3.5, 10.5), ("Knight", 3.5, 13.5),
                        ("Rocket", 3.5, 25.5), ("Log", 3.5, 22), ("GoblinBarrel", 3.5, 25.5)],
                    4: [("IceSpirits", 3.5, 10), ("Cannon", 7, 11.5), ("Fireball", 3.5, 25.5),
                        ("HogRider", 3.5, 15), ("Log", 4.982, 8.623), ("IceSpirits", 4.495, 9.766)],
                }[cfg["family"]]
                if ref.decision < len(openings):
                    card, x, y = openings[ref.decision]
                    hand = ref.game.state.players[0].hand
                    slot = next(i for i, cid in enumerate(hand) if ref.game.card_name(cid) == card)
                    action = dict(cmd="play", slot=slot, x=x, y=y)
                else:
                    chosen, _ = planner.act(ref.game.engine.save_state())
                    if chosen:
                        _, slot, x, y = chosen
                        x, y = ref.game.own_tiles(0, x, y)
                        action = dict(cmd="play", slot=slot, x=x, y=y)
            elif policy == "spell-rush":
                # Deliberately cheap alternative: cycle any affordable card, send spells at tower.
                moves = [m for m in ref.game.legal_moves(0) if m.slot >= 0]
                spells = [m for m in moves if m.card in ("Fireball", "Rocket", "Log", "Zap")
                          and m.target == "enemy left princess tower"]
                choices = spells or sorted(moves, key=lambda m: (m.cost, m.index))
                if choices:
                    m = choices[0]
                    x, y = ref.game.own_tiles(0, m.x, m.y)
                    action = dict(cmd="play", slot=m.slot, x=x, y=y)
            entries.append(ref.entry(action, 5.0))
            ref.act_action(action)
            if policy == "planner" and ref.decision % 5 == 0:
                print(f"{cfg['id']}: reference decision {ref.decision}, elapsed "
                      f"{(ref.tick-ref.start_tick)/20:.1f}s", flush=True)
        write(path, "".join(json.dumps(e) + "\n" for e in entries))
        return ref.outcome()
    finally:
        if planner:
            planner.close()
        ref.opponent.close()


def calibrate(cfg, evidence=EVIDENCE):
    start_protocol = protocol_digest()
    dest = Path(evidence) / cfg["id"]
    reference = dest / "reference.jsonl"
    explored = Path(evidence) / "exploration" / cfg["id"] / "reference.jsonl"
    first = verify(cfg, explored, None) if explored.exists() else None
    if first and first["rewards"]["reward"] == first["rewards"]["integrity"] == 1:
        write(reference, explored.read_text())
    else:
        outcome = play(cfg, reference)
        print(json.dumps(dict(task=cfg["id"], result=outcome["result"], elapsed_s=outcome["elapsed_s"])), flush=True)
        if outcome["result"] != "win":
            raise ValueError(f"{cfg['id']}: no winning reference; keep gated")
        first = verify(cfg, reference, None)
    second = verify(cfg, reference, None)
    print(f"{cfg['id']}: winning reference replayed twice; checking controls", flush=True)
    negative = {}
    for policy in ("wait", "spell-rush"):
        path = dest / f"{policy}.jsonl"
        play(cfg, path, policy)
        negative[policy] = verify(cfg, path, None)["rewards"]["reward"]
    for name, content in (("empty", ""), ("malformed", "not json\n"), ("wrong-type", "[]\n")):
        path = dest / f"{name}.jsonl"
        write(path, content)
        negative[name] = verify(cfg, path, None)["rewards"]["reward"]
    path = dest / "partial.jsonl"
    write(path, reference.read_text().splitlines()[0] + "\n")
    negative["partial"] = verify(cfg, path, None)["rewards"]["reward"]
    if first != second or first["rewards"]["reward"] != 1 or any(negative.values()):
        raise ValueError(f"{cfg['id']}: replay or difficulty controls failed: {negative}")
    if protocol_digest() != start_protocol:
        raise ValueError("runtime sources changed during calibration; retry")
    row = dict(task=cfg["id"], config_sha256=digest(cfg), protocol_sha256=start_protocol,
               reference_log_sha256=digest(reference.read_text()), reward=1, integrity=1,
               deterministic=True, negative_rewards=negative, reference_outcome=first["outcome"],
               decisions=first["decisions_applied"], frontier_model_runs=[],
               reference_policy="explicit defensive opening followed by privileged Planner; actual log is the solvability proof")
    write(dest / "validation.json", json.dumps(row, indent=2) + "\n")
    print(f"Validated {cfg['id']}: actual win, deterministic, all negative controls zero", flush=True)
    return row


def instruction(cfg):
    text = coordinate_instruction(cfg)
    spells = "; ".join(f"{name}: {damage} HP" for name, damage in spell_crown_damage().items()
                       if name in cfg["agent_deck"])
    text = text.replace("## Fixed starting state\n", "Simulator crown damage per cast (measured in the pinned engine): "
                        + spells + ". Spell travel and effect delays still apply.\n\n## Fixed starting state\n")
    text = text.replace("Damage means additional damage to all your crown\ntowers after the starting state. Spending includes all accepted plays, even as elixir regenerates.\nSpending and lane budgets are checked by the verifier; overspending is possible and fails the objective.\nAny stated card restriction or maximum decision count still applies.",
                        "The sole gameplay success condition is an actual match win (engine winner BLUE).\nThere are no spending, lane, damage, card, or decision-count objectives. An HP lead only counts\nif it produces an actual win at the overtime deadline. A seed-parity tiebreak is part of the engine rules.")
    text = text.replace("After the task's maximum decision count, or its single allowed spell, the referee resolves waits.\n", "")
    text = text.replace("For fixed defense windows the stated survival/damage objective determines the score.", "")
    return text


def build(out=OUT, evidence=EVIDENCE):
    """Require fresh replay and all controls before publishing any runnable task."""
    import tomli_w
    for package, expected in json.loads((BASE / "manifest.json").read_text())["dependencies"].items():
        if version(package) != expected:
            raise ValueError(f"{package} must be {expected}")
    out, evidence = Path(out).resolve(), Path(evidence).resolve()
    if out.name != "royalebench-win":
        raise ValueError("output must be a separate royalebench-win dataset")
    configs, rows = catalog(), []
    start_protocol = protocol_digest()
    unexpected = {p.parent.name for p in out.glob("*/task.toml")} - {c["id"] for c in configs}
    if unexpected:
        raise ValueError(f"output contains tasks outside this catalog: {sorted(unexpected)}")
    for cfg in configs:
        dest = evidence / cfg["id"]
        row = json.loads((dest / "validation.json").read_text())
        reference = dest / "reference.jsonl"
        if (row["config_sha256"] != digest(cfg) or row["protocol_sha256"] != protocol_digest()
                or row["reference_log_sha256"] != digest(reference.read_text())
                or row["reward"] != 1 or row["deterministic"] is not True
                or set(row["negative_rewards"]) != {"wait", "spell-rush", "empty", "malformed", "wrong-type", "partial"}
                or any(row["negative_rewards"].values())):
            raise ValueError(f"stale or failing validation: {cfg['id']}")
        report = verify(cfg, reference, None)
        if report["rewards"]["reward"] != 1 or report["outcome"] != row["reference_outcome"]:
            raise ValueError(f"reference replay failed: {cfg['id']}")
        rows.append(row)
    from .build_tasks import START_SERVER, SUDOERS, TEST_SH
    template = BASE / "08-cycle-to-lethal"
    for cfg in configs:
        dest = out / cfg["id"]
        if dest.is_symlink() or dest.resolve().parent != out:
            raise ValueError("unsafe output path")
        if dest.exists():
            shutil.rmtree(dest)
        text = instruction(cfg)
        packaged = dict(cfg, task_id=cfg["id"], instruction_sha256=digest(text),
                        rubric="binary-win-coordinates-v1", capture_schema_version=CAPTURE_VERSION,
                        resources=dict(agent_timeout_s=3600, verifier_timeout_s=600,
                                       cpus=1, memory_mb=2048, storage_mb=4096))
        for source in RUNTIME:
            write(dest / "environment/referee" / source, (ROOT / source).read_text(encoding="utf-8"))
        files = {"environment/Dockerfile": (template / "environment/Dockerfile").read_text(),
                 "environment/cr": (ROOT / "cr_client.py").read_text(),
                 "environment/royale-start-server": START_SERVER, "environment/sudoers": SUDOERS,
                 "environment/task.json": json.dumps(packaged, indent=2) + "\n",
                 "tests/task.json": json.dumps(packaged, indent=2) + "\n",
                 "tests/test.sh": TEST_SH, "instruction.md": text,
                 "solution/solve.sh": "#!/bin/bash\nset -euo pipefail\npython3 /solution/replay_reference.py\n",
                 "solution/replay_reference.py": SOLUTION,
                 "solution/reference.jsonl": (evidence / cfg["id"] / "reference.jsonl").read_text()}
        for relative, content in files.items():
            write(dest / relative, content)
        task = tomllib.loads((template / "task.toml").read_text())
        task["task"].update(name=f"royalebench/win-{cfg['id']}", description=(
            f"{cfg['capability']}. time_left={cfg['scenario']['horizon_s']}s overtime | player={cfg['player_deck_name']} | "
            f"opponent_deck={cfg['opponent_deck_name']} | opponent=planner | seed={cfg['seed']} | "
            "scoring=actual completed match win only"))
        task["metadata"].update(dataset_version=VERSION, action_mode="coordinates-v1", family=cfg["family"],
                                difficulty="hard", seed=cfg["seed"], deck=cfg["player_deck_name"],
                                opponent_deck=cfg["opponent_deck_name"], control=False)
        from .build_v1 import MODEL_API_HOSTS
        task["agent"]["allowed_hosts"] = list(MODEL_API_HOSTS)
        write(dest / "task.toml", tomli_w.dumps(task))
    if protocol_digest() != start_protocol:
        raise ValueError("runtime sources changed during packaging; rebuild")
    manifest = dict(benchmark=TITLE, version=VERSION, action_mode="coordinates-v1",
                    rubric="binary-win-coordinates-v1", protocol_sha256=protocol_digest(),
                    capture_schema_version=CAPTURE_VERSION, runnable_tasks=[c["id"] for c in configs],
                    dependencies={p: version(p) for p in ("royalegym", "royalesim", "msgspec")},
                    tasks=rows, aggregation="Mean binary completed-match win reward; all tasks equally weighted.",
                    status="Local calibration; container and frontier evidence recorded separately.")
    write(out / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    write(out / "benchmark.toml", tomli_w.dumps({"benchmark": dict(title=TITLE, kind="eval",
          description=f"{len(configs)} strategic overtime continuations. Success requires winning the actual match.")}))
    write(out / "README.md", f"# RoyaleBench Win\n\n{len(configs)} win-only coordinate continuations against Planner.\n"
          "See [the guide](../../docs/royalebench_win.md) for design, validation, and results.\n"
          "Build with `uv run python -m cr_arena.win_benchmark --build`.\n")
    write(evidence / "validation.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--tasks", type=int, nargs="*")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--reference-only", action="store_true", help="explore candidates without marking validation complete")
    parser.add_argument("--replay-exploration", action="store_true", help="rebuild a candidate trace from its actions after changing inputs")
    args = parser.parse_args()
    if args.calibrate:
        configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
        if args.jobs == 1:
            for cfg in configs:
                calibrate(cfg)
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                list(pool.map(calibrate, configs))
    if args.reference_only:
        configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(explore_reference, configs))
    if args.replay_exploration:
        configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(replay_exploration, configs))
    if args.build:
        build()


def explore_reference(cfg):
    outcome = play(cfg, EVIDENCE / "exploration" / cfg["id"] / "reference.jsonl")
    write(EVIDENCE / "exploration" / cfg["id"] / "outcome.json", json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(dict(task=cfg["id"], result=outcome["result"], elapsed_s=outcome["elapsed_s"])), flush=True)


def replay_exploration(cfg):
    from .coordinate_benchmark import play as replay_actions
    path = EVIDENCE / "exploration" / cfg["id"] / "reference.jsonl"
    actions = {e["tick"]: e["action"] for e in map(json.loads, path.read_text().splitlines())}
    ref = replay_actions(cfg, path, actions)
    outcome = ref.outcome()
    write(path.with_name("outcome.json"), json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(dict(task=cfg["id"], result=outcome["result"], elapsed_s=outcome["elapsed_s"])), flush=True)


if __name__ == "__main__":
    main()
