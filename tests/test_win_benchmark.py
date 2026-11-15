"""The new cohort must award actual wins, never a short defensive survival window."""
from copy import deepcopy
import json
from unittest.mock import PropertyMock, patch

import msgspec
import pytest

from cr_arena.coordinate_benchmark import packaged_protocol_digest
from cr_arena.royale_task import make_referee
from cr_arena.win_benchmark import OUT, VERSION, catalog, instruction, spell_crown_damage
from rb_evals.benchmarks import load_benchmark, task_problems


def test_win_only_cohort_keeps_its_separate_dataset():
    assert OUT.name == "royalebench-win"


@pytest.mark.parametrize("cfg", catalog(), ids=lambda c: c["id"])
def test_every_objective_requires_a_finished_engine_win(cfg):
    ref = make_referee(cfg)
    try:
        assert cfg["scenario"]["grading"] == "win"
        assert ref.end_tick == 6000
        assert not ref.success()
        # An HP lead or crowns on a live match must never pass.
        s = ref.game.state
        assert s.players[0].crowns == s.players[1].crowns == 0
        assert not s.game_over
        with patch.object(type(ref.game), "state", new_callable=PropertyMock) as state:
            state.return_value = msgspec.structs.replace(s, game_over=False, winner=0)
            assert not ref.success()
            state.return_value = msgspec.structs.replace(s, game_over=True, winner=1)
            assert not ref.success()
            state.return_value = msgspec.structs.replace(s, game_over=True, winner=0)
            assert ref.success()
        assert not {"spend_budget", "damage_limit", "only_card", "max_decisions",
                    "right_lane_budget"}.intersection(cfg["scenario"])
        # No starting tower can be killed by one Fireball; the bait task also exceeds Rocket.
        assert min(cfg["scenario"]["tower_hp"][1][1:]) > (342 if cfg["family"] == 3 else 159)
        text = instruction(cfg)
        assert "actual match win" in text and "cr play SLOT X Y" in text
        assert "keep both princess towers" not in text.lower()
    finally:
        ref.opponent.close()


def test_catalog_is_not_mutated_by_a_caller():
    original = deepcopy(catalog())
    changed = catalog()
    changed[0]["scenario"]["order"].reverse()
    changed[0]["planner"]["top_k"] = 99
    assert catalog() == original


def test_disclosed_spell_damage_matches_the_pinned_engine():
    assert spell_crown_damage() == {"Fireball": 159, "Zap": 48, "Log": 35, "Rocket": 342}


def test_critical_pair_changes_only_starting_own_tower_health():
    normal, critical = catalog()[0], catalog()[3]
    for key in ("seed", "agent_deck", "opponent_deck", "planner", "decision_ticks", "objective"):
        assert normal[key] == critical[key]
    changed = deepcopy(critical["scenario"])
    assert changed["tower_hp"][0][1] == 250
    changed["tower_hp"][0][1] = normal["scenario"]["tower_hp"][0][1]
    assert changed == normal["scenario"]


def test_packaged_cohort_has_complete_consistent_isolated_tasks():
    if not (OUT / "manifest.json").exists():
        pytest.skip("build the win-only dataset first")
    manifest = json.loads((OUT / "manifest.json").read_text())
    benchmark = load_benchmark(OUT)
    assert set(benchmark.tasks) == {c["id"] for c in catalog()}
    assert manifest["version"] == VERSION
    for name, task in benchmark.tasks.items():
        assert not task_problems(task)
        # This published package is frozen even if the working runtime evolves.
        assert packaged_protocol_digest(task.path) == manifest["protocol_sha256"]
        cfg = json.loads((task.path / "tests/task.json").read_text())
        assert cfg == json.loads((task.path / "environment/task.json").read_text())
        assert cfg["scenario"]["grading"] == "win"
        assert task.config["agent"]["user"] == "player"
        assert task.config["verifier"]["network_mode"] == "no-network"
        assert not list((task.path / "environment").rglob("reference.jsonl"))
        row = next(r for r in manifest["tasks"] if r["task"] == name)
        assert row["reward"] == row["integrity"] == 1
        assert row["reference_outcome"]["result"] == "win"
        assert row["deterministic"] is True
        assert not any(row["negative_rewards"].values())
        for path in task.path.rglob("*"):
            if path.is_file() and (path.suffix == ".sh" or path.name == "Dockerfile"):
                assert b"\r\n" not in path.read_bytes()
