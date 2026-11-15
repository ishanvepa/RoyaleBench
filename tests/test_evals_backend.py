"""Evals backend: config, local benchmarks, job specs, results/leaderboard and the Valkyrie facade.

No network and no real credentials: Valkyrie is replaced by fakes.
    uv run python -m unittest tests.test_evals_backend -v
"""

import asyncio
import io
import json
import os
import tarfile
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from valkyrie.sdk import ValkyrieAPIError
from valkyrie.sdk.models import HostedDataset

from rb_evals import benchmarks as bm
from rb_evals import jobs, results
from rb_evals.config import ROOT, EvalsConfig, ModelPreset, load_config, secret_env_for
from rb_evals.valkyrie import TTLCache, Valkyrie, ValkyrieError, describe_error, run_sync

CFG = EvalsConfig(benchmarks_dir=Path("unused"))


def write(path: Path, text: str | bytes = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, newline="\n")  # text mode would write CRLF on Windows
    return path


def make_task(folder: Path, *, instruction="Do the thing.", tests="#!/bin/bash\necho 1 > /logs/verifier/reward.txt\n",
              toml='[task]\nname = "x/t"\n[metadata]\ncategory = "c"\ndifficulty = "easy"\n[agent]\ntimeout_sec = 60\n[verifier]\ntimeout_sec = 10\n'):
    write(folder / "task.toml", toml)
    if instruction is not None:
        write(folder / "instruction.md", instruction)
    if tests is not None:
        write(folder / "tests" / "test.sh", tests)


class ConfigTests(unittest.TestCase):
    def test_defaults_when_the_file_is_missing(self):
        cfg = load_config(Path(tempfile.gettempdir()) / "does-not-exist-evals.toml")
        self.assertEqual((cfg.benchmark, cfg.provider, cfg.default_concurrency), ("royalebench", "modal", 1))
        self.assertEqual(cfg.models, ())
        self.assertEqual(cfg.default_dataset, "royalebench-v8")

    def test_reads_values_and_read_only_flag(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d) / "evals.toml", '[valkyrie]\ndefault_dataset = "custom-coordinates"\nmax_concurrency = 3\nconfirm_over_tasks = 2\n'
                                                '[[models]]\nid = "openai/gpt-x"\nsecret_env = "MY_KEY"\n')
            with patch.dict(os.environ, {"ROYALEBENCH_EVALS_READONLY": "1"}):
                cfg = load_config(path)
            self.assertEqual((cfg.max_concurrency, cfg.confirm_over_tasks), (3, 2))
            self.assertEqual(cfg.default_dataset, "custom-coordinates")
            self.assertEqual(cfg.models, (ModelPreset("openai/gpt-x", "MY_KEY"),))
            self.assertTrue(cfg.read_only)
            with patch.dict(os.environ, {"ROYALEBENCH_EVALS_READONLY": ""}):
                self.assertFalse(load_config(path).read_only)

    def test_secret_env_for(self):
        presets = (ModelPreset("anthropic/special", "SPECIAL_KEY"),)
        self.assertEqual(secret_env_for("anthropic/claude-sonnet-4-6"), "ANTHROPIC_API_KEY")
        self.assertEqual(secret_env_for("openai/gpt-5"), "OPENAI_API_KEY")
        self.assertEqual(secret_env_for("acme-ai/m"), "ACME_AI_API_KEY")
        self.assertEqual(secret_env_for("anthropic/special", presets), "SPECIAL_KEY")

    def test_reads_endpoint_secret_references_and_stock_agent_options(self):
        with tempfile.TemporaryDirectory() as d:
            path = write(Path(d) / "evals.toml", '''[[models]]
id = "openai/Qwen/example"
secret_env = "OPENAI_API_KEY"
agent = "mini_swe_agent"
secrets = { OPENAI_API_BASE = "endpoint-url" }
agent_kwargs = { cost_tracking = "ignore_errors", step_limit = "12" }
''')
            preset = load_config(path).models[0]
            self.assertEqual(preset.agent, "mini_swe_agent")
            self.assertEqual(preset.secrets, {"OPENAI_API_BASE": "endpoint-url"})
            self.assertEqual(preset.agent_kwargs, {"cost_tracking": "ignore_errors", "step_limit": "12"})

    def test_repo_config_targets_modal_and_the_verified_model(self):
        cfg = load_config(ROOT / "evals.toml")
        self.assertEqual((cfg.benchmark, cfg.provider), ("royalebench", "modal"))
        self.assertIn("anthropic/claude-sonnet-4-6", [m.id for m in cfg.models])


class LocalBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write(self.root / "alpha" / "benchmark.toml", '[benchmark]\ntitle = "Alpha"\ndescription = "d"\nkind = "eval"\n')
        make_task(self.root / "alpha" / "t1")
        make_task(self.root / "alpha" / "group" / "t2")  # task folders may be nested
        write(self.root / "alpha" / "t1" / "inner" / "task.toml", "")  # inside a task: not another task
        write(self.root / "beta" / "benchmark.toml", '[benchmark]\nkind = "weird"\n')
        make_task(self.root / "beta" / "b1", toml="not = [valid")
        (self.root / "empty").mkdir()
        make_task(self.root / ".hidden" / "h1")

    def test_discovery_matches_dataset_push_rules(self):
        found = bm.discover_local(self.root)
        self.assertEqual(sorted(found), ["alpha", "beta"])
        self.assertEqual(sorted(found["alpha"].tasks), ["t1", "t2"])
        self.assertEqual((found["alpha"].display_title, found["alpha"].kind), ("Alpha", "eval"))

    def test_bad_metadata_is_reported_not_fatal(self):
        beta = bm.discover_local(self.root)["beta"]
        self.assertEqual(beta.kind, "eval")
        self.assertTrue(any("kind must be" in e for e in beta.errors))
        self.assertTrue(any("b1/task.toml" in e for e in beta.errors))

    def test_task_accessors(self):
        task = bm.discover_local(self.root)["alpha"].tasks["t1"]
        self.assertEqual((task.category, task.difficulty, task.agent_timeout_s, task.verifier_timeout_s),
                         ("c", "easy", 60, 10))
        self.assertEqual(task.instruction, "Do the thing.")
        self.assertIsNone(task.read("solution/solve.sh"))
        self.assertIn(("tests/test.sh", len(task.read("tests/test.sh"))), task.files())

    def test_task_problems(self):
        good = bm.discover_local(self.root)["alpha"].tasks["t1"]
        self.assertEqual(bm.task_problems(good), [])
        make_task(self.root / "alpha" / "bad", instruction="", tests=None, toml="[task]\nname='x'\n")
        bad = bm.discover_local(self.root)["alpha"].tasks["bad"]
        problems = " | ".join(bm.task_problems(bad))
        for expected in ("instruction.md", "tests/test.sh is missing", "timeout_sec"):
            self.assertIn(expected, problems)
        make_task(self.root / "alpha" / "crlf", tests=b"#!/bin/bash\r\necho reward\r\n")
        crlf = bm.discover_local(self.root)["alpha"].tasks["crlf"]
        self.assertTrue(any("CRLF" in p for p in bm.task_problems(crlf)))

    def test_benchmark_difficulties_override_display_without_changing_packages(self):
        path = self.root / "alpha"
        before = bm.local_digests(bm.load_benchmark(path))
        with (path / "benchmark.toml").open("a") as meta:
            meta.write('\n[task_difficulties]\nt1 = "hard"\n')
        bench = bm.load_benchmark(path)
        self.assertEqual(bench.errors, [])
        self.assertEqual(bench.tasks["t1"].difficulty, "hard")
        self.assertEqual(bench.tasks["t2"].difficulty, "easy")
        self.assertEqual(bench.tasks["t1"].config["metadata"]["difficulty"], "easy")
        self.assertEqual(bm.local_digests(bench), before)

    def test_invalid_difficulty_overrides_are_reported_without_hiding_tasks(self):
        path = self.root / "alpha"
        with (path / "benchmark.toml").open("a") as meta:
            meta.write('\n[task_difficulties]\nt1 = "impossible"\nmissing = "hard"\n')
        bench = bm.load_benchmark(path)
        self.assertEqual(len(bench.errors), 2)
        self.assertEqual(bench.tasks["t1"].difficulty, "easy")
        self.assertEqual(set(bench.tasks), {"t1", "t2"})

    def test_sync_states_and_benchmark_state(self):
        states = bm.sync_states({"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "X", "d": "4"})
        self.assertEqual(states, {"a": "in sync", "b": "modified", "c": "not published", "d": "published only"})
        v = [{"revision": 1}]
        self.assertEqual(bm.benchmark_state(True, [], {}), "draft")
        self.assertEqual(bm.benchmark_state(False, v, {"a": "published only"}), "remote only")
        self.assertEqual(bm.benchmark_state(True, v, {"a": "in sync"}), "published")
        self.assertEqual(bm.benchmark_state(True, v, {"a": "in sync", "b": "modified"}), "modified")

    def test_the_repo_smoke_benchmark_is_wellformed(self):
        smoke = bm.discover_local(ROOT / "benchmarks")["smoke"]
        self.assertEqual((smoke.kind, list(smoke.tasks)), ("smoke", ["elixir-check"]))
        self.assertEqual(bm.task_problems(smoke.tasks["elixir-check"]), [])


class FakeRemote:
    """Valkyrie stand-in for collect_benchmarks."""

    def __init__(self, fail=False):
        self.fail = fail

    def datasets(self, benchmark):
        if self.fail:
            raise ValkyrieError("offline", "network")
        return [{"name": "alpha", "description": ""}, {"name": "gamma", "description": "remote only"}]

    def dataset_versions(self, benchmark, dataset):
        return [{"revision": 2, "tags": ["latest", "v2"]}, {"revision": 1, "tags": ["v1"]}]

    def dataset_tasks(self, benchmark, dataset, ref="latest"):
        return [{"task_id": "t1", "digest": "same"}, {"task_id": "t2", "digest": "old"}] if dataset == "alpha" \
            else [{"task_id": "g1", "digest": "g"}]


class CollectBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        make_task(root / "alpha" / "t1")
        make_task(root / "alpha" / "t2")
        make_task(root / "beta" / "b1")
        self.cfg = EvalsConfig(benchmarks_dir=root)
        digests = patch("rb_evals.benchmarks.local_digests",
                        side_effect=lambda b: {"t1": "same", "t2": "changed"} if b.name == "alpha" else {})
        digests.start()
        self.addCleanup(digests.stop)

    def test_merges_local_and_published(self):
        infos, error = bm.collect_benchmarks(self.cfg, FakeRemote())
        self.assertIsNone(error)
        by = {i.name: i for i in infos}
        self.assertEqual({n: i.state for n, i in by.items()}, {"alpha": "modified", "beta": "draft", "gamma": "remote only"})
        self.assertEqual(by["alpha"].task_states, {"t1": "in sync", "t2": "modified"})
        self.assertEqual(by["alpha"].latest["revision"], 2)
        self.assertEqual(by["alpha"].tags, ["latest", "v1", "v2"])
        self.assertEqual(by["gamma"].description, "remote only")
        self.assertEqual(by["gamma"].task_ids, ["g1"])
        self.assertEqual(by["beta"].task_states, {"b1": "not published"})

    def test_works_offline_with_drafts_only(self):
        infos, error = bm.collect_benchmarks(self.cfg, FakeRemote(fail=True))
        self.assertIn("offline", error)
        self.assertEqual({i.name: i.state for i in infos}, {"alpha": "draft", "beta": "draft"})
        self.assertEqual(bm.collect_benchmarks(self.cfg, None)[1], None)


class JobTests(unittest.TestCase):
    def spec(self, **kw):
        base = dict(dataset="smoke", revision="1", agent="claude_code-v1.0.0", model="anthropic/claude-sonnet-4-6",
                    secret_name="anthropic-api-key-ishan", secret_env="ANTHROPIC_API_KEY", concurrency=2, label="my job")
        return jobs.JobSpec(**{**base, **kw})

    def test_valid_spec_builds_start_kwargs_for_modal(self):
        spec = self.spec(task_ids=["a", "b"])
        spec.validate(CFG, known_tasks={"a", "b", "c"})
        self.assertEqual(spec.start_kwargs(), {
            "benchmark": "royalebench", "dataset": "smoke", "ref": "1", "agent": "claude_code-v1.0.0",
            "model": "anthropic/claude-sonnet-4-6", "concurrency": 2, "task_ids": ["a", "b"], "label": "my job",
            "provider": "modal", "secrets": {"ANTHROPIC_API_KEY": "anthropic-api-key-ishan"}})

    def test_whole_benchmark_sends_no_task_ids(self):
        spec = self.spec(task_ids=None)
        spec.validate(CFG, known_tasks={"a", "b"})
        self.assertIsNone(spec.start_kwargs()["task_ids"])
        self.assertEqual(spec.task_count({"a", "b"}), 2)

    def test_validation_errors(self):
        cases = [
            (dict(provider="daytona"), "Modal"), (dict(dataset=""), "benchmark"), (dict(revision=" "), "revision"),
            (dict(agent=""), "harness"), (dict(model="gpt"), "model key"), (dict(model="a/"), "model key"),
            (dict(secret_name=""), "secret"), (dict(concurrency=0), "Concurrency"),
            (dict(concurrency=CFG.max_concurrency + 1), "Concurrency"),
            (dict(label="  "), "name"), (dict(task_ids=[]), "at least one"), (dict(task_ids=["a", "a"]), "duplicates"),
            (dict(task_ids=["zzz"]), "Not in this revision"),
        ]
        for change, text in cases:
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, text):
                    self.spec(**change).validate(CFG, known_tasks={"a", "b"})

    def test_confirmation_threshold(self):
        spec = self.spec(task_ids=None)
        self.assertFalse(spec.needs_confirmation(CFG, [str(i) for i in range(5)]))
        self.assertTrue(spec.needs_confirmation(CFG, [str(i) for i in range(6)]))
        self.assertFalse(self.spec(task_ids=["a"]).needs_confirmation(CFG, [str(i) for i in range(50)]))

    def test_cli_command_names_secrets_but_never_values(self):
        cmd = self.spec(task_ids=["a", "b"], label="it's a job").cli_command()
        self.assertTrue(cmd.startswith("valkyrie run start --agent claude_code-v1.0.0 --dataset royalebench/smoke@1"))
        for part in ("--provider modal", "-s ANTHROPIC_API_KEY anthropic-api-key-ishan", "--task-ids a,b", "--concurrency 2"):
            self.assertIn(part, cmd)
        self.assertIn("'it'\"'\"'s a job'", cmd)

    def test_default_label_and_secret(self):
        self.assertEqual(jobs.default_label("smoke", "anthropic/claude-sonnet-4-6", datetime(2026, 11, 14, 9, 5)),
                         "smoke-claude-sonnet-4-6-20261114-0905")
        names = ["modal-credentials", "anthropic-api-key-ben", "anthropic-api-key-ishan"]
        self.assertEqual(jobs.default_secret(names, "anthropic", "anthropic-api-key-ishan"), "anthropic-api-key-ishan")
        self.assertEqual(jobs.default_secret(names, "anthropic", "missing"), "anthropic-api-key-ben")
        self.assertIsNone(jobs.default_secret(names, "openai"))

    def run_row(self, **kw):
        return {"id": "r1", "name": "royalebench", "dataset": "smoke", "label": "x", "status": "IN_PROGRESS",
                "total_tasks": 10, "finished_tasks": 4, "started_at": "2026-11-14T10:00:00", "finished_at": None,
                "agent_name": "claude_code-v1.0.0", "model": "anthropic/m", "final_score": None, **kw}

    def test_timestamps_without_offset_are_utc(self):
        self.assertEqual(jobs.parse_ts("2026-11-14T10:00:00"), datetime(2026, 11, 14, 10, tzinfo=timezone.utc))
        self.assertEqual(jobs.parse_ts("2026-11-14T10:00:00Z"), datetime(2026, 11, 14, 10, tzinfo=timezone.utc))
        self.assertIsNone(jobs.parse_ts(None))

    def test_eta_and_duration_for_an_active_run(self):
        now = datetime(2026, 11, 14, 10, 20, tzinfo=timezone.utc).timestamp()  # 20 min, 4 of 10 done
        self.assertEqual(jobs.duration_s(self.run_row(), now), 1200)
        self.assertEqual(jobs.eta_seconds(self.run_row(), now), 1800)
        self.assertIsNone(jobs.eta_seconds(self.run_row(status="FINISHED"), now))
        self.assertIsNone(jobs.eta_seconds(self.run_row(finished_tasks=0), now))

    def test_job_row_and_task_rows(self):
        row = jobs.job_row(self.run_row(label=None, status="ERROR", finished_at="2026-11-14T10:05:00"))
        self.assertEqual((row["job"], row["state"], row["progress"], row["duration_s"], row["benchmark"]),
                         ("(no label)", "❌ failed", 0.4, 300, "royalebench/smoke"))
        tasks = [{"task_id": "b", "status": "FINISHED", "started_at": "2026-11-14T10:00:00", "finished_at": "2026-11-14T10:01:00"},
                 {"task_id": "a", "status": "ERROR", "started_at": "2026-11-14T10:00:00", "finished_at": None,
                  "error_message": "boom", "failure_category": "agent"},
                 {"task_id": "c", "status": "IN_PROGRESS", "started_at": "2026-11-14T10:00:00", "finished_at": None}]
        rows = jobs.task_rows(tasks, now=datetime(2026, 11, 14, 10, 2, tzinfo=timezone.utc).timestamp())
        self.assertEqual([r["task"] for r in rows], ["c", "a", "b"])  # running, then errors, then finished
        self.assertEqual(rows[2]["duration_s"], 60)
        self.assertEqual((rows[1]["category"], rows[1]["error"]), ("agent", "boom"))


def synthetic_results(rewards: dict, errors: dict | None = None, categories: dict | None = None, model="m/a", agent="h",
                      dataset="smoke", revision="1") -> dict:
    return {
        "benchmark_arguments": {"contract": {"name": agent, "model": model}, "dataset": dataset, "concurrency": 1,
                                "dataset_version": {"id": f"royalebench/{dataset}@{revision}"}},
        "evaluation_results": {t: {"rewards": {"reward": r}, "task_breakdown": {"agent_run_duration": 10.0},
                                   "metadata": {"verifier_output": f"out {t}"}} for t, r in rewards.items()},
        "task_errors": errors or None, "task_failure_categories": categories or None,
    }


class ResultsTests(unittest.TestCase):
    def test_parses_a_real_saved_results_file(self):
        data = json.loads((ROOT / "runs" / "valkyrie-ben-key-smoke-results.json").read_text())
        info = results.run_info(data)
        self.assertEqual((info["agent"], info["model"], info["dataset"], info["revision"]),
                         ("claude_code-v1.0.0", "anthropic/claude-sonnet-4-6", "smoke", "1"))
        rows = results.task_results(data)
        self.assertEqual([(r["task"], r["reward"], r["solved"], r["counted"]) for r in rows], [("elixir-check", 1.0, True, True)])
        self.assertGreater(rows[0]["agent_s"], 0)

    def test_reads_agent_cost_from_the_saved_output_folder(self):
        metrics = results.read_agent_metrics(ROOT / "runs" / "valkyrie-ben-key-smoke-output" / "elixir-check")
        self.assertAlmostEqual(metrics["cost"], 0.0158661)
        self.assertEqual(metrics["output_tokens"], 152)
        flat = results.read_agent_metrics(ROOT / "runs" / "valkyrie-smoke-output" / "elixir-check")
        self.assertAlmostEqual(flat["cost"], 0.0158661)  # metrics_total.json layout
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(results.read_agent_metrics(Path(d)))

    def test_error_classification(self):
        data = synthetic_results({"ok": 1.0, "half": 0.5},
                                 errors={"crash": "agent died", "net": "sandbox lost", "mystery": "?"},
                                 categories={"crash": "agent", "net": "infrastructure"})
        by = {r["task"]: r for r in results.task_results(data)}
        self.assertEqual((by["ok"]["solved"], by["half"]["solved"]), (True, False))
        self.assertTrue(by["crash"]["counted"] and by["crash"]["reward"] is None)  # agent failure: counts as a loss
        self.assertFalse(by["net"]["counted"])  # infrastructure: not the model's fault
        self.assertFalse(by["mystery"]["counted"])  # unknown category: excluded too

    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            cache = results.ResultsCache(Path(d))
            self.assertIsNone(cache.results("r1"))
            cache.save_results("r1", {"a": 1})
            self.assertEqual(cache.results("r1"), {"a": 1})
            self.assertEqual(cache.task_dir("r1", "x/y").name, "x_y")
            root = Path(d).resolve()
            for hostile in ("..", ".", "../..", "a/../../b", "..\\..\\x"):  # ids come from URLs: never leave the cache
                self.assertTrue(cache.task_dir(hostile, hostile).resolve().is_relative_to(root), hostile)
                self.assertTrue(cache.task_dir("r1", hostile).resolve().is_relative_to(root), hostile)

    def test_concurrent_cache_writers_do_not_share_a_temporary_file(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        barrier = threading.Barrier(2)
        replace = os.replace

        def simultaneous_replace(source, target):
            barrier.wait(timeout=2)
            replace(source, target)

        with tempfile.TemporaryDirectory() as folder:
            cache = results.ResultsCache(Path(folder))
            with patch("rb_evals.results.os.replace", side_effect=simultaneous_replace):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    list(pool.map(lambda value: cache.save_results("r1", {"a": value}), [1, 2]))
            self.assertIn(cache.results("r1"), [{"a": 1}, {"a": 2}])


def record(model, agent, tasks, started=None, run_id="r", dataset="smoke"):
    full = [{"task": f"t{i}", "reward": None, "solved": False, "agent_s": None, "counted": True, "cost": None,
             "error": "", "failure_category": "", "tokens_out": None, **t} for i, t in enumerate(tasks)]
    return {"run_id": run_id, "label": "", "model": model, "agent": agent, "dataset": dataset, "revision": "1",
            "started_at": started, "tasks": full}


class LeaderboardTests(unittest.TestCase):
    def test_pools_runs_and_ranks_by_score(self):
        old, new = datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 11, 2, tzinfo=timezone.utc)
        weak = [record("m/weak", "h", [dict(reward=1.0, solved=True, agent_s=10, cost=0.5),
                                      dict(reward=0.5, agent_s=20, cost=0.5),
                                      dict(reward=None, counted=True),  # agent failure: scores 0
                                      dict(reward=None, counted=False)],  # infrastructure: ignored
                       started=old, run_id="a"),
                record("m/weak", "h", [dict(reward=0.0)], started=new, run_id="b")]
        strong = [record("m/strong", "h", [dict(reward=1.0, solved=True, agent_s=5, cost=0.1),
                                          dict(reward=1.0, solved=True, agent_s=7)], started=old)]
        rows = results.leaderboard(weak + strong)
        self.assertEqual([r["model"] for r in rows], ["m/strong", "m/weak"])
        s, w = rows
        self.assertEqual((s["rank"], s["runs"], s["tasks_run"], s["solved"], s["pass_rate"], s["score"]), (1, 1, 2, 2, 1.0, 100.0))
        self.assertEqual((w["rank"], w["runs"], w["tasks_run"], w["solved"]), (2, 2, 4, 1))
        self.assertAlmostEqual(w["score"], 100 * (1.0 + 0.5 + 0 + 0) / 4)
        self.assertEqual((w["agent_failures"], w["infra_errors"]), (1, 1))
        self.assertAlmostEqual(w["cost_usd"], 1.0)
        self.assertAlmostEqual(w["cost_per_task"], 0.5)
        self.assertEqual((w["cost_known"], s["cost_known"]), (2, 1))
        self.assertEqual(w["last_run"], new)
        self.assertAlmostEqual(w["avg_agent_s"], 15.0)

    def test_groups_by_model_and_harness(self):
        rows = results.leaderboard([record("m/a", "h1", [dict(reward=1.0, solved=True)]),
                                    record("m/a", "h2", [dict(reward=0.0)])])
        self.assertEqual([(r["model"], r["harness"]) for r in rows], [("m/a", "h1"), ("m/a", "h2")])

    def test_no_cost_data_is_none_not_zero(self):
        row = results.leaderboard([record("m/a", "h", [dict(reward=1.0, solved=True)])])[0]
        self.assertIsNone(row["cost_usd"])
        self.assertIsNone(row["cost_per_task"])

    def test_empty(self):
        self.assertEqual(results.leaderboard([]), [])

    def test_task_history_filters_by_dataset_and_sorts_newest_first(self):
        a = record("m/a", "h", [dict(reward=1.0, solved=True)], started=datetime(2026, 11, 1, tzinfo=timezone.utc), run_id="old")
        b = record("m/b", "h", [dict(reward=0.0)], started=datetime(2026, 11, 3, tzinfo=timezone.utc), run_id="new")
        c = record("m/c", "h", [dict(reward=1.0)], dataset="other", run_id="elsewhere")
        rows = results.task_history([a, b, c], "smoke", "t0")
        self.assertEqual([r["run_id"] for r in rows], ["new", "old"])


class FakeResultsRemote:
    """Valkyrie stand-in for load_records: results JSON plus agent_output tarballs with a cost."""

    def __init__(self):
        self.results_calls, self.downloads = [], []

    def results(self, run_id):
        self.results_calls.append(run_id)
        return synthetic_results({"t1": 1.0, "t2": 0.0}, errors={"t3": "x"}, categories={"t3": "infrastructure"})

    def download_artifact(self, run_id, path, dest):
        self.downloads.append((run_id, path))
        task = path.split("/")[0]
        if task == "t3":
            raise ValkyrieError("FileNotFoundError: No artifacts found", "other")
        target = Path(dest) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"metrics": {"cost": 0.25 if task == "t1" else 0.75, "output_tokens": 9}}).encode()
        with tarfile.open(target, "w:gz") as tar:
            info = tarfile.TarInfo("logs/summary.json")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        return Path(dest)


class LoadRecordsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = results.ResultsCache(Path(self.tmp.name))
        self.remote = FakeResultsRemote()
        self.runs = [{"id": "run-1", "status": "FINISHED", "label": "job", "total_tasks": 3, "started_at": "2026-11-14T10:00:00"},
                     {"id": "run-2", "status": "ERROR", "total_tasks": 1},
                     {"id": "run-3", "status": "IN_PROGRESS", "total_tasks": 1}]

    def test_only_finished_runs_and_costs_are_attached_then_cached(self):
        self.assertEqual(results.uncached_task_count(self.cache, self.runs), 3)
        records = results.load_records(self.remote, self.cache, self.runs, fetch_costs=True)
        self.assertEqual([r["run_id"] for r in records], ["run-1"])
        costs = {t["task"]: t["cost"] for t in records[0]["tasks"]}
        self.assertEqual(costs, {"t1": 0.25, "t2": 0.75, "t3": None})
        self.assertEqual(results.uncached_task_count(self.cache, self.runs), 0)
        before = (len(self.remote.results_calls), len(self.remote.downloads))
        again = results.load_records(self.remote, self.cache, self.runs, fetch_costs=True)  # all from disk now
        self.assertEqual((len(self.remote.results_calls), len(self.remote.downloads)), before)
        self.assertEqual({t["task"]: t["cost"] for t in again[0]["tasks"]}, costs)

    def test_skipping_cost_downloads_leaves_costs_blank(self):
        records = results.load_records(self.remote, self.cache, self.runs, fetch_costs=False)
        self.assertEqual(self.remote.downloads, [])
        self.assertTrue(all(t["cost"] is None for t in records[0]["tasks"]))
        self.assertEqual(results.uncached_task_count(self.cache, self.runs), 3)

    def test_a_transient_download_error_is_not_remembered(self):
        def flaky(run_id, path, dest):
            raise ValkyrieError("Cannot reach Valkyrie", "network")

        self.remote.download_artifact = flaky
        records = results.load_records(self.remote, self.cache, self.runs, fetch_costs=True)
        self.assertTrue(all(t["cost"] is None for t in records[0]["tasks"]))
        self.assertEqual(results.uncached_task_count(self.cache, self.runs), 3)  # will retry next time


