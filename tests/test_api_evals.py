"""The /api/evals endpoints against a fake Valkyrie.

    uv run python -m unittest tests.test_api_evals -v
"""

import dataclasses
import time
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from rb_evals.valkyrie import ValkyrieError
from rb_server.app import create_app
from rb_server.context import build_context
from rb_server.export_openapi import OPENAPI_PATH, build_openapi, render
from rb_server.settings import Settings
from tests.helpers import ApiCase, make_task, write

JOBS = "/api/evals/jobs"


class EnvironmentTests(ApiCase):
    def test_reports_identity_modal_secrets_agents_and_settings(self):
        env = self.client.get("/api/evals/environment").json()
        self.assertTrue(env["valkyrie_ok"])
        self.assertEqual(env["identity"]["email"], "me@example.com")
        self.assertTrue(env["modal_configured"])
        self.assertIn("anthropic-api-key-demo", env["secrets"])
        self.assertIn("claude_code-v1.0.0", env["agents"])
        self.assertEqual((env["read_only"], env["settings"]["provider"], env["settings"]["max_concurrency"]), (False, "modal", 4))
        self.assertEqual(env["queue"], {"waiting": 0, "building": 0, "in_progress": 0, "evaluating": 0})
        self.assertEqual(env["settings"]["default_dataset"], "royalebench-v3")

    def test_a_valkyrie_outage_is_reported_not_raised(self):
        def down(*args, **kwargs):
            raise ValkyrieError("Not signed in to Valkyrie. Run `valkyrie login`.", "auth")

        for name in ("identity", "providers", "secret_names", "agent_names", "queue"):
            setattr(self.fake, name, down)
        r = self.client.get("/api/evals/environment")
        self.assertEqual(r.status_code, 200)
        env = r.json()
        self.assertFalse(env["valkyrie_ok"])
        self.assertEqual(env["valkyrie_error_kind"], "auth")
        self.assertIn("valkyrie login", env["valkyrie_error"])
        self.assertFalse(env["modal_configured"])
        self.assertEqual(env["settings"]["benchmark"], "royalebench")  # local settings still available


class CostRefreshTests(ApiCase):
    def test_refresh_downloads_missing_finished_costs_and_reuses_cache(self):
        from rb_server.cost_refresh import CostRefresher
        from rb_evals import results as R

        active_id = self.start(task_ids=["t1"])
        refresher = CostRefresher(self.ctx)
        with patch.object(self.fake, "download_artifact", wraps=self.fake.download_artifact) as download:
            refresher.refresh(lambda done, total: None)
            self.assertGreater(download.call_count, 0)
            self.assertNotIn(active_id, [call.args[0] for call in download.call_args_list])
            self.assertEqual(R.uncached_task_count(self.ctx.cache, self.fake.list_runs(self.cfg.benchmark)), 0)
            count = download.call_count
            refresher.refresh(lambda done, total: None)
            self.assertEqual(download.call_count, count)
            # The next check picks up this job only after every task has finished.
            self.advance(30)
            refresher.refresh(lambda done, total: None)
            self.assertIn(active_id, [call.args[0] for call in download.call_args_list])
        job = self.client.get(JOBS + "/claude-smoke").json()["job"]
        self.assertGreater(job["cost_usd"], 0)

    def test_scheduler_runs_on_startup_repeats_and_stops(self):
        from rb_server.cost_refresh import COST_CHECK_SECONDS, CostRefresher

        self.assertEqual(COST_CHECK_SECONDS, 10)
        repeated = threading.Event()
        calls = []

        def start(work):
            calls.append(work)
            if len(calls) >= 2:
                repeated.set()
            return True

        refresher = CostRefresher(self.ctx, interval=0.01)
        with patch.object(self.ctx.costs, "start", side_effect=start):
            refresher.start()
            try:
                self.assertTrue(repeated.wait(timeout=2))
            finally:
                refresher.close()
        self.assertFalse(refresher._thread.is_alive())


