# Public play: five concurrent matches

One warm server supports at most **five active matches**. Visitors choose their
own deck from the seven presets, then face **planner-bot playing Hog 2.6 Cycle**.
The opponent and its deck are fixed on the server. The public UI shows no bot or
opponent-deck selectors. Local mode retains the full bot catalog and both deck
selectors.

The deck picker uses no match slot. A sixth start receives **“Server at capacity —
please try again shortly.”** Finish, quit, disconnect, or worker failure releases
a slot. A game expires after 15 minutes including pauses. Reconnect starts a new
game rather than resuming the previous one.

All four legal-placement masks arrive with the initial hand. Hand changes and
changes to deployment geometry push replacement masks with the same game update.
Selecting a card reads its cached mask immediately, without sending a placement
request. The engine still validates every actual deployment. Masks invalidate on
card changes, pending plays, relevant buildings/spells, and tower destruction.

Play online: [public game](https://b-charest04--royalebench-play-playserver.us-west.modal.direct/).
The [original shared link](https://b-charest04--royalebench-play-serve.us-west.modal.run/)
also works through a redirect.

See the [implementation plan](public_play_plan.md) and
[validation record](public_play_validation.json). Historical heuristic measurements
are retained in the record; the `planner_release` section describes this version.
A local 30-second five-Planner check sustained 20 ticks/second in all five games,
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
It runs Uvicorn in one warm native Modal Server with 16 reserved physical CPU cores and 8 GB of
memory, plus a persistent Modal Volume. Each match gets two Planner search workers;
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

The deploy command prints the permanent `https://….modal.direct` game URL. The
previously shared `https://b-charest04--royalebench-play-serve.us-west.modal.run/`
link redirects browsers to it, so that link remains usable. Its `/health` endpoint reports `active_games` and `max_games`; a full server
remains healthy and serves its capacity message.

`min_containers=1` keeps the game server warm and incurs idle hosting charges
while deployed. `max_containers=1` keeps game capacity in one process. Request
autoscaling is disabled; setup visitors and the sixth player reach the application
and see its capacity response. **The game's match cap remains five.** A separate
redirect Function preserves the original link and scales to zero when unused.
Do not increase the game container count or deploy another game process against
the same volume.

The volume `royalebench-play-data` holds `/data/arena.db` and
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

## Check five-match responsiveness

Use a disposable server with all five slots free. The check starts five scripted
players using different decks against Planner's fixed Hog Cycle deck, verifies a
sixth start is refused, deploys cards using the pushed masks, and verifies a freed
slot can be reused. It also requires each bot to make a successful play.

```bash
uv run --frozen python -m cr_arena.check_live --seconds 30
uv run --frozen python -m cr_arena.check_live --full-games --output /tmp/live-check.json
```

Use `--url https://YOUR_DEPLOYED_URL.modal.direct` to check the hosted server, preferably
from near its region. `--full-games` allows ten minutes and requires all five
matches to finish and save. The check prints per-match tick rates, snapshot gaps,
preloaded mask availability/update counts, successful bot plays, and time from
input to the server reporting a pending deployment. It sends no placement-mask
requests. It fails if a hand arrives without matching masks, a bot makes no play,
a match advances below 19 ticks/second, or p95 input latency reaches 150 ms. It excludes the first two seconds of stream startup from
tick-rate measurements.

The engine runs at 20 ticks/second and the page interpolates at the display's
refresh rate. Both sides retain the intentional **21-tick / 1.05-second card
deployment delay**; a local drop marker appears immediately. That game rule is
separate from network latency. Replay compression/database writes and worker
shutdown run outside the event loop, and slow socket writes time out after one
second instead of retaining a match indefinitely.

Regression checks:

```bash
uv run --frozen python -m unittest tests.test_public_play tests.test_bot_registry tests.test_human_search_v2 tests.test_placement tests.test_rendering -v
node --test tests/battle_renderer.test.cjs
```
