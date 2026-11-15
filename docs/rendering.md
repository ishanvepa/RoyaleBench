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

## Live HUD and placement cues

The live HUD follows the layout of the Arena 1 reference video while keeping the
original artwork. A timer box shows "Time left", "Overtime", or "Paused", and a
badge appears when elixir runs at x2 or x3. Each side has a crown badge. The hand
tray shows a "Next:" preview card, four portrait cards with the elixir cost in a drop
at the bottom, and a ten-segment elixir bar with the whole-elixir count beneath them.
Hand art is defined only for the 35 distinct cards in the seven `CLASSIC_DECKS`.
Other cards fall back to the shared unit icon. The cards, next card, timer, crowns,
and elixir meter have accessible labels.

`placement.draw` still shades each blocked half-cell. It also outlines the boundary
between blocked and allowed cells, then previews the selected card at the hovered
half-cell centre, which is the point sent on a play:

- Troops show a ring and the snapped half-cell.
- Buildings show their engine `footprint_tiles` square, sent as the fourth field of
  each `init` card. Cannon, Inferno Tower, Tombstone, and X-Bow use 3 tiles; Tesla
  uses 2.
- Spells show their area. The engine does not report spell areas, so these radii are
  display-only approximations: Fireball and Zap 2.5, Arrows 4, Rocket 2, Lightning
  and Poison 3.5, and Goblin Barrel 1.5. The Log shows a 3.9-tile-wide lane that
  rolls forward. Legality always comes from the mask.

The preview's name label turns red and adds "not here" over a blocked cell. Phone
screenshots at 390×844, taken before and after this change, are in
[`images/hud/`](images/hud/).

REA 6.9.0 static analysis (`rea-agents analyze-javascript-application`) of
`battle_renderer.js` and the live page's inline script found one `WebSocket`
request, one `JSON.parse` boundary for incoming messages, and one timer, used by
the toast. On macOS with the 27.0 Command Line Tools SDK, REA's Swift helper fails
to compile. Run REA with `SDKROOT` set to the 26.5 SDK instead.