class JobListTests(ApiCase):
    def test_per_run_costs_download_and_appear_in_list_and_detail(self):
        run_id = self.start(task_ids=["t1", "t2"], label="costed run")
        self.advance(30)
        before = self.client.get(f"{JOBS}/{run_id}").json()["job"]
        self.assertIsNone(before["cost_usd"])
        self.assertEqual((before["cost_known"], before["costs_pending"]), (0, 2))
        self.assertEqual(self.client.post(JOBS + "/costs", json=[run_id]).status_code, 200)
        for _ in range(100):
            status = self.client.get("/api/evals/leaderboard/costs").json()
            if status["state"] != "running":
                break
            time.sleep(0.01)
        self.assertEqual(status["state"], "done")
        detail = self.client.get(f"{JOBS}/{run_id}").json()["job"]
        listed = next(j for j in self.client.get(JOBS).json()["jobs"] if j["id"] == run_id)
        self.assertGreater(detail["cost_usd"], 0)
        self.assertEqual((detail["cost_known"], detail["costs_pending"]), (2, 0))
        self.assertAlmostEqual(detail["cost_usd"], detail["cost_per_task"] * 2)
        for field in ("cost_usd", "cost_per_task", "cost_known", "costs_pending"):
            self.assertEqual(detail[field], listed[field])
        with patch.object(self.fake, "download_artifact", wraps=self.fake.download_artifact) as download:
            tasks = self.client.get(f"{JOBS}/{run_id}/tasks").json()["tasks"]
            download.assert_not_called()
        self.assertTrue(all(t["cost_usd"] is not None for t in tasks))
        self.assertAlmostEqual(sum(t["cost_usd"] for t in tasks), detail["cost_usd"])
        other = self.client.get(f"{JOBS}/claude-smoke").json()["job"]
        self.assertIsNone(other["cost_usd"])  # only the selected run was downloaded

    def test_partial_costs_include_zero_cost_tasks(self):
        from rb_evals.results import fetch_task_files
        run_id = self.start(task_ids=["t1", "t2"])
        self.advance(30)
        folder = fetch_task_files(self.fake, self.ctx.cache, run_id, "t1", final=True)
        summary = next(folder.rglob("summary.json"))
        summary.write_text('{"metrics": {"cost": 0}}', encoding="utf-8")
        job = self.client.get(f"{JOBS}/{run_id}").json()["job"]
        self.assertEqual((job["cost_usd"], job["cost_per_task"], job["cost_known"], job["costs_pending"]), (0, 0, 1, 1))
        tasks = self.client.get(f"{JOBS}/{run_id}/tasks").json()["tasks"]
        self.assertEqual({t["task"]: t["cost_usd"] for t in tasks}, {"t1": 0, "t2": None})
        # A retry/resume must not expose costs from a previous completed attempt.
        with patch.object(self.fake, "run", return_value={"status": "IN_PROGRESS"}):
            tasks = self.client.get(f"{JOBS}/{run_id}/tasks").json()["tasks"]
        self.assertTrue(all(t["cost_usd"] is None for t in tasks))

    def test_lists_runs_newest_first_with_provider_family(self):
        body = self.client.get(JOBS).json()
        self.assertEqual(body["total"], 7)
        starts = [j["started_at"] for j in body["jobs"]]
        self.assertEqual(starts, sorted(starts, reverse=True))
        claude = next(j for j in body["jobs"] if j["job"] == "royalebench-connection-smoke")
        self.assertEqual((claude["family"], claude["logo_url"], claude["status"], claude["harness"]),
                         ("claude", "/api/assets/logos/claude", "FINISHED", "claude_code-v1.0.0"))
        self.assertEqual((claude["done"], claude["total"], claude["progress"], claude["score"]), (1, 1, 1.0, 100.0))
        self.assertIn("arena-lite", body["datasets"])
        self.assertEqual(body["me"], "me@example.com")

    def test_filters(self):
        def labels(query):
            return sorted(j["job"] for j in self.client.get(JOBS + query).json()["jobs"])

        self.assertEqual(labels("?status=ERROR"), ["royalebench-mini-swe-smoke"])
        self.assertEqual(len(labels("?dataset=arena-lite")), 4)
        self.assertEqual(len(labels("?model=openai/gpt-5")), 2)
        self.assertEqual(len(labels("?status=ERROR&status=FINISHED")), 7)
        self.assertEqual(labels("?mine=true"), ["royalebench-connection-smoke", "royalebench-mini-swe-smoke"])  # started by me
        self.assertEqual(self.client.get(JOBS + "?status=IN_PROGRESS").json()["jobs"], [])