class FakeClient:
    """Async-context-manager client exposing only what a test needs."""

    def __init__(self, **resources):
        for name, value in resources.items():
            setattr(self, name, value)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FacadeTests(unittest.TestCase):
    def test_list_runs_is_filtered_by_benchmark_and_memoised(self):
        seen = []

        async def iterate(request):
            seen.append(request)
            for row in ({"id": "1"}, {"id": "2"}):
                yield row

        opened = []
        v = Valkyrie(lambda: opened.append(1) or FakeClient(runs=SimpleNamespace(iter=iterate)))
        self.assertEqual([r["id"] for r in v.list_runs("royalebench")], ["1", "2"])
        v.list_runs("royalebench")
        self.assertEqual(len(opened), 1)  # second call came from the memo
        self.assertEqual(seen[0].benchmark_name, ["royalebench"])
        v.invalidate()
        v.list_runs("royalebench")
        self.assertEqual(len(opened), 2)

    def test_start_run_builds_a_hosted_dataset_request_and_clears_the_memo(self):
        captured = {}

        async def start_run(agent, dataset, **kw):
            captured.update(agent=agent, dataset=dataset, **kw)
            return SimpleNamespace(benchmark_id="11111111-1111-1111-1111-111111111111", task_count=3,
                                   dataset_version=None, dataset_version_warning=None,
                                   started_at=datetime(2026, 11, 14, tzinfo=timezone.utc))

        v = Valkyrie(lambda: FakeClient(datasets=SimpleNamespace(start_run=start_run)))
        v._cache.get_or_set("k", 60, lambda: "stale")
        out = v.start_run(benchmark="royalebench", dataset="smoke", ref="1", agent="claude_code-v1.0.0",
                          model="anthropic/claude-sonnet-4-6", concurrency=2, task_ids=["a"], label="L",
                          provider="modal", secrets={"ANTHROPIC_API_KEY": "s"},
                          agent_kwargs={"cost_tracking": "ignore_errors"})
        self.assertEqual(out["run_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(out["task_count"], 3)
        self.assertEqual(captured["agent_kwargs"], {"cost_tracking": "ignore_errors"})
        self.assertEqual(captured["dataset"], HostedDataset(benchmark="royalebench", dataset="smoke", ref="1"))
        self.assertEqual((captured["provider"], captured["task_ids"], captured["secrets"], captured["concurrency"]),
                         ("modal", ["a"], {"ANTHROPIC_API_KEY": "s"}, 2))
        self.assertEqual(v._cache.get_or_set("k", 60, lambda: "fresh"), "fresh")  # memo was cleared

    def test_whole_benchmark_start_sends_no_task_ids(self):
        captured = {}

        async def start_run(agent, dataset, **kw):
            captured.update(kw)
            return SimpleNamespace(benchmark_id="11111111-1111-1111-1111-111111111111", task_count=1, dataset_version=None,
                                   dataset_version_warning=None, started_at=datetime(2026, 11, 14, tzinfo=timezone.utc))

        v = Valkyrie(lambda: FakeClient(datasets=SimpleNamespace(start_run=start_run)))
        v.start_run(benchmark="royalebench", dataset="smoke", ref="1", agent="a", model="p/m", concurrency=1,
                    task_ids=None, label="L", provider="modal", secrets={})
        self.assertIsNone(captured["task_ids"])

    def test_error_messages_are_ui_safe(self):
        unauthorized = describe_error(ValkyrieAPIError(401, "no"))
        self.assertEqual(unauthorized.kind, "auth")
        self.assertIn("valkyrie login", str(unauthorized))
        invalid = describe_error(ValkyrieAPIError(422, [{"loc": ["body", "concurrency"], "msg": "too big"}]))
        self.assertEqual(invalid.kind, "rejected")
        self.assertIn("concurrency: too big", str(invalid))
        self.assertEqual(describe_error(ConnectionError("down")).kind, "network")
        self.assertEqual(describe_error(FileNotFoundError("x")).kind, "other")

    def test_failures_surface_as_valkyrie_error(self):
        async def boom(request):
            raise ValkyrieAPIError(401, "no")
            yield  # pragma: no cover

        v = Valkyrie(lambda: FakeClient(runs=SimpleNamespace(iter=boom)))
        with self.assertRaises(ValkyrieError) as ctx:
            v.list_runs("royalebench")
        self.assertEqual(ctx.exception.kind, "auth")

    def test_push_dataset_collects_notes(self):
        async def push(benchmark, dataset, folder, *, tags, on_stored, on_created, on_left_out, on_warning):
            on_stored("t1", None)
            on_created("royalebench/x")
            on_left_out("t1", ["notes.txt"])
            on_warning("careful")
            return SimpleNamespace(model_dump=lambda mode: {"revision": 3, "tags": list(tags)})

        v = Valkyrie(lambda: FakeClient(datasets=SimpleNamespace(push=push)))
        out = v.push_dataset("royalebench", "x", "folder", tags=["v3"])
        self.assertEqual(out["version"], {"revision": 3, "tags": ["v3"]})
        self.assertEqual((out["stored"], out["created"], out["warnings"], out["left_out"]),
                         (["t1"], ["royalebench/x"], ["careful"], {"t1": ["notes.txt"]}))

    def test_run_sync_works_with_and_without_a_running_loop(self):
        async def value():
            return 7

        self.assertEqual(run_sync(value), 7)

        async def inside_loop():
            return run_sync(value)

        self.assertEqual(asyncio.run(inside_loop()), 7)

    def test_ttl_cache_expires(self):
        cache, calls = TTLCache(), []
        make = lambda: calls.append(1) or len(calls)  # noqa: E731
        self.assertEqual(cache.get_or_set("k", 0.05, make), 1)
        self.assertEqual(cache.get_or_set("k", 0.05, make), 1)
        time.sleep(0.08)
        self.assertEqual(cache.get_or_set("k", 0.05, make), 2)


if __name__ == "__main__":
    unittest.main()
