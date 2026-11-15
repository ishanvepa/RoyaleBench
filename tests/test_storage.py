"""Storage integration checks.

uv run python -m unittest discover -s tests -v
"""

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cr_arena.db import DB, ROOT, database_target


class Rollback(Exception):
    pass


class TargetConfiguration(unittest.TestCase):
    def test_local_path_overrides_environment_and_ignores_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example/test", "CR_ARENA_DB": "other.db"}), \
                patch("cr_arena.db.load_dotenv"):
            self.assertEqual(database_target(), "other.db")
            self.assertEqual(database_target("offline.db"), "offline.db")

    def test_sqlite_fallback_is_relative_to_repo_not_launch_directory(self):
        with patch.dict(os.environ, {"CR_ARENA_DB": ""}), \
                patch("cr_arena.db.load_dotenv"):
            self.assertEqual(database_target(), str(ROOT / "runs" / "arena.db"))


class StorageContract:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DB(self.target())
        self.ids = []

    def tearDown(self):
        for jid in self.ids:
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
        reader = DB(self.db.target)
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


if __name__ == "__main__":
    unittest.main()