class JobMonitorTests(ApiCase):
    def test_a_running_job_progresses_to_finished(self):
        run_id = self.start(task_ids=["t1", "t2", "t3"], concurrency=1, label="monitor me")
        detail = self.client.get(f"{JOBS}/{run_id}").json()
        self.assertEqual((detail["job"]["status"], detail["job"]["job"], detail["active"], detail["provider"]),
                         ("IN_PROGRESS", "monitor me", True, "modal"))
        self.assertEqual(detail["dataset_version"], "royalebench/alpha@1")
        self.assertEqual(detail["secrets"], {"ANTHROPIC_API_KEY": "anthropic-api-key-demo"})  # a name, never a value
        self.assertEqual(detail["queue"]["waiting"], 2)
        self.assertEqual(detail["queue"]["position"], 1)
        tasks = self.client.get(f"{JOBS}/{run_id}/tasks").json()
        self.assertEqual([t["status"] for t in tasks["tasks"]], ["BUILDING", "PENDING", "PENDING"])
        self.assertEqual(tasks["counts"], {"BUILDING": 1, "PENDING": 2})
        self.advance(60)
        done = self.client.get(f"{JOBS}/{run_id}").json()
        self.assertEqual((done["job"]["status"], done["active"], done["queue"]), ("FINISHED", False, None))
        rows = self.client.get(f"{JOBS}/{run_id}/tasks").json()["tasks"]
        self.assertTrue(all(t["status"] == "FINISHED" and t["reward"] is not None for t in rows))
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}").json()["job"]["score"], 100 * sum(t["reward"] for t in rows) / 3)

    def test_eta_appears_while_running(self):
        run_id = self.start(task_ids=["t1", "t2", "t3"], concurrency=1)
        self.advance(8)  # one task done after 5.5 s
        detail = self.client.get(f"{JOBS}/{run_id}").json()
        self.assertEqual(detail["job"]["done"], 1)
        self.assertGreater(detail["eta_s"], 0)

    def test_task_detail_trace_logs_and_errors(self):
        run_id = self.start(task_ids=["t1"], label="one")
        self.advance(30)
        task = self.client.get(f"{JOBS}/{run_id}/tasks/t1").json()
        self.assertEqual((task["status"], task["solved"] or task["reward"] == 0.0), ("FINISHED", True))
        self.assertIn("Verifier reward for t1", task["verifier_output"])
        self.assertGreater(task["agent_s"], 0)
        trace = self.client.get(f"{JOBS}/{run_id}/tasks/t1/trace").json()
        self.assertTrue(trace["available"])
        self.assertEqual([s["kind"] for s in trace["steps"]], ["system", "thinking", "text", "tool_use", "tool_result", "result"])
        self.assertGreater(trace["cost_usd"], 0)
        self.assertTrue(trace["final_message"])
        logs = self.client.get(f"{JOBS}/{run_id}/logs").json()["lines"]
        self.assertTrue(any("agent started" in line["message"] for line in logs))
        filtered = self.client.get(f"{JOBS}/{run_id}/logs", params={"q": "verifier", "task_id": "t1"}).json()["lines"]
        self.assertTrue(filtered and all("verifier" in line["message"] for line in filtered))
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}/errors").json(), {"run": None, "tasks": {}})

    def test_failed_run_exposes_errors_and_no_trace(self):
        run_id = self.start(model="anthropic/claude-haiku-broken", task_ids=["t1"])
        self.advance(30)
        detail = self.client.get(f"{JOBS}/{run_id}").json()
        self.assertEqual(detail["job"]["status"], "ERROR")
        self.assertIn("No tasks were completed", detail["job"]["error"])
        errors = self.client.get(f"{JOBS}/{run_id}/errors").json()
        self.assertIn("Sandbox lost", errors["tasks"]["t1"])
        task = self.client.get(f"{JOBS}/{run_id}/tasks").json()["tasks"][0]
        self.assertEqual((task["status"], task["category"]), ("ERROR", "infrastructure"))
        self.assertFalse(self.client.get(f"{JOBS}/{run_id}/tasks/t1/trace").json()["available"])

    def test_unknown_ids_and_bad_ids(self):
        self.assertEqual(self.client.get(f"{JOBS}/does-not-exist").status_code, 404)
        self.assertEqual(self.client.get(f"{JOBS}/claude-smoke/tasks/ghost").status_code, 404)
        r = self.client.get(f"{JOBS}/claude-smoke/tasks/..%2F..%2Fetc")  # path-ish ids never reach the cache or Valkyrie
        self.assertIn(r.status_code, (404, 422))
        self.assertEqual(self.client.get(f"{JOBS}/-bad").status_code, 422)


class JobControlTests(ApiCase):
    def test_stop_resume_and_concurrency(self):
        run_id = self.start(task_ids=["t1", "t2", "t3"], concurrency=1)
        self.assertEqual(self.client.patch(f"{JOBS}/{run_id}", json={"concurrency": 3}).json(), {"concurrency": 3})
        self.assertEqual(self.client.patch(f"{JOBS}/{run_id}", json={"concurrency": 0}).status_code, 422)
        self.advance(2)
        self.assertEqual(self.client.post(f"{JOBS}/{run_id}/stop").json()["status"], "stopping")
        stopped = self.client.get(f"{JOBS}/{run_id}").json()
        self.assertEqual(stopped["job"]["status"], "STOPPED")
        self.assertEqual(self.client.post(f"{JOBS}/{run_id}/resume", json={"concurrency": 3}).status_code, 200)
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}").json()["job"]["status"], "IN_PROGRESS")
        self.advance(60)
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}").json()["job"]["status"], "FINISHED")

    def test_retry_reruns_errored_tasks(self):
        run_id = self.start(model="anthropic/claude-haiku-broken", task_ids=["t1"])
        self.advance(30)
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}").json()["job"]["status"], "ERROR")
        self.assertEqual(self.client.post(f"{JOBS}/{run_id}/retry").status_code, 200)
        self.advance(30)
        self.assertEqual(self.client.get(f"{JOBS}/{run_id}").json()["job"]["status"], "FINISHED")


