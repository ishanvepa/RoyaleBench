"""Coordinate protocol behavior, independent replay, CLI/socket integration and packaging."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

import pytest

from cr_arena import cr_client
from cr_arena.coordinate_benchmark import (BASE, OUT, PILOT, config, packaged_protocol_digest,
                                           reference_actions, play, protocol_digest)
from cr_arena.royale_task import GameServer, make_referee, read_log, replay_entries, verify
from cr_arena.telemetry import digest


@pytest.fixture
def cfg():
    return config("08-cycle-to-lethal")


def test_observation_has_slots_but_no_menu_or_target_suggestions(cfg):
    text = make_referee(cfg).observation()
    assert "HAND SLOTS (zero-based): 0: IceSpirits" in text
    assert "LEGAL MOVES" not in text and "cr act" not in text
    assert "cr play SLOT X Y" in text


@pytest.mark.parametrize("action", [
    {"cmd": "play", "slot": 9, "x": 3.5, "y": 10.5},
    {"cmd": "play", "slot": 0, "x": -1, "y": 10.5},
    {"cmd": "play", "slot": 0, "x": 18, "y": 10.5},
    {"cmd": "play", "slot": 0, "x": 3.5, "y": 32},
    {"cmd": "play", "slot": -1, "x": 3.5, "y": 10.5},
])
def test_illegal_plays_consume_interval_as_wait_and_replay(cfg, action, tmp_path):
    ref, idle = make_referee(cfg), make_referee(cfg)
    entry = ref.entry(action, 3.0)
    assert entry["accepted"] is False and entry["rejection"]
    assert "rejected" in ref.act_action(action)
    idle.act(0)
    assert ref.tick == idle.tick == entry["tick"] + 40
    assert digest(ref.game.state) == digest(idle.game.state)
    assert ref.spent == 0 and ref.rejected_actions == 1
    fresh = make_referee(cfg)
    assert replay_entries(fresh, [entry]) == 1
    assert fresh.outcome() == ref.outcome()


def test_raw_illegal_point_is_not_snapped(cfg):
    cfg = config("01-immediate-lethal")
    ref = make_referee(cfg)
    # Cannon can be snapped to a legal nearby position by the legacy menu builder.
    assert ref.game._legal_point(0, 1, 9, 15.5, True) is not None
    _, metadata = ref.prepare_action(dict(cmd="play", slot=1, x=9, y=15.5))
    assert metadata["accepted"] is False and metadata["rejection"] == "WATER"


def test_coordinates_outside_prepared_menu_are_accepted():
    ref = make_referee(config("03-spell-placement"))
    x, y = 4.25, 10.25
    assert all(ref.game.own_tiles(0, m.x, m.y) != (x, y)
               for m in ref.game.legal_moves(0) if m.slot == 0)
    _, meta = ref.prepare_action(dict(cmd="play", slot=0, x=x, y=y))
    assert meta["accepted"]
    assert ref.game.own_tiles(0, meta["deployment"]["x"], meta["deployment"]["y"]) == (x, y)
    assert "played Fireball" in ref.act_action(dict(cmd="play", slot=0, x=x, y=y))
    assert (ref.plays[0]["x"], ref.plays[0]["y"]) == (meta["deployment"]["x"], meta["deployment"]["y"])


def test_overspending_is_possible_but_scores_zero(tmp_path):
    cfg = json.loads((BASE / "02-efficient-defense/tests/task.json").read_text())
    cfg.update(action_mode="coordinates-v1")
    ref = make_referee(cfg)
    actions = [dict(cmd="play", slot=0, x=9, y=10.5),
               dict(cmd="play", slot=3, x=14.5, y=25.5)]
    entries = []
    for action in actions:
        entry = ref.entry(action, 3.0)
        assert entry["accepted"]
        entries.append(entry)
        ref.act_action(action)
    assert ref.spent == 5 > cfg["scenario"]["spend_budget"]
    while not ref.over:
        entries.append(ref.entry({"cmd": "wait"}, 3.0))
        ref.act(0)
    log = tmp_path / "overspend.jsonl"
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))
    rewards = verify(cfg, log, None)["rewards"]
    assert rewards["completed"] == rewards["integrity"] == 1
    assert rewards["reward"] == 0


@pytest.mark.parametrize("name", PILOT)
def test_reference_solvability_and_deterministic_replay(name, tmp_path):
    cfg = config(name)
    log = tmp_path / "reference.jsonl"
    ref = play(cfg, log, reference_actions(name))
    a, b = verify(cfg, log, None), verify(cfg, log, None)
    assert a == b and a["outcome"] == ref.outcome()
    assert a["rewards"]["reward"] == a["rewards"]["integrity"] == 1
    assert verify(cfg, tmp_path / "absent.jsonl", None)["rewards"]["reward"] == 0


@pytest.mark.parametrize("field,value", [
    ("state_hash", "tampered"), ("application_tick", -1),
    ("accepted", False), ("deployment", None), ("tick", 0),
    ("action", {"cmd": "play", "slot": 0, "x": 14.5, "y": 25.5}),
    ("action", {"cmd": "play", "slot": 0, "x": 3.500001, "y": 25.5}),
])
def test_tampering_is_detected(field, value, tmp_path):
    cfg = config("01-immediate-lethal")
    log = tmp_path / "reference.jsonl"
    play(cfg, log, reference_actions(cfg["id"]))
    entries = read_log(log)
    entries[0][field] = value
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))
    rewards = verify(cfg, log, None)["rewards"]
    assert rewards["reward"] == rewards["integrity"] == 0


def test_nested_deployment_types_are_checked(tmp_path):
    cfg = config("01-immediate-lethal")
    log = tmp_path / "reference.jsonl"
    play(cfg, log, reference_actions(cfg["id"]))
    entries = read_log(log)
    entries[0]["deployment"]["team"] = False  # False == 0 in Python, but not in the log schema.
    log.write_text("".join(json.dumps(e) + "\n" for e in entries))
    assert verify(cfg, log, None)["rewards"]["integrity"] == 0


def test_scenario_card_restriction_still_applies():
    ref = make_referee(config("03-spell-placement"))
    _, metadata = ref.prepare_action(dict(cmd="play", slot=2, x=3.5, y=10.5))
    assert metadata["accepted"] is False
    assert metadata["rejection"] == "SCENARIO_CARD_UNAVAILABLE"


@pytest.mark.parametrize("action", [
    {"cmd": "act", "move": 0}, {"cmd": "play", "slot": True, "x": 1, "y": 1},
    {"cmd": "play", "slot": 0, "x": float("nan"), "y": 1},
    {"cmd": "play", "slot": 0, "x": 1, "y": float("inf")},
    {"cmd": "play", "slot": 0, "x": "3.5", "y": 1},
    {"cmd": "wait", "extra": 1},
])
def test_malformed_requests_do_not_mutate_state(cfg, action):
    ref = make_referee(cfg)
    before = digest(ref.game.state)
    with pytest.raises(ValueError):
        ref.act_action(action)
    assert ref.decision == 0 and digest(ref.game.state) == before


def test_cli_payload_and_nan_rejection(monkeypatch):
    calls = []
    monkeypatch.setattr(cr_client, "call", lambda p: calls.append(p) or {"ok": True, "text": "ok"})
    assert cr_client.main(["play", "2", "4.25", "10.5"]) == 0
    assert calls[-1] == dict(cmd="play", slot=2, x=4.25, y=10.5)
    assert cr_client.main(["wait"]) == 0 and calls[-1] == {"cmd": "wait"}
    assert cr_client.main(["play", "0", "nan", "1"]) == 2
    assert len(calls) == 2


def test_unobserved_action_timing_is_unknown_and_replays(cfg, tmp_path):
    with tempfile.TemporaryDirectory(prefix="cr-coord-", dir="/tmp") as short:
        log = tmp_path / "actions.jsonl"
        server = GameServer(str(Path(short) / "cr.sock"), make_referee(cfg), log)
        try:
            assert server.handle_command({"cmd": "wait"})["ok"]
        finally:
            server.server_close()
        assert read_log(log)[0]["think_s"] is None
        assert verify(cfg, log, None)["timing_known"] == 0


def test_rejection_telemetry_is_not_a_voluntary_wait(cfg, tmp_path):
    from rb_evals.archive import export_tables, read_jsonl
    from cr_arena.telemetry import TABLES
    with tempfile.TemporaryDirectory(prefix="cr-coord-", dir="/tmp") as short:
        server = GameServer(str(Path(short) / "cr.sock"), make_referee(cfg), tmp_path / "actions.jsonl")
        try:
            server.handle_command({"cmd": "observe"})
            server.handle_command(dict(cmd="play", slot=9, x=0, y=0))
        finally:
            server.server_close()
        events = list(read_jsonl(tmp_path / "capture/events.jsonl"))
        assert any(r["data"].get("event") == "coordinate_attempt"
                   and r["data"]["accepted"] is False for r in events)
        commands = list(read_jsonl(tmp_path / "capture/commands.jsonl"))
        assert any(r["data"].get("action_source") == "rejected_action" for r in commands)
        (tmp_path / "manifest.json").write_text("{}")
        rows = {table: {} for table in TABLES}
        for path in (tmp_path / "capture").glob("*.jsonl"):
            rows[path.stem] = {r["record_id"]: r for r in read_jsonl(path)}
        export_tables(tmp_path, rows)
        players = list(read_jsonl(tmp_path / "derived/v1/players.jsonl"))
        player = next(p for p in players if p["team"] == 0)
        assert player["voluntary_waits"] == player["wait_rate"] == 0
        assert player["error_waits"] == 1


def test_cli_socket_partial_restart_and_rejected_attempt(cfg, tmp_path):
    with tempfile.TemporaryDirectory(prefix="cr-coord-", dir="/tmp") as short:
        sock = str(Path(short) / "cr.sock")
        log = tmp_path / "actions.jsonl"
        server = GameServer(sock, make_referee(cfg), log)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def cli(*args):
            return subprocess.run([sys.executable, str(Path(cr_client.__file__)), *args],
                                  env={**os.environ, "CR_SOCKET": sock}, text=True, capture_output=True,
                                  timeout=20)
        try:
            assert "HAND SLOTS" in cli().stdout
            assert cli("act", "0").returncode == 1
            assert not log.exists()
            assert "rejected" in cli("play", "9", "0", "0").stdout
            assert "DECISION 2" in cli().stdout
            assert cli("wait").returncode == 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        resumed = make_referee(cfg)
        assert replay_entries(resumed, read_log(log)) == 2
        assert resumed.outcome() == server.ref.outcome()
        report = verify(cfg, log, None)
        assert report["rewards"]["integrity"] == 1 and report["rewards"]["completed"] == 0


def test_packaged_coordinate_pilot_and_frozen_baseline():
    from rb_evals.benchmarks import load_benchmark, task_problems
    if not OUT.exists():
        pytest.skip("build the coordinate pilot first")
    benchmark = load_benchmark(OUT)
    assert set(benchmark.tasks) == set(PILOT)
    manifest = json.loads((OUT / "manifest.json").read_text())
    for task in benchmark.tasks.values():
        assert packaged_protocol_digest(task.path) == manifest["protocol_sha256"]
        assert not task_problems(task)
        assert task.config["metadata"]["action_mode"] == "coordinates-v1"
        assert task.config["verifier"]["environment_mode"] == "separate"
        text = (task.path / "instruction.md").read_text()
        assert "cr play SLOT X Y" in text and "cr act N" not in text
        baseline = json.loads((BASE / task.path.name / "tests/task.json").read_text())
        coordinate = json.loads((task.path / "tests/task.json").read_text())
        assert baseline["scenario"] == coordinate["scenario"]
        assert baseline["planner"] == coordinate["planner"]
        assert "action_mode" not in baseline
