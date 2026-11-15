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
The King and Princess Tower artwork was refined against timestamped frames from
the local gameplay reference. [REA](https://github.com/morluto/rea) inspected the
JavaScript drawing path; ffmpeg extracted the video frames and those images were
inspected visually. REA did **not** analyze the video or judge visual similarity.
REA is an analysis tool and is not needed at runtime.

![Arena preview from a recorded battle](images/tower-after.png)

The [Arena 1 gameplay video](https://www.youtube.com/watch?v=PD6QCK7GzA8)
is the tower reference; see [data documentation](../data/README.md#visual-reference)
for its source and checksum, and the sampling record below.

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

## Tower reference and scope

This pass changes only King/Princess Tower canvas artwork and remembers observed
tower sites to draw ruins after their entities disappear. Terrain, troop and
building drawing, spells, HUD, health bars, simulator state, placement masks and
tooltip radii are unchanged. The first tower path clips decoration to its existing
footprint. Optional Princess Tower rectangles are transformed with `X`/`Y`,
including non-square rectangles and old replay rows without footprint columns.
King Towers keep their existing 3.1-tile drawing bounds. Team colors on towers
use their own blue/crimson palette, leaving the HUD and other entities' palette
alone. Camera-facing fronts/backs follow screen orientation when flipped.

The stone walls now have staggered courses, beveled sides, ivory battlements,
wood platforms, gold crown plaques on the far side, and rear ladders on near
Princess Towers. The near King has a hipped team-colored roof, gold-rimmed
cannon, recessed door and steps; the far King stands on the platform. Shadows
extend toward the lower left as in the reference. Low-health samples retain
their masonry and silhouette, so this pass keeps the existing transient hit
flash without adding percentage-based cracks or fire. Removed towers leave a
low pale stone ring and broken timber. Those remembered ruins add no tooltip
target and do not change placement eligibility; reset clears their history.

The exact video used here is at
`/Users/ben/.codex/worktrees/eb33/RoyaleBench/data/references/arena-1-PD6QCK7GzA8.mp4`
(1920×1080, 60 fps). These are **video timestamps**, not the in-game clock:

| Timestamp | Frame at 60 fps | Visible evidence |
|---|---:|---|
| 00:30.000 | 1800 | Clear far red battlements, archers, crown plaques and King; near blue roof, cannon, Princess backs and ladders. |
| 01:30.000 | 5400 | Far King at 948 HP with cannon deployed; Princess walls retain their silhouette. |
| 05:10.000 | 18600 | Far Princess at 748 HP beside an already destroyed Princess Tower; pale rubble ring and crossed timber. |
| 05:12.000 | 18720 | Follow-up view of the same low-health tower and rubble after attack effects clear. |
| 05:15.000 | 18900 | Far King at 186 HP, surviving Princess at 748 HP, and clear destroyed-tower rubble. |

![Timestamped tower reference crops](images/tower-reference.jpg)

Extract each full-resolution frame with ffmpeg, for example:

```sh
mkdir -p output/playwright/towers
ffmpeg -hide_banner -loglevel error -ss 00:00:30 \
  -i /Users/ben/.codex/worktrees/eb33/RoyaleBench/data/references/arena-1-PD6QCK7GzA8.mp4 \
  -frames:v 1 output/playwright/towers/ref-00m30s.png
# Repeat with the timestamps above. The composite only crops/scales these frames.
```

## REA code inspection

REA 6.9.0 analyzed `cr_arena` with only `battle_renderer.js` selected. The original
source SHA-256 was
`3dfdb5f2c3088106ca49b80ac3dcce3a65a3c6b4e1b0f34a89acf4b25b5dbe10`.
Its static semantic graph recovered `draw` (original lines 580–778), `drawEntity`
(472–541), `drawTower` (263–324), and `X`/`Y` (96–97). It recorded resolved calls
to `drawEntity` at line 631 and `drawTower` at line 501. Reading those ranges
confirmed the KING/PRINCESS branch, optional footprint handling, and the separate
`drawn.push` used for tooltips. This is static code evidence, not runtime proof.
The bounded semantic caller query reported partial coverage and 24 relevant
unknowns; dynamic canvas calls are not a complete behavioral model.

The default SDK failed to compile REA's process helper on this machine. Selecting
the already installed macOS 26.5 SDK allowed parsing to finish, without changing
the tool or system SDK selection:

```sh
SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk \
  npx --yes rea-agents@6.9.0 analyze-javascript-application cr_arena \
  --source-path battle_renderer.js --detail summary \
  --evidence_output output/playwright/towers/rea-before.json --format json
```

The completed original evidence bundle in this workspace is
`output/playwright/towers/rea-before-sdk26.json`; its evidence ID is
`ev_8796f5e61898951f2deaaaecabf23776ec78dc085d4ef79e3e76fe9533119401`.
The same git-ignored folder holds the caller query/result and sampled full video
frames. The selected comparison images and validation record are kept under
`docs/images/`.

## Tower comparison and validation

Before and after use
`runs/samples/heuristic-bot__vs__random-bot__s2.msgpack`, stride 1, paused at tick
1200 (1:00.0), interpolation off, Chromium viewport 1280×1100, and 28 pixels per
tile. Both show state hash `4a812d60b54536a1`. The full screenshots include the
same HUD and canvas; the comparison below crops the boards without resizing.

![Same replay frame before and after tower changes](images/tower-comparison.png)

- Full screenshots: [before](images/tower-before.png), [after](images/tower-after.png).
- [Flipped at the same tick](images/tower-after-flipped.png): blue fronts at the
  top and crimson roofs/backs at the bottom. A browser pointer check on the near
  King still reports `KING_TOWER (Red, uid 1)`, HP 4824/4824, tile (9,29).
- [Destroyed-tower frame](images/tower-after-destroyed.png): tick 3778 (3:08.9),
  final hash `21760f6f67a06341`. The missing red Princess now leaves rubble; its
  destruction effect and nearby troops retain their existing drawing paths.
- Pixel comparison outside the six tower/shadow regions found 37 differing
  edge pixels at tick 1200 in either orientation, and 57 at tick 3778. The
  largest color-channel difference was 4/255; no outside pixel differed by more
  than that tolerance. These are not asserted to be bit-identical captures.
  [Machine-readable capture record](images/tower-validation.json).

Checks passed:

```sh
node --test tests/battle_renderer.test.cjs                       # 11 tests
uv run python -m unittest discover -s tests -p 'test_rendering.py' # 5 tests
uv run python -m unittest discover -s tests -p 'test_placement.py' # 9 tests
```

Renderer checks cover default/optional Princess footprints, both flips, King
bounds and tooltip anchors, transient damage, low-HP silhouettes, and rebuilding
ruins after reset/seek. Python checks exercise shared live/replay embedding,
standalone exports, and seeking/flipping/interpolation in the exported scripts.
The exported page was also checked in Chromium with no JavaScript console errors.

## Remaining tower differences

- These are small original canvas miniatures. The reference uses textured 3D
  meshes, soft lighting, irregular stones and smoother shadows; this pass uses
  flat layered shapes and simplified bevels. Occupant faces, bows and crowns
  remain stylized, with no aiming, recoil, idle or collapse animation.
- The existing orthographic arena and tower bounds constrain the reference's
  perspective and vertical proportions. Tower bodies are inset within those
  bounds to distinguish the wider King from the slimmer Princess. Shadows are
  approximate polygons rather than reference-extracted silhouettes.
- The reference mixes tower levels and views. Its low-health samples do not
  establish a reliable progressive damage texture, and no clear destroyed King
  is sampled. King rubble reuses the Princess rubble motif at King size.
- Far King cannon visibility uses HP below maximum as the available activation
  cue; the drawing contract has no explicit King activation state. A King
  activated by losing a Princess while still at full HP can therefore retain
  the idle pose. Near Kings keep the reference's roof/cannon view.
- Ruins require that a tower was previously observed. A stream starting after
  destruction without tower history cannot reconstruct the missing site. Live
  play and full saved replays normally begin with all six towers.