class StartJobTests(ApiCase):
    def test_model_preset_supplies_endpoint_to_unmodified_mini_swe(self):
        from rb_evals.config import ModelPreset
        preset = ModelPreset("openai/Qwen/example", "OPENAI_API_KEY", agent="mini_swe_agent",
                             secrets={"OPENAI_API_BASE": "endpoint-url"},
                             agent_kwargs={"cost_tracking": "ignore_errors", "step_limit": "12"})
        self.ctx.cfg = dataclasses.replace(self.cfg, models=(preset,))
        with patch.object(self.fake, "agent_names", return_value=["mini_swe_agent"]), \
             patch.object(self.fake, "secret_names", return_value=["anthropic-api-key-demo", "endpoint-url"]):
            preview = self.preview(agent="mini_swe_agent", model=preset.id)
            self.assertTrue(preview["valid"], preview)
            self.assertIn("-s OPENAI_API_BASE endpoint-url", preview["cli_command"])
            self.assertIn("-s OPENAI_API_KEY anthropic-api-key-demo", preview["cli_command"])
            self.assertIn("-k cost_tracking ignore_errors", preview["cli_command"])
            rid = self.start(agent="mini_swe_agent", model=preset.id)
            contract = self.fake.run_metadata(rid)["benchmark_arguments"]["contract"]
            self.assertIn("OPENAI_API_BASE", contract["secrets"])
            self.assertEqual(contract["kwargs"]["step_limit"], "12")
            wrong = self.preview(agent="claude_code-v1.0.0", model=preset.id)
            self.assertFalse(wrong["valid"])
            self.assertIn("requires harness", " ".join(wrong["errors"]))
        with patch.object(self.fake, "agent_names", return_value=["mini_swe_agent"]):
            missing = self.preview(agent="mini_swe_agent", model=preset.id)
            self.assertFalse(missing["valid"])
            self.assertIn("endpoint-url", " ".join(missing["errors"]))

    def preview(self, **overrides):
        r = self.client.post(f"{JOBS}/preview", json=self.spec(**overrides))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_valid_preview_resolves_latest_and_builds_the_cli_command(self):
        p = self.preview(task_ids=["t1", "t2"])
        self.assertTrue(p["valid"], p)
        self.assertEqual((p["task_count"], p["resolved_revision"], p["dataset_ref"], p["secret_env"]),
                         (2, "1", "royalebench/alpha@1", "ANTHROPIC_API_KEY"))
        self.assertEqual(p["known_tasks"], ["t1", "t2", "t3"])
        self.assertFalse(p["needs_confirmation"])
        for part in ("valkyrie run start", "--dataset royalebench/alpha@1", "--provider modal", "--task-ids t1,t2",
                     "-s ANTHROPIC_API_KEY anthropic-api-key-demo"):
            self.assertIn(part, p["cli_command"])
        self.assertEqual(p["warnings"], [])  # sonnet-4-6 is the model in evals.toml

    def test_whole_benchmark_counts_every_task_and_may_need_confirmation(self):
        p = self.preview(task_ids=None)
        self.assertEqual((p["task_count"], p["needs_confirmation"]), (3, True))  # threshold is 2 in the test config
        self.assertNotIn("--task-ids", p["cli_command"])

    def test_errors_are_all_reported_together(self):
        p = self.preview(dataset="nope", model="not-a-model-key", secret_name="missing", agent="ghost-agent", concurrency=99)
        self.assertFalse(p["valid"])
        text = " | ".join(p["errors"])
        for expected in ("not published", "Harness", "Secret", "Model must be"):
            self.assertIn(expected, text)
        self.assertIsNone(p["cli_command"])

    def test_task_and_revision_validation(self):
        self.assertIn("Not in this revision", " ".join(self.preview(task_ids=["t1", "ghost"])["errors"]))
        self.assertIn("does not exist", " ".join(self.preview(revision="9")["errors"]))
        self.assertTrue(self.preview(revision="v1")["valid"])  # tags resolve to a revision
        self.assertEqual(self.preview(revision="v1")["resolved_revision"], "1")
        self.assertIn("Concurrency", " ".join(self.preview(concurrency=5)["errors"]))

    def test_unverified_model_is_a_warning_not_an_error(self):
        p = self.preview(model="openai/gpt-5")
        self.assertTrue(p["valid"])
        self.assertEqual(len(p["warnings"]), 1)
        self.assertEqual(p["secret_env"], "OPENAI_API_KEY")

    def test_start_creates_a_run_that_shows_up_in_the_list(self):
        run_id = self.start(task_ids=["t1"], label="from the test")
        jobs = self.client.get(JOBS).json()["jobs"]
        mine = next(j for j in jobs if j["id"] == run_id)
        self.assertEqual((mine["job"], mine["dataset"], mine["total"], mine["started_by"]), ("from the test", "alpha", 1, "me@example.com"))
        self.assertEqual(jobs[0]["id"], run_id)

    def test_large_jobs_need_confirmation(self):
        r = self.client.post(JOBS, json=self.spec(task_ids=None))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "confirmation_required"))
        self.assertEqual(self.client.post(JOBS, json=self.spec(task_ids=None, confirm=True)).status_code, 201)

    def test_invalid_requests_are_rejected_with_every_reason(self):
        r = self.client.post(JOBS, json=self.spec(secret_name="missing", model="nope"))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "validation_error"))
        self.assertGreaterEqual(len(r.json()["error"]["detail"]), 2)
        self.assertEqual(len([j for j in self.client.get(JOBS).json()["jobs"]]), 7)  # nothing was started

    def test_malformed_body_uses_the_error_envelope(self):
        r = self.client.post(JOBS, json={"dataset": "alpha"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["code"], "validation_error")
        self.assertIn("agent", r.json()["error"]["message"])

    def test_valkyrie_outage_while_starting_maps_to_503(self):
        def down(**kwargs):
            raise ValkyrieError("Cannot reach Valkyrie: ConnectError", "network")

        self.fake.start_run = down
        r = self.client.post(JOBS, json=self.spec())
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (503, "valkyrie_network"))


