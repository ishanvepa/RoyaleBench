"""Storage integration checks.

uv run python -m unittest discover -s tests -v
Set ARENA_TEST_DATABASE_URL to a disposable Postgres database to include cloud-adapter tests.
"""

import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cr_arena.db import DB, ROOT, database_target
from cr_arena.migrate import import_snapshot, snapshot


class Rollback(Exception):
    pass


class TargetConfiguration(unittest.TestCase):
    def test_all_entry_points_prefer_shared_url_and_allow_explicit_local_override(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example/test", "CR_ARENA_DB": "other.db"}), \
                patch("cr_arena.db.load_dotenv"):
            self.assertEqual(database_target(), "postgresql://example/test")
            self.assertEqual(database_target("offline.db"), "offline.db")

    def test_sqlite_fallback_is_relative_to_repo_not_launch_directory(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "CR_ARENA_DB": ""}), \
                patch("cr_arena.db.load_dotenv"):
            self.assertEqual(database_target(), str(ROOT / "runs" / "arena.db"))


class StorageContract:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DB(self.target())
        self.ids = []

    def tearDown(self):
        for jid in self.ids:
            if self.db.postgres:
                self.db.execute("DELETE FROM replays WHERE job_id = ?", (jid,))
            self.db.execute("DELETE FROM decisions WHERE job_id = ?", (jid,))
            self.db.execute("DELETE FROM matches WHERE job_id = ?", (jid,))
            self.db.execute("DELETE FROM jobs WHERE id = ?", (jid,))
        self.db.close()
        self.tmp.cleanup()

    def job(self):
        name = "storage-test-" + uuid.uuid4().hex
        jid = self.db.get_or_create_job(name, "test-config", ["blue", "red"], [1], 40, 1)
        self.ids.append(jid)
        return name, jid

    def match(self, jid):
        row = {"match_id": "test-match", "blue": "blue", "red": "red", "seed": 1, "deck": []}
        self.db.queue_matches(jid, [row])
        self.db.match_started(jid, "test-match", "", "")

    def test_resume_and_live_reader(self):
        name, jid = self.job()
        self.match(jid)
        self.assertEqual(self.db.get_or_create_job(name, "ignored", [], [], 40, 1), jid)
        self.db.add_decisions([(jid, "test-match", 0, 0, "blue", 180., 5., 100, 100, 2,
                                1, "wait", "waited", 1, None, .125, 17, 8, 0, 0,
                                "raw reply \U0001f3c6", "board state", .001)])
        reader = DB(self.db.target, initialize=False)
        try:
            row = reader.query("SELECT * FROM decisions WHERE job_id = ?", (jid,))[0]
            self.assertEqual(row["raw"], "raw reply \U0001f3c6")
            self.assertEqual(row["tokens_in"], 17)
            self.db.match_finished(jid, {"match_id": "test-match", "winner": 0, "crowns": [1, 0],
                                       "tower_hp": [100, 0], "ticks": 200, "wall_s": 3.,
                                       "stats_blue": {}, "stats_red": {}})
            self.assertEqual(reader.results(jid)[0]["winner"], 0)
            self.db.queue_matches(jid, [{"match_id": "test-match", "blue": "blue", "red": "red", "seed": 1, "deck": []}])
            self.assertEqual(self.db.done_match_ids(jid), {"test-match"})
        finally:
            reader.close()

    def test_atomic_save_and_recovery_after_error(self):
        _, jid = self.job()
        with self.assertRaises(Rollback):
            with self.db.transaction():
                self.match(jid)
                raise Rollback()
        self.assertFalse(self.db.query("SELECT * FROM matches WHERE job_id = ?", (jid,)))
        self.match(jid)
        with self.assertRaises(Exception):
            self.db.execute("INSERT INTO matches (job_id, match_id) VALUES (?, ?)", (jid, "test-match"))
        self.assertEqual(self.db.query("SELECT status FROM matches WHERE job_id = ?", (jid,))[0]["status"], "running")

    def test_retry_clears_partial_decisions(self):
        _, jid = self.job()
        self.match(jid)
        self.db.execute("INSERT INTO decisions (job_id,match_id,step,team) VALUES (?, ?, 0, 0)", (jid, "test-match"))
        self.db.match_crashed(jid, "test-match", "test failure")
        self.db.queue_matches(jid, [])
        self.db.match_started(jid, "test-match", "", "")
        self.assertFalse(self.db.query("SELECT * FROM decisions WHERE job_id = ?", (jid,)))
        row = self.db.query("SELECT * FROM matches WHERE job_id = ?", (jid,))[0]
        self.assertIsNone(row["error"])
        self.assertIsNone(row["finished_at"])

    def test_percent_literals_and_qmark_parameters(self):
        row = self.db.query("SELECT ? AS value, CASE WHEN ? LIKE 'played%' THEN 1 ELSE 0 END AS played, "
                            "5 % 2 AS remainder", ("100% raw", "played Giant"))[0]
        self.assertEqual(row, {"value": "100% raw", "played": 1, "remainder": 1})
        self.assertEqual(self.db.query("SELECT '100%' AS value")[0]["value"], "100%")


