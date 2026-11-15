"""Scenario setup, scoring, anti-shortcut and packaging checks using the real engine."""
import json
from pathlib import Path

import pytest

from cr_arena.build_v1 import release_problem
from cr_arena.decks import validate_deck
from cr_arena.royale_task import make_referee, verify
from cr_arena.royalebench_v1 import catalog, fireball_damage
from cr_arena.validate_v1 import pick, play


@pytest.fixture(scope="module")
def configs():
    return catalog()


def test_catalog_preserves_requested_families_and_planner(configs):
    assert len(configs) == 14
    assert {c["family"] for c in configs} == set(range(1, 13))
    assert len({c["id"] for c in configs}) == len(configs)
    for c in configs:
        assert c["benchmark"] == "RoyaleBench v1"
        assert c["opponent"] == "planner"
        assert validate_deck(c["agent_deck"]) == c["agent_deck"]
        assert set(c["scenario"]["order"]) == set(c["agent_deck"])
        assert set(c["scenario"]["opponent_order"]) == set(c["opponent_deck"])


def test_setup_and_cycle_are_exact(configs):
    cfg = next(c for c in configs if c["family"] == 8)
    a, b = make_referee(cfg), make_referee(cfg)
    assert a.setup_hash == b.setup_hash
    assert a.game.time_left_s() == (18, True)
    assert [a.game.card_name(c) for c in a.game.state.players[0].hand] == cfg["scenario"]["order"][:4]
    assert cfg["scenario"]["order"].index("Fireball") == 5


def test_verified_lethal_replays_and_requires_submission(configs, tmp_path):
    cfg = configs[0]
    assert cfg["scenario"]["tower_hp"][1][2] < fireball_damage()
    log = tmp_path / "actions.jsonl"
    ref = play(cfg, log, lambda r: pick(r, "Fireball", "enemy left princess tower"))
    report = verify(cfg, log, tmp_path / "verified")
    assert ref.success()
    assert report["rewards"]["reward"] == 1
    assert report["rewards"]["integrity"] == 1
    assert report == verify(cfg, log, tmp_path / "verified-again")
    assert (tmp_path / "verified/replay.msgpack").is_file()
    assert verify(cfg, tmp_path / "missing.jsonl", None)["rewards"]["reward"] == 0


@pytest.mark.parametrize("content", ["invalid json", "[]", "null", '{"move": true}',
                                     '{"decision":0,"tick":5100,"move":1.5,"label":"wrong"}',
                                     '{"decision":0,"tick":5100,"move":0,"label":"wrong","think_s":{}}'])
def test_bad_logs_score_zero_without_crashing(configs, tmp_path, content):
    log = tmp_path / "bad.jsonl"
    log.write_text(content)
    rewards = verify(configs[0], log, None)["rewards"]
    assert rewards["reward"] == 0 and rewards["integrity"] == 0


def test_overspending_is_unavailable_and_partial_log_is_not_success(configs, tmp_path):
    cfg = next(c for c in configs if c["family"] == 2)
    ref = make_referee(cfg)
    ref.act(pick(ref, "Cannon", "center (between towers)"))
    assert ref.spent == 3 and ref.over and ref.success()
    # Cannon spends all but 1 of the hard budget, so the remaining window is forced waiting.
    assert ref.outcome()["elapsed_s"] == 12
    log = tmp_path / "empty.jsonl"
    log.write_text("")
    assert verify(cfg, log, None)["rewards"]["completed"] == 0


def test_wrong_spell_target_fails(configs, tmp_path):
    cfg = next(c for c in configs if c["family"] == 3)
    good = play(cfg, tmp_path / "good.jsonl", lambda r: pick(r, "Fireball", "enemy Minions"))
    bad = play(cfg, tmp_path / "bad.jsonl", lambda r: pick(r, "Fireball", "enemy right princess tower"))
    assert good.success() and not bad.success()
    assert good.outcome()["tower_damage"] < bad.outcome()["tower_damage"]


def test_unproven_scenarios_cannot_be_released(configs):
    for cfg in configs:
        assert release_problem(cfg, None)
        if cfg["family"] in (11, 12):
            assert cfg["release_gate"]


