"""Audit every immediate menu opening in the one-card race and trade scenarios.

    python -m cr_arena.audit_tactics --tasks 3 4

The remainder of each attempt waits. This is an opening-policy audit, not an exhaustive
search over delayed policies. Protected logs and independent replay results are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .royale_task import make_referee
from .royalebench_v1 import protocol_digest
from .tactics import catalog
from .validate_tactics import attempt
from .telemetry import atomic_json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", type=int, nargs="+", default=[3, 4], choices=[3, 4])
    ap.add_argument("--out", type=Path, default=Path("runs/tactics/openings"))
    ap.add_argument("--evidence", type=Path, default=Path("runs/tactics"))
    args = ap.parse_args()
    records = []
    source_hash = hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    for cfg in catalog():
        if cfg["family"] not in args.tasks:
            continue
        ref = make_referee(cfg)
        trials = []
        for move in ref.moves:
            result = attempt(cfg, args.out, f"opening-{move.index:02d}",
                lambda r, i=move.index: i if r.decision == 0 else 0)
            result.update(move_index=move.index, card=move.card, target=move.target,
                          target_kind=move.target.split(" at (")[0])
            trials.append(result)
        config_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        audit = dict(task=cfg["id"], family=cfg["family"], config_sha256=config_hash,
            protocol_sha256=protocol_digest(), source_sha256=source_hash, trials=trials)
        records.append(audit)
        path = args.evidence / cfg["id"] / "validation.json"
        evidence = json.loads(path.read_text())
        if evidence.get("config_sha256") != config_hash or evidence.get("protocol_sha256") != protocol_digest():
            raise RuntimeError(f"Calibrate the current reference before auditing {cfg['id']}")
        evidence["opening_audit"] = audit
        atomic_json(path, evidence)
        atomic_json(args.out / "validation.json", dict(protocol_sha256=protocol_digest(), tasks=records))
    result = dict(protocol_sha256=protocol_digest(),
        audit_source_sha256=source_hash, tasks=records)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "validation.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
