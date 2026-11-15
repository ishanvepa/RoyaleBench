# Public play: seven concurrent matches

One warm server supports at most **seven active matches**. Visitors choose their
own deck from the seven presets, then face **planner-bot playing Hog 2.6 Cycle**.
The opponent and its deck are fixed on the server. The public UI shows no bot or
opponent-deck selectors. Local mode retains the full bot catalog and both deck
selectors.

The shared link opens an arena lobby with a miniature battlefield and a gold
**Battle** button. Enter your arena name, then press Battle to open deck selection;
it does not start a match. Choose
a preset to see its strategy and all eight card portraits, then press **Enter
battle** to begin. **Back to arena** returns to the lobby and keeps the selected
deck. The **How to play** button explains deployment, elixir, and winning. On
phones, the final Enter battle button stays visible while browsing the decks.

The deck picker uses no match slot. An eighth start receives **“Server at capacity —
please try again shortly.”** Finish, quit, disconnect, or worker failure releases
a slot. A game expires after 15 minutes including pauses. Reconnect starts a new
game rather than resuming the previous one.

Completed battles open a result dialog over the dimmed arena, using the lobby's
navy panels, crown emblem, and gold **Battle again** button. Victory, defeat, and
draw results show both players, decks, and final crown scores, followed by your
record and replay status. **Battle again** keeps the same matchup; **Change deck**
returns to deck selection, and **View leaderboard** opens the standings. Keyboard
focus stays in the dialog; Escape returns to deck selection. The dialog scrolls
on short screens so every action remains reachable.

## Persistent leaderboard

The lobby header and match result screen link to an all-time leaderboard showing
player names, wins, and losses. Most wins rank first; fewer losses break ties,
and identical records share a rank. The board shows the top 50 plus your own
record, even when you are outside the top 50. It refreshes when setup opens,
after a completed game, or when you press **Refresh**.

Each server appends completed wins/losses to one CSV file. Draws, quits,
disconnects, expired games, and worker failures do not change standings. A match
ID prevents duplicate results if saving is retried. Results come from the game
engine; the HTTP endpoint accepts no score submissions. The CSV write uses the
existing single-server setup and a thread lock for simultaneous finishes.

The start screen requires an arena name of 1–24 visible characters. It remembers
the name in browser storage, shows it in deck selection and the live HUD, and
sends it as `player_name` in the WebSocket start message. The server normalizes
whitespace and Unicode, rejects invalid names before allocating a game, and
stores the validated name with completed results. **Edit name** returns to the
lobby; changing a name keeps the same record and updates its displayed name
after the next completed win or loss. Ranked starts require a name on the server,
including for older clients. Scripted checks send `ranked: false`; these may omit
the name and retain a generated `Player ABC123` label during play, but their
completed results never enter the leaderboard. Replays still save normally.

A persistent browser cookie identifies each player independently of their name.
The cookie lasts one year; clearing cookies, changing browsers, or using a
different tunnel hostname creates a new identity. This is a casual leaderboard
with no accounts; matching names do not merge records. `Session.player_id`
remains the stable aggregation key. The CSV's `player_name` column supplies the
displayed name, using the latest result.

The play page requests a fixed 1× viewport and suppresses pinch, double-tap,
trackpad, and keyboard page-zoom gestures while allowing normal scrolling.
Name entry uses a 16px font to avoid mobile input-focus zoom. Browser menus,
accessibility settings, and OS magnification can override page zoom restrictions.

`GET /leaderboard` returns `entries`, `you`, and `total`. Each entry includes
`rank`, `name`, `wins`, `losses`, and `is_you`. The default local file is
`runs/round_robin/human-play/leaderboard.csv`; override it with
`CR_ARENA_LEADERBOARD`. Local and public modes on the same file share standings,
so use separate file paths if running practice and public servers together.
On Modal, the file is `/data/leaderboard.csv` on the existing persistent volume.
It survives normal restarts and redeploys under the volume's durability behavior
described below. Old matches have no player identity and are not backfilled.

All four legal-placement masks arrive with the initial hand. Hand changes and
changes to deployment geometry push replacement masks with the same game update.
Selecting a card reads its cached mask immediately, without sending a placement
request. The engine still validates every actual deployment. Masks invalidate on
card changes, pending plays, relevant buildings/spells, and tower destruction.

