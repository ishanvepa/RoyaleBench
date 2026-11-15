# Data snapshot

## TikTok interaction references

`references/tiktok/` holds the two downloaded source MP4s and downloader metadata
for the [clip recreations](../docs/tiktok_recreations.md). They are local,
Git-ignored reference media. Source URLs and SHA-256 hashes are retained in
[`runs/clip-recreations/checks.json`](../runs/clip-recreations/checks.json).
The guide explains re-extraction, simulator inputs, controls, and the difference
between preventing a Balloon attack and preventing its death-bomb damage.

## Frozen Tactics menu inputs

[`royalebench-tactics-menu-source`](royalebench-tactics-menu-source) preserves the historical
Tactics `@2` configurations, templates, references, runtime and generator sources. Coordinate
Tactics uses these checksummed inputs for provenance; current runtime files come from the v3
foundation. See [the Tactics guide](../docs/tactics.md).

## Frozen RoyaleBench v1 build inputs

[`royalebench-v1-source`](royalebench-v1-source) is a byte-for-byte source snapshot of
`benchmarks/royalebench-v1` from commit `e514cc3e71cef4c11ab224fb4191f16438625d1e` (the
published `royalebench/royalebench-v1@1` inputs). RoyaleBench coordinates and v3 use it only
to preserve their derivation; it is never mounted into a player image. Later v1 package revisions
remain in `benchmarks/royalebench-v1` and must not change v3 provenance.

`arena.db.gz`: a gzip'd copy of `runs/arena.db`, the SQLite database every run writes to and the dashboard
reads. Snapshot taken 2026-11-07 (45 benchmark games plus earlier test jobs; ~37k logged decisions).

