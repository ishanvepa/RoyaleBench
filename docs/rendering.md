# Battle graphics

Live play and saved HTML replays use `cr_arena/battle_renderer.js` for the arena,
units, names, health bars, projectiles, spells, and animation effects. Change those
graphics there so both views stay consistent. The renderer takes positions and
radii in tiles, with Blue at the bottom; its file header documents the row layout.
Both views supply the arena grid from the simulation or trace, rather than
guessing bridge positions.

The arena now uses layered grass, water, stone banks, and wooden bridge planks.
Bridges and rails follow the simulator's actual water grid. Towers and troops
are original canvas miniatures with team-colored roofs or bases, so replay files
remain self-contained and work offline. The troop silhouettes cover the common
RoyaleGym cards; an unknown card receives a generic armored miniature and its
name label. These are illustrative graphics, not imported Clash Royale assets.
REA 6.9.0 parsed `battle_renderer.js` as a standalone JavaScript source and
found no module imports in that file; it did not evaluate the artwork. The
graphics were then checked in a browser against a recorded replay. REA is an
analysis tool and is not needed at runtime.

![Arena preview from a recorded battle](images/arena-preview.png)

The [Arena 1 gameplay video](https://www.youtube.com/watch?v=PD6QCK7GzA8)
is saved locally at `data/references/arena-1-PD6QCK7GzA8.mp4` for a future
reference-matching pass; see [data documentation](../data/README.md#visual-reference).

## Classic-deck spells

Arrows, Fireball, Goblin Barrel, Lightning, The Log, Poison, Rocket, and Zap have
their own travel, landing, and impact art (`SPELL_ART` in the renderer). Every other
spell and effect object keeps the generic drawing, and so do units and troop
projectiles (`pr`). Goblins that leave a Goblin Barrel are ground troops and are not
part of this art. The art changes only the picture. It uses the same row positions,
arc, interpolation, fx clock (450 ms), marker sizes, and tooltip hit targets. The
drawing contract carries no spell hit radius, so the landing ring (2.2 tiles) and
centre ring (1 tile) are still markers, not damage areas.

![Before and after at matched replay ticks](images/classic-spells-before-after.png)

What the simulator reports (RoyaleSim 0.1.48, a scripted match at seed 7):

| Spell | `sp` motion and lifetime | Drawn |
|---|---|---|
| Arrows | FLIGHT, three volleys sharing one key | every volley in flight; arrows stuck in the ground as each volley lands |
| Fireball | FLIGHT, 38 ticks | flame head with a smoke trail; flash, fire, smoke, and embers |
| Goblin Barrel | FLIGHT, 57 ticks | spinning hooped barrel; dust puff and flying staves |
| Rocket | FLIGHT, 66 ticks | finned rocket with exhaust and pale smoke; larger blast with a shock ring |
| The Log | AIRBORNE 8 ticks, then ROLLING 51 | log in the air, a dust landing, then a rolling log with turning bark and dust |
| Poison | PULSING, 160 ticks | golden pool with dark specks and rising bubbles |
| Lightning | STRIKES, 27 ticks | bolts from above on a 460 ms beat (decorative; strike targets are not reported) |
| Zap | not reported; it resolves in its cast tick | live play draws it from the cast event; an AREA row would draw a blue flash |

Before this change, all three Arrows volleys used one `spKey`, so only the last
volley was drawn. Now every row with that key is drawn, and each extra volley is
interpolated from the nearest row in the earlier frame. The key's main row, its
arrival burst, and its hit target are unchanged. Replays show no Zap art, because
traces contain no Zap spell row.

REA 6.9.0 traced `sp`, `pr`, and `drawFx` in this file (`analyze-javascript-application`,
then `trace-javascript-semantics` and `trace-application-feature`). On macOS SDK 27,
the analyzer's helper compiles only with
`SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk`. The trace found
`sp` reads in `observe`, in the landing-marker, ground, and flight loops, and in the
`a.spBy` lookup used for interpolation. `pr` is read only in the troop-projectile
block. `drawFx` has one caller, `draw`, and `fx` is written only by `reset` and its
lifetime filter.

References: the [Arena 1 video](https://www.youtube.com/watch?v=PD6QCK7GzA8)
(local copy) shows Arrows at 2:04–2:06, Goblin Barrel at 2:12–2:16, and Fireball at
3:38–3:42. The other five spells do not appear in it. For those spells, see
[How To (Properly) Use Every Spell](https://www.youtube.com/watch?v=Y_vE99tPRXk):
Zap at 3:14, The Log at 6:41, Rocket at 11:10, Lightning at 12:33, and Poison at 13:37.
To check that other graphics did not change, render the same frames with the old and
new renderers and compare canvas operations. Non-classic spells, units, towers,
projectiles, and death or drop effects produce identical operations.

`live.html` handles the WebSocket stream, HUD, and placement controls. `replay.html`
adapts RoyaleGym's named trace columns into the same drawing contract and handles
playback, scrubbing, flipping, and tooltips. Its playback controls were adapted
from RoyaleGym under the MIT license in `third_party/RoyaleGym-LICENSE.txt`.
`replay.py` continues using RoyaleGym to validate and prepare traces, but no longer
patches upstream JavaScript strings.

`rendering.embed_renderer` embeds the shared JavaScript in both pages. Generated
replays remain single HTML files that work offline. Existing generated HTML files
need to be re-rendered to pick up graphics changes:

```sh
uv run python -m cr_arena.replay path/to/battle.msgpack -o battle.html
uv run python -m unittest discover -s tests
node --test tests/battle_renderer.test.cjs
```

Live input previews and replay deploy annotations are view-specific overlays.
Live placement masks use RoyaleGym's `PlacementOracle` at half-tile resolution,
independent of elixir and the opening lockout. Each mask carries its dimensions,
resolution, and card ID. The same half-cell defines its shading and the centre
sent on a click, and stale masks for a different card are ignored. Spatially
eligible cells can still require more elixir or waiting before a play is accepted.
Living friendly princess towers exclude their engine-reported placement footprints
for troop and building drops; spells can still target them. Their shared graphics
use those same footprints, and destroyed towers release the occupied area. King
towers retain their arena-defined exclusion block.
Replay interpolation is a straight-line estimate between recorded frames; a
replay cannot recover live events or pending placements absent from its trace.
