"""Replay selected v9 policies and small counterfactuals in their packaged runtime."""
from __future__ import annotations

import hashlib
import importlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads(Path(__file__).with_name("failure-analysis.json").read_text(encoding="utf-8"))
RESULTS = []


def run(task, label, *, model=None, reference=False, changes=None, offset=0, mechanics=False):
    folder = ROOT / "benchmarks/royalebench-v9" / task
    package = "frozen_" + task.replace("-", "_")
    if package not in sys.modules:
        module = types.ModuleType(package)
        module.__path__ = [str(folder / "environment/referee")]
        sys.modules[package] = module
    make_referee = importlib.import_module(package + ".royale_task").make_referee
    cfg = json.loads((folder / "tests/task.json").read_text())
    ref = make_referee(cfg, record=mechanics)
    policy, expected = {}, None
    if reference:
        entries = [json.loads(l) for l in (folder / "solution/reference.jsonl").read_text().splitlines() if l.strip()]
        policy = {r["decision"] + offset: dict(r["action"]) for r in entries if r["action"]["cmd"] == "play"}
    elif model:
        attempt = next(a for a in DATA["attempts"] if a["task"] == task and a["model"] == model)
        assert attempt["rewards"]["rejected_actions"] == 0
        expected = attempt["outcome"]
        policy = {p["decision"]: dict(cmd="play", card=p["card"], x=p["x"] / ref.game.sub,
                                       y=p["y"] / ref.game.sub) for p in expected["plays"]}
    for decision, change in (changes or {}).items():
        policy[decision] = dict(policy.get(decision, {}), **change)
    boards = []
    try:
        while not ref.over:
            boards.append(dict(decision=ref.decision, tick=ref.tick,
                               observation=ref.observation()))
            action = dict(policy.get(ref.decision, {"cmd": "wait"}))
            if "card" in action:
                card = action.pop("card")
                action["slot"] = next(i for i, cid in enumerate(ref.game.state.players[0].hand)
                                      if ref.game.card_name(cid) == card)
            _, meta = ref.prepare_action(action)
            assert meta["accepted"], (task, label, action, meta)
            ref.act_action(action)
        outcome = ref.outcome()
        result = dict(task=task, label=label, model=model, reference=reference, changes=changes,
                      decision_offset=offset, success=ref.success(), outcome=outcome,
                      final_tower_hp=[list(p.tower_hp) for p in ref.game.state.players],
                      boards=boards,
                      configuration_sha256=hashlib.sha256((folder / "tests/task.json").read_bytes()).hexdigest())
        if expected is not None and not changes and not offset:
            result["matches_recorded_outcome"] = outcome == expected
            assert result["matches_recorded_outcome"], (task, label, outcome, expected)
        if mechanics:
            trace = ref.game.finish()[-1]
            events, previous = [], {}
            for frame in trace.frames:
                current = {e.uid:e for e in frame.entities}
                for uid, entity in current.items():
                    prev = previous.get(uid)
                    if prev is None:
                        continue
                    if entity.hp < prev.hp or (entity.knockback_ticks > 0 and prev.knockback_ticks == 0):
                        events.append(dict(elapsed_s=(frame.tick-ref.start_tick)/20,
                                           uid=uid, card=ref.game.card_name(entity.card_id),
                                           team=entity.team, tower_slot=entity.tower_slot,
                                           x=entity.x/ref.game.sub, y=entity.y/ref.game.sub,
                                           hp=entity.hp, hp_change=entity.hp-prev.hp,
                                           knockback_ticks=entity.knockback_ticks))
                for uid in previous.keys()-current.keys():
                    entity = previous[uid]
                    events.append(dict(elapsed_s=(frame.tick-ref.start_tick)/20, uid=uid,
                                       card=ref.game.card_name(entity.card_id), team=entity.team,
                                       tower_slot=entity.tower_slot, removed=True))
                previous = current
            result["damage_and_knockback_events"] = events
        RESULTS.append(result)
        print(task, label, "success",result["success"],"damage",outcome["tower_damage"],
              "elapsed",outcome["elapsed_s"],"hp",result["final_tower_hp"], flush=True)
    finally:
        ref.opponent.close()


