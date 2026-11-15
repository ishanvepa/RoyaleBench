"""Reproduce the two supplied TikTok interactions on the unmodified Rust engine.

Run: uv run python -m cr_arena.recreate_clips
The videos do not expose exact taps or hidden match state. These are explicit,
deterministic reconstructions of their visible interactions, not recovered saves.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from dataclasses import asdict, dataclass, replace
from importlib.metadata import version
from pathlib import Path

import msgspec
from royalegym import RustEngine, deck_ids
from royalegym.protocol import DeployCommand, DeployStatus, MatchSetup, ShuffleMode, SpawnSpec
from royalegym.replay import ReplayRecorder, save_trace, verify_trace

from .replay import patched_html

BLUE = ["Skeletons", "Fireball", "Knight", "Archer", "Giant", "Minions", "Cannon", "Zap"]
RED = ["MiniPekka", "Balloon", "Knight", "Archer", "Giant", "Minions", "Cannon", "Zap"]
SEED, START_TICK, HORIZON_TICKS = 42, 100, 460


@dataclass(frozen=True)
class Clip:
    slug: str
    video_id: str
    source: str
    title: str
    attacker: str
    defense: str
    level: int
    tower_levels: tuple[int, int]
    cast_tick: int
    tap: tuple[float, float]
    explanation: str


CLIPS = (
    Clip("skeletons-mini-pekka", "7575314632915701009", "https://www.tiktok.com/t/ZTPDWutTM/",
         "Skeletons vs Mini P.E.K.K.A.", "MiniPekka", "Skeletons", 11, (11, 11), 75, (7.5, 13.5),
         "One elixir of Skeletons pulls the Mini P.E.K.K.A. inward and buys enough Princess Tower shots. "
         "The defending tower finishes at 3052 / 3052 HP."),
    Clip("fireball-balloon", "7646672093966355726", "https://www.tiktok.com/t/ZTPD72qTU/",
         "Fireball vs Balloon", "Balloon", "Fireball", 16, (15, 16), 200, (3.5, 7.5),
         "A Fireball placed behind the approaching Balloon knocks it away and prevents its direct attack. "
         "The tower stays at 4424 HP until the death bomb, then falls to 4040 HP. "
         "The TikTok ends with the bomb timer still running."),
)


def simulate(clip: Clip, *, defense: bool = True, record: bool = True) -> tuple[dict, object]:
    engine = RustEngine()
    cards = list(engine.cards())
    ids = {c.name: c.card_id for c in cards}
    sub = engine.arena().subtile
    setup = MatchSetup(
        decks=[deck_ids(BLUE, cards), deck_ids(RED, cards)], shuffle=ShuffleMode.NONE,
        start_tick=START_TICK, elixir_milli=[10000, 10000],
        levels=[[clip.level] * 8, [clip.level] * 8], tower_levels=list(clip.tower_levels),
        spawns=[SpawnSpec(1, ids[clip.attacker], round(3.5 * sub), round(20.5 * sub))],
        # The damaged far towers are visible in the Balloon reference. The cropped
        # near-right HP is incomplete, so leave that unrelated tower at its default.
        tower_hp=None if clip.attacker == "MiniPekka" else [[7032, 4424, 4424], [7728, 3912, 278]],
    )
    engine.reset(SEED, setup)
    recorder = ReplayRecorder(frame_every_tick=True) if record else None
    if recorder:
        recorder.begin(engine, SEED, setup)
    initial_hp = engine.state().players[0].tower_hp[1]
    previous_hp = initial_hp
    death_tick = None
    events, commands_log = [], []
    attacker_at_cast = None
    for elapsed in range(HORIZON_TICKS):
        before = engine.state()
        attacker = next((u for u in before.entities
                         if u.team == 1 and u.card_id == ids[clip.attacker]), None)
        commands = []
        if defense and elapsed == clip.cast_tick:
            slot = before.players[0].hand.index(ids[clip.defense])
            commands = [DeployCommand(0, slot, *(round(v * sub) for v in clip.tap))]
            if attacker:
                attacker_at_cast = {"x": attacker.x / sub, "y": attacker.y / sub,
                                    "hp": attacker.hp, "level": attacker.level}
        results = engine.step(commands, 1)
        if commands:
            if any(r.status != DeployStatus.OK for r in results):
                raise RuntimeError(f"reconstruction command refused: {results}")
            commands_log.append({"elapsed_tick": elapsed, "elapsed_s": elapsed / 20,
                                 "card": clip.defense,
                                 "command": msgspec.to_builtins(commands[0]),
                                 "result": msgspec.to_builtins(results[0])})
        if recorder:
            recorder.record_step(before.tick, 1, commands, results)
            recorder.record_frame(engine)
        after = engine.state()
        alive = any(u.team == 1 and u.card_id == ids[clip.attacker] for u in after.entities)
        if not alive and death_tick is None:
            death_tick = elapsed + 1
            events.append({"elapsed_tick": death_tick, "elapsed_s": death_tick / 20,
                           "event": "attacker_died", "tower_hp": after.players[0].tower_hp[1]})
        hp = after.players[0].tower_hp[1]
        if hp != previous_hp:
            events.append({"elapsed_tick": elapsed + 1, "elapsed_s": (elapsed + 1) / 20,
                           "event": "tower_damage", "damage": previous_hp - hp, "tower_hp": hp,
                           "after_attacker_death": death_tick is not None and elapsed + 1 > death_tick})
            previous_hp = hp
    trace = recorder.end(engine) if recorder else None
    discrepancies = verify_trace(trace, RustEngine()) if trace else []
    if discrepancies:
        raise AssertionError(discrepancies[:3])
    damage = [e for e in events if e["event"] == "tower_damage"]
    result = {
        "clip": asdict(clip), "defense_enabled": defense, "seed": SEED,
        "start_tick": START_TICK, "horizon_ticks": HORIZON_TICKS,
        "setup": msgspec.to_builtins(setup), "engine": engine.config(),
        "initial_tower_hp": initial_hp, "final_tower_hp": previous_hp,
        "total_tower_damage": initial_hp - previous_hp,
        "damage_before_attacker_death": sum(e["damage"] for e in damage if not e["after_attacker_death"]),
        "damage_after_attacker_death": sum(e["damage"] for e in damage if e["after_attacker_death"]),
        "attacker_dead": death_tick is not None, "attacker_at_cast": attacker_at_cast,
        "events": events, "commands": commands_log,
        "verified_frame_count": len(trace.frames) if trace else 0,
        "trace_verification_errors": discrepancies,
        "final_hash": f"{engine.state_hash():016x}",
    }
    return result, trace


def write_page(out: Path, results: list[dict]) -> None:
    sections = []
    for clip, result in zip(CLIPS, results):
        sections.append(f"""<section>
          <div class="heading"><span class="number">0{len(sections)+1}</span><h2>{html.escape(clip.title)}</h2>
          <strong>{'0 tower damage' if result['total_tower_damage'] == 0 else '0 direct hits · death bomb: 384 damage'}</strong></div>
          <p>{html.escape(clip.explanation)}</p>
          <div class="comparison">
            <div><h3>Extracted TikTok reference</h3><video controls playsinline preload="metadata"
              src="../../data/references/tiktok/{clip.video_id}.mp4"></video>
              <p><a href="{clip.source}">Original clip</a> · Source timing includes edits and zooms.</p></div>
            <div><h3>Engine recreation</h3><iframe title="{html.escape(clip.title)} replay"
              src="{clip.slug}.html"></iframe>
              <p><a href="{clip.slug}.html">Open full replay</a> · <a href="{clip.slug}.mp4">Watch recreation video</a>
              · <a href="{clip.slug}-no-defense.html">No-defense control</a>
              · <a href="{clip.slug}-mistimed.html">Mistimed control</a></p></div>
          </div>
          <details><summary>Exact simulation inputs and verification</summary><pre>{html.escape(json.dumps({k: result[k] for k in ['attacker_at_cast','commands','events','verified_frame_count','final_hash']}, indent=2))}</pre></details>
        </section>""")
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>TikTok plays, recreated in RoyaleBench</title><style>
    :root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0c1320;color:#e8edf7;font:15px/1.6 system-ui,sans-serif}
    main{max-width:1340px;margin:auto;padding:40px 30px 70px}h1{font-size:38px;line-height:1.15;margin:12px 0 20px;letter-spacing:-1px}
    h2{font-size:23px;margin:0}h3{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:#acb9ce}
    .eyebrow{color:#8bbaff;font-size:12px;font-weight:700;letter-spacing:2px}.lede{max-width:950px;color:#acb9ce}
    section{margin-top:32px;border:1px solid #2d3b53;border-radius:16px;background:#141e30;padding:24px}
    .heading{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.number{color:#80b4ff;font-size:21px;font-weight:700}
    strong{margin-left:auto;background:#183e36;border:1px solid #286452;border-radius:20px;color:#8ce5ba;padding:4px 14px;font-size:12px}
    p{color:#bac6d8}a{color:#94bfff} .comparison{display:grid;grid-template-columns:320px 1fr;gap:24px}
    video{width:100%;height:640px;object-fit:contain;background:#080d16;border-radius:10px}
    iframe{width:100%;height:640px;border:1px solid #2d3b53;border-radius:10px;background:#0e1420}
    details{border-top:1px solid #2d3b53;padding-top:15px;margin-top:12px;color:#acb9ce}summary{cursor:pointer}pre{white-space:pre-wrap;font-size:12px}
    @media(max-width:800px){main{padding:24px 12px}h1{font-size:30px}section{padding:16px}.comparison{grid-template-columns:1fr}video{height:480px}strong{margin-left:0}}
    </style></head><body><main><div class="eyebrow">ROYALEBENCH / CLIP RECONSTRUCTIONS</div>
    <h1>Two plays. Real engine replays.</h1><p class="lede">Both tactical outcomes can occur in our unmodified simulator.
    Watch the extracted references alongside deterministic recreations, then inspect the controls.
    These reproduce the interactions, not the original match saves: taps, hidden state and Fireball level are not recoverable exactly from the videos.
    Arena artwork, movement timing and camera framing differ. The Balloon recreation continues through the death-bomb explosion.</p>
    __SECTIONS__<p>Each replay contains 461 engine frames, checked by independently replaying every command and comparing every state hash.
    <a href="checks.json">Validation and provenance</a></p></main></body></html>"""
    (out / "index.html").write_text(page.replace("__SECTIONS__", "\n".join(sections)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("runs/clip-recreations"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    all_results, main_results = {}, []
    for clip in CLIPS:
        for suffix, variant, defense in (
            ("", clip, True), ("-no-defense", clip, False),
            ("-mistimed", replace(clip, cast_tick=clip.cast_tick - (5 if clip.attacker == "MiniPekka" else 40)), True),
        ):
            result, trace = simulate(variant, defense=defense)
            name = clip.slug + suffix
            replay = args.out / f"{name}.msgpack"
            save_trace(trace, replay)
            label = clip.title + (" / " + suffix[1:].replace("-", " ") if suffix else " / recreation")
            page = patched_html(replay, title=label, decisions_note="Scripted recreation; see the comparison page for inputs and controls.")
            # A compact export still uses the production replay controls and renderer.
            style = "<style>.team-panels,.decision-panel,footer{display:none!important}main{padding:8px!important}#boardwrap{order:0!important}header .meta{display:none}</style>"
            (args.out / f"{name}.html").write_text(page.replace("</head>", style + "</head>"))
            result["replay_sha256"] = hashlib.sha256(replay.read_bytes()).hexdigest()
            all_results[name] = result
            if not suffix:
                main_results.append(result)
            print(name, result["total_tower_damage"], "tower damage;", result["verified_frame_count"], "verified frames", flush=True)
    assert all_results["skeletons-mini-pekka"]["total_tower_damage"] == 0
    assert all_results["fireball-balloon"]["damage_before_attacker_death"] == 0
    assert all_results["fireball-balloon"]["damage_after_attacker_death"] == 384
    assert all(r["attacker_dead"] for r in all_results.values())
    assert all(all_results[c.slug + "-no-defense"]["total_tower_damage"] > all_results[c.slug]["total_tower_damage"] for c in CLIPS)
    assert all(all_results[c.slug + "-mistimed"]["total_tower_damage"] > all_results[c.slug]["total_tower_damage"] for c in CLIPS)
    sources = {}
    for clip in CLIPS:
        path = Path("data/references/tiktok") / f"{clip.video_id}.mp4"
        if path.exists():
            sources[clip.video_id] = {"url": clip.source, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    checks = {"packages": {p: version(p) for p in ["royalegym", "royalesim"]},
              "sources": sources,
              "limitations": ["Pixel coordinates and cast timing are inferred and calibrated in simulator tiles, not recovered exactly.",
                              "Fireball level is not visible; level 16 is an explicit assumption.",
                              "Initial attackers are full-health public SpawnSpecs at (3.5,20.5); no private save edits or rule overrides.",
                              "Only the isolated left-lane interaction is modeled. Other lane units and hidden hands are not reconstructed. Visible far-tower HP is matched; cropped near-right HP is not inferred.",
                              "Balloon clip uses level-15 Princess Towers and a level-16 King; public setup uses one tower level per team, so blue King is 15 here.",
                              "The Balloon video cuts before death-bomb damage, so it supports no direct attack, not zero total damage."],
              "results": all_results}
    (args.out / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    write_page(args.out, main_results)


if __name__ == "__main__":
    main()
