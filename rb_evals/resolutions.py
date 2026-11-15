"""Playback of a locally validated Harbor task reference solution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .replays import MAX_REPLAY_BYTES


def resolution_replay(task: Path, evidence_root: Path) -> dict:
    """Render a Docker-validated reference for the exact packaged task on disk.

    Old Docker runs can coexist with newer dataset revisions. Match both the
    packaged referee protocol and task configuration before showing a replay.
    """
    config_path = task / "tests/task.json"
    if not config_path.is_file():
        return {"available": False, "message": "This task has no saved reference replay."}
    candidates = sorted(evidence_root.glob("docker*/validation.json"), reverse=True)
    if not candidates:
        return {"available": False, "message": "No validated resolution replay matches this task version."}

    from cr_arena.validate_v1_docker import protocol_for

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    config_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    protocol_hash = protocol_for(cfg, task)
    for manifest_path in candidates:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != protocol_hash:
            continue
        row = next((r for r in manifest.get("tasks", []) if r.get("task") == task.name), None)
        if row is None or row.get("config_sha256") != config_hash or row.get("protocol_sha256") != protocol_hash:
            continue
        if any(row.get(key) != 1 for key in ("reward", "integrity")):
            continue
        if not all(row.get(key) is True for key in ("isolated", "restart_verified", "replay_hashes_verified")):
            continue
        replay = manifest_path.parent / task.name / "replay.msgpack"
        if not replay.is_file() or replay.stat().st_size > MAX_REPLAY_BYTES:
            continue
        from royalegym.replay import load_trace
        from cr_arena.replay import patched_html

        if load_trace(replay).result is None:
            continue
        return {"available": True, "html": patched_html(replay, title=f"Reference solution: {task.name}", stride=2)}

    return {"available": False, "message": "No validated resolution replay matches this task version."}