def main():
    if "--aim" in sys.argv:
        run("07-balloon-fireball", "sol_change_x_only", model="openai/gpt-6.1-sol", changes={10:dict(x=3.5)})
        run("07-balloon-fireball", "sol_change_y_only", model="openai/gpt-6.1-sol", changes={10:dict(y=7.5)})
        run("07-balloon-fireball", "sol_one_second_earlier_same_center", reference=True,
            changes={10:dict(cmd="wait"),9:dict(cmd="play",slot=1,x=3.3,y=6.7)})
        Path(__file__).with_name("failure-aim-ablation.json").write_text(json.dumps(RESULTS,indent=2)+"\n",encoding="utf-8")
        return
    if "--allocation" in sys.argv:
        run("02-reserve-counter-a", "reference", reference=True)
        run("02-reserve-counter-a", "opus_recorded", model="anthropic/claude-opus-5-5")
        run("02-reserve-counter-a", "reference_golem_left_instead_of_center", reference=True,
            changes={0:dict(x=3.5,y=10.5)})
        run("03-supported-tank-conversion", "fable52_recorded", model="anthropic/claude-fable-5-2")
        run("02-second-wave-air-race", "fable52_recorded", model="anthropic/claude-fable-5-2")
        run("04-split-lane-conversion", "fable52_recorded", model="anthropic/claude-fable-5-2")
        Path(__file__).with_name("failure-allocation.json").write_text(json.dumps(RESULTS,indent=2)+"\n",encoding="utf-8")
        return
    if "--mechanics" in sys.argv:
        run("07-balloon-fireball", "reference", reference=True, mechanics=True)
        run("07-balloon-fireball", "sol_recorded", model="openai/gpt-6.1-sol", mechanics=True)
        run("07-balloon-fireball", "astra_recorded", model="openai/gpt-6-astra", mechanics=True)
        run("03-tower-race-b", "opus_recorded_fireball", model="anthropic/claude-opus-5-5", mechanics=True)
        Path(__file__).with_name("failure-mechanics.json").write_text(json.dumps(RESULTS,indent=2)+"\n",encoding="utf-8")
        return
    task = "07-balloon-fireball"
    run(task, "reference", reference=True)
    run(task, "sol_recorded", model="openai/gpt-6.1-sol")
    run(task, "sol_same_time_reference_center", model="openai/gpt-6.1-sol", changes={10:dict(x=3.5,y=7.5)})
    run(task, "astra_recorded", model="openai/gpt-6-astra")
    run(task, "reference_one_second_early", reference=True, offset=-1)
    run(task, "reference_sol_center", reference=True, changes={10:dict(x=3.3,y=6.7)})
    task = "05-hog-body-block"
    run(task, "reference", reference=True)
    run(task, "reference_both_plays_half_second_early", reference=True, offset=-1)
    run(task, "opus_recorded", model="anthropic/claude-opus-5-5")
    task = "06-mini-pekka-kite"
    run(task, "reference", reference=True)
    run(task, "reference_half_second_late", reference=True, offset=1)
    task = "03-tower-race-b"
    run(task, "reference_cannon", reference=True)
    run(task, "opus_recorded_fireball", model="anthropic/claude-opus-5-5")
    task = "04-critical-cycle-and-connect"
    run(task, "reference", reference=True)
    run(task, "sol_recorded", model="openai/gpt-6.1-sol")
    run(task, "sol_cannon_reference_position", model="openai/gpt-6.1-sol", changes={1:dict(x=7,y=11.5)})
    out = Path(__file__).with_name("failure-counterfactuals.json")
    out.write_text(json.dumps(dict(engine_versions={n:version(n) for n in ["royalegym","royalesim","numpy"]},
                                   method="Local packaged Python referee runtime, pinned installed engine versions; accepted policies reconstructed from verifier card/decision/position records. Counterfactuals are diagnostic probes, not new model attempts or scores.",
                                   probes=RESULTS),indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
