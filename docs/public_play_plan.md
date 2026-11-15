# Five-player public play implementation plan

Scope: one always-on server, at most five active matches, the existing live
renderer and seven preset decks, and the existing Planner bot with its deck fixed to Hog 2.6 Cycle. Browsing the
deck picker consumes no match slot. A sixth start receives “Server at capacity —
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

Five matches must advance concurrently at approximately 20 ticks/second; a sixth
cannot start. Warm local input/placement responses should remain under 150 ms at
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

## Planner release

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

The preceding heuristic measurements are historical. Current results are recorded
under `planner_release` in the validation JSON.

Planner release validation: 219 Python tests (9 skipped), 32 renderer tests, and
five concurrent local and hosted Planner matches with preloaded masks ready for
every hand. Local games held 20 ticks/second; hosted games held 19.99–20. The
hosted worst p95 input acknowledgment was 220.36 ms, above the 150 ms WAN target.
Phone-size browser instrumentation recorded four cached masks and zero mask
requests when selecting a card and sending a play.
