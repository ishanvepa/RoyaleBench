# Play against the bots on your phone

The live browser game supports `planner-bot` and `search-bot`, with independent
choices of player and opponent decks. No model API credentials are needed.

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

Choose an opponent and decks, then press **Start game**. Tap a card and then
tap a legal location on the arena to deploy it. Use **Change deck** to return
to setup and switch opponents. Finished games save to `runs/arena.db`, with
replays under `runs/round_robin/human-play/replays/`.

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

This reproduces the launch and dependency setup. Games currently choose a
random seed on start; it does not guarantee identical matches or live timing.

Reference: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
