"""Build RoyaleBench v3, the default coordinate-action continuation benchmark.

    uv run python -m cr_arena.build_v3 --jobs 2

The eleven released v1 states are recalibrated through coordinates. Candidate families
remain gated. Frozen v1 and coordinate-pilot snapshots are never regenerated here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .coordinate_benchmark import BASE, ROOT, build as build_coordinates

TITLE = "RoyaleBench v3"
VERSION = "3.0.0"
OUT = ROOT.parent / "benchmarks/royalebench-v3"
EVIDENCE = ROOT.parent / "runs/royalebench-v3"


def task_names():
    return tuple(json.loads((BASE / "manifest.json").read_text())["runnable_tasks"])


def build(out=OUT, evidence=EVIDENCE, *, jobs=1, reuse=True):
    out = Path(out).resolve()
    if out == (ROOT.parent / "benchmarks/royalebench-coordinates").resolve():
        raise ValueError("the historical coordinate pilot cannot be overwritten")
    return build_coordinates(out, evidence, names=task_names(), title=TITLE, version=VERSION,
                             guide="royalebench_v3.md", task_prefix="v3-", command="cr_arena.build_v3",
                             reuse=reuse, jobs=jobs, include_candidates=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1,
                        help="independent local calibration processes; each Planner still uses workers=0")
    parser.add_argument("--fresh", action="store_true", help="rerun negative controls even for matching cached evidence")
    args = parser.parse_args()
    build(args.out, args.evidence, jobs=args.jobs, reuse=not args.fresh)


if __name__ == "__main__":
    main()