class ReadOnlyTests(ApiCase):
    read_only = True

    def test_mutations_are_refused_but_reads_and_preview_work(self):
        for method, url, body in (("post", JOBS, self.spec()), ("post", f"{JOBS}/claude-smoke/stop", None),
                                  ("post", f"{JOBS}/claude-smoke/resume", None), ("post", f"{JOBS}/claude-smoke/retry", None),
                                  ("patch", f"{JOBS}/claude-smoke", {"concurrency": 2}),
                                  ("post", "/api/evals/benchmarks/alpha/publish", {"tags": []})):
            r = self.client.request(method, url, json=body)
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (403, "read_only"), url)
        self.assertEqual(self.client.get(JOBS).status_code, 200)
        self.assertEqual(self.client.post(f"{JOBS}/preview", json=self.spec()).status_code, 200)
        self.assertTrue(self.client.get("/api/evals/environment").json()["read_only"])
        self.assertEqual(self.client.get(JOBS).json()["total"], 7)


class RequestGuardTests(ApiCase):
    def test_state_changing_requests_need_the_client_header(self):
        bare = TestClient(self.app)  # no x-rb-client header: what a cross-site form or no-cors fetch would send
        self.addCleanup(bare.close)
        r = bare.post(f"{JOBS}/claude-smoke/stop")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (403, "forbidden"))
        self.assertEqual(bare.get(JOBS).status_code, 200)  # reads are fine

    def test_unexpected_host_headers_are_rejected(self):
        r = self.client.get("/api/health", headers={"host": "evil.example"})  # DNS rebinding
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get("/api/health", headers={"host": "localhost:8000"}).status_code, 200)

    def test_unknown_api_paths_return_json_404(self):
        r = self.client.get("/api/does-not-exist")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (404, "not_found"))


