"""Run the live game and a temporary Cloudflare tunnel together.

    uv run --frozen python -m cr_arena.share
"""

from __future__ import annotations

import argparse
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


ROOT = Path(__file__).resolve().parents[1]


def wait_for_server(server: subprocess.Popen, url: str, timeout: float = 30) -> None:
    """Wait for this child to serve the game before exposing it through the tunnel."""
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Game server exited with code {server.returncode}")
        try:
            with opener.open(url, timeout=1) as response:
                if b"<title>CR Arena Live</title>" in response.read():
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Game server did not become ready at {url}")


def stop_processes(processes: list[subprocess.Popen]) -> None:
    # Each child owns a process group, including any bot worker grandchildren.
    # Signal the groups even if their leaders exited, so workers cannot be orphaned.
    for process in reversed(processes):
        try:
            signal_group(process, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for process in reversed(processes):
        try:
            signal_group(process, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def signal_group(process: subprocess.Popen, sig: int) -> None:
    import os

    os.killpg(process.pid, sig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8601, help="local game port (default: 8601)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        parser.error("cloudflared is required; on macOS run: brew install cloudflared")
    if sys.platform == "win32":
        parser.error("This launcher currently supports macOS and Linux")
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
    except OSError as exc:
        parser.error(f"Cannot use port {args.port}: {exc}. Choose another port with --port.")

    url = f"http://127.0.0.1:{args.port}"
    processes: list[subprocess.Popen] = []

    def terminate(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        print(f"Starting game at {url}", flush=True)
        server = subprocess.Popen(
            [sys.executable, "-m", "cr_arena.live", "--host", "127.0.0.1", "--port", str(args.port)],
            cwd=ROOT, start_new_session=True,
        )
        processes.append(server)
        wait_for_server(server, url)
        print("Open the https://…trycloudflare.com link printed below on your phone.", flush=True)
        print("Anyone with the link can play. Keep this command running; Ctrl+C stops both services.", flush=True)
        tunnel = subprocess.Popen(
            [cloudflared, "tunnel", "--url", url], cwd=ROOT, start_new_session=True,
        )
        processes.append(tunnel)
        while True:
            for name, process in (("Game server", server), ("Tunnel", tunnel)):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited with code {process.returncode}")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping game and tunnel…", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        # Finish cleanup if another interrupt arrives while children are exiting.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
