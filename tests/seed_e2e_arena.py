"""Seed a throw-away arena database for the browser tests (nothing here touches the real arena).

    uv run python -m tests.seed_e2e_arena runs/e2e-arena/arena.db

It holds the same data the API tests use: a running tournament with one finished match (with a replay and
logged decisions), a finished battle and an empty human-play job.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cr_arena.db import DB
from tests.helpers import seed_arena


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        raise SystemExit(__doc__)
    path = Path(argv[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink(missing_ok=True)
    except PermissionError:  # Windows will not delete a file another process has open
        raise SystemExit(f"{path} is open in another process, probably a server left running from an earlier session. Stop it and try again.")
    db = DB(path)
    try:
        seed_arena(db)
    finally:
        db.close()
    print("seeded", path)


if __name__ == "__main__":
    main(sys.argv[1:])