class BenchmarkTests(ApiCase):
    def test_list_shows_states_and_run_stats(self):
        body = self.client.get("/api/evals/benchmarks").json()
        by = {b["name"]: b for b in body["benchmarks"]}
        self.assertEqual({n: b["state"] for n, b in by.items()},
                         {"alpha": "published", "arena-lite": "remote only", "draft": "published", "smoke": "published"})

    def test_a_never_published_folder_is_a_draft(self):
        from rb_evals.fake import FakeValkyrie

        self.fake._versions.pop("draft")
        by = {b["name"]: b for b in self.client.get("/api/evals/benchmarks").json()["benchmarks"]}
        self.assertEqual((by["draft"]["state"], by["draft"]["versions"], by["draft"]["latest_revision"]), ("draft", 0, None))
        self.assertTrue(by["draft"]["local"])
        self.assertFalse(by["arena-lite"]["local"])
        self.assertEqual((by["arena-lite"]["runs"], by["arena-lite"]["best_score"]), (4, 75.0))
        self.assertEqual((by["smoke"]["kind"], by["smoke"]["title"], by["smoke"]["runs"]), ("smoke", "Smoke", 3))
        self.assertEqual(by["alpha"]["description"], "Lanes")
        self.assertIsNone(FakeValkyrie and None)

    def test_detail_lists_tasks_versions_and_sync_state(self):
        d = self.client.get("/api/evals/benchmarks/alpha").json()
        self.assertEqual((d["dataset_ref"], d["folder"], d["benchmark"]["task_count"]), ("royalebench/alpha", "benchmarks/alpha", 3))
        self.assertEqual([(t["id"], t["sync"], t["category"], t["agent_timeout_s"]) for t in d["tasks"]],
                         [("t1", "in sync", "c", 60.0), ("t2", "in sync", "c", 60.0), ("t3", "in sync", "c", 60.0)])
        self.assertEqual([(v["revision"], v["tags"], v["task_count"]) for v in d["versions"]], [(1, ["latest", "v1"], 3)])
        self.assertEqual(d["tasks"][0]["resources"], {"cpus": 1.0, "memory_mb": 512.0})

    def test_editing_a_local_task_marks_it_modified(self):
        write(self.benchmarks / "alpha" / "t2" / "instruction.md", "Changed instructions.")
        d = self.client.get("/api/evals/benchmarks/alpha").json()
        self.assertEqual({t["id"]: t["sync"] for t in d["tasks"]}, {"t1": "in sync", "t2": "modified", "t3": "in sync"})
        self.assertEqual(d["benchmark"]["state"], "modified")

    def test_remote_only_benchmark_has_tasks_but_no_local_files(self):
        d = self.client.get("/api/evals/benchmarks/arena-lite").json()
        self.assertEqual((d["folder"], d["benchmark"]["local"], [t["local"] for t in d["tasks"]]), (None, False, [False] * 4))
        self.assertEqual({t["sync"] for t in d["tasks"]}, {"published only"})
        self.assertEqual(self.client.get("/api/evals/benchmarks/arena-lite/tasks/lane-defense").status_code, 404)

    def test_task_page_data(self):
        d = self.client.get("/api/evals/benchmarks/alpha/tasks/t1").json()
        self.assertEqual((d["benchmark"], d["task"]["id"], d["instruction"]), ("alpha", "t1", "Do the thing."))
        self.assertIn("[agent]", d["config_toml"])
        self.assertIn("FROM python", d["dockerfile"])
        self.assertIn("reward.txt", d["test_script"])
        self.assertIn("solved", d["solution_script"])
        self.assertIn("tests/test.sh", [f["path"] for f in d["files"]])

    def test_unknown_benchmark_or_task_is_404(self):
        self.assertEqual(self.client.get("/api/evals/benchmarks/nope").status_code, 404)
        self.assertEqual(self.client.get("/api/evals/benchmarks/alpha/tasks/ghost").status_code, 404)
        self.assertEqual(self.client.get("/api/evals/benchmarks/..%2Fetc").status_code, 404)

    def test_lint_problems_are_surfaced(self):
        make_task(self.benchmarks / "alpha" / "broken", instruction="", tests=None)
        d = self.client.get("/api/evals/benchmarks/alpha").json()
        broken = next(t for t in d["tasks"] if t["id"] == "broken")
        self.assertTrue(any("instruction.md" in p for p in broken["problems"]))
        self.assertEqual(broken["sync"], "not published")
        self.assertGreaterEqual(d["benchmark"]["problems"], 2)

    def test_results_across_runs_for_a_task(self):
        run_id = self.start(task_ids=["t1"], model="anthropic/claude-opus-5-5", label="opus on alpha")
        self.advance(30)
        r = self.client.get("/api/evals/benchmarks/alpha/tasks/t1/results").json()
        self.assertEqual([x["run_id"] for x in r["results"]], [run_id])
        self.assertEqual((r["results"][0]["model"], r["results"][0]["family"], r["results"][0]["solved"]),
                         ("anthropic/claude-opus-5-5", "claude", True))
        self.assertEqual([(s["attempts"], s["solved"], s["pass_rate"]) for s in r["summary"]], [(1, 1, 1.0)])
        self.assertEqual(self.client.get("/api/evals/benchmarks/draft/tasks/d1/results").json(), {"results": [], "summary": []})


