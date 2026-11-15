# Public play implementation plan

Scope: one always-on server, at most seven active matches, the existing live
renderer and seven preset decks, and the existing Planner bot with its deck fixed to Hog 2.6 Cycle. Browsing the
deck picker consumes no match slot. An eighth start receives “Server at capacity —
please try again shortly.” Slots return when matches end, disconnect, or quit.

## Original public implementation (historical)

- [x] Add the heuristic bot to the shared catalog and a public launch mode that
  offers only that bot. Preserve local access to the other bots.
- [x] Enforce five active games in one server process. Clean up workers on every
  exit path, including natural completion and errors. Bound paused/abandoned
  sessions and slow socket writes.
- [x] Keep simulation at 20 Hz and existing browser interpolation. Move replay
  saving and worker shutdown off the event loop; use unique match identifiers.
  Show immediate placement feedback and useful loading/capacity/disconnect states.
- [x] Add a single-container Modal deployment with persistent
  storage, a health check, and deployment instructions. Keep the existing
  temporary tunnel launcher usable.
- [x] Test capacity, slot reuse, malformed messages, worker failure, slow clients,
  and simultaneous saves. Exercise five real games over WebSockets, including
  placement requests, and report measured timing. Check the phone UI.
- [x] Update the documentation index, bot guide, and phone-play guide with launch
  commands, operational limits, and validation results.

## Acceptance and operational limits

Seven matches must advance concurrently at approximately 20 ticks/second; an eighth
cannot start. Each public Planner gets the same worker budget as a lone local game. Warm local input/placement responses should remain under 150 ms at
p95. Report actual measurements and distinguish them from internet latency and
the intentional 21-tick (1.05-second) deployment delay shared by both players.

Use exactly one application instance and one server process: capacity is tracked
in memory. Restarts end active games; clients can reload to start again. Deploy
between games. Hosting requires a locally authenticated Modal account; local
tests do not establish latency or capacity on the eventual hosted machine.

## Historical heuristic validation

All five real-time matches completed and saved at 20 ticks/second. Worst per-match
p95 placement-mask latency was 22.62 ms; worst p95 input-to-pending latency was
56.67 ms. A sixth start was refused and a freed slot was reused. See the
[validation record](public_play_validation.json) for per-match data and limits.

The game is deployed as one native Modal Server. The original shared URL
redirects to it. The hosted 15-second five-match run verified capacity refusal,
slot reuse, and approximately 20 ticks/second, but did not meet the 150 ms WAN
response target: worst p95 input-to-pending latency was 334.94 ms. Network ping
RTT was 100–181 ms and server-local placement computation was 6–16 ms. See the
[public guide](public_play.md) and validation record for the measured limits.
Hosted full-game completion remains unverified: that run was stopped so the
user could play. The local five-full-game validation above remains valid.

Regression checks passed: 216 Python tests (9 skipped) and 32 renderer tests.

## Planner release (historical five-match capacity)

- [x] Confirm the requested bot: the user selected the existing `planner-bot`.
- [x] Pin the public opponent and Hog 2.6 Cycle deck on the server; only the human
  deck remains selectable in the public UI.
- [x] Push all four placement masks with the first hand and refresh masks when
  card identities, pending state, or deployment geometry changes. Selecting a
  card sends no mask request.
- [x] Allocate two Planner search workers per game, independent of connection
  order, and reserve 16 physical CPU cores / 8 GB for the single Modal game server.
- [x] Check pending plays, hand cycling, building placement, and tower destruction
  against fresh engine masks; verify five real Planner matches and the phone UI.

The preceding heuristic measurements are historical. Five-match Planner results are recorded
under `planner_release` in the validation JSON.

Planner release validation: 219 Python tests (9 skipped), 32 renderer tests, and
five concurrent local and hosted Planner matches with preloaded masks ready for
every hand. Local games held 20 ticks/second; hosted games held 19.99–20. The
hosted worst p95 input acknowledgment was 220.36 ms, above the 150 ms WAN target.
Phone-size browser instrumentation recorded four cached masks and zero mask
requests when selecting a card and sending a play.

## Vertical scaling to ten matches

- [x] Double the single Modal Server reservation to 32 physical CPU cores and
  16 GiB RAM, and raise admission to ten matches. Preserve two Planner search
  workers per match and the existing search settings.
- [x] Extend admission, slot reuse, disconnect cleanup, and simultaneous replay
  persistence checks to ten matches. Verify server-side bot response-time telemetry.
- [x] Make the WebSocket load checker use the server's advertised capacity,
  cycle decks when there are more matches than deck presets, and support
  `--sessions` for a smaller comparison load.
- [x] Verify eleventh-player refusal and reuse of a quit slot while nine other
  matches are still active. Separate gameplay checks from the 150 ms input target
  in JSON results; keep the overall check unsuccessful if either fails.
- [x] Deploy and compare 30-second five-match and ten-match WAN runs. The ten-match
  run sustained 19.94–20.01 ticks/second; the input target remained unmet.
- [x] Run ten games to completion and record saving and sustained responsiveness
  under `vertical_scale` in the validation JSON.

All ten hosted matches completed and saved at 19.79–19.97 ticks/second. The worst
per-match bot response p95 was 250 ms across 4,750 decisions. The worst input p95
was 314.93 ms and the maximum snapshot gap was 964.34 ms: gameplay checks passed,
but the overall latency acceptance check remains failed. The first full-game
attempt was interrupted by the separate lobby deployment; the successful rerun
used a combined build preserving both changes. The load result does not establish
equivalent responsiveness to five sessions.

Regression validation after lobby integration: 42 Python checks and 32 renderer checks passed. The
five-match baseline used the new 32-core instance, not the previous 16-core one.
Server-side bot response timings include IPC, scheduling, and lazy search-pool
startup; they exclude the initial bot-worker ready handshake.

## Planner parity with local play

Shared-play Planner felt weaker than local Planner. Root cause: two search workers
per public match versus eight for a lone local game. Planner has no time budget, so
fewer workers mean slower decisions on staler positions (see
[public play](public_play.md#planner-strength-parity-seven-matches-eight-workers)).

- [x] Give every public match `PLANNER_WORKERS` (eight), shared with the local
  single-game budget, and test that the two stay equal.
- [x] Lower admission to seven matches and reserve 64 physical CPU cores
  (about nine per match plus the game loop); keep 16 GiB (about 1.4 GB per match).
- [x] Start every Planner search worker before the bot reports ready, and hold the
  match clock at tick 0 until then (20-second limit), so the first decision is no
  longer a cold start. Fix Planner treating slot 0 as pending whenever any card was
  on its way (pending rows name the card, not the slot).
- [ ] Deploy and run `check_live --full-games` against the hosted server; compare
  bot decision p95/max with a lone local game.
- [ ] Record the results under a new section in the validation JSON.
