"""Task resolution playback uses only matching, passing local validation evidence."""

import dataclasses
import hashlib
import json

from cr_arena.validate_v1_docker import protocol_for
from tests.helpers import ApiCase, SAMPLE_REPLAY, write


class TaskResolutionTests(ApiCase):
    URL = "/api/evals/benchmarks/alpha/tasks/t1/resolution"

    def save_resolution(self, *, folder="docker", config=None, **changes):
        task = self.benchmarks / "alpha" / "t1"
        cfg = config or {"family": 1, "seed": 1}
        write(task / "tests/task.json", json.dumps(cfg))
        protocol = protocol_for(cfg, task)
        row = dict(task="t1", reward=1, integrity=1, protocol_sha256=protocol,
                   config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                   isolated=True, restart_verified=True, replay_hashes_verified=True)
        row.update(changes)
        evidence = self.benchmarks.parent / "runs" / "alpha" / folder
        write(evidence / "validation.json", json.dumps(dict(protocol_sha256=protocol, tasks=[row])))
        write(evidence / "t1" / "replay.msgpack", SAMPLE_REPLAY.read_bytes())
        return task, evidence

    def test_plays_validated_reference_without_starting_a_run(self):
        self.save_resolution()
        before = len(self.fake.list_runs(self.cfg.benchmark))
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200, response.text[:200])
        result = response.json()
        self.assertTrue(result["available"])
        self.assertFalse(result["partial"])
        self.assertIn("Reference solution: t1", result["html"])
        self.assertIn('aria-label="Timeline"', result["html"])
        self.assertEqual(len(self.fake.list_runs(self.cfg.benchmark)), before)
        self.ctx.cfg = dataclasses.replace(self.ctx.cfg, read_only=True)
        self.assertTrue(self.client.get(self.URL).json()["available"])

    def test_ignores_stale_revision_and_selects_matching_validation(self):
        self.save_resolution(config={"family": 1, "seed": 0})
        self.save_resolution(folder="docker-revision2", config={"family": 1, "seed": 1})
        self.assertTrue(self.client.get(self.URL).json()["available"])
        write(self.benchmarks / "alpha" / "t1" / "tests/task.json", '{"family": 1, "seed": 2}')
        result = self.client.get(self.URL).json()
        self.assertFalse(result["available"])
        self.assertIn("matches this task version", result["message"])

    def test_missing_or_unvalidated_references_explain_why(self):
        self.assertIn("no saved reference replay", self.client.get(self.URL).json()["message"])
        _, evidence = self.save_resolution(reward=0)
        self.assertFalse(self.client.get(self.URL).json()["available"])
        self.save_resolution()
        (evidence / "t1" / "replay.msgpack").unlink()
        self.assertFalse(self.client.get(self.URL).json()["available"])
        self.assertEqual(self.client.get("/api/evals/benchmarks/alpha/tasks/ghost/resolution").status_code, 404)
