"""V3 promotion must preserve states, gates and historical datasets while defaulting to coordinates."""
import json
import shutil

import pytest

from cr_arena.build_v3 import EVIDENCE, OUT, TITLE, VERSION, build, task_names
from cr_arena.build_v1 import MODEL_API_HOSTS
from cr_arena.coordinate_benchmark import (BASE, OUT as PILOT, build as build_coordinates, calibrate,
                                           packaged_protocol_digest, protocol_digest)
from cr_arena.telemetry import VERSION as CAPTURE_VERSION, digest
from rb_evals.benchmarks import load_benchmark, task_problems
from rb_evals.config import load_config


def test_v3_promotes_the_full_released_set():
    assert OUT.name == "royalebench-v3"
    assert len(task_names()) == 11
    assert set(task_names()) == set(json.loads((BASE / "manifest.json").read_text())["runnable_tasks"])


@pytest.mark.parametrize("historical", [BASE, PILOT])
def test_v3_cannot_overwrite_historical_datasets(historical, tmp_path):
    before = (historical / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="overwritten"):
        build(historical, tmp_path)
    assert (historical / "manifest.json").read_bytes() == before


def test_gated_scenario_cannot_be_promoted_by_selecting_it(tmp_path):
    with pytest.raises(ValueError, match="released v1"):
        build_coordinates(tmp_path / "dataset", tmp_path / "evidence", names=["12-comeback"])
    assert not (tmp_path / "dataset").exists()


def test_changed_cached_reference_is_recalibrated_before_release(tmp_path):
    name = "01-immediate-lethal"
    if not (EVIDENCE / name / "validation.json").exists():
        pytest.skip("calibrate v3 before checking its reference cache")
    shutil.copytree(EVIDENCE / name, tmp_path / name)
    reference = tmp_path / name / "reference.jsonl"
    reference.write_text("tampered reference\n")
    _, evidence = calibrate(name, tmp_path, title=TITLE, version=VERSION, reuse=True)
    assert evidence["reward"] == evidence["integrity"] == 1
    assert evidence["negative_rewards"] == dict(wait=0, empty=0, malformed=0)
    assert json.loads(reference.read_text().splitlines()[0])["action"]["cmd"] == "play"


def test_packaged_v3_has_coordinates_for_every_task_and_keeps_candidates_gated():
    if not (OUT / "manifest.json").exists():
        pytest.skip("build v3 before checking its packaged snapshot")
    manifest = json.loads((OUT / "manifest.json").read_text())
    benchmark = load_benchmark(OUT)
    assert benchmark.title == TITLE
    assert manifest["version"] == VERSION == "3.0.0"
    assert manifest["capture_schema_version"] == CAPTURE_VERSION
    assert set(benchmark.tasks) == set(task_names())
    assert {g["family"] for g in manifest["gated_tasks"]} == {11, 12}
    assert len(manifest["gated_tasks"]) == 3
    assert not list((OUT / "candidates").rglob("task.toml"))
    for name, task in benchmark.tasks.items():
        assert packaged_protocol_digest(task.path) == manifest["protocol_sha256"]
        assert not task_problems(task)
        assert task.config["metadata"]["action_mode"] == "coordinates-v1"
        assert task.config["metadata"]["dataset_version"] == VERSION
        assert task.config["task"]["name"] == f"royalebench/v3-{name}"
        cfg = json.loads((task.path / "tests/task.json").read_text())
        assert cfg == json.loads((task.path / "environment/task.json").read_text())
        assert cfg["task_id"] == name
        assert cfg["instruction_sha256"] == digest(task.instruction)
        assert cfg["rubric"] == "scenario-objective-coordinates-v1"
        assert cfg["capture_schema_version"] == CAPTURE_VERSION
        assert cfg["resources"] == {"agent_timeout_s": 3600, "verifier_timeout_s": 600,
                                    "cpus": 1, "memory_mb": 2048, "storage_mb": 4096}
        assert task.config["agent"]["network_mode"] == "allowlist"
        assert task.config["agent"]["allowed_hosts"] == list(MODEL_API_HOSTS)
        assert task.config["verifier"]["network_mode"] == "no-network"
        old = json.loads((BASE / name / "tests/task.json").read_text())
        for field in ("scenario", "seed", "agent_team", "agent_deck", "opponent_deck", "planner", "decision_ticks"):
            assert cfg[field] == old[field]
        assert cfg["benchmark"] == TITLE and cfg["version"] == VERSION
        assert "cr play SLOT X Y" in task.instruction and "cr act N" not in task.instruction
        assert not list((task.path / "environment").rglob("reference.jsonl"))
