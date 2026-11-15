"""v9 preserves v8 and all three requested tasks, with playable exact-version resolutions."""
from collections import Counter
import dataclasses
import hashlib
import json

import pytest
from valkyrie.sdk.task_content import task_digest

from cr_arena.build_v9 import ADDITIONS, BASE, EVIDENCE, HOG_RUN, OUT, ROOT
from cr_arena.coordinate_benchmark import packaged_protocol_digest
from cr_arena.validate_v9 import inherited_reference
from rb_evals.benchmarks import load_benchmark, task_problems
from rb_evals.resolutions import resolution_replay
from tests.helpers import ApiCase


def manifest():
    return json.loads((OUT / "manifest.json").read_text())


def test_v9_extends_the_exact_v8_release_with_only_the_requested_tasks():
    m = manifest(); benchmark = load_benchmark(OUT)
    base = load_benchmark(ROOT / "benchmarks/royalebench-v8")
    assert m["version"] == "9.0.0" and m["task_count"] == len(benchmark.tasks) == 21
    assert m["base_dataset"] == "royalebench/royalebench-v8@1"
    assert m["sources"][0]["digest"] == BASE[2]
    assert set(benchmark.tasks) == set(m["runnable_tasks"]) == set(base.tasks) | set(ADDITIONS)
    assert Counter(r["source"] for r in m["tasks"]) == {
        "royalebench/royalebench-v8@1": 18, "royalebench/royalebench-tactics@6": 3}
    assert m["requested_hog_run"]["run_id"] == HOG_RUN
    assert m["requested_hog_run"]["dataset"] == "royalebench/royalebench-tactics@5"
    assert m["requested_hog_run"]["digest"] == ADDITIONS["05-hog-body-block"]
    assert m["task_packages_unchanged"]
    assert not (OUT / "dataset.toml").exists() and not (OUT / "metric.py").exists()
    for row in m["tasks"]:
        task = benchmark.tasks[row["task"]]
        source = base.tasks[task.id].path if task.id in base.tasks else ROOT / "benchmarks/royalebench-tactics" / task.id
        assert task_digest(task.path) == row["digest"] == task_digest(source)
        assert not task_problems(task)
        assert packaged_protocol_digest(task.path) == row["protocol_sha256"]
        cfg = json.loads((task.path / "tests/task.json").read_text())
        assert cfg == json.loads((task.path / "environment/task.json").read_text())
        assert cfg["objective"] == row["objective"] and cfg["scenario"]["grading"] == row["grading"]
        assert task.config["agent"]["user"] == "player"
        assert task.config["verifier"]["network_mode"] == "no-network"


@pytest.mark.parametrize("task", [r["task"] for r in manifest()["tasks"]])
def test_every_task_has_a_playable_matching_resolution(task):
    result = resolution_replay(OUT / task, EVIDENCE)
    assert result["available"], result.get("message")
    assert f"Reference solution: {task}" in result["html"]
    assert 'aria-label="Timeline"' in result["html"]
    assert 'aria-label="Play or pause"' in result["html"]


def test_runtime_specific_manifests_support_existing_dashboard_versions():
    seen = set()
    for path in EVIDENCE.glob("docker-runtime-*/validation.json"):
        m = json.loads(path.read_text())
        for row in m["tasks"]:
            assert row["task"] not in seen
            seen.add(row["task"])
            assert row["protocol_sha256"] == m["protocol_sha256"]
            assert row["reward"] == row["integrity"] == 1
            assert row["isolated"] and row["restart_verified"] and row["replay_hashes_verified"]
            replay = path.parent / row["task"] / "replay.msgpack"
            assert hashlib.sha256(replay.read_bytes()).hexdigest() == row["replay_sha256"]
    assert seen == set(manifest()["runnable_tasks"])


def test_inherited_evidence_cannot_be_reused_for_changed_task_bytes():
    row = next(r for r in manifest()["tasks"] if r["source"].endswith("v8@1"))
    with pytest.raises(ValueError, match="exact v9 package"):
        inherited_reference(dict(row, digest="sha256:changed"))


class V9ResolutionAPITests(ApiCase):
    def test_all_21_resolutions_open_through_api_without_a_model_run(self):
        self.ctx.cfg = dataclasses.replace(self.ctx.cfg, benchmarks_dir=ROOT / "benchmarks", read_only=True)
        before = len(self.fake.list_runs(self.cfg.benchmark))
        for task in manifest()["runnable_tasks"]:
            with self.subTest(task=task):
                response = self.client.get(f"/api/evals/benchmarks/royalebench-v9/tasks/{task}/resolution")
                self.assertEqual(response.status_code, 200, response.text[:150])
                self.assertTrue(response.json()["available"])
                self.assertIn('aria-label="Timeline"', response.json()["html"])
        self.assertEqual(len(self.fake.list_runs(self.cfg.benchmark)), before)
