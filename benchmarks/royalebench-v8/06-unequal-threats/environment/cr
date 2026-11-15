#!/usr/bin/env python3
"""cr: play your Clash Royale match.

    cr            show the current state and the numbered legal moves
    cr act N      play move N (0 = wait); the game advances and the next state is shown
    cr play SLOT X Y   coordinate mode: deploy hand slot 0-3 at own-frame tile coordinates
    cr wait           coordinate mode: wait for one decision interval

The game is paused while you think. Keep playing until it prints GAME OVER.
"""

# Installed as /usr/local/bin/cr inside the task image. Standard library only: the agent's side
# of the sandbox has no game engine; it talks to the referee's game server over a Unix socket.

import json
import math
import os
import socket
import subprocess
import sys
import time

SOCKET = os.environ.get("CR_SOCKET", "/var/lib/royale-run/cr.sock")
START = ["sudo", "-n", "-u", "referee", "/usr/local/sbin/royale-start-server"]


def request(payload: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(300)
        s.connect(SOCKET)
        s.sendall((json.dumps(payload) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data)


def call(payload: dict) -> dict:
    try:
        return request(payload)
    except (FileNotFoundError, ConnectionRefusedError):
        pass
    # The server is not up (first call, or it was restarted): start it. It resumes the same match.
    subprocess.run(START, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    deadline = time.time() + 60
    while True:
        try:
            return request(payload)
        except (FileNotFoundError, ConnectionRefusedError):
            if time.time() > deadline:
                raise SystemExit("cr: the game server is not responding; try again in a few seconds.")
            time.sleep(0.5)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("observe", "show", "state"):
        payload = {"cmd": "observe"}
    elif argv[0] == "act" and len(argv) == 2:
        try:
            payload = {"cmd": "act", "move": int(argv[1])}
        except ValueError:
            print("usage: cr act <move number>")
            return 2
    elif argv[0] == "play" and len(argv) == 4:
        try:
            payload = {"cmd": "play", "slot": int(argv[1]), "x": float(argv[2]), "y": float(argv[3])}
            if not all(math.isfinite(payload[k]) for k in ("x", "y")):
                raise ValueError("coordinates must be finite")
        except ValueError:
            print("usage: cr play <hand-slot integer> <finite x> <finite y>")
            return 2
    elif argv == ["wait"]:
        payload = {"cmd": "wait"}
    else:
        print(__doc__.strip())
        return 0 if argv and argv[0] in ("-h", "--help", "help") else 2
    resp = call(payload)
    print(resp.get("text", ""))
    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
