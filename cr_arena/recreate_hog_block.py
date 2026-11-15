"""Recreate the TikTok Hog Rider / Ice Golem / Skeletons body-block.

Run: uv run --only-group play python -m cr_arena.recreate_hog_block --sweep
This is a mechanics experiment, not a published benchmark task.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
from importlib.metadata import version
import itertools
import json
from pathlib import Path

from royalegym import RustEngine, deck_ids
from royalegym.protocol import DeployCommand, DeployStatus, MatchSetup, ShuffleMode
from royalegym.replay import ReplayRecorder, load_trace, save_trace, verify_trace

from .replay import patched_html


SOURCE = "https://www.tiktok.com/@clashchallenger1/video/7704162569065352478"
DECK = ["HogRider", "IceGolemite", "Skeletons", "Musketeer", "Cannon", "IceSpirits", "Fireball", "Log"]
SEED, START_TICK, HORIZON_TICKS = 1, 200, 400


@dataclass(frozen=True)
class Setup:
    # Blue's absolute tile coordinates; no red-seat coordinate transform here.
    hog_x: float = 2.5
    hog_y: float = 18.5
    ice_x: float = 1.5
    ice_y: float = 12.5
    skeleton_x: float = 3.5
    skeleton_y: float = 12.5
    ice_tick: int = 10
    skeleton_tick: int = 20
    ice: bool = True
    skeletons: bool = True


def simulate(cfg: Setup, replay_path: Path | None = None) -> dict:
    engine = RustEngine()
    cards = list(engine.cards())
    ids = {card.name: card.card_id for card in cards}
    deck = deck_ids(DECK, cards)
    setup = MatchSetup(decks=[deck, deck], shuffle=ShuffleMode.NONE,
                       start_tick=START_TICK, elixir_milli=[10000, 10000])
    engine.reset(SEED, setup)
    sub = engine.arena().subtile
    initial_hp = engine.state().players[0].tower_hp[1]
    tick_ms = engine.state().tick_ms
    recorder = ReplayRecorder(frame_every_tick=True) if replay_path else None
    if recorder:
        recorder.begin(engine, SEED, setup)
    schedule = [(0, 1, "HogRider", cfg.hog_x, cfg.hog_y)]
    if cfg.ice:
        schedule.append((cfg.ice_tick, 0, "IceGolemite", cfg.ice_x, cfg.ice_y))
    if cfg.skeletons:
        schedule.append((cfg.skeleton_tick, 0, "Skeletons", cfg.skeleton_x, cfg.skeleton_y))
    plays, path, hit_ticks, crossings = [], [], [], {}
    last_hp, death_tick = initial_hp, None
    for elapsed in range(HORIZON_TICKS):
        commands = []
        for tick, team, card, x, y in schedule:
            if elapsed != tick:
                continue
            slot = engine.state().players[team].hand.index(ids[card])
            commands.append(DeployCommand(team, slot, round(x * sub), round(y * sub)))
            plays.append(dict(elapsed_tick=tick, team=team, card=card, x=x, y=y))
        results = engine.step(commands, 1)
        if any(result.status != DeployStatus.OK for result in results):
            raise RuntimeError(f"Deployment refused: {results}")
        if recorder:
            recorder.record_step(START_TICK + elapsed, 1, commands, results)
            recorder.record_frame(engine)
        state = engine.state()
        hp = state.players[0].tower_hp[1]
        if hp < last_hp:
            hit_ticks.append(elapsed + 1)
        last_hp = hp
        hog = next((unit for unit in state.entities if unit.card_id == ids["HogRider"]), None)
        if hog is None:
            death_tick = elapsed + 1
            break
        for y in (15, 14, 13, 12, 11, 10, 9):
            if hog.y <= y * sub and str(y) not in crossings:
                crossings[str(y)] = elapsed + 1
        path.append(dict(elapsed_tick=elapsed + 1, x=hog.x / sub, y=hog.y / sub, hp=hog.hp))
    result = dict(setup=asdict(cfg), plays=plays, tick_ms=tick_ms,
                  tower_damage=initial_hp - last_hp, tower_hits=len(hit_ticks),
                  hit_ticks=hit_ticks, hog_death_tick=death_tick,
                  first_crossing_ticks=crossings, hog_path=path)
    if recorder:
        trace = recorder.end(engine)
        replay_path.parent.mkdir(parents=True, exist_ok=True)
        save_trace(trace, replay_path)
        # Verify the persisted artifact on a fresh engine, including every frame hash.
        errors = verify_trace(load_trace(replay_path), RustEngine())
        if errors:
            raise RuntimeError(f"Replay diverged: {errors[:3]}")
        result.update(replay_verified=True, final_hash=trace.result.final_hash,
                      replay_sha256=hashlib.sha256(replay_path.read_bytes()).hexdigest())
        replay_path.with_suffix(".html").write_text(patched_html(
            replay_path, title=f"Hog body-block: {replay_path.stem}",
            decisions_note="Scripted mechanics experiment; estimated clip placement and timing. "
                           "Blue uses only Ice Golem and Skeletons. No model or opponent bot."))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("runs/hog-body-block"))
    parser.add_argument("--sweep", action="store_true", help="Repeat the 144-case placement/timing check")
    args = parser.parse_args()
    selected = Setup()
    cases = {
        "body-block": selected,
        "skeletons-only": replace(selected, ice=False),
        "ice-golem-only": replace(selected, skeletons=False),
        "undefended": replace(selected, ice=False, skeletons=False),
        "skeletons-one-tile-higher": replace(selected, skeleton_y=13.5),
    }
    report = dict(source=SOURCE, seed=SEED, start_tick=START_TICK,
                  horizon_ticks=HORIZON_TICKS, deck=DECK,
                  versions={p: version(p) for p in ("royalegym", "royalesim")},
                  engine_identity=RustEngine().engine_identity(),
                  coordinate_frame="Absolute blue tiles: river y=15..17; blue left tower (3.5,6.5)",
                  cases={name: simulate(cfg, args.out / "replays" / f"{name}.msgpack")
                         for name, cfg in cases.items()})
    if args.sweep:
        sweep = []
        for hx, it, delta, ix, iy, sy in itertools.product(
                (2.5, 3.5), (0, 10, 20), (1, 10, 20), (1.5, 2.5), (11.5, 12.5), (12.5, 13.5)):
            result = simulate(Setup(hog_x=hx, ice_tick=it, skeleton_tick=it + delta,
                                    ice_x=ix, ice_y=iy, skeleton_y=sy))
            result.pop("hog_path")
            sweep.append(result)
        report["sweep"] = sweep
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, result in report["cases"].items():
        print(f"{name}: {result['tower_hits']} hits, {result['tower_damage']} damage, "
              f"Hog death tick {result['hog_death_tick']}, replay verified")
    print(f"Results: {args.out / 'results.json'}")


if __name__ == "__main__":
    main()
