"""Package only Tactics scenarios with current winning references and passing contrasts."""
from __future__ import annotations

import argparse
from pathlib import Path

from .build_v1 import build
from .tactics import catalog


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("benchmarks/royalebench-tactics"))
    ap.add_argument("--evidence", type=Path, default=Path("runs/tactics"))
    args = ap.parse_args()
    build(args.out, args.evidence, configs=catalog(), guide="tactics.md", generator="cr_arena.build_tactics",
          description="Timed spells, counter reservation, tower races and deliberate tower trades against Planner. "
                      "Binary objectives; references and strategy contrasts gate local packaging. Model difficulty pending.",
          aggregation="Primary: equal-weight mean of the four family means. Report per-task results and "
                      "Valkyrie's default flat task mean separately; mirrored variants are not independent families.")


if __name__ == "__main__":
    main()
