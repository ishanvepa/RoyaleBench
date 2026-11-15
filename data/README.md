# Data snapshot

`arena.db.gz`: a gzip'd copy of `runs/arena.db`, the SQLite database every run writes to and the dashboard
reads. Snapshot taken 2026-11-07 (45 benchmark games plus earlier test jobs; ~37k logged decisions).

```bash
gunzip -k data/arena.db.gz && cp data/arena.db runs/arena.db    # restore locally, then:
uv run streamlit run dashboard/app.py
```

To refresh the snapshot after new runs:

```bash
sqlite3 runs/arena.db ".backup data/arena.db" && sqlite3 data/arena.db "PRAGMA journal_mode=DELETE; VACUUM;"
gzip -9 -k -f data/arena.db
for t in jobs matches model_checks; do sqlite3 -header -csv data/arena.db "select * from $t" > data/csv/$t.csv; done
```

`csv/`: the small tables as CSV (readable on GitHub). `decisions` (one row per player per 2 s decision,
including the exact board text sent and the model's full reply) is only in the database; it is most of its size.

## Jobs in the snapshot

| job | what | status |
|---|---|---|
| `classic-v2` | **benchmark**: 5 Claude models, classic decks (mirrored), 10 games per model | done (equalized; rest of schedule `skipped`) |
| `build-v2` | **benchmark**: 5 Claude models build their own decks, 8 games per model | done (equalized; rest `skipped`) |
| `classic-v1`, `build-v1` | earlier attempt including bots, stopped early | stopped |
| `fable-vs-haiku`, `counter-deck` | early experiments (Fable vs Haiku + bots; Haiku with a counter deck) | done |
| `bots-smoke`, `mock-demo`, `live-test` | pipeline tests (bots / fake LLMs) | done |

## Tables (for moving to a hosted database, e.g. Supabase Postgres)

The repository now includes a Supabase adapter and complete importer. Set `DATABASE_URL` in
your git-ignored `.env`, then run `uv run python -m cr_arena.migrate`. This reads `arena.db.gz`
directly, preserves every table and decision, and can be retried without duplication. The import
is atomic and never changes this snapshot. See the root README's **Shared Supabase database**
section for project setup and team access. New runs use the configured shared database automatically.

The notes below describe the original SQLite representation; the deployed Postgres schema is
in `supabase/migrations/202611070001_arena.sql` (JSON stays TEXT for compatibility with the dashboard).

Schema is in `cr_arena/db.py` (`SCHEMA`). Notes for a Postgres port:
- `jobs.id` is `INTEGER PRIMARY KEY AUTOINCREMENT` -> `BIGSERIAL`; `matches` PK is `(job_id, match_id)`.
- Timestamps (`created_at`, `started_at`, `finished_at`, `checked_at`) are Unix seconds as `REAL` -> use
  `DOUBLE PRECISION` (Postgres `REAL` is 4-byte and would lose precision).
- JSON is stored as TEXT (`crowns`, `tower_hp`, `deck`, `stats_blue`, `stats_red`, `players`, `seeds`) -> `jsonb` works.
- SQLite-specific statements in `cr_arena/db.py`: `?` placeholders (-> `%s` in psycopg), `INSERT OR IGNORE`
  (-> `ON CONFLICT DO NOTHING`), `PRAGMA` calls, `cursor.lastrowid` (-> `RETURNING id`), and one
  `ALTER TABLE decisions ADD COLUMN cost_usd` migration.
- Size: ~75 MB uncompressed; `decisions.state` + `decisions.raw` are ~46 MB of it. Supabase free tier is 500 MB.

## Visual reference

The local graphics reference is `data/references/arena-1-PD6QCK7GzA8.mp4`,
downloaded from [JustAction, “terrorizing arena 1 players”](https://www.youtube.com/watch?v=PD6QCK7GzA8)
(published 2025-11-22). It is a 14:20, 1920×1080, 60 fps H.264/AAC video.
SHA-256: `b8eb9da25d3dcbcc94d9dfed278d70329d1c1ee0f0759d6ae7c36ac9541a0a55`.
The 145 MB video is git-ignored; the source link and checksum remain in the repository.

To restore the same local reference:

```bash
uvx --from yt-dlp yt-dlp --js-runtimes node --no-playlist -f '299+140-12' \
  --merge-output-format mp4 -o 'data/references/arena-1-PD6QCK7GzA8.%(ext)s' \
  'https://www.youtube.com/watch?v=PD6QCK7GzA8'
```