class SQLiteStorage(StorageContract, unittest.TestCase):
    def target(self):
        return Path(self.tmp.name) / "test.db"


@unittest.skipUnless(os.getenv("ARENA_TEST_DATABASE_URL"), "Set ARENA_TEST_DATABASE_URL for Postgres integration")
class PostgresStorage(StorageContract, unittest.TestCase):
    def target(self):
        return os.environ["ARENA_TEST_DATABASE_URL"]

    def test_job_lock_excludes_second_runner_and_releases(self):
        name, _ = self.job()
        other = DB(self.target(), initialize=False)
        try:
            with self.db.job_lock(name):
                with self.assertRaises(RuntimeError):
                    with other.job_lock(name):
                        self.fail("second runner obtained lock")
            with other.job_lock(name):
                pass
        finally:
            other.close()

    def test_dashboard_reconnects_but_runner_never_silently_loses_lock(self):
        name, jid = self.job()
        self.db.conn.close()  # simulate a disconnected cached dashboard connection
        self.assertEqual(self.db.query("SELECT id FROM jobs WHERE name = ?", (name,))[0]["id"], jid)
        with self.db.job_lock(name):
            self.db.conn.close()
            with self.assertRaisesRegex(RuntimeError, "resume the job"):
                self.db.query("SELECT id FROM jobs WHERE name = ?", (name,))
        self.assertEqual(self.db.query("SELECT id FROM jobs WHERE name = ?", (name,))[0]["id"], jid)

    def test_broken_import_rolls_back_jobs_and_import_marker(self):
        source = Path(self.tmp.name) / "broken.db"
        local = DB(source)
        name = "broken-import-" + uuid.uuid4().hex
        local.get_or_create_job(name, "", [], [], 40, 0)
        # A legacy SQLite DB can contain orphan rows; the importer must reject them atomically.
        local.execute("INSERT INTO decisions (job_id,match_id,step,team) VALUES (999, 'orphan', 0, 0)")
        local.close()
        before = self.db.query("SELECT COUNT(*) AS n FROM imports")[0]["n"]
        with self.assertRaises(KeyError):
            import_snapshot(source, self.db)
        self.assertFalse(self.db.query("SELECT id FROM jobs WHERE name = ?", (name,)))
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM imports")[0]["n"], before)

    def test_replay_is_shared_and_failed_finish_is_atomic(self):
        _, jid = self.job()
        self.match(jid)
        path = Path(self.tmp.name) / "replay.msgpack"
        self.db.execute("UPDATE matches SET replay_path = ? WHERE job_id = ?", (str(path), jid))
        result = {"match_id": "test-match", "winner": 0, "crowns": [1, 0], "tower_hp": [100, 0],
                  "ticks": 200, "wall_s": 3., "stats_blue": {}, "stats_red": {}}
        with self.assertRaises(FileNotFoundError):
            self.db.match_finished(jid, result)
        self.assertEqual(self.db.query("SELECT status FROM matches WHERE job_id = ?", (jid,))[0]["status"], "running")
        path.write_bytes(b"test-replay-content")
        self.db.match_finished(jid, result)
        path.unlink()
        other = DB(self.target(), initialize=False)
        try:
            cached = other.replay_file(jid, "test-match", str(path))
            self.assertEqual(cached.read_bytes(), b"test-replay-content")
        finally:
            other.close()

    def test_full_snapshot_import_is_lossless_and_repeatable(self):
        source = ROOT / "data" / "arena.db.gz"
        with self.assertRaises(Rollback):
            with self.db.transaction():
                before = {t: self.db.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
                          for t in ("jobs", "matches", "decisions", "model_checks")}
                result = import_snapshot(source, self.db)
                self.assertFalse(result["already_imported"])
                again = import_snapshot(source, self.db)
                self.assertTrue(again["already_imported"])
                with snapshot(source) as (local, _, counts):
                    for t, count in counts.items():
                        self.assertEqual(self.db.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] - before[t], count)
                    # Compare every stored value, mapping generated job IDs back to source IDs.
                    source_jobs = {r["name"]: r["id"] for r in local.execute("SELECT * FROM jobs")}
                    mapping = {r["id"]: source_jobs[r["name"]] for r in self.db.query("SELECT id,name FROM jobs")
                               if r["name"] in source_jobs}
                    for t in counts:
                        source_rows = [dict(r) for r in local.execute(f"SELECT * FROM {t}")]
                        remote = self.db.query(f"SELECT * FROM {t}")
                        converted = []
                        for row in remote:
                            key = "id" if t == "jobs" else "job_id" if "job_id" in row else None
                            if key:
                                if row[key] not in mapping:
                                    continue
                                row[key] = mapping[row[key]]
                            converted.append(row)
                        encode = lambda rows: sorted(json.dumps(r, sort_keys=True, ensure_ascii=True) for r in rows)
                        self.assertEqual(encode(source_rows), encode(converted))
                from cr_arena.site import build
                page = build(self.db, out=Path(self.tmp.name) / "leaderboard.html")
                self.assertIn('"Classic decks"', page.read_text(encoding="utf-8"))
                raise Rollback()


if __name__ == "__main__":
    unittest.main()
