"""Strategic variations calibrated separately from the immutable RoyaleBench v1 release."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

from .royalebench_v1 import catalog as v1_catalog, unit

TITLE = "RoyaleBench Tactics"
VERSION = "1.0.0"


def mirror(cfg):
    """Reflect across the arena's center line, including owner-relative tower slots."""
    for u in cfg["scenario"]["units"]:
        u["x"] = 18 - u["x"]
    for hp in cfg["scenario"]["tower_hp"]:
        hp[1], hp[2] = hp[2], hp[1]
    if attack := cfg["scenario"].get("scheduled_attack"):
        attack["x"] = 18 - attack["x"]


def catalog():
    base = v1_catalog()
    rows = []
    design_hash = hashlib.sha256(Path(__file__).with_name("validate_tactics.py").read_bytes()
                                 .replace(b"\r\n", b"\n")).hexdigest()

    def add(source, family, slug, title, variant):
        c = deepcopy(source)
        c.update(id=f"{family:02d}-{slug}-{variant}", family=family, title=f"{title}: position {variant.upper()}",
                 benchmark=TITLE, version=VERSION, csv_win_rate=None, difficulty="hard",
                 control=False, calibration_source_sha256=design_hash,
                 release_gate="Winning reference and task-specific contrast evidence are required.")
        # Expected strategies are private calibration metadata, never agent instructions.
        c["validation_requirements"] = {}
        rows.append(c)
        return c

    for variant in ["a", "b"]:
        c = add(base[2], 1, "timed-spell", "Time an area spell", variant)
        enemy = ["Giant", "Goblins", "Musketeer", "Minions", "Cannon", "Zap", "Fireball", "Knight"]
        c.update(opponent_deck=enemy, opponent_deck_name="giant-goblin-pressure")
        c["scenario"].update(opponent_order=enemy, horizon_s=12, damage_limit=100,
            units=[unit("Giant", 3.5, 13, hp=800)] +
                  [unit("Goblins", x, 20, hp=150) for x in [2.8, 3.1, 3.5, 3.8, 4.2]])
        if variant == "b":
            mirror(c)
        c["objective"] = ("Cast exactly one Fireball, keep both princess towers alive for 12 seconds, "
                          "and take at most 100 additional total crown-tower damage. Only Fireball and waiting are available.")
        c["agent_notes"] = "Spell targets are fixed coordinates when submitted; units keep moving before impact."
        c["validation_requirements"] = {"immediate_best": 0, "late_best": 0}

    for variant in ["a", "b"]:
        c = add(base[4], 2, "reserve-counter", "Allocate a counter across two attacks", variant)
        lane = "left" if variant == "a" else "right"
        x = 3.5 if variant == "a" else 14.5
        c["scenario"]["spend_budget"] = 6
        if variant == "b":
            mirror(c)
        c["objective"] = ("Keep both princess towers alive for 20 seconds, take at most 450 additional total "
            "crown-tower damage, and spend at most 6 elixir. At elapsed 6.0 seconds the opponent casts its "
            f"reserved GoblinBarrel on your {lane} princess tower ({x}, 6.5).")
        c["validation_requirements"] = {"spend_then_musketeer": 0, "spend_then_recover": 0}

    for variant, y in [("a", 10.25), ("b", 10.0)]:
        c = add(base[8], 3, "tower-race", "Resolve an overtime tower race", variant)
        c["scenario"].update(start_tick=5840, horizon_s=8, elixir=4, spend_budget=4,
            units=[unit("Giant", 3.5, 24, team=0, hp=150), unit("Balloon", 3.5, y)])
        c["objective"] = ("Win before the remaining 8 seconds of overtime end, spending at most 4 elixir. "
            "At the actual overtime deadline, tied crowns use total remaining tower HP, then seed parity.")
        c["validation_requirements"] = {"commit": int(variant == "a"), "defend": int(variant == "b")}

    for variant in ["a", "b"]:
        c = add(base[8], 4, "tower-trade", "Choose a winning tower trade", variant)
        c["scenario"].update(start_tick=3320, horizon_s=14, elixir=4, spend_budget=4,
            tower_hp=[[4000, 305, 500], [4824, 366, 0]],
            units=[unit("Giant", 14.5, 23, team=0, hp=150), unit("Balloon", 3.5, 10)])
        if variant == "b":
            mirror(c)
        c["objective"] = ("Win by the end of the remaining 14 seconds of regulation, spending at most "
            "4 elixir. Entering overtime without a win does not meet the objective. "
            "You may lose a princess tower; any match win within the window succeeds.")
        c["validation_requirements"] = {"save_tower": 0, "reference_loses_princess": 1}
    audit_hash = hashlib.sha256(Path(__file__).with_name("audit_tactics.py").read_bytes()
                               .replace(b"\r\n", b"\n")).hexdigest()
    for c in rows:
        if c["family"] == 3:
            c["opening_audit_source_sha256"] = audit_hash
            c["opening_audit_requirements"] = {
                "winning_cards": ["Fireball" if c["id"].endswith("a") else "Cannon"]}
    return rows
