"""The merged release preserves every pinned source package and its objective."""
from collections import Counter
import json

from valkyrie.sdk.task_content import task_digest

from cr_arena.build_v6 import OUT, SOURCES
from cr_arena.coordinate_benchmark import packaged_protocol_digest
from rb_evals.benchmarks import load_benchmark, task_problems
from rb_evals.config import load_config


def test_v6_is_the_dashboard_default():
    assert load_config().default_dataset == OUT.name == "royalebench-v6"


def test_merge_is_the_exact_pinned_union_with_original_grading():
    manifest = json.loads((OUT / "manifest.json").read_text())
    benchmark = load_benchmark(OUT)
    assert manifest["version"] == "6.0.0"
    assert manifest["task_count"] == len(benchmark.tasks) == 14
    assert manifest["task_packages_unchanged"] is True
    assert Counter(row["source"] for row in manifest["tasks"]) == {
        "royalebench/royalebench-v5@1": 10, "royalebench/royalebench-win@2": 4}
    assert {(s["dataset"], s["digest"]) for s in manifest["sources"]} == {
        (f"royalebench/{name}@{revision}", digest) for name, revision, digest, _ in SOURCES}
    assert set(benchmark.tasks) == set(manifest["runnable_tasks"])
    assert not (OUT / "dataset.toml").exists()
    assert not (OUT / "metric.py").exists()
    for row in manifest["tasks"]:
        task = benchmark.tasks[row["task"]]
        assert not task_problems(task)
        assert task_digest(task.path) == row["digest"]
        assert packaged_protocol_digest(task.path) == row["protocol_sha256"]
        cfg = json.loads((task.path / "tests/task.json").read_text())
        assert cfg == json.loads((task.path / "environment/task.json").read_text())
        assert cfg["scenario"]["grading"] == row["grading"]
        assert cfg["objective"] == row["objective"]
        if row["source"].endswith("win@2"):
            assert row["grading"] == "win"
        assert task.config["agent"]["user"] == "player"
        assert task.config["verifier"]["network_mode"] == "no-network"
        assert not list((task.path / "environment").rglob("reference.jsonl"))