Play online: [RoyaleBench](https://b-charest04--royalebench.us-west.modal.run/).
This short share link redirects to the
[game server](https://b-charest04--royalebench-play-playserver.us-west.modal.direct/).
The [original shared link](https://b-charest04--royalebench-play-serve.us-west.modal.run/)
also works through a redirect.

See the [implementation plan](public_play_plan.md) and
[validation record](public_play_validation.json). The `planner_release` section
retains the historical five-match Planner measurements; `vertical_scale` records
the earlier ten-match deployment and its load tests.

### Planner strength parity (seven matches, eight workers)

Planner searches every candidate with no time budget, so its worker count sets how
long each decision takes, not how deep it searches. The ten-match deployment gave each
match two workers while a lone local game gets eight. On busy defensive positions,
two workers took a median 167 ms (p90 819 ms, max 1.3 s) per decision against 64 ms
(p90 384 ms, max 0.5 s) with eight, and hosted runs logged worst decisions of 3.3–4.1
s. Planner's answers are not discarded when stale, so slow decisions arrived as late
defense and spells aimed where units used to be: shared play was measurably weaker.

Each public match now gets `PLANNER_WORKERS` (eight), the same budget as a lone
local game, and a test keeps the two equal. Eight workers plus the bot process need
about nine cores per match, so the cap fell from ten to seven and the Modal
reservation doubled to 64 physical cores (seven matches × nine cores, plus the game
loop). Each match uses about 1.4 GB, so 16 GiB remains sufficient. The seven-match
deployment has not yet been load-checked; the measurements below are from the
two-worker ten-match deployment.

On November 14, 2026, the 32-core / 16-GiB deployment completed and saved all ten
scripted matches, with the eleventh start refused and a quit slot successfully
reused while the other nine remained active. Per-match tick rates were
19.79–19.97/second, and server-side bot response p95 was at most 250 ms across
4,750 decisions. The worst per-match input-to-pending p95 was **314.93 ms**,
above the unchanged 150 ms WAN target; the longest snapshot-delivery gap was
**964.34 ms**. Gameplay checks passed, but the overall load check remains failed
on input latency. This establishes ten-match functionality, not equivalent
responsiveness or an absence of stalls. Matches lasted 38.60–182.38 seconds;
concurrency decreased as matches completed.

For comparison, a 30-second five-match run on the same larger instance measured
272.77 ms worst input p95; the ten-match short run measured 403.94 ms. These short
runs have few accepted plays and are sensitive to startup outliers. The combined
deployment preserves the new arena lobby, player names, and leaderboard.

A historical local 30-second five-Planner check sustained 20 ticks/second in all five games,
with worst per-match p95 input-to-pending latency of 63.16 ms. Hosted internet
latency is measured separately and is not guaranteed by those local results.
The hosted 30-second five-Planner run verified ready masks for every hand,
successful bot plays, capacity refusal, and slot reuse at 19.99–20 ticks/second.
Its worst per-match p95 input acknowledgment was 220.36 ms, so the 150 ms WAN
target remains unmet. Card selection itself sends no placement request.

## Local play and a temporary link

```bash
uv sync --frozen
uv run --frozen python -m cr_arena.live --public
```

Open `http://127.0.0.1:8600`. To share a temporary public link using the existing
Cloudflare launcher instead:

```bash
uv run --frozen python -m cr_arena.share --public
```

See [phone play](phone_play.md) for the `cloudflared` prerequisite. Temporary
links depend on the local computer staying awake and running the command.

## Permanent hosting on Modal

[`modal_play.py`](../modal_play.py) deploys the existing Starlette game directly.
It runs Uvicorn in one warm native Modal Server with 64 reserved physical CPU cores and 16 GiB of
memory, plus a persistent Modal Volume. Each match gets eight Planner search workers, matching a lone local game;
the worker budget does not depend on which player connected first. Native Servers proxy WebSockets directly
to the game process to reduce transport latency. The application expires matches
after 15 minutes, including pauses. Compute and request routing are both set to
`us-west` for the initial California audience. Region selection carries Modal's
documented pricing multiplier.

From the repository root:

```bash
uv sync --frozen --extra hosting
uv run --frozen --extra hosting modal setup
uv run --frozen --extra hosting modal deploy modal_play.py
```

`modal setup` opens the browser for account/workspace authentication; skip it if
this machine is already authenticated. Select the workspace with your hackathon
credits. The Valkyrie provider secret is hosted by Valkyrie and does not sign the
local Modal CLI in automatically. No model API keys or Valkyrie credentials are
needed by the game.

Share `https://b-charest04--royalebench.us-west.modal.run/`, configured with
`@modal.asgi_app(label="royalebench")` on the `share` Function. It redirects to
the permanent `https://….modal.direct` game URL printed by the deploy command. The
previously shared `https://b-charest04--royalebench-play-serve.us-west.modal.run/`
link redirects browsers to it, so that link remains usable. Its `/health` endpoint reports `active_games` and `max_games`; a full server
remains healthy and serves its capacity message.

`min_containers=1` keeps the game server warm and incurs idle hosting charges
while deployed. `max_containers=1` keeps game capacity in one process. Request
autoscaling is disabled; setup visitors and the eighth player reach the application
and see its capacity response. **The game's match cap is seven.** Two
redirect Functions serve the short share link and the original link;
both scale to zero when unused.
Do not increase the game container count or deploy another game process against
the same volume.

The volume `royalebench-play-data` holds `/data/arena.db`, `/data/leaderboard.csv`, and
`/data/human-play/replays/`. Modal commits changes in the background, and the app
also flushes the volume on clean shutdown. The latest uncommitted writes can be
lost on abrupt termination. Active matches live in memory and end on a container
restart. Redeploy only when `/health` reports zero active games.

To stop the warm server and its idle compute charges:

```bash
uv run --frozen --extra hosting modal app stop royalebench-play
```

The volume is retained. Run the deploy command again to bring the app back.
The image installs the committed lockfile's `play` dependency group, containing
the CPU game runtime without the benchmark's model SDKs, training packages, or
GPU dependencies. It includes game code, bot configs, and migrations. It does not
copy the repository's `.env`, run data, or frontend dependencies. Docker is not
required locally.

Keep `.env()` and other image build steps before `.add_local_dir()` calls in
`modal_play.py`; Modal requires runtime file mounts to be last in the image chain.

Reference: [Modal Servers](https://modal.com/docs/guide/servers),
[WebSocket transport](https://modal.com/blog/serverless-servers),
[container limits](https://modal.com/docs/guide/scale),
[regions](https://modal.com/docs/guide/region-selection),
[volumes](https://modal.com/docs/guide/volumes).

## Check seven-match responsiveness

Use a disposable server with all seven slots free. The check starts seven unranked scripted
players, one per preset, against Planner's fixed Hog Cycle deck, verifies an
eighth start is refused, reuses a freed slot while the other six are occupied,
then deploys cards using the pushed masks. It also requires each bot to make a successful play.

```bash
uv run --frozen python -m cr_arena.check_live --seconds 30
uv run --frozen python -m cr_arena.check_live --sessions 5 --seconds 30
uv run --frozen python -m cr_arena.check_live --full-games --output /tmp/live-check.json
```

Use `--url https://YOUR_DEPLOYED_URL.modal.direct` to check the hosted server, preferably
from near its region. `--full-games` allows ten minutes and requires every
match to finish and save. The check prints per-match tick rates, snapshot gaps,
preloaded mask availability/update counts, successful bot plays, and time from
input to the server reporting a pending deployment. It also reports bot response
time and source-snapshot age, measured on the server from snapshot submission to
answer consumption (including IPC and scheduling; excluding the bot worker's
start-up, which happens before the clock starts — see below).
It sends no placement-mask
requests. It fails if a hand arrives without matching masks, a bot makes no play,
a match advances below 19 ticks/second, or p95 input latency reaches 150 ms. It excludes the first two seconds of stream startup from
tick-rate measurements. `--sessions` defaults to the capacity advertised by the server;
smaller runs skip the capacity-refusal check. The JSON separates `gameplay_passed`
from `latency_target_met`, and `passed` requires both. Bot timings are diagnostic;
they have no absolute pass threshold and must be compared across equivalent runs.

Each match's clock holds at tick 0, with the HUD showing **Starting**, until the bot
worker reports ready. A Planner worker first starts and initialises all eight search
processes, which took about 1.3 s locally; previously this happened lazily on the first
decision, and on November 14, 2026 seven hosted matches starting together each lost
their first 6–7 s of decisions to it. The hold lasts at most 20 seconds
(`BOT_READY_TIMEOUT_SECONDS`), after which the clock starts anyway. A quit during
warm-up frees the slot immediately; the worker is then given up to 15 seconds to close
its pool cleanly before it is killed.

The engine runs at 20 ticks/second and the page interpolates at the display's
refresh rate. Both sides retain the intentional **21-tick / 1.05-second card
deployment delay**; a local drop marker appears immediately. That game rule is
separate from network latency. Replay compression/database writes and worker
shutdown run outside the event loop, and slow socket writes time out after one
second instead of retaining a match indefinitely.

Regression checks:

```bash
uv run --frozen python -m unittest tests.test_live_leaderboard tests.test_public_play tests.test_bot_registry tests.test_human_search_v2 tests.test_placement tests.test_rendering tests.test_planner -v
node --test tests/battle_renderer.test.cjs
```
