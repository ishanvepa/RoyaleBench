"""On-demand playback of the referee replay carried by current match tasks."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from .protocol import ValkyrieAPI
from .results import ResultsCache
from .valkyrie import ValkyrieError

MAX_REPLAY_BYTES = 64 * 1024 * 1024


def _render(path: Path, task_id: str) -> dict:
    from royalegym.replay import load_trace
    from cr_arena.replay import patched_html

    partial = load_trace(path).result is None
    return {"available": True, "html": patched_html(path, title=f"Task replay: {task_id}", stride=2),
            "partial": partial}


def task_replay(remote: ValkyrieAPI, cache: ResultsCache, run_id: str, task_id: str, *, final: bool) -> dict:
    """Read only royale/replay.msgpack from the carried royale archive; never execute remote HTML.

    Only a FINISHED run is immutable. Stopped/errored runs can be resumed/retried, so their snapshots
    are fetched again. Missing artifacts and transfer/render failures are never cached.
    """
    path = cache.replay_dir(run_id, task_id) / "replay.msgpack"
    if final and path.is_file():
        return _render(path, task_id)

    with tempfile.TemporaryDirectory(prefix="rb-replay-") as tmp:
        stage = Path(tmp)
        try:
            downloaded = Path(remote.download_artifact(run_id, f"{task_id}/artifacts/royale.tar.gz", stage / "download"))
        except ValkyrieError as exc:
            if exc.kind == "not_found" or (exc.kind == "other" and "No artifacts found" in str(exc)):
                return {"available": False, "message": "No game replay was saved for this task attempt."}
            raise
        candidates = [downloaded] if downloaded.is_file() else list(downloaded.rglob("royale.tar.gz"))
        if len(candidates) != 1:
            raise ValueError("Expected one royale replay archive in the task artifacts")
        with tarfile.open(candidates[0]) as archive:
            members = [m for m in archive if m.name.removeprefix("./") == "royale/replay.msgpack"]
            if not members:
                return {"available": False, "message": "No game replay was saved for this task attempt."}
            if len(members) != 1 or not members[0].isfile():
                raise ValueError("Replay must be a single regular file")
            if members[0].size > MAX_REPLAY_BYTES:
                raise ValueError("Replay exceeds the 64 MiB size limit")
            incoming = stage / "replay.msgpack"
            with archive.extractfile(members[0]) as source, incoming.open("wb") as target:
                shutil.copyfileobj(source, target)
        rendered = _render(incoming, task_id)
        if final:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Each request gets a unique staging file, and readers only see complete snapshots.
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
                staged_path = Path(staged.name)
                try:
                    with incoming.open("rb") as source:
                        shutil.copyfileobj(source, staged)
                    staged.close()
                    os.replace(staged_path, path)
                finally:
                    staged_path.unlink(missing_ok=True)
        return rendered
