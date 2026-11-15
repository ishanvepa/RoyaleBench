"""Calibrate Tactics references, negative controls and required strategy contrasts.

    python -m cr_arena.validate_tactics --tasks 1 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .royale_task import make_referee, verify
from .royalebench_v1 import protocol_digest
from .tactics import TITLE, VERSION, catalog
from .validate_v1 import MenuPlanner, calibrate, pick, play

OUT = Path("runs/tactics")


def reference(ref):
    family = ref.cfg["family"]
    t = (ref.tick - ref.start_tick) / 20
    variant = ref.cfg["id"][-1]
    if family == 1:
        return pick(ref, "Fireball", "enemy Giant") if t >= 2 and not ref.plays else 0
    if family == 2:
        if ref.decision == 0:
            return pick(ref, "IceGolemite", "center (between towers)")
        if ref.decision == 1:
            lane = "left" if variant == "a" else "right"
            return pick(ref, "IceSpirits", f"in front of {lane} tower")
        lane = "left" if variant == "a" else "right"
        if t >= 8 and not any(p["card"] == "Log" for p in ref.plays):
            return pick(ref, "Log", f"behind {lane} tower")
        return 0
    if family == 3:
        if ref.decision:
            return 0
        return pick(ref, "Fireball", "enemy left princess tower") if variant == "a" else pick(ref, "Cannon", "left bridge")
    if family == 4:
        lane = "right" if variant == "a" else "left"
        return pick(ref, "Fireball", f"enemy {lane} princess tower") if ref.decision == 0 else 0
    raise ValueError(f"Unknown Tactics family {family}")


def attempt(cfg, out, name, chooser):
    path = out / cfg["id"] / "contrasts" / f"{name}.jsonl"
    ref = play(cfg, path, chooser)
    report = verify(cfg, path, None)
    if report["rewards"]["integrity"] != 1:
        raise RuntimeError(f"Contrast failed replay: {cfg['id']}/{name}")
    result = dict(name=name, reward=report["rewards"]["reward"], outcome=report["outcome"],
                  integrity=1, own_hp=list(ref.game.state.players[0].tower_hp),
                  actions=len(path.read_text().splitlines()))
    print(json.dumps(dict(task=cfg["id"], contrast=name, reward=result["reward"],
                          damage=result["outcome"]["tower_damage"])), flush=True)
    return result


def spell_sweep(cfg, out, delay):
    ref = make_referee(cfg)
    while not ref.over and (ref.tick - ref.start_tick) / 20 < delay:
        ref.act(0)
    choices = [(m.x, m.y) for m in (ref.moves or []) if m.card == "Fireball"]
    if not choices:
        raise RuntimeError("Spell contrast has no available Fireball")
    results = []
    for i, point in enumerate(choices):
        def choose(r):
            if (r.tick - r.start_tick) / 20 < delay or r.plays:
                return 0
            return next(m.index for m in r.moves if m.card == "Fireball" and (m.x, m.y) == point)
        results.append(attempt(cfg, out, f"cast-{delay}s-{i:02d}", choose))
    return results


def contrasts(cfg, out):
    family, variant = cfg["family"], cfg["id"][-1]
    results, rewards = [], {}
    if family == 1:
        for name, delay in [("immediate_best", 0), ("late_best", 4)]:
            trials = spell_sweep(cfg, out, delay)
            rewards[name] = max(t["reward"] for t in trials)
            results.extend(trials)
    elif family == 2:
        lane = "left" if variant == "a" else "right"
        def spend_then_musketeer(ref):
            if ref.decision == 0:
                return pick(ref, "Log", "enemy GoblinGang")
            if (ref.tick-ref.start_tick)/20 >= 4 and not any(p["card"] == "Musketeer" for p in ref.plays):
                return pick(ref, "Musketeer", f"in front of {lane} tower")
            return 0
        results.append(attempt(cfg, out, "spend_then_musketeer", spend_then_musketeer))
        planner = None
        try:
            def recover(ref):
                nonlocal planner
                if ref.decision == 0:
                    return pick(ref, "Log", "enemy GoblinGang")
                if planner is None:
                    planner = MenuPlanner(ref)
                return planner.choose()
            results.append(attempt(cfg, out, "spend_then_recover", recover))
        finally:
            if planner:
                planner.close()
        rewards.update((r["name"], r["reward"]) for r in results)
    elif family in (3, 4):
        lane = "left" if family == 3 or variant == "b" else "right"
        for name, card, target in [("commit", "Fireball", f"enemy {lane} princess tower"),
                                   ("defend" if family == 3 else "save_tower", "Cannon",
                                    "right bridge" if family == 4 and variant == "b" else "left bridge")]:
            results.append(attempt(cfg, out, name,
                lambda r, c=card, t=target: pick(r, c, t) if r.decision == 0 else 0))
        rewards.update((r["name"], r["reward"]) for r in results)
        if family == 4:
            before = cfg["scenario"]["tower_hp"][0]
            after = results[0]["own_hp"]
            rewards["reference_loses_princess"] = int(results[0]["reward"] == 1 and
                any(before[i] > 0 and after[i] == 0 for i in (1, 2)))
    return results, rewards


def validate(cfg, out):
    evidence = calibrate(cfg, out, chooser=reference)
    # Write the failed gate first: interrupted contrast checks must never release a task.
    evidence["release_gate_passed"] = False
    path = out / cfg["id"] / "validation.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    trials, rewards = contrasts(cfg, out)
    evidence.update(contrast_trials=trials, contrast_rewards=rewards,
        release_gate_passed=all(rewards.get(k) == v for k, v in cfg["validation_requirements"].items()))
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(dict(task=cfg["id"], gate=evidence["release_gate_passed"], contrasts=rewards)), flush=True)
    return evidence


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", type=int, nargs="*")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--reference-only", action="store_true", help="explore references without release evidence")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    configs = [c for c in catalog() if not args.tasks or c["family"] in args.tasks]
    for cfg in configs:
        if args.reference_only:
            ref = play(cfg, args.out / cfg["id"] / "probe.jsonl", reference)
            print(json.dumps(dict(task=cfg["id"], success=ref.success(), outcome=ref.outcome(),
                                  own_hp=list(ref.game.state.players[0].tower_hp))), flush=True)
        else:
            validate(cfg, args.out)
    if not args.reference_only:
        evidence = [json.loads(p.read_text()) for c in catalog()
                    if (p := args.out / c["id"] / "validation.json").exists()]
        (args.out / "validation.json").write_text(json.dumps(dict(benchmark=TITLE, version=VERSION,
            protocol_sha256=protocol_digest(), tasks=evidence,
            status="Local reference and contrast calibration; hosted model difficulty is not established."), indent=2) + "\n")


if __name__ == "__main__":
    main()
