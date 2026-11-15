"""Tests of strategic contrasts and release gates, using the pinned battle engine."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from cr_arena.build_v1 import build, instruction, release_problem
from cr_arena.royale_task import verify
from cr_arena.royalebench_v1 import protocol_digest
from cr_arena.tactics import TITLE, catalog, mirror
from cr_arena.validate_tactics import reference
from cr_arena.validate_v1 import pick, play


@pytest.fixture(scope="module")
def configs():
    return {c["id"]: c for c in catalog()}


def test_mirror_preserves_state_and_disclosed_schedule(configs):
    c = deepcopy(configs["02-reserve-counter-a"])
    initial = deepcopy(c)
    mirror(c)
    assert c["scenario"]["units"][0]["x"] == 14.5
    assert c["scenario"]["scheduled_attack"]["x"] == 14.5
    mirror(c)
    assert c == initial
    text = instruction(configs["02-reserve-counter-b"])
    assert "(14.5, 6.5)" in text and TITLE in text


def test_release_requires_each_contrast_even_with_winning_reference(configs):
    c = configs["03-tower-race-a"]
    evidence = dict(config_sha256=hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        protocol_sha256=protocol_digest(), reference_reward=1, deterministic=True,
        wait_success=False, empty_reward=0, malformed_reward=0, release_gate_passed=True)
    assert "contrast" in release_problem(c, evidence).lower()
    evidence["contrast_rewards"] = dict(c["validation_requirements"])
    assert "opening audit" in release_problem(c, evidence).lower()
    from cr_arena.royale_task import make_referee
    moves = make_referee(c).moves
    evidence["opening_audit"] = dict(config_sha256=evidence["config_sha256"],
        protocol_sha256=protocol_digest(), source_sha256=c["opening_audit_source_sha256"],
        trials=[dict(move_index=m.index, integrity=1, reward=int(m.card == "Fireball"), card=m.card) for m in moves])
    assert release_problem(c, evidence) is None
    evidence["opening_audit"]["trials"][0].update(reward=1, card="Cannon")
    assert "shortcut" in release_problem(c, evidence).lower()
    evidence["contrast_rewards"]["defend"] = 1
    assert release_problem(c, evidence) is not None


def test_timed_spell_requires_waiting_and_replays(configs, tmp_path):
    c = configs["01-timed-spell-a"]
    good_log = tmp_path / "good.jsonl"
    good = play(c, good_log, reference)
    bad = play(c, tmp_path / "early.jsonl", lambda r: pick(r, "Fireball", "enemy Giant") if not r.plays else 0)
    assert good.success() and good.outcome()["tower_damage"] == 0
    assert good.plays[0]["decision"] == 1
    assert not bad.success() and bad.outcome()["tower_damage"] > c["scenario"]["damage_limit"]
    assert verify(c, good_log, None)["rewards"]["reward"] == 1


@pytest.mark.parametrize("variant", ["a", "b"])
def test_tower_race_reverses_opening_outcomes(configs, tmp_path, variant):
    c = configs[f"03-tower-race-{variant}"]
    wins = {}
    for name, card, target in [("commit", "Fireball", "enemy left princess tower"),
                                ("defend", "Cannon", "left bridge"),
                                ("near_commit", "Fireball", "on your Giant")]:
        ref = play(c, tmp_path / f"{name}.jsonl", lambda r: pick(r, card, target) if r.decision == 0 else 0)
        wins[name] = int(ref.success())
    assert wins == {**c["validation_requirements"], "near_commit": int(variant == "a")}


def test_tower_trade_wins_after_losing_a_princess(configs, tmp_path):
    c = configs["04-tower-trade-a"]
    ref = play(c, tmp_path / "trade.jsonl", reference)
    assert ref.success()
    assert ref.game.state.players[0].tower_hp[1] == 0
    assert ref.outcome()["crowns_for"] == 2 and ref.outcome()["crowns_against"] == 1
    assert ref.outcome()["elapsed_s"] == 14


def test_generic_builder_preserves_title_and_gates_unvalidated_tasks(configs, tmp_path):
    result = build(tmp_path / "dataset", tmp_path / "no-evidence", configs=list(configs.values()),
                   guide="tactics.md", generator="cr_arena.build_tactics")
    assert result["benchmark"] == TITLE and result["runnable_tasks"] == []
    assert len(list((tmp_path / "dataset/candidates").glob("*.json"))) == 8
    assert "tactics.md" in (tmp_path / "dataset/README.md").read_text()


def test_packaged_tasks_are_discoverable_and_do_not_include_answers_in_environment():
    from rb_evals.benchmarks import load_benchmark, task_problems
    root = Path("benchmarks/royalebench-tactics")
    if not (root / "manifest.json").is_file():
        pytest.skip("build the calibrated Tactics dataset first")
    benchmark = load_benchmark(root)
    manifest = json.loads((root / "manifest.json").read_text())
    assert set(benchmark.tasks) == set(manifest["runnable_tasks"])
    for task in benchmark.tasks.values():
        assert task_problems(task) == []
        assert task.config["metadata"]["control"] is False
        assert task.config["verifier"]["environment_mode"] == "separate"
        assert not list((task.path / "environment").rglob("*reference*"))
        cfg = json.loads((task.path / "environment/task.json").read_text())
        assert cfg == json.loads((task.path / "tests/task.json").read_text())