class PublishTests(ApiCase):
    URL = "/api/evals/benchmarks/alpha/publish"

    def test_publishing_an_unchanged_folder_is_a_no_op(self):
        r = self.client.post(self.URL, json={"tags": []})
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.assertEqual((out["changed"], out["version"]["revision"], out["stored"]), (False, 1, []))

    def test_a_modified_folder_creates_a_new_revision_with_tags(self):
        write(self.benchmarks / "alpha" / "t1" / "instruction.md", "A better instruction.")
        out = self.client.post(self.URL, json={"tags": ["v2"]}).json()
        self.assertEqual((out["changed"], out["version"]["revision"], "v2" in out["version"]["tags"], out["stored"]),
                         (True, 2, True, ["t1"]))
        d = self.client.get("/api/evals/benchmarks/alpha").json()
        self.assertEqual([v["revision"] for v in d["versions"]], [2, 1])
        self.assertEqual({t["sync"] for t in d["tasks"]}, {"in sync"})
        self.assertEqual(d["benchmark"]["state"], "published")

    def test_a_first_publish_of_a_draft(self):
        self.fake._versions.pop("draft")
        out = self.client.post("/api/evals/benchmarks/draft/publish", json={"tags": ["v1"]}).json()
        self.assertEqual((out["changed"], out["version"]["revision"], out["created"]), (True, 1, ["royalebench/draft"]))

    def test_bad_tags_are_rejected(self):
        for tag in ("latest", "12", "bad tag", ""):
            r = self.client.post(self.URL, json={"tags": [tag]})
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "validation_error"), tag)

    def test_tasks_with_problems_need_an_explicit_override(self):
        make_task(self.benchmarks / "alpha" / "broken", tests=None)
        r = self.client.post(self.URL, json={"tags": []})
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "has_problems"))
        self.assertIn("broken", str(r.json()["error"]["detail"]))
        self.assertEqual(self.client.post(self.URL, json={"tags": [], "allow_problems": True}).status_code, 200)

    def test_remote_only_benchmarks_cannot_be_published(self):
        self.assertEqual(self.client.post("/api/evals/benchmarks/arena-lite/publish", json={}).status_code, 404)