```bash
gunzip -k data/arena.db.gz && cp data/arena.db runs/arena.db    # restore locally, then:
uv run python -m rb_server        # open http://127.0.0.1:8000/legacy/overview
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

## Deck strength (CrownScribe archetypes)

`deck_strength.csv`: each classic deck in `cr_arena/decks.py` is mapped to the [CrownScribe](https://crownscribe.com/)
archetype it belongs to, and the file tracks that archetype's win rate and battle count so deck strength can be used as
a task lever (see [Task design](../docs/task_design.md)). It is append-only: each capture adds one row per deck, old
rows are never edited, and `uv run python -m cr_arena.deck_strength` ranks each deck's newest row. The first capture is
2026-11-14.

A person copies the numbers from each archetype page (the `url` column). Use one patch window and mode for every deck
in a capture and record them in `filters`. The first capture's table did not state them; they were read from the pages
the numbers match, which show "Since the Oct 19, 2026 patch · Ladder and Ranked". Each row was also checked against its
live page later on 2026-11-14: win rates agree within 0.1 point and battle counts are 1.3% to 2.8% higher, as expected
from a page that keeps accumulating.

| Column | Meaning |
|---|---|
| `captured` | date the numbers were copied (ISO) |
| `deck` | key in `CLASSIC_DECKS` |
| `archetype` | the archetype's name on CrownScribe |
| `win_rate_pct` | the archetype's win rate in percent (one decimal, as shown) |
| `battles` | battles behind that win rate |
| `usage_pct` | the archetype's share of decks, in percent |
| `signature` | the archetype's signature cards as engine names, joined by a vertical bar; CrownScribe counts a deck in an archetype when it contains all of them and no more specific archetype matches |
| `url` | the archetype's page |
| `filters` | patch window and mode |
| `notes` | anything else |

To refresh: open each `url`, append one row per deck with the new `captured` date and the same `filters`, then run the
ranking command and `uv run python -m unittest discover -s tests -p test_deck_strength.py`.

Snapshot 2026-11-14, ranked by the lower bound of the 95% Wilson interval on win rate. Decks in the same tier have
intervals that overlap the tier's best deck, so they cannot be told apart. A tier says a gap is real, not that it is
big: adjacent tiers are 0.8 to 2.2 points apart.

| Rank | Tier | Deck | CrownScribe archetype | Win rate | 95% interval | Battles | Usage | Signature cards in our deck |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | pekka-bridge-spam | Pekka Bridge Spam | 50.8% | 50.5-51.1% | 85,248 | 1.1% | yes |
| 2 | 2 | log-bait | Log Bait | 49.8% | 49.5-50.1% | 130,486 | 1.7% | yes |
| 3 | 2 | giant-beatdown | Giant decks | 49.6% | 49.5-49.7% | 624,221 | 8.3% | yes |
| 4 | 3 | golem-beatdown | Golem Beatdown | 47.4% | 47.1-47.7% | 118,357 | 1.6% | no (missing NightWitch) |
| 5 | 4 | hog-2.6-cycle | 2.6 Hog Cycle | 46.6% | 46.4-46.8% | 183,726 | 2.4% | yes |
| 6 | 5 | xbow-cycle | X-Bow 2.9 | 45.1% | 44.8-45.4% | 82,328 | 1.1% | yes |
| 7 | 5 | lavaloon | LavaLoon | 45.0% | 44.5-45.5% | 38,573 | 0.5% | yes |

Read this table with care:

- **Archetype, not our eight cards.** The numbers cover every deck that contains the archetype's signature cards,
  which is far broader than our one eight-card list per archetype.
- **golem-beatdown does not fit its archetype.** CrownScribe's Golem Beatdown needs Golem and Night Witch, and our list
  has no Night Witch (it is not an engine card), so its row is the closest named archetype, not a match. By signature
  cards our list fits the broader "Golem decks" (46.8% over 160,710 battles when read later on 2026-11-14), which would
  tie it with hog-2.6-cycle instead of ranking it above. The row stays as pasted.
- **giant-beatdown is the broad "Giant decks" family.** CrownScribe has no "Giant Beatdown" archetype. These numbers
  match its "Giant decks" page (the pasted label carried an asterisk); the only signature card is Giant.
- **Sampling error only.** The intervals do not remove who plays each archetype or which opponents it meets. The whole
  set spans 5.8 points (45.0% to 50.8%).
- **Not the engine.** The engine uses ~2018 card balance, so live-game numbers may not match strength inside it.

### Head-to-head within the set

`deck_matchups.csv`: how each classic deck's archetype does against each of the other six, one row per deck and
opponent (42 rows per capture; CrownScribe lists every pair on both decks' pages, from the same battles). Columns:
`captured`, `deck`, `opponent` (a `CLASSIC_DECKS` key), `win_rate_pct` (the deck's win rate against the opponent),
`battles`, `url` (the deck's archetype page, where the table is) and `filters`. It is append-only, like the file
above. The first capture was read from the live pages later on 2026-11-14, so its battle counts are a little higher
than in `deck_strength.csv`. The two directions of a pair agree within 0.3 points and
`cr_arena/deck_strength.py` averages them (a test checks the agreement). Every pair has at least 545 battles.

Strength within the set is a deck's mean win rate against the other six, each opponent counting equally, which is the
position of a task designer choosing opponents from this set. Ranked by the lower bound of its 95% interval, with
tiers as above:

| Rank | Tier | Deck | Mean win rate vs the other six | 95% interval | Overall rank |
|---|---|---|---|---|---|
| 1 | 1 | giant-beatdown | 53.7% | 53.2-54.2% | 3 |
| 2 | 1 | log-bait | 52.2% | 51.3-53.2% | 2 |
| 3 | 2 | pekka-bridge-spam | 52.1% | 51.1-53.1% | 1 |
| 4 | 2 | golem-beatdown | 50.5% | 49.6-51.3% | 4 |
| 5 | 3 | hog-2.6-cycle | 47.5% | 46.6-48.4% | 5 |
| 6 | 3 | xbow-cycle | 47.4% | 46.4-48.5% | 6 |
| 7 | 3 | lavaloon | 46.5% | 45.2-47.9% | 7 |

Head-to-head win % of the row deck against the column deck, strongest first:

| row beats column | giant | log | pekka | golem | hog | xbow | lavaloon |
|---|---|---|---|---|---|---|---|
| giant | - | 47.2 | 51.4 | 58.0 | 56.0 | 62.6 | 46.9 |
| log | 52.8 | - | 47.7 | 49.3 | 48.0 | 49.5 | 66.1 |
| pekka | 48.6 | 52.3 | - | 59.0 | 46.8 | 49.0 | 57.0 |
| golem | 42.0 | 50.6 | 41.0 | - | 53.2 | 67.3 | 48.5 |
| hog | 44.0 | 52.0 | 53.2 | 46.8 | - | 45.6 | 43.5 |
| xbow | 37.4 | 50.5 | 51.0 | 32.7 | 54.4 | - | 58.7 |
| lavaloon | 53.1 | 33.9 | 43.0 | 51.4 | 56.5 | 41.3 | - |

The order agrees with the overall ranking for the bottom four decks; the top three trade places because giant-beatdown
beats the weaker decks by the most. Rank is only a rough guide, because the decks beat each other in cycles:
lavaloon, the weakest, beats hog-2.6-cycle 56.5% of the time. For a task, read the matrix cell for the exact pair.

## Visual reference

The local graphics reference is `data/references/arena-1-PD6QCK7GzA8.mp4`,
downloaded from [JustAction, “terrorizing arena 1 players”](https://www.youtube.com/watch?v=PD6QCK7GzA8)
(published 2025-11-22). It is a 14:20, 1920×1080, 60 fps H.264/AAC video.
SHA-256: `b8eb9da25d3dcbcc94d9dfed278d70329d1c1ee0f0759d6ae7c36ac9541a0a55`.
The 145 MB video is git-ignored; the source link and checksum remain in the repository.

The tower artwork pass sampled it with ffmpeg at 00:30.000, 01:30.000,
05:10.000, 05:12.000 and 05:15.000. Timestamped crops, code-inspection provenance,
before/after comparisons and remaining differences are recorded in
[Battle graphics](../docs/rendering.md#tower-reference-and-scope). The video was
inspected visually; REA inspected the renderer JavaScript, not the video.

To restore the same local reference:

```bash
uvx --from yt-dlp yt-dlp --js-runtimes node --no-playlist -f '299+140-12' \
  --merge-output-format mp4 -o 'data/references/arena-1-PD6QCK7GzA8.%(ext)s' \
  'https://www.youtube.com/watch?v=PD6QCK7GzA8'
```
