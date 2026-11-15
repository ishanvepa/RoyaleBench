"""Shared Postgres (DATABASE_URL) or local SQLite storage for all arena data."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DB = Path("runs/arena.db")
ROOT = Path(__file__).resolve().parents[1]


def database_target(explicit: Path | str | None = None) -> str:
    """Explicit --db wins; otherwise every entry point uses the same .env."""
    load_dotenv(ROOT / ".env")
    return str(explicit or os.getenv("DATABASE_URL") or os.getenv("CR_ARENA_DB") or ROOT / DEFAULT_DB)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',      -- queued | running | done | stopped
    created_at REAL, started_at REAL, finished_at REAL,
    config_toml TEXT, players TEXT, seeds TEXT, decision_ticks INTEGER,
    total_matches INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS matches (
    job_id INTEGER NOT NULL, match_id TEXT NOT NULL,
    blue TEXT, red TEXT, seed INTEGER, deck TEXT,
    status TEXT NOT NULL DEFAULT 'queued',      -- queued | running | done | crashed | skipped
    winner INTEGER, crowns TEXT, tower_hp TEXT, ticks INTEGER, wall_s REAL,
    stats_blue TEXT, stats_red TEXT, error TEXT,
    started_at REAL, finished_at REAL, replay_path TEXT, log_path TEXT,
    PRIMARY KEY (job_id, match_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    job_id INTEGER, match_id TEXT, step INTEGER, team INTEGER, player TEXT,
    time_left REAL, elixir REAL, my_towers INTEGER, enemy_towers INTEGER,
    n_moves INTEGER, asked INTEGER, move TEXT, result TEXT, ok INTEGER, error TEXT,
    latency_s REAL, tokens_in INTEGER, tokens_out INTEGER, cache_read INTEGER, cache_write INTEGER,
    raw TEXT, state TEXT, cost_usd REAL
);
CREATE INDEX IF NOT EXISTS decisions_match ON decisions (job_id, match_id, step);
CREATE INDEX IF NOT EXISTS decisions_player ON decisions (job_id, player);
CREATE TABLE IF NOT EXISTS model_checks (
    name TEXT, provider TEXT, model TEXT, ok INTEGER, latency_s REAL, detail TEXT, checked_at REAL
);
CREATE TABLE IF NOT EXISTS custom_decks (
    id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, cards TEXT NOT NULL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL
);
"""


