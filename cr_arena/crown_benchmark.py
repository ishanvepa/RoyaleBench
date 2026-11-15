"""RoyaleBench Crown: mirror-deck king-tower kills (three-crown wins and king-tower-only duels).

    uv run python -m cr_arena.crown_benchmark --calibrate
    uv run python -m cr_arena.crown_benchmark --build

The grading rule is the unchanged completed-match win. Every window ends before regulation
does, so the match can only be over, with Blue the winner, once the enemy king tower has fallen.
That makes the win a king-tower kill without touching the shared referee runtime.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import tomllib

from .bots.planner import Planner
from .build_v1 import write
from .coordinate_benchmark import BASE, ROOT, RUNTIME, SOLUTION, protocol_digest
from .decks import CLASSIC_DECKS
from .royale_task import make_referee, verify
from .royalebench_v1 import PLANNER, unit
from .telemetry import VERSION as CAPTURE_VERSION, digest
from .win_benchmark import instruction as win_instruction

TITLE = "RoyaleBench Crown"
VERSION = "1.0.0"
OUT = ROOT.parent / "benchmarks/royalebench-crown"
EVIDENCE = ROOT.parent / "runs/royalebench-crown"
PRINCESS_HP, KING_HP = 3052, 4824


def catalog():
    rows = []

    def add(number, slug, title, deck, tank, hand_extra, left_s, horizon_s, elixir, opp_elixir, enemy_hp,
            lane_x, king_only, capability, failure):
        order = list(CLASSIC_DECKS[deck])
        units = [unit(tank, lane_x, 15 if hand_extra else 14, team=0)]
        if hand_extra:
            units.append(unit(hand_extra, lane_x, 12, team=0))
        start = 3600 - left_s * 20
        assert horizon_s <= left_s, "the window must end before regulation does"
        princess = [0, 0] if king_only else None
        foe = princess or [round(enemy_hp[0] * PRINCESS_HP), round(enemy_hp[1] * PRINCESS_HP)]
        own = princess or [PRINCESS_HP, PRINCESS_HP]
        goal = ("Destroy the enemy king tower. Neither side has princess towers; both sides have only a king tower."
                if king_only else
                "Destroy all three enemy towers, including the king tower, for a three-crown win.")
        rows.append(dict(
            id=f"{number:02d}-{slug}", family=number, title=title, difficulty="hard",
            benchmark=TITLE, version=VERSION, seed=800 + number, agent_team=0,
            agent_deck=order, opponent_deck=order, player_deck_name=deck, opponent_deck_name=deck,
            csv_win_rate=None, opponent="planner", planner=deepcopy(PLANNER), decision_ticks=40,
            action_mode="coordinates-v1", release_gate=None,
            objective=f"{goal} You have {horizon_s} seconds, and regulation time does not run out before then, so "
                      "only a destroyed enemy king tower wins. Surviving, dealing damage, or leading on tower HP "
                      "earns no credit. This is a mirror match: both sides play the same deck.",
            capability=capability, expected_failure=failure,
            scenario=dict(start_tick=start, horizon_s=horizon_s, elixir=elixir, opponent_elixir=opp_elixir,
                          order=order, opponent_order=order, units=units, grading="win",
                          tower_hp=[[KING_HP, own[0], own[1]], [KING_HP, foe[1], foe[0]]],
                          disclose_queue=True)))

    add(11, "giant-mirror-three-crown", "Three-crown a Giant mirror", "giant-beatdown", "Giant", "Musketeer",
        110, 105, 7, 4, (.5, .6), 3.5, False,
        "Convert a tank push into three crowns while the mirror opponent defends with the same cards",
        "Take one or two towers, then stall or defend instead of committing to the king tower")
    add(12, "golem-mirror-three-crown", "Three-crown a Golem mirror", "golem-beatdown", "Golem", "Musketeer",
        75, 70, 7, 4, (.65, .75), 3.5, False,
        "Time the Golem's death damage and follow-up pushes to finish every tower inside a short window",
        "Lose the push to a defensive building or counterattack and run out of time")
    add(13, "giant-mirror-king-only", "King-tower duel, Giant mirror", "giant-beatdown", "Giant", None,
        110, 105, 8, 3, None, 3.5, True,
        "Reach and destroy a king tower with no princess towers diverting the opponent's defense",
        "Treat it as a tower race and settle for chip damage that cannot win")
    add(14, "golem-mirror-king-only", "King-tower duel, Golem mirror", "golem-beatdown", "Golem", None,
        75, 70, 7, 5, None, 14.5, True,
        "Push the opposite lane to the previous duel and finish the king tower before time runs out",
        "Send the Golem without support timing and lose it before the king tower is reachable")
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
                chosen, _ = planner.act(ref.game.engine.save_state())
                if chosen:
                    _, slot, x, y = chosen
                    x, y = ref.game.own_tiles(0, x, y)
                    action = dict(cmd="play", slot=slot, x=x, y=y)
            elif policy == "spell-rush":
                moves = [m for m in ref.game.legal_moves(0) if m.slot >= 0]
                spells = [m for m in moves if m.card in ("Fireball", "Rocket", "Log", "Zap", "Lightning", "Earthquake")
                          and "king" in m.target]
                choices = spells or sorted(moves, key=lambda m: (m.cost, m.index))
                if choices:
                    m = choices[0]
                    x, y = ref.game.own_tiles(0, m.x, m.y)
                    action = dict(cmd="play", slot=m.slot, x=x, y=y)
            entries.append(ref.entry(action, 5.0))
            ref.act_action(action)
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
    outcome = play(cfg, reference)
    print(json.dumps(dict(task=cfg["id"], result=outcome["result"], elapsed_s=outcome["elapsed_s"])), flush=True)
    if outcome["result"] != "win":
        raise ValueError(f"{cfg['id']}: no winning reference; keep gated")
    first = verify(cfg, reference, None)
    second = verify(cfg, reference, None)
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
               reference_policy="privileged Planner search; the actual log is the solvability proof")
    write(dest / "validation.json", json.dumps(row, indent=2) + "\n")
    print(f"Validated {cfg['id']}: king kill, deterministic, all negative controls zero", flush=True)
    return row


def build(out=OUT, evidence=EVIDENCE):
    """Require fresh replay and all controls before packaging any runnable task."""
    import tomli_w
    for package, expected in json.loads((BASE / "manifest.json").read_text())["dependencies"].items():
        if version(package) != expected:
            raise ValueError(f"{package} must be {expected}")
    out, evidence = Path(out).resolve(), Path(evidence).resolve()
    if out.name != "royalebench-crown":
        raise ValueError("output must be a separate royalebench-crown dataset")
    configs, rows = catalog(), []
    start_protocol = protocol_digest()
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
        text = win_instruction(cfg)
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
        task["task"].update(name=f"royalebench/crown-{cfg['id']}", description=(
            f"{cfg['capability']}. regulation_left={3600 - cfg['scenario']['start_tick']}t window={cfg['scenario']['horizon_s']}s | "
            f"player={cfg['player_deck_name']} | opponent_deck={cfg['opponent_deck_name']} (mirror) | opponent=planner | "
            f"seed={cfg['seed']} | scoring=king-tower kill (completed match win inside regulation)"))
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
          description=f"{len(configs)} mirror-deck king-tower-kill continuations against Planner.")}))
    write(out / "README.md", f"# RoyaleBench Crown\n\n{len(configs)} mirror-deck king-tower-kill tasks against Planner.\n"
          "Build with `uv run python -m cr_arena.crown_benchmark --build`.\n")
    write(evidence / "validation.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--tasks", type=int, nargs="*")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    if args.calibrate:
        configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(calibrate, configs))
    if args.build:
        build()


if __name__ == "__main__":
    main()
