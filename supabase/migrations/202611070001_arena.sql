-- Private schema: use Postgres from Python; do not expose this schema via the Data API.
CREATE SCHEMA IF NOT EXISTS cr_arena;
CREATE TABLE IF NOT EXISTS cr_arena.jobs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at DOUBLE PRECISION, started_at DOUBLE PRECISION, finished_at DOUBLE PRECISION,
    config_toml TEXT, players TEXT, seeds TEXT, decision_ticks INTEGER,
    total_matches INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS cr_arena.matches (
    job_id BIGINT NOT NULL REFERENCES cr_arena.jobs(id), match_id TEXT NOT NULL,
    blue TEXT, red TEXT, seed INTEGER, deck TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    winner INTEGER, crowns TEXT, tower_hp TEXT, ticks INTEGER, wall_s DOUBLE PRECISION,
    stats_blue TEXT, stats_red TEXT, error TEXT,
    started_at DOUBLE PRECISION, finished_at DOUBLE PRECISION, replay_path TEXT, log_path TEXT,
    PRIMARY KEY (job_id, match_id)
);
CREATE TABLE IF NOT EXISTS cr_arena.decisions (
    job_id BIGINT, match_id TEXT, step INTEGER, team INTEGER, player TEXT,
    time_left DOUBLE PRECISION, elixir DOUBLE PRECISION, my_towers INTEGER, enemy_towers INTEGER,
    n_moves INTEGER, asked INTEGER, move TEXT, result TEXT, ok INTEGER, error TEXT,
    latency_s DOUBLE PRECISION, tokens_in INTEGER, tokens_out INTEGER, cache_read INTEGER, cache_write INTEGER,
    raw TEXT, state TEXT, cost_usd DOUBLE PRECISION,
    FOREIGN KEY (job_id, match_id) REFERENCES cr_arena.matches(job_id, match_id)
);
CREATE INDEX IF NOT EXISTS decisions_match ON cr_arena.decisions(job_id, match_id, step);
CREATE INDEX IF NOT EXISTS decisions_player ON cr_arena.decisions(job_id, player);
CREATE TABLE IF NOT EXISTS cr_arena.model_checks (
    name TEXT, provider TEXT, model TEXT, ok INTEGER, latency_s DOUBLE PRECISION,
    detail TEXT, checked_at DOUBLE PRECISION
);
-- A completed import is recorded in the same transaction as its data.
CREATE TABLE IF NOT EXISTS cr_arena.imports (
    source_sha256 TEXT PRIMARY KEY, source_name TEXT NOT NULL, imported_at DOUBLE PRECISION NOT NULL,
    counts TEXT NOT NULL
);
-- Replays are binary artifacts. Keeping them here makes them available to every local dashboard.
-- They count against the database storage quota; migrate to object storage if they grow large.
CREATE TABLE IF NOT EXISTS cr_arena.replays (
    job_id BIGINT NOT NULL, match_id TEXT NOT NULL, content BYTEA NOT NULL,
    PRIMARY KEY (job_id, match_id),
    FOREIGN KEY (job_id, match_id) REFERENCES cr_arena.matches(job_id, match_id)
);
