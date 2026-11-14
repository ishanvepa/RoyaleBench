CREATE TABLE IF NOT EXISTS cr_arena.custom_decks (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    cards TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);
