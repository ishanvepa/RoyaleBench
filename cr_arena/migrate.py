"""Import a complete offline SQLite snapshot into the configured shared Postgres DB.

    uv run python -m cr_arena.migrate --inspect
    uv run python -m cr_arena.migrate

The source is never modified. A transaction and content fingerprint make retries safe.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from .db import DB, ROOT

TABLES = ("jobs", "matches", "decisions", "model_checks")


@contextmanager
def snapshot(source: Path):
    source = source.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="arena-import-") as tmp:
        path = Path(tmp) / "snapshot.db"
        if source.suffix == ".gz":
            with gzip.open(source, "rb") as src, path.open("wb") as out:
                shutil.copyfileobj(src, out)
        else:
            # backup() includes committed WAL data and gives a consistent copy of a live DB.
            src = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
            dest = sqlite3.connect(path)
            try:
                src.backup(dest)
            finally:
                src.close()
                dest.close()
        with path.open("rb") as f:
            hasher = hashlib.sha256()
            for block in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(block)
            digest = hasher.hexdigest()
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Source SQLite database failed its integrity check")
            counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}
            yield conn, digest, counts
        finally:
            conn.close()


def import_snapshot(source: Path, db: DB) -> dict:
    if not db.postgres:
        raise ValueError("Set DATABASE_URL to your Supabase Postgres Session pooler URL before importing")
    from psycopg import sql

    with snapshot(source) as (local, digest, counts), db.transaction():
        db.query("SELECT pg_advisory_xact_lock(68267, 1)")
        existing = db.query("SELECT counts FROM imports WHERE source_sha256 = ?", (digest,))
        if existing:
            return {"already_imported": True, "counts": json.loads(existing[0]["counts"])}
        jobs = [dict(r) for r in local.execute("SELECT * FROM jobs ORDER BY id")]
        for job in jobs:
            if db.query("SELECT id FROM jobs WHERE name = ?", (job["name"],)):
                raise ValueError(f"Job {job['name']!r} already exists in the destination. "
                                 "Import into a fresh database to avoid overwriting live runs.")
        id_map = {}
        for job in jobs:
            old_id = job.pop("id")
            columns = list(job)
            query = sql.SQL("INSERT INTO jobs ({}) VALUES ({}) RETURNING id").format(
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
            id_map[old_id] = db.conn.execute(query, list(job.values())).fetchone()["id"]
        # COPY streams the large decisions table without loading it all into memory.
        for table in TABLES[1:]:
            cur = local.execute(f"SELECT * FROM {table}")
            columns = [c[0] for c in cur.description]
            job_index = columns.index("job_id") if "job_id" in columns else None
            query = sql.SQL("COPY {} ({}) FROM STDIN").format(
                sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
            )
            with db.conn.cursor() as dest, dest.copy(query) as copy:
                for row in cur:
                    values = list(row)
                    if job_index is not None:
                        values[job_index] = id_map[values[job_index]]
                    copy.write_row(values)
        db.execute("INSERT INTO imports (source_sha256, source_name, imported_at, counts) VALUES (?, ?, ?, ?)",
                   (digest, source.name, time.time(), json.dumps(counts)))
        return {"already_imported": False, "counts": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "arena.db.gz")
    parser.add_argument("--inspect", action="store_true", help="Validate and count the snapshot without connecting")
    args = parser.parse_args()
    if args.inspect:
        with snapshot(args.source) as (_, digest, counts):
            print(json.dumps({"sha256": digest, "counts": counts}, indent=2))
        return
    db = DB()
    try:
        print(json.dumps(import_snapshot(args.source, db), indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
