"""Task gameplay playback through the dashboard, without credentials or model calls."""

import dataclasses
import io
import tarfile
from pathlib import Path
from unittest.mock import patch

from rb_evals.valkyrie import ValkyrieError
from tests.helpers import ApiCase, SAMPLE_REPLAY


class TaskReplayTests(ApiCase):
    def finished_game(self):
        run_id = self.start(dataset="arena-lite", task_ids=["lane-defense"])
        self.advance(30)
        return run_id, f"/api/evals/jobs/{run_id}/tasks/lane-defense/replay"

    def archive_download(self, files):
        def download(run_id, path, dest):
            target = Path(dest) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(target, "w:gz") as tar:
                for name, data in files.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
            return Path(dest)
        return download

    def test_renders_game_and_caches_separately_from_agent_output(self):
        run_id, url = self.finished_game()
        with patch.object(self.fake, "download_artifact", wraps=self.fake.download_artifact) as download:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.text[:500])
            replay = response.json()
            self.assertTrue(replay["available"])
            self.assertFalse(replay["partial"])
            self.assertIn("Task replay: lane-defense", replay["html"])
            self.assertIn('aria-label="Timeline"', replay["html"])
            self.assertIn('aria-label="Playback speed"', replay["html"])
            self.assertIn('id="board"', replay["html"])
            self.client.get(url.replace("/replay", "/trace"))
            self.assertEqual(self.client.get(url).json(), replay)
            self.assertEqual([c.args[1] for c in download.call_args_list],
                             ["lane-defense/artifacts/royale.tar.gz", "lane-defense/agent_output.tar.gz"])

    def test_active_task_does_not_download_and_unknown_ids_are_404(self):
        run_id = self.start()
        with patch.object(self.fake, "download_artifact") as download:
            replay = self.client.get(f"/api/evals/jobs/{run_id}/tasks/t1/replay").json()
            self.assertFalse(replay["available"])
            self.assertIn("finishes or stops", replay["message"])
            download.assert_not_called()
        self.assertEqual(self.client.get(f"/api/evals/jobs/{run_id}/tasks/ghost/replay").status_code, 404)
        self.assertEqual(self.client.get("/api/evals/jobs/ghost/tasks/t1/replay").status_code, 404)

    def test_task_without_game_has_explanation(self):
        run_id = self.start()
        self.advance(30)
        replay = self.client.get(f"/api/evals/jobs/{run_id}/tasks/t1/replay").json()
        self.assertFalse(replay["available"])
        self.assertIn("No game replay was saved", replay["message"])

    def test_missing_replay_is_not_cached_and_remote_html_is_not_served(self):
        run_id, url = self.finished_game()
        with patch.object(self.fake, "download_artifact", side_effect=self.archive_download({"royale/replay.html": b"untrusted script"})):
            replay = self.client.get(url).json()
            self.assertFalse(replay["available"])
            self.assertEqual(replay["html"], "")
        self.assertTrue(self.client.get(url).json()["available"])

    def test_partial_stopped_attempt_is_refetched_after_resume(self):
        from royalegym.replay import load_trace, save_trace

        run_id = self.start(dataset="arena-lite", task_ids=["lane-defense"])
        self.advance(2)
        self.fake.stop_run(run_id)
        url = f"/api/evals/jobs/{run_id}/tasks/lane-defense/replay"
        sample = Path(self.tmp.name) / "partial.msgpack"
        trace = load_trace(SAMPLE_REPLAY)
        trace.result = None
        save_trace(trace, sample)
        with patch.object(self.fake, "download_artifact", side_effect=self.archive_download({"royale/replay.msgpack": sample.read_bytes()})):
            replay = self.client.get(url).json()
            self.assertTrue(replay["available"])
            self.assertTrue(replay["partial"])
        self.assertFalse((self.ctx.cache.replay_dir(run_id, "lane-defense") / "replay.msgpack").exists())
        self.fake.resume_run(run_id)
        self.advance(30)
        self.assertFalse(self.client.get(url).json()["partial"])

    def test_transfer_errors_and_corrupt_replays_are_retryable(self):
        run_id, url = self.finished_game()
        for kind, status in (("network", 503), ("auth", 401), ("other", 502)):
            with self.subTest(kind=kind), patch.object(self.fake, "download_artifact", side_effect=ValkyrieError("transfer failed", kind)):
                self.assertEqual(self.client.get(url).status_code, status)
        with patch.object(self.fake, "download_artifact", side_effect=self.archive_download({"royale/replay.msgpack": b"bad replay"})):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 502)
            self.assertIn("Could not render", response.json()["error"]["message"])
        self.assertFalse((self.ctx.cache.replay_dir(run_id, "lane-defense") / "replay.msgpack").exists())
        self.assertTrue(self.client.get(url).json()["available"])

    def test_playback_works_on_read_only_dashboard(self):
        _, url = self.finished_game()
        self.ctx.cfg = dataclasses.replace(self.ctx.cfg, read_only=True)
        self.assertTrue(self.client.get(url).json()["available"])