def test_reference_revalidation_refuses_changed_scenarios_or_logs(configs, tmp_path):
    import hashlib
    from cr_arena.validate_v1 import calibrate

    cfg = configs[0]
    folder = tmp_path / cfg["id"]
    folder.mkdir()
    (folder / "reference.jsonl").write_text("{}\n")
    evidence = dict(config_sha256="old configuration", reference_reward=1,
                    reference_log_sha256=hashlib.sha256(b"{}\n").hexdigest())
    (folder / "validation.json").write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="unchanged"):
        calibrate(cfg, tmp_path, reuse_reference=True)
    evidence["config_sha256"] = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    (folder / "validation.json").write_text(json.dumps(evidence))
    (folder / "reference.jsonl").write_text("different log\n")
    with pytest.raises(ValueError, match="differs"):
        calibrate(cfg, tmp_path, reuse_reference=True)


def test_built_dataset_is_discoverable_and_has_lf_only():
    from rb_evals.benchmarks import load_benchmark, task_problems

    root = Path("benchmarks/royalebench-v1")
    if not (root / "manifest.json").exists():
        pytest.skip("run build_v1 after local calibration")
    benchmark = load_benchmark(root)
    assert benchmark.title == "RoyaleBench v1"
    manifest = json.loads((root / "manifest.json").read_text())
    assert set(benchmark.tasks) == set(manifest["runnable_tasks"])
    for task in benchmark.tasks.values():
        assert task_problems(task) == []
        assert task.config["metadata"]["opponent"] == "planner"
        assert task.config["verifier"]["environment_mode"] == "separate"
        assert task.config["agent"]["network_mode"] == "allowlist"
        assert task.config["environment"]["network_mode"] == "public"
        assert task.config["verifier"]["network_mode"] == "no-network"
        from cr_arena.telemetry import digest
        config = json.loads((task.path / "environment/task.json").read_text())
        assert config == json.loads((task.path / "tests/task.json").read_text())
        assert config["task_id"] == task.path.name
        assert config["instruction_sha256"] == digest((task.path / "instruction.md").read_text())
        assert config["capture_schema_version"] == "1.0"
        assert config["resources"]["cpus"] == task.config["environment"]["cpus"]
        assert (task.path / "environment/referee/telemetry.py").is_file()
        for path in task.path.rglob("*"):
            if path.is_file():
                assert b"\r\n" not in path.read_bytes(), path


@pytest.mark.parametrize("family", [1, 2, 10])
def test_scenario_carried_capture_replays_actual_play(configs, tmp_path, family):
    import tempfile
    from royalegym import RustEngine
    from royalegym.replay import load_trace, verify_trace
    from cr_arena.royale_task import GameServer
    from rb_evals.archive import read_jsonl

    cfg = next(c for c in configs if c["family"] == family)
    ref = make_referee(cfg, record=True)
    server = GameServer(tempfile.mktemp(dir="/tmp", prefix="rb-"), ref, tmp_path / "actions.jsonl")
    try:
        start = ref.tick
        server.handle_command({"cmd": "observe"})
        rejected = server.handle_command({"cmd": "act", "move": -1})
        assert not rejected["ok"]
        choice = pick(ref, "Fireball", "enemy left princess tower") if family == 1 else (
            pick(ref, "Cannon", "center (between towers)") if family == 2 else 0)
        server.handle_command({"cmd": "act", "move": choice})
        trace = load_trace(tmp_path / "replay.msgpack")
        assert trace.frames[0].tick == start
        assert trace.frames[-1].tick == ref.tick
        assert not verify_trace(trace, RustEngine())
        assert ref.over == (family != 10)
        events = list(read_jsonl(tmp_path / "capture/events.jsonl"))
        assert any(r["data"].get("event") == "invalid_command" for r in events)
        ticks = [r["data"] for r in events if r["data"].get("event") == "engine_tick"]
        assert len(ticks) == ref.tick - start
        assert all(resource["exact"] for tick in ticks for resource in tick["resources"])
        commands = list(read_jsonl(tmp_path / "capture/commands.jsonl"))
        if family == 2:
            assert any(r["data"].get("action_source") == "forced_wait" for r in commands)
        manifest = json.loads((tmp_path / "capture/manifest.json").read_text())
        assert not manifest["capture_errors"]
        assert list(read_jsonl(tmp_path / "capture/observations.jsonl"))
    finally:
        server.server_close()
