# Hog Rider body-block recreation

This local mechanics experiment recreates the **temporary body-block** shown in
[Clash Challenger's TikTok](https://www.tiktok.com/@clashchallenger1/video/7704162569065352478).
The caption is “Pro tip to counter Incoming Hog rider with skeleton and ice golem”.

The separately calibrated [Tactics task](tactics.md) `05-hog-body-block` packages this
idea as a three-elixir, zero-damage defense. It uses an already-active incoming Hog
and its own verified reference, rather than treating this experiment's action
timestamps as interchangeable with a continuation setup.
The clip shows an Ice Golem outside the left lane and Skeletons in the lane
constricting a Hog Rider's route just below the bridge. It cuts away before a
complete defense outcome is visible, so we do not claim its final damage matches
the simulator. Coordinates and timing are estimates from the cropped video.

The engine can reproduce the qualitative interaction without modifications:
the selected setup holds the Hog between y=14 and y=13 for **3.75 seconds**,
compared with 0.45 seconds with Skeletons alone. The Hog dies after 7.95 seconds
without dealing tower damage. This is a scripted mechanics check, not a released
benchmark or evidence of model difficulty.

## Extracting the reference

The browser login/birthday gate prevented playback. `yt-dlp` with `curl-cffi`
successfully downloaded the public video without browser cookies or signing in:

```sh
uvx --with curl-cffi yt-dlp --no-playlist \
  -o 'data/references/hog-ice-golem-skeletons.%(ext)s' \
  'https://www.tiktok.com/@clashchallenger1/video/7704162569065352478'
```

The downloaded MP4 is a local, ignored reference. It is not redistributed in Git.
Plain `uvx yt-dlp` failed here because its browser impersonation dependency was
missing. See the [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp#impersonation).

## Reproducing the simulation

```sh
uv sync --locked --only-group play
uv run --only-group play python -m cr_arena.recreate_hog_block --sweep
```

The runner writes `runs/hog-body-block/results.json` and standalone HTML/MessagePack
replays under `runs/hog-body-block/replays/` (ignored generated artifacts).
Open `body-block.html` in a browser to watch. All five persisted traces are
re-simulated on a fresh engine, checking deployment statuses and every frame hash.
The runner raises an error for refused plays or replay divergence.

Both seats use a fixed deck and the locked RoyaleGym 0.1.28 / RoyaleSim 0.1.48
engine. Units and towers use the engine's default level 11; the blue princess
tower starts at 3052 HP, also visible in the reference. There are no bots, spells,
custom unit HP values, state patches, or engine changes. The setup begins at tick
200 to clear the engine's initial deployment lockout; times below are relative
to that setup. Commands have zero additional command delay and each engine tick
is 50 ms. Card deployment timers still apply.

Coordinates are absolute blue tiles, with blue at the bottom, left bridge around
x=3.5 and river around y=15–17. Red's action is already expressed in that frame.

| Time | Side | Card | Position |
| --- | --- | --- | --- |
| 0.00 s | Red | Hog Rider | (2.5, 18.5) |
| 0.50 s | Blue | Ice Golem (`IceGolemite`) | (1.5, 12.5) |
| 1.00 s | Blue | Skeletons | (3.5, 12.5) |

## Controls and limitations

| Case | Tower hits | Tower damage | Hog dies after |
| --- | ---: | ---: | ---: |
| Selected body-block | 0 | 0 | 7.95 s |
| Skeletons alone | 2 | 634 | 8.70 s |
| Ice Golem alone | 7 | 2219 | 15.30 s |
| Undefended | 7 | 2219 | 15.30 s |
| Same timing, Skeletons one tile higher | 2 | 634 | 8.35 s |

The optional sweep repeats all 144 combinations of Hog x={2.5,3.5}, Ice Golem
x={1.5,2.5}, y={11.5,12.5}, Skeletons x=3.5, y={12.5,13.5}, Ice Golem
command time={0,0.5,1.0}s, and Skeleton command delay after Ice Golem={0.05,0.5,1.0}s.
Four combinations prevent all tower damage. This is a local sensitivity check;
it is not an exhaustive search or an exact reconstruction of the original taps.
The selected case retains the Ice Golem's estimated outside-lane placement and
uses a half-second gap between defensive commands. An initial estimate with
Skeletons one tile higher did not produce the stall.

The experiment establishes a similar emergent collision interaction in our
current engine. It does not establish identical collision physics, exact live
game timing, or behavior at other levels, lanes, or placements. Full per-tick Hog
paths, accepted command schedules, package versions, engine identity, final hashes,
and replay file hashes are recorded in the results JSON.
