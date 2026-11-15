"""Run the dashboard server:  uv run python -m rb_server [--fake] [--host H] [--port P] [--reload]"""

from __future__ import annotations

import argparse
import os

import uvicorn

from .settings import Settings


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m rb_server", description=__doc__)
    ap.add_argument("--host", help="default 127.0.0.1; anything else exposes a server that can spend your credits")
    ap.add_argument("--port", type=int)
    ap.add_argument("--fake", action="store_true", help="simulated Valkyrie (no network, no credentials, no cost)")
    ap.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    args = ap.parse_args()
    # The app factory reads the environment, so flags travel the same way under --reload.
    if args.host:
        os.environ["ROYALEBENCH_HOST"] = args.host
    if args.port:
        os.environ["ROYALEBENCH_PORT"] = str(args.port)
    if args.fake:
        os.environ["ROYALEBENCH_FAKE_VALKYRIE"] = "1"
    settings = Settings.from_env()
    flags = [f for f, on in (("FAKE Valkyrie", settings.fake_valkyrie),
                             ("read-only", os.environ.get("ROYALEBENCH_EVALS_READONLY", "") not in ("", "0"))) if on]
    print(f"RoyaleBench: http://{settings.host}:{settings.port}" + (f"  [{', '.join(flags)}]" if flags else ""))
    if not (settings.static_dir / "index.html").is_file():
        print("  web app not built: run `cd web && npm install && npm run build` (or `npm run dev` for hot reload)")
    uvicorn.run("rb_server.app:create_app", factory=True, host=settings.host, port=settings.port, reload=args.reload,
                log_level="info")


if __name__ == "__main__":
    main()
