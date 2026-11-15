"""Clip defenses retain the frozen protocol and grade timing, survival and delayed damage."""
import json

import pytest
from valkyrie.sdk.task_content import task_digest

from cr_arena.build_tactics import FOUNDATION_PROTOCOL, OUT
from cr_arena.build_tactics_clips import EVIDENCE, SOURCE_DIGESTS, TASKS, configs, instruction
from cr_arena.build_tactics_hog import build as historical_hog_build
from cr_arena.coordinate_benchmark import packaged_protocol_digest
from cr_arena.royale_task import make_referee, verify


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("case,expected", [("reference", 1), ("mistimed", 0), ("misplaced", 0)])
def test_packaged_logs_grade_timing_and_placement(task, case, expected):
    cfg = json.loads((OUT / task / "tests/task.json").read_text())
    report = verify(cfg, EVIDENCE / task / f"{case}.jsonl", None)
    assert report["rewards"]["reward"] == expected
    assert report["rewards"]["integrity"] == report["rewards"]["completed"] == 1
    assert not report["outcome"]["opponent_plays"]
    assert report["outcome"]["elapsed_s"] == 16


def test_balloon_death_bomb_is_resolved_and_spends_the_full_damage_allowance(tmp_path):
    cfg = configs()[1]
    report = verify(cfg, EVIDENCE / cfg["id"] / "reference.jsonl", tmp_path)
    assert report["rewards"]["reward"] == 1
    assert report["outcome"]["tower_damage"] == cfg["scenario"]["damage_limit"] == 240
    from royalegym.replay import load_trace
    trace = load_trace(tmp_path / "replay.msgpack")
    def tower_hp(frame, slot):
        return next(e.hp for e in frame.entities if e.team == 0 and e.tower_slot == slot and e.card_id == -1)
    assert [tower_hp(trace.frames[-1], slot) for slot in range(3)] == [4824, 1, 3052]
    changes = [(f.tick, tower_hp(f, 1)) for f in trace.frames if tower_hp(f, 1) < 241]
    assert changes and changes[0][0] > cfg["scenario"]["start_tick"] + 12 * 20
    assert trace.frames[-1].tick == cfg["scenario"]["start_tick"] + 16 * 20


def test_wrong_card_is_rejected_without_bypassing_one_play_restriction():
    for cfg in configs():
        ref = make_referee(cfg)
        try:
            action = dict(cmd="play", slot=1 if cfg["family"] == 6 else 0, x=7.5, y=13.5)
            before = ref.tick
            assert ref.entry(action, 1)["rejection"] == "SCENARIO_CARD_UNAVAILABLE"
            ref.act_action(action)
            assert ref.tick == before + cfg["decision_ticks"]
            assert ref.spent == 0 and ref.rejected_actions == 1 and not ref.over
        finally:
            ref.opponent.close()


def test_only_new_tasks_change_and_share_the_frozen_runtime():
    for task, expected in SOURCE_DIGESTS.items():
        assert task_digest(OUT / task) == expected
    for task in TASKS:
        assert packaged_protocol_digest(OUT / task) == FOUNDATION_PROTOCOL
        assert (OUT / task / "tests/task.json").read_bytes() == (OUT / task / "environment/task.json").read_bytes()
        assert (OUT / task / "solution/reference.jsonl").read_bytes() == (EVIDENCE / task / "reference.jsonl").read_bytes()


def test_historical_hog_builder_cannot_remove_clip_tasks(tmp_path):
    with pytest.raises(ValueError, match="build_tactics_clips"):
        historical_hog_build(OUT, tmp_path)


def test_instructions_disclose_limits_and_normalized_levels_without_solution():
    for cfg in configs():
        text = instruction(cfg)
        assert "standard level 11" in text and "exactly once" in text
        assert "12 decisions" in text and "delayed explosions" in text
        assert "7.5, 13.5" not in text and "3.5, 7.5" not in text
        assert cfg["scenario"]["grading"] == "one_spell"
