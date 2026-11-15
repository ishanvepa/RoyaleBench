"""The combined benchmark retains the complete v6 and v7 source packages."""
from collections import Counter
import json

from valkyrie.sdk.task_content import task_digest

from cr_arena.build_v8 import OUT, ROOT, SOURCES
from cr_arena.coordinate_benchmark import packaged_protocol_digest
from rb_evals.benchmarks import load_benchmark, task_problems
from rb_evals.config import EvalsConfig, load_config


def test_v8_is_the_dashboard_and_fallback_default():
    assert load_config().default_dataset == EvalsConfig().default_dataset == OUT.name


def test_v8_is_the_exact_published_source_union_with_original_grading():
    manifest = json.loads((OUT / "manifest.json").read_text())
    benchmark = load_benchmark(OUT)
    assert manifest["version"] == "8.0.0"
    assert manifest["task_count"] == len(benchmark.tasks) == 18
    assert manifest["task_packages_unchanged"] is True
    assert Counter(row["source"] for row in manifest["tasks"]) == {
        "royalebench/royalebench-v6@1": 14, "royalebench/royalebench-v7@1": 4}
    assert {(s["dataset"], s["digest"], s["task_count"]) for s in manifest["sources"]} == {
        (f"royalebench/{name}@{revision}", digest, count) for name, revision, digest, count in SOURCES}
    sources = {name: load_benchmark(ROOT / "benchmarks" / name) for name, *_ in SOURCES}
    assert set(benchmark.tasks) == set().union(*(set(s.tasks) for s in sources.values()))
    assert set(benchmark.tasks) == set(manifest["runnable_tasks"])
    assert not (OUT / "dataset.toml").exists()
    assert not (OUT / "metric.py").exists()
    win_count = 0
    for row in manifest["tasks"]:
        task = benchmark.tasks[row["task"]]
        source_name = row["source"].split("/")[1].split("@")[0]
        source = sources[source_name].tasks[row["task"]]
        assert task_digest(task.path) == row["digest"] == task_digest(source.path)
        assert not task_problems(task)
        assert packaged_protocol_digest(task.path) == row["protocol_sha256"]
        cfg = json.loads((task.path / "tests/task.json").read_text())
        assert cfg == json.loads((task.path / "environment/task.json").read_text())
        assert cfg["scenario"]["grading"] == row["grading"]
        assert cfg["objective"] == row["objective"]
        win_count += row["grading"] == "win"
        if source_name == "royalebench-v7":
            assert row["grading"] == "win"
            assert cfg["scenario"]["start_tick"] + cfg["scenario"]["horizon_s"] * 20 < 6000
        assert task.config["agent"]["user"] == "player"
        assert task.config["verifier"]["network_mode"] == "no-network"
        assert not list((task.path / "environment").rglob("reference.jsonl"))
    assert win_count == 12
