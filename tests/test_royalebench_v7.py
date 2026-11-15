"""v7 must require tower conversion, retain isolation, and reject stale evidence."""
from copy import deepcopy
import json
from unittest.mock import PropertyMock, patch

import msgspec
import pytest

from cr_arena.build_v7 import EVIDENCE, OUT, VERSION, catalog, instruction
from cr_arena.coordinate_benchmark import packaged_protocol_digest, protocol_digest
from cr_arena.decks import validate_deck
from cr_arena.royale_task import make_referee
from cr_arena.telemetry import digest
from rb_evals.benchmarks import load_benchmark, task_problems


def test_v7_remains_a_separate_challenge_release():
    assert OUT.name == "royalebench-v7"


@pytest.mark.parametrize("cfg", catalog(), ids=lambda c: c["id"])
def test_win_window_cannot_reach_hp_or_seed_tiebreak(cfg):
    ref = make_referee(cfg)
    try:
        assert cfg["scenario"]["grading"] == "win"
        assert ref.start_tick == 4800 < ref.end_tick < 6000
        assert ref.game.state.elixir_rate == 3
        assert not ref.success()
        state = ref.game.state
        with patch.object(type(ref.game), "state", new_callable=PropertyMock) as mocked:
            mocked.return_value = msgspec.structs.replace(state, game_over=False, winner=0)
            assert not ref.success(), "An unfinished HP lead must fail"
            mocked.return_value = msgspec.structs.replace(state, game_over=True, winner=1)
            assert not ref.success()
        assert not {"spend_budget", "damage_limit", "only_card", "max_decisions"}.intersection(cfg["scenario"])
        assert "before the overtime HP tiebreak" in cfg["objective"]
        text = instruction(cfg)
        assert "cr play SLOT X Y" in text and "Missing or partial play scores zero" in text
        assert "60 seconds" in text and "cannot award success here" in text
        assert "no spending, lane, damage, card, or decision-count objectives" in text
        assert min(cfg["scenario"]["tower_hp"][1][1:]) > 342
        for deck in (cfg["agent_deck"], cfg["opponent_deck"]):
            validate_deck(deck)
        assert set(cfg["scenario"]["order"]) == set(cfg["agent_deck"])
        assert set(cfg["scenario"]["opponent_order"]) == set(cfg["opponent_deck"])
        for unit in cfg["scenario"]["units"]:
            assert unit["card"] in cfg["agent_deck"] if unit["team"] == 0 else unit["card"] in cfg["opponent_deck"]
    finally:
        ref.opponent.close()


def test_second_wave_is_disclosed_and_reserved_in_a_legal_hand():
    cfg = catalog()[1]
    attack = cfg["scenario"]["scheduled_attack"]
    assert attack == dict(card="Minions", after_s=4, x=3.5, y=22)
    assert attack["card"] in cfg["scenario"]["opponent_order"][:4]
    text = instruction(cfg)
    assert "scheduled Minions is guaranteed" in text and "4.0 seconds" in text


def test_catalog_does_not_share_mutable_inputs():
    expected = deepcopy(catalog())
    changed = catalog()
    changed[0]["scenario"]["tower_hp"][0][1] = 0
    changed[1]["planner"]["top_k"] = 99
    assert catalog() == expected


def test_packaged_cohort_matches_validated_states_and_runtime():
    if not (OUT / "manifest.json").exists():
        pytest.skip("build the v7 cohort first")
    manifest = json.loads((OUT / "manifest.json").read_text())
    benchmark = load_benchmark(OUT)
    assert set(benchmark.tasks) == {c["id"] for c in catalog()}
    assert manifest["version"] == VERSION
    assert not (OUT / "dataset.toml").exists()
    for cfg in catalog():
        task = benchmark.tasks[cfg["id"]]
        assert not task_problems(task)
        assert packaged_protocol_digest(task.path) == manifest["protocol_sha256"] == protocol_digest()
        packaged = json.loads((task.path / "tests/task.json").read_text())
        assert packaged == json.loads((task.path / "environment/task.json").read_text())
        assert packaged["scenario"] == cfg["scenario"]
        assert packaged["instruction_sha256"] == digest((task.path / "instruction.md").read_text())
        assert packaged["rubric"] == "binary-crown-win-coordinates-v1"
        assert task.config["agent"]["user"] == "player"
        assert task.config["verifier"]["network_mode"] == "no-network"
        assert not list((task.path / "environment").rglob("reference.jsonl"))
        assert not (task.path / "environment/referee/build_v7.py").exists()
        row = next(r for r in manifest["tasks"] if r["task"] == cfg["id"])
        assert row["config_sha256"] == digest(cfg)
        assert row["reference_log_sha256"] == digest((EVIDENCE / cfg["id"] / "reference.jsonl").read_text())
        assert row["reward"] == row["integrity"] == 1 and row["deterministic"] is True
        assert row["reference_outcome"]["crowns_for"] == 1
        assert row["reference_outcome"]["rejected_actions"] == 0
        assert set(row["negative_rewards"]) == {"wait", "spell-rush", "bridge-rush", "empty", "malformed", "wrong-type", "partial"}
        assert not any(row["negative_rewards"].values())
        for path in task.path.rglob("*"):
            if path.is_file() and (path.suffix == ".sh" or path.name == "Dockerfile"):
                assert b"\r\n" not in path.read_bytes()
