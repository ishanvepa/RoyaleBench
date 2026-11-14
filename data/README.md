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

Schema is in `cr_arena/db.py` (`SCHEMA`). Notes for a Postgres port:
- `jobs.id` is `INTEGER PRIMARY KEY AUTOINCREMENT` -> `BIGSERIAL`; `matches` PK is `(job_id, match_id)`.
- Timestamps (`created_at`, `started_at`, `finished_at`, `checked_at`) are Unix seconds as `REAL` -> use
  `DOUBLE PRECISION` (Postgres `REAL` is 4-byte and would lose precision).
- JSON is stored as TEXT (`crowns`, `tower_hp`, `deck`, `stats_blue`, `stats_red`, `players`, `seeds`) -> `jsonb` works.
- SQLite-specific statements in `cr_arena/db.py`: `?` placeholders (-> `%s` in psycopg), `INSERT OR IGNORE`
  (-> `ON CONFLICT DO NOTHING`), `PRAGMA` calls, `cursor.lastrowid` (-> `RETURNING id`), and one
  `ALTER TABLE decisions ADD COLUMN cost_usd` migration.
- Size: ~75 MB uncompressed; `decisions.state` + `decisions.raw` are ~46 MB of it. Supabase free tier is 500 MB.
