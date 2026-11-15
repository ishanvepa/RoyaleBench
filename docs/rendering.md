# Battle graphics

Live play and saved HTML replays use `cr_arena/battle_renderer.js` for the arena,
units, names, health bars, projectiles, spells, and animation effects. Change those
graphics there so both views stay consistent. The renderer takes positions and
radii in tiles, with Blue at the bottom; its file header documents the row layout.
Both views supply the arena grid from the simulation or trace, rather than
guessing bridge positions.

The terrain follows Arena 1: a two-tone grass checker, worn lanes from each
bridge towards the princess towers, a turquoise river with a shaded upper bank
and lily pads, plank bridges that reach half a tile onto each bank, and a wooden
palisade border with bushes at the river ends. `drawGround` derives the water
cells and bridge decks from the simulator grid, so the decks, their rails, and
the lanes follow the actual walkable bridge cells in either board orientation.
This pass covers Arena 1 only and is shared by the seven classic decks in
`cr_arena/decks.py`; there are no alternate arena skins. Towers and troops are
original canvas miniatures with team-colored roofs or bases, so replay files
remain self-contained and work offline. These are illustrative graphics, not
imported Clash Royale assets.

![Arena preview from a recorded battle](images/arena-preview.png)

### Arena 1 terrain reference check

Terrain colours were sampled from the
[Arena 1 gameplay video](https://www.youtube.com/watch?v=PD6QCK7GzA8), saved
locally at `data/references/arena-1-PD6QCK7GzA8.mp4` (see
[data documentation](../data/README.md#visual-reference)). REA does not read
MP4 frames, so frames were taken with ffmpeg at 0:20, 0:45, 1:10, 1:40, 2:10
and 2:40, for example:

```sh
ffmpeg -ss 00:01:40 -i data/references/arena-1-PD6QCK7GzA8.mp4 -frames:v 1 -vf "crop=960:1080:960:0" ref.png
```

The 1:40 frame shows the arena without a placement overlay and was averaged
over 7×7-pixel patches for grass, lanes, water, the bank shadow, lily pads,
bridge planks, and the border. Palette values in `battle_renderer.js` are those
samples, toned down slightly because the video is saturated by compression.

The comparison below shows, from left to right, the previous terrain, the new
terrain, the new terrain with Red at the bottom, and the 1:40 reference frame.
The first three are the same replay frame (tick 400, 0:20.0) of
`runs/samples/heuristic-bot__vs__claude-fable-5.1__s2.msgpack`. The geometry is
the simulator's, not the video's: the simulated river is wider relative to the
field than the reference river is.

![Before, after, flipped, and reference terrain](images/arena-1-terrain-compare.png)

REA 6.9.0 (`npx rea-agents analyze-javascript-application`) was run on a copy of
the previous `battle_renderer.js`. It inventoried the file and recorded its
SHA-256 (`3dfdb5f2…5dbe10`, matching the file before this change), but source
parsing failed at startup on macOS: its process-ownership helper did not
compile against the installed Command Line Tools SDK (`MacOSX27.0.sdk`). It
reported every semantic graph family (call flow, data flow, closures, and
others) as partial, with zero retained relations. Its follow-up commands,
such as `trace-javascript-semantics`, need evidence from a successful analysis,
so they were not run. The terrain drawing path was therefore traced by reading
the source: `draw` calls `drawGround` first, which used only `arena.grid`,
`arena.half`, `arena.water_half_rows`, and `arena.bits.WATER`, and did not read
entity state. REA is an analysis tool and is not needed at runtime.

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