class DB:
    def __init__(self, path: Path | str | None = None, *, initialize: bool | None = None):
        self.target = database_target(path)
        self.postgres = self.target.startswith(("postgres://", "postgresql://"))
        self.lock = threading.RLock()
        self._transaction_depth = 0
        self._job_name = None
        self._closed = False
        self.path = None if self.postgres else Path(self.target)
        if self.postgres:
            self.conn = self._connect_postgres()
            try:
                if initialize is None:
                    initialize = os.getenv("CR_ARENA_DB_INIT", "1") != "0"
                if initialize:
                    with self.conn.transaction():
                        self.conn.execute("SELECT pg_advisory_xact_lock(68267, 0)")
                        for migration in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
                            self.conn.execute(migration.read_text(), prepare=False)
            except BaseException:
                self.conn.close()
                raise
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(decisions)")}
            if "cost_usd" not in cols:
                self.conn.execute("ALTER TABLE decisions ADD COLUMN cost_usd REAL")
            self.conn.commit()

    def _connect_postgres(self):
        import psycopg
        from psycopg.rows import dict_row

        # Session pooler or direct connection. Never expose the URL in the UI/logs.
        conn = psycopg.connect(self.target, autocommit=True, row_factory=dict_row,
                               prepare_threshold=None, connect_timeout=15)
        try:
            conn.execute("SET search_path TO cr_arena, public")
            # Some hosted configs round float text by default. Preserve timestamps/costs.
            conn.execute("SET extra_float_digits TO 3")
        except BaseException:
            conn.close()
            raise
        return conn

    def _ensure_connection(self):
        if self._closed:
            raise RuntimeError("Database has been closed")
        if self.postgres and self.conn.closed:
            # A dashboard may reconnect on its next refresh/save attempt. Never silently
            # retry a write with an unknown commit outcome or lose an active runner's lock.
            if self._transaction_depth or self._job_name:
                raise RuntimeError("Database connection lost during a run; restore connectivity and resume the job")
            self.conn = self._connect_postgres()

    @property
    def label(self) -> str:
        return "Shared PostgreSQL" if self.postgres else str(self.path)

    def _sql(self, sql: str) -> str:
        # Internal queries use qmark parameters and contain no quoted question marks.
        return sql.replace("%", "%%").replace("?", "%s") if self.postgres else sql

    @contextmanager
    def transaction(self):
        with self.lock:
            self._ensure_connection()
            self._transaction_depth += 1
            try:
                if self.postgres:
                    with self.conn.transaction():
                        yield
                else:
                    # Savepoints support nested DB methods and roll back the entire outer unit.
                    self.conn.execute("SAVEPOINT arena_write")
                    try:
                        yield
                        self.conn.execute("RELEASE SAVEPOINT arena_write")
                    except BaseException:
                        self.conn.execute("ROLLBACK TO SAVEPOINT arena_write")
                        self.conn.execute("RELEASE SAVEPOINT arena_write")
                        raise
            finally:
                self._transaction_depth -= 1

    @contextmanager
    def job_lock(self, name: str):
        """One runner per shared job; released by Postgres even if the runner dies."""
        if not self.postgres:
            yield
            return
        row = self.query("SELECT pg_try_advisory_lock(68268, hashtext(?)) AS acquired", (name,))[0]
        if not row["acquired"]:
            raise RuntimeError(f"Job {name!r} already has an active runner. Use a different --job name.")
        self._job_name = name
        try:
            yield
        finally:
            try:
                if not self.conn.closed:
                    self.query("SELECT pg_advisory_unlock(68268, hashtext(?))", (name,))
            finally:
                self._job_name = None

    def close(self):
        with self.lock:
            self._closed = True
            self.conn.close()

    def execute(self, sql: str, params=()):
        with self.transaction():
            cur = self.conn.execute(self._sql(sql), params)
            return cur

    def executemany(self, sql: str, rows):
        with self.transaction():
            if self.postgres:
                with self.conn.cursor() as cur:
                    cur.executemany(self._sql(sql), rows)
            else:
                self.conn.executemany(sql, rows)

    def query(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            self._ensure_connection()
            return [dict(r) for r in self.conn.execute(self._sql(sql), params).fetchall()]

    # ------------------------------------------------------------------ custom decks
    def custom_decks(self) -> list[dict]:
        rows = self.query("SELECT * FROM custom_decks ORDER BY name, id")
        return [{**row, "cards": json.loads(row["cards"])} for row in rows]

    def save_custom_deck(self, name: str, cards: list[str], deck_id: str | None = None) -> str:
        from .decks import validate_deck

        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Give your deck a name between 1 and 80 characters.")
        cards = validate_deck(cards)
        now = time.time()
        with self.transaction():
            if deck_id is not None and not self.query("SELECT id FROM custom_decks WHERE id = ?", (deck_id,)):
                raise ValueError("This deck no longer exists. Create a new deck instead.")
            duplicate = self.query("SELECT id FROM custom_decks WHERE name = ?", (name,))
            if duplicate and duplicate[0]["id"] != deck_id:
                raise ValueError("A deck with this name already exists. Choose another name.")
            if deck_id is None:
                deck_id = uuid.uuid4().hex
                self.execute("INSERT INTO custom_decks (id, name, cards, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                             (deck_id, name, json.dumps(cards), now, now))
            else:
                self.execute("UPDATE custom_decks SET name = ?, cards = ?, updated_at = ? WHERE id = ?",
                             (name, json.dumps(cards), now, deck_id))
        return deck_id

    def delete_custom_deck(self, deck_id: str) -> None:
        self.execute("DELETE FROM custom_decks WHERE id = ?", (deck_id,))

    # ------------------------------------------------------------------ jobs
    def get_or_create_job(self, name: str, config_toml: str, players: list[str], seeds: list[int],
                          decision_ticks: int, total: int, notes: str = "") -> int:
        with self.transaction():
            row = self.query(
                "INSERT INTO jobs (name, status, created_at, config_toml, players, seeds, decision_ticks, total_matches, notes)"
                " VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (name) DO UPDATE SET total_matches = excluded.total_matches RETURNING id",
                (name, time.time(), config_toml, json.dumps(players), json.dumps(seeds), decision_ticks, total, notes),
            )
            return row[0]["id"]

    def set_job_status(self, job_id: int, status: str) -> None:
        col = {"running": "started_at", "done": "finished_at", "stopped": "finished_at"}.get(status)
        if col == "started_at":
            self.execute("UPDATE jobs SET status = ?, started_at = COALESCE(started_at, ?), finished_at = NULL WHERE id = ?",
                         (status, time.time(), job_id))
        elif col:
            self.execute(f"UPDATE jobs SET status = ?, {col} = ? WHERE id = ?", (status, time.time(), job_id))
        else:
            self.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))

    # ------------------------------------------------------------------ matches
    def queue_matches(self, job_id: int, jobs: list[dict]) -> None:
        self.executemany(
            "INSERT INTO matches (job_id, match_id, blue, red, seed, deck, status) VALUES (?, ?, ?, ?, ?, ?, 'queued')"
            " ON CONFLICT (job_id, match_id) DO NOTHING",
            [(job_id, j["match_id"], j["blue"], j["red"], j["seed"], json.dumps(j["deck"])) for j in jobs],
        )
        # Anything left 'running' by a killed process is re-queued.
        self.execute("UPDATE matches SET status = 'queued' WHERE job_id = ? AND status IN ('running', 'crashed')", (job_id,))

    def done_match_ids(self, job_id: int) -> set[str]:
        return {r["match_id"] for r in self.query("SELECT match_id FROM matches WHERE job_id = ? AND status = 'done'", (job_id,))}

    def match_started(self, job_id: int, match_id: str, log_path: str, replay_path: str) -> None:
        with self.transaction():
            self.execute("DELETE FROM decisions WHERE job_id = ? AND match_id = ?", (job_id, match_id))  # clean retry
            if self.postgres:
                self.execute("DELETE FROM replays WHERE job_id = ? AND match_id = ?", (job_id, match_id))
            self.execute("UPDATE matches SET status = 'running', started_at = ?, finished_at = NULL, error = NULL, log_path = ?, replay_path = ?"
                         " WHERE job_id = ? AND match_id = ?", (time.time(), log_path, replay_path, job_id, match_id))

    def match_finished(self, job_id: int, res: dict) -> None:
        # Save the replay before publishing status=done. Never claim a cloud save succeeded
        # when any part of the persistence failed.
        with self.transaction():
            if self.postgres:
                rows = self.query("SELECT replay_path FROM matches WHERE job_id = ? AND match_id = ?",
                                  (job_id, res["match_id"]))
                replay = rows[0]["replay_path"] if rows else None
                if replay:
                    content = Path(replay).read_bytes()
                    self.execute("INSERT INTO replays (job_id, match_id, content) VALUES (?, ?, ?) "
                                 "ON CONFLICT (job_id, match_id) DO UPDATE SET content = excluded.content",
                                 (job_id, res["match_id"], content))
            self._finish_match(job_id, res)

    def replay_file(self, job_id: int, match_id: str, local_path: str | None) -> Path | None:
        if self.postgres:
            # Cache by content hash so different jobs/reruns cannot return a stale local replay.
            import hashlib
            rows = self.query("SELECT content FROM replays WHERE job_id = ? AND match_id = ?", (job_id, match_id))
            if not rows:
                return None
            content = bytes(rows[0]["content"])
            path = ROOT / "runs" / "replay-cache" / f"{hashlib.sha256(content).hexdigest()}.msgpack"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(content)
            return path
        if not local_path:
            return None
        path = Path(local_path)
        return path if path.is_absolute() else ROOT / path

    def _finish_match(self, job_id: int, res: dict) -> None:
        self.execute(
            "UPDATE matches SET status = 'done', winner = ?, crowns = ?, tower_hp = ?, ticks = ?, wall_s = ?,"
            " stats_blue = ?, stats_red = ?, finished_at = ? WHERE job_id = ? AND match_id = ?",
            (res["winner"], json.dumps(res["crowns"]), json.dumps(res["tower_hp"]), res["ticks"], res["wall_s"],
             json.dumps(res["stats_blue"]), json.dumps(res["stats_red"]), time.time(), job_id, res["match_id"]),
        )

    def set_match_decks(self, job_id: int, match_id: str, deck_blue: list[str], deck_red: list[str]) -> None:
        deck = deck_blue if deck_blue == deck_red else {"blue": deck_blue, "red": deck_red}
        self.execute("UPDATE matches SET deck = ? WHERE job_id = ? AND match_id = ?", (json.dumps(deck), job_id, match_id))

    def match_crashed(self, job_id: int, match_id: str, error: str) -> None:
        self.execute("UPDATE matches SET status = 'crashed', error = ?, finished_at = ? WHERE job_id = ? AND match_id = ?",
                     (error[-4000:], time.time(), job_id, match_id))

    def add_decisions(self, rows: list[tuple]) -> None:
        self.executemany(
            "INSERT INTO decisions (job_id, match_id, step, team, player, time_left, elixir, my_towers, enemy_towers,"
            " n_moves, asked, move, result, ok, error, latency_s, tokens_in, tokens_out, cache_read, cache_write, raw, state,"
            " cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def results(self, job_id: int | None = None) -> list[dict]:
        """Finished matches in the shape ratings.py expects."""
        where, params = ("WHERE status = 'done'", ())
        if job_id is not None:
            where, params = ("WHERE status = 'done' AND job_id = ?", (job_id,))
        return self.query(f"SELECT job_id, match_id, blue, red, seed, winner, crowns FROM matches {where}", params)

    # ------------------------------------------------------------------ model checks
    def add_model_check(self, name, provider, model, ok, latency_s, detail) -> None:
        self.execute("INSERT INTO model_checks VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (name, provider, model, int(ok), latency_s, detail[:1000], time.time()))
