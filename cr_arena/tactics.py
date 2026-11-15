"""Coordinate-action Tactics scenarios on the RoyaleBench v3 foundation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .coordinate_task import MODE

TITLE = "RoyaleBench Tactics"
VERSION = "2.0.0"
SOURCE = Path(__file__).resolve().parents[1] / "data/royalebench-tactics-menu-source"


def source_manifest():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen Tactics source changed: {name}")
    return manifest


def catalog():
    source_manifest()
    rows = []
    for path in sorted(SOURCE.glob("*/config.json")):
        c = json.loads(path.read_text())
        for key in ("opening_audit_requirements", "opening_audit_source_sha256", "calibration_source_sha256"):
            c.pop(key, None)
        c.update(benchmark=TITLE, version=VERSION, action_mode=MODE,
                 foundation_dataset="royalebench/royalebench-v3@2",
                 source_dataset="royalebench/royalebench-tactics@2",
                 source_config_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if c["family"] == 3:
            # Free placement can preserve towers where the old menu could not.
            c["scenario"]["tower_hp"][0][1] = 50
            c["scenario"]["units"][0]["hp"] = 150 if c["id"].endswith("a") else 400
            c["scenario"]["units"][1]["y"] = 10.25 if c["id"].endswith("a") else 9.5
            c["validation_requirements"].update(wrong_strategy_screen_wins=0, wrong_strategy_witness_best=0)
        if c["family"] == 1:
            c["validation_requirements"].update(screen_immediate_best=0, screen_late_best=0)
        if c["family"] == 4:
            c["validation_requirements"].update(defensive_cannon_screen_wins=0, defensive_cannon_best=0)
        c["release_gate"] = "Current coordinate references, negative controls and strategic contrasts are required."
        rows.append(c)
    return rows
