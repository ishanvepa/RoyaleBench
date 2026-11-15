# Play against the bots on your phone

The live browser game supports `heuristic-bot`, `planner-bot`, `search-bot`, and `search-v2`, with independent
choices of player and opponent decks. No model API credentials are needed.
The shared [bot catalog](../configs/bots.toml) controls these choices; see
[bot setup](bots.md) to change presets or add an opponent.

For public play against Planner's fixed Hog Cycle deck, use `uv run --frozen python -m cr_arena.share --public`.
It allows five active matches and shows “Server at
capacity” on a sixth start. See [public play](public_play.md) for permanent hosting
on Modal and the five-match load check.

## One-time setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[cloudflared](https://developers.cloudflare.com/tunnel/downloads/).
On macOS with Homebrew:

```bash
brew install uv cloudflared
```

From the repository root, install the committed Python dependency versions:

```bash
uv sync --frozen
```

The project selects Python 3.12 through `.python-version`. The phone-play setup
was checked with cloudflared 2026.11.0 on macOS. The launcher also supports Linux.

## Start phone play

```bash
uv run --frozen python -m cr_arena.share
```

This starts the game on `http://127.0.0.1:8601`, waits for it to become ready,
then starts a Cloudflare Quick Tunnel. Open the printed
`https://….trycloudflare.com` URL in Safari or Chrome on your phone.
Your devices can stay on their existing Wi-Fi; they only need internet access.

Choose **search-v2** in the opponent selector to play the selected Search v2
preset, or choose another bot. Search v2 thinks in a separate process,
uses the same command delay as you, and discards outdated card choices. It uses
a soft 1.2-second search deadline at completed comparison rounds; a round can
finish after that target. Its live results are separate from the paused benchmark.

Choose an opponent and decks, then press **Start game**. Tap a card and then
tap a legal location on the arena to deploy it. Use **Change deck** to return
to setup and switch opponents. Finished games save to `runs/arena.db`, with
replays under `runs/round_robin/human-play/replays/`.
The setup screen includes a persistent wins/losses leaderboard backed by
`runs/round_robin/human-play/leaderboard.csv`, with a placeholder name per browser
until name entry is added. See [leaderboard behavior and storage](public_play.md#persistent-leaderboard).

Keep your Mac awake and the command running. Press **Ctrl+C** to stop the
tunnel, game server, and bot workers. If either service exits, the launcher
stops the other. The launcher does not reuse or stop existing game servers.

If port 8601 is already in use, choose a different port:

```bash
uv run --frozen python -m cr_arena.share --port 8602
```

## Link behavior and troubleshooting

- The tunnel needs no Cloudflare account or domain. Anyone with its URL can
  access the game. Stopping the command closes that tunnel; each launch gets
  a new URL. This is a temporary testing setup, not an authenticated deployment.
- If a new link is not immediately reachable, wait briefly for it to become
  available. Check the terminal for tunnel errors if it continues to fail.
- If your network blocks `trycloudflare.com` or tunnel traffic, this setup may
  also fail on that network. The launcher prints Cloudflare's diagnostics.
- For local play without a public tunnel, use
  `uv run --frozen python -m cr_arena.live` and open `http://127.0.0.1:8600`.

Search v2 is also available in the dashboard's **You vs model** opponent selector.
That mode pauses between decisions and uses the original fixed-budget preset.

This reproduces the launch and dependency setup. Games currently choose a
random seed on start; it does not guarantee identical matches or live timing.

Reference: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
