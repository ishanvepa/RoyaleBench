# TikTok interaction recreations

The two user-supplied clips were extracted with `yt-dlp` and browser-compatible
`curl-cffi` networking on November 15, 2026. Frames were extracted with ffmpeg and
visually inspected. The original deterministic mechanics demonstrations were
created outside the benchmark dataset, without changing simulator rules.

The interactions are now separately calibrated as Tactics @6 tasks
`06-mini-pekka-kite` and `07-balloon-fireball`. See [the task guide](tactics_clips.md)
for their level-11 normalization, scoring, reference solutions, and validation.
The original demonstrations below retain their original inputs.

Open `runs/clip-recreations/index.html` through a local HTTP server to watch the
downloaded references beside the engine replays. Each interaction also has an
exported standalone HTML replay, a MessagePack trace, a no-defense control, and
a mistimed-defense control. `checks.json` records the complete public setup,
accepted commands, damage events, source file hashes, package versions, engine
binary/data identity, final state hashes, and trace verification results.

## Results

| Interaction | Recreation | Mistimed defense | No defense |
|---|---|---|---|
| Level-11 Skeletons vs level-11 Mini P.E.K.K.A. | 0 damage; tower remains 3052 HP | 755 damage | 3020 damage |
| Fireball vs level-16 Balloon, level-15 Princess Tower | 0 direct attacks; 384 death-bomb damage; tower 4424 → 4040 HP | One 1022-damage attack plus 384 death-bomb damage | Tower destroyed |

The Balloon reference ends with the death-bomb fuse still running. Its visible
claim is preventing a direct attack. It does not demonstrate zero eventual damage.
Our recreation continues through the explosion and the controls run long enough
for their explosions as well.

The main Skeletons defense is a legal tap at `(7.5, 13.5)`, 75 ticks (3.75 s)
after the reconstruction begins. The main Fireball is a legal tap at `(3.5, 7.5)`,
200 ticks (10 s) after the reconstruction begins. Coordinates use Blue's frame,
with its back edge at y=0. Both attackers start at full HP at `(3.5, 20.5)` using
public `SpawnSpec`. The two demonstrations start at engine tick 100 to clear the
engine's opening deployment lockout; simulation elapsed time starts at that tick.
Both players begin with 10 elixir. There are no pending commands or other troops.

Skeletons, Mini P.E.K.K.A., Balloon, the defended tower HP, and their visible
levels match the clips. The damaged far Princess Towers in the Balloon clip are
also set to the visible 278 and 3912 HP. The Fireball's level is hidden; level 16
is an explicit reconstruction assumption. Blue's King is visibly level 16 in
that clip, but the public setup sets one tower level per team, so Blue's King
is level 15 here. The King never fires in this interaction. The cropped right
lane's troops and partly hidden HP are not reconstructed. Deck filler, elixir,
the match clock, exact taps, and prior hidden state cannot be recovered from
these edited videos. Geometry, animation, arena artwork and movement timing
differ from the live game.

Consequently these establish that **the two tactical outcomes are possible in
the current simulator**, rather than establishing an exact recovery of either
original match. No unit HP was reduced to force a defense, and no damage,
targeting, deployment, movement, or knockback rules were overridden.

## Reproduce

Download the two public sources (the MP4s and full downloader metadata are ignored
by Git; file hashes are retained in `checks.json`):

```sh
mkdir -p data/references/tiktok
uvx --with curl-cffi yt-dlp --no-playlist --write-info-json \
  -o 'data/references/tiktok/%(id)s.%(ext)s' \
  'https://www.tiktok.com/@daily.clashroyale01/video/7575314632915701009' \
  'https://www.tiktok.com/@royale.clasher2/video/7646672093966355726'

uv sync --locked
uv run python -m cr_arena.recreate_clips
python3 -m http.server 8768 --bind 127.0.0.1
# Open http://127.0.0.1:8768/runs/clip-recreations/index.html
```

Generation independently replays all six traces on a fresh engine, checks every
recorded state hash (461 frames per trace), verifies command acceptance, and
asserts the two outcomes and that both controls are worse. Generation fails on
any discrepancy. The recorded versions are RoyaleGym 0.1.28 and RoyaleSim 0.1.48;
engine binary and card-table identities are recorded because versions alone do
not identify locally rebuilt engines. The creation run used an existing local
environment with those versions; the trace identity is the authoritative record.

The standalone exports use the production replay controls and battle renderer,
with unrelated side panels hidden for the comparison view. Browser checks cover
reference video loading, all replay timelines, playback, and final HP. Captured
MP4s show the actual replay canvas, including the Balloon's delayed explosion.

Sources: [Skeletons clip](https://www.tiktok.com/t/ZTPDWutTM/) and
[Fireball clip](https://www.tiktok.com/t/ZTPD72qTU/).