class LeaderboardTests(ApiCase):
    URL = "/api/evals/leaderboard"

    def test_default_excludes_smoke_and_ranks_by_score(self):
        body = self.client.get(self.URL).json()
        rows = body["rows"]
        self.assertEqual([r["model"] for r in rows], ["anthropic/claude-opus-5-5", "anthropic/claude-sonnet-4-6", "openai/gpt-5",
                                                       "anthropic/claude-haiku-5-5"][: len(rows)])
        self.assertEqual([r["rank"] for r in rows], list(range(1, len(rows) + 1)))
        self.assertEqual(body["smoke_datasets"], ["smoke"])
        self.assertEqual(body["filters"]["datasets"], ["arena-lite"])
        self.assertEqual(body["runs_considered"], 4)
        self.assertEqual(body["tasks_considered"], 16)
        scores = [r["score"] for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(r["tasks_run"] == 4 and r["infra_errors"] == 0 for r in rows))

    def test_include_smoke_pools_smoke_runs_in(self):
        rows = {(r["model"], r["harness"]): r for r in self.client.get(self.URL, params={"include_smoke": True}).json()["rows"]}
        sonnet = rows[("anthropic/claude-sonnet-4-6", "claude_code-v1.0.0")]
        self.assertEqual((sonnet["runs"], sonnet["tasks_run"]), (2, 5))  # one arena-lite run + one smoke run
        # The mini-swe smoke run ERRORED (its harness could not install): only FINISHED runs are ranked, because a
        # failed or stopped run can still be retried or resumed and would otherwise score a model 0 for a broken harness.
        self.assertNotIn(("anthropic/claude-sonnet-4-6", "mini_swe_agent"), rows)

    def test_filters_and_option_lists(self):
        body = self.client.get(self.URL, params={"dataset": "smoke", "harness": "codex-v1.0.0"}).json()
        self.assertEqual([r["model"] for r in body["rows"]], ["openai/gpt-5"])
        self.assertEqual(body["filters"]["harnesses"], ["claude_code-v1.0.0", "codex-v1.0.0"])
        self.assertEqual(body["filters"]["revisions"], ["1"])
        self.assertEqual(self.client.get(self.URL, params={"dataset": "arena-lite", "revision": "7"}).json()["rows"], [])

    def test_cost_download_runs_in_the_background_and_fills_in_costs(self):
        before = self.client.get(self.URL).json()
        self.assertEqual(before["costs_pending"], 16)
        self.assertTrue(all(r["cost_usd"] is None for r in before["rows"]))
        status = self.client.post(self.URL + "/costs").json()
        self.assertIn(status["state"], ("running", "done"))
        for _ in range(100):
            status = self.client.get(self.URL + "/costs").json()
            if status["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual((status["state"], status["done"], status["total"]), ("done", 16, 16))
        after = self.client.get(self.URL).json()
        self.assertEqual(after["costs_pending"], 0)
        self.assertTrue(all(r["cost_usd"] > 0 and r["cost_known"] == 4 for r in after["rows"]))
        self.assertAlmostEqual(after["rows"][0]["cost_per_task"] * 4, after["rows"][0]["cost_usd"])

    def test_a_cost_download_failure_is_reported(self):
        def boom(*args, **kwargs):
            raise RuntimeError("disk full")

        from rb_server.services import leaderboard as service
        import rb_evals.results as results_module

        original = results_module.load_records
        results_module.load_records = lambda *a, fetch_costs=False, **k: (boom() if fetch_costs else original(*a, fetch_costs=False, **k))
        self.addCleanup(setattr, results_module, "load_records", original)
        self.client.post(self.URL + "/costs")
        for _ in range(100):
            status = self.client.get(self.URL + "/costs").json()
            if status["state"] != "running":
                break
            time.sleep(0.05)
        self.assertEqual(status["state"], "error")
        self.assertIn("disk full", status["error"])
        self.assertIsNone(service and None)


class AssetTests(ApiCase):
    def test_logos(self):
        for family in ("claude", "qwen", "inkling", "deepseek", "kimi"):
            with self.subTest(family=family):
                r = self.client.get(f"/api/assets/logos/{family}")
                self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/svg+xml"))
                self.assertIn("max-age", r.headers["cache-control"])
                self.assertIn("<svg", r.text)
        self.assertEqual(self.client.get("/api/assets/logos/other").status_code, 404)


class StaticFrontendTests(ApiCase):
    def make_client(self, with_build: bool) -> TestClient:
        static = Path(self.tmp.name) / ("web" if with_build else "missing")
        if with_build:
            write(static / "index.html", "<!doctype html><title>RB</title><div id=root></div>")
            write(static / "assets" / "app-abc123.js", "console.log(1)")
        settings = Settings(static_dir=static)
        client = TestClient(create_app(settings, ctx=build_context(settings, valkyrie=self.fake, cfg=self.cfg)))
        self.addCleanup(client.close)
        return client

    def test_serves_the_spa_with_history_fallback(self):
        client = self.make_client(True)
        index = client.get("/")
        self.assertEqual((index.status_code, index.headers["cache-control"]), (200, "no-cache"))
        deep = client.get("/evals/jobs/some-run")  # a client-side route, reloaded
        self.assertEqual((deep.status_code, deep.text), (200, index.text))
        self.assertEqual(client.get("/assets/app-abc123.js").status_code, 200)
        self.assertNotEqual(client.get("/assets/app-abc123.js").headers.get("cache-control"), "no-cache")
        missing = client.get("/api/nope")
        self.assertEqual((missing.status_code, missing.json()["error"]["code"]), (404, "not_found"))
        self.assertEqual(client.get("/api/health").json(), {"status": "ok", "read_only": False, "fake": False})

    def test_health_tells_the_web_app_when_the_server_is_read_only(self):
        client = self.make_client(False)
        self.assertFalse(client.get("/api/health").json()["read_only"])
        settings = Settings(static_dir=Path(self.tmp.name) / "missing")
        locked = TestClient(create_app(settings, ctx=build_context(settings, valkyrie=self.fake, cfg=dataclasses.replace(self.cfg, read_only=True))))
        self.addCleanup(locked.close)
        self.assertTrue(locked.get("/api/health").json()["read_only"])

    def test_explains_how_to_build_when_the_frontend_is_missing(self):
        client = self.make_client(False)
        r = client.get("/evals/jobs")
        self.assertEqual(r.status_code, 503)
        self.assertIn("npm run build", r.text)
        self.assertEqual(client.get("/api/health").status_code, 200)


class OpenApiContractTests(unittest.TestCase):
    def test_committed_openapi_matches_the_code(self):
        committed = OPENAPI_PATH.read_text(encoding="utf-8") if OPENAPI_PATH.exists() else ""
        self.assertEqual(committed, render(build_openapi()),
                         "rb_server/openapi.json is stale: run `uv run python -m rb_server.export_openapi` and then "
                         "`cd web && npm run gen:api`")

    def test_every_error_code_the_client_handles_is_declared(self):
        from rb_server.errors import ERROR_CODES

        self.assertIn("valkyrie_auth", ERROR_CODES)
        self.assertEqual(len(ERROR_CODES), len(set(ERROR_CODES)))


if __name__ == "__main__":
    unittest.main()
