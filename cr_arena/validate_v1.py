"""Calibrate v1 locally and retain reference decisions plus replay-verified evidence.

    python -m cr_arena.validate_v1 --tasks 1 2 3 --out runs/royalebench-v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

from .bots.planner import Planner
from .royale_task import make_referee, verify
from .royalebench_v1 import TITLE, VERSION, catalog, protocol_digest


class MenuPlanner(Planner):
    """Privileged reference: Planner search restricted to the agent's actual legal menu."""
    def __init__(self, ref):
        self.ref = ref
        super().__init__(ref.game.decks, ref.cfg["seed"], 0, **ref.cfg["planner"])

    def choose(self):
        # Restrict the actual decision, while deeper plies generate candidates from
        # their simulated states (a future hand need not match the current menu).
        plays = [(0, m.slot, m.x, m.y) for m in self.ref.moves if m.slot >= 0]
        play, _ = self.act(self.ref.game.engine.save_state(), plays)
        if play is None:
            return 0
        return next(m.index for m in self.ref.moves if (0, m.slot, m.x, m.y) == play)


def pick(ref, card, target):
    return next((m.index for m in ref.moves if m.card == card and target in m.target), 0)


def reference(ref, planner):
    family, n = ref.cfg["family"], ref.decision
    if family == 1:
        return pick(ref, "Fireball", "enemy left princess tower")
    if family == 2:
        return pick(ref, "Cannon", "center (between towers)") if n == 0 else 0
    if family == 3:
        return pick(ref, "Fireball", "enemy Minions") if n == 0 else 0
    if family == 4:
        if n == 0:
            return pick(ref, "InfernoTower", "in front of left tower")
        if not any(p["card"] == "Knight" for p in ref.plays):
            return pick(ref, "Knight", "left bridge")
        return 0
    if family == 5:
        elapsed = (ref.tick-ref.start_tick) / 20
        if n == 0:
            return pick(ref, "IceGolemite", "center (between towers)")
        if n == 1:
            return pick(ref, "IceSpirits", "in front of left tower")
        if elapsed >= 8 and not any(p["card"] == "Log" for p in ref.plays):
            return pick(ref, "Log", "behind left tower")
        return 0
    if family == 6:
        if n == 0:
            return pick(ref, "Knight", "left bridge")
        if not any(p["card"] == "Cannon" for p in ref.plays):
            return pick(ref, "Cannon", "in front of left tower")
        return 0
    if family == 8:
        for card, target in [("Fireball", "enemy left princess tower"), ("Cannon", "in front of left tower"),
                             ("IceSpirits", "in front of left tower"), ("Skeletons", "left bridge")]:
            move = pick(ref, card, target)
            if move:
                return move
        return 0
    if family == 9:
        if n == 0:
            return pick(ref, "Fireball", "enemy left princess tower") if ref.cfg["id"].endswith("commit") else pick(ref, "Cannon", "left bridge")
        return 0
    return planner.choose()


def play(cfg, path, chooser=None):
    ref = make_referee(cfg)
    planner = MenuPlanner(ref) if chooser is None else None
    entries = []
    while not ref.over:
        index = chooser(ref) if chooser else reference(ref, planner)
        entry = dict(decision=ref.decision, tick=ref.tick, move=index,
                     label=ref.moves[index].label(), think_s=5.0)
        entries.append(entry)
        ref.act(index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e)+"\n" for e in entries), encoding="utf-8", newline="\n")
    if planner:
        planner.close()
    return ref


def calibrate(cfg, out):
    t0 = time.perf_counter()
    d = out / cfg["id"]
    log = d / "reference.jsonl"
    ref = play(cfg, log)
    first = verify(cfg, log, None)
    second = verify(cfg, log, None)
    idle = play(cfg, d / "wait.jsonl", lambda r: 0)
    # A zero-length log differs from explicitly playing wait to completion.
    empty = d / "empty.jsonl"
    empty.write_text("")
    empty_report = verify(cfg, empty, None)
    malformed = d / "malformed.jsonl"
    malformed.write_text("not json\n")
    malformed_report = verify(cfg, malformed, None)
    result = dict(task=cfg["id"], family=cfg["family"], reference_reward=first["rewards"]["reward"],
                  reference_outcome=first["outcome"], wait_success=idle.success(),
                  empty_reward=empty_report["rewards"]["reward"],
                  malformed_reward=malformed_report["rewards"]["reward"],
                  deterministic=first == second, setup_hash=ref.setup_hash,
                  config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                  protocol_sha256=protocol_digest(),
                  reference_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                  reference_decisions=len(log.read_text().splitlines()),
                  elapsed_s=round(time.perf_counter()-t0, 3), frontier_model_run=None)
    (d / "validation.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["task", "reference_reward", "wait_success", "deterministic", "elapsed_s"]}), flush=True)
    return result


def contrasts(configs, out):
    """Measure meaningful wrong actions; retain evidence rather than just success scores."""
    results = []
    for cfg in configs:
        if cfg["family"] == 3:
            choices = [("minions", "Fireball", "enemy Minions"),
                       ("balloon", "Fireball", "enemy Balloon"),
                       ("unrelated-tower", "Fireball", "enemy right princess tower")]
        elif cfg["family"] == 9:
            choices = [("commit-fireball", "Fireball", "enemy left princess tower"),
                       ("defend-cannon", "Cannon", "left bridge"), ("wait", "wait", "")]
        else:
            continue
        for label, card, target in choices:
            ref = play(cfg, out / "contrasts" / f"{cfg['id']}--{label}.jsonl",
                       lambda r, c=card, t=target: pick(r, c, t) if r.decision == 0 else 0)
            results.append(dict(task=cfg["id"], opening=label, objective_met=ref.success(),
                                damage=ref.outcome()["tower_damage"], elapsed_s=ref.outcome()["elapsed_s"]))
    (out / "contrasts.json").write_text(json.dumps(results, indent=2)+"\n")
    print(f"Wrote {len(results)} action contrasts.", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", type=int, nargs="*")
    ap.add_argument("--out", type=Path, default=Path("runs/royalebench-v1"))
    ap.add_argument("--contrasts", action="store_true", help="compare fixed spell and tower-race openings instead of full calibration")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
    if args.contrasts:
        contrasts(cs, args.out)
        return
    for c in cs:
        calibrate(c, args.out)
    results = [json.loads(p.read_text()) for p in sorted(args.out.glob("*/validation.json"))]
    summary = dict(benchmark=TITLE, version=VERSION,
                   commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                   python=platform.python_version(), platform=platform.platform(),
                   dependencies={p: version(p) for p in ["royalegym", "royalesim", "msgspec"]},
                   protocol_sha256=protocol_digest(),
                   tasks=results, status="local calibration; no frontier-model or Modal validation claimed")
    (args.out / "validation.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
