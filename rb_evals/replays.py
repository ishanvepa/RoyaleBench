"""On-demand playback of the referee replay carried by current match tasks."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from .protocol import ValkyrieAPI
from .replay_decisions import read_decisions
from .results import ResultsCache, fetch_task_files
from .valkyrie import ValkyrieError

MAX_REPLAY_BYTES = 64 * 1024 * 1024


def _render(path: Path, task_id: str, decisions: list[dict], note: str) -> dict:
    from royalegym.replay import load_trace
    from cr_arena.replay import patched_html

    partial = load_trace(path).result is None
    return {"available": True, "html": patched_html(path, title=f"Task replay: {task_id}", stride=2,
                                                  decisions=decisions, decisions_note=note),
            "partial": partial}


def task_replay(remote: ValkyrieAPI, cache: ResultsCache, run_id: str, task_id: str, *, final: bool) -> dict:
    """Read the replay and observation text/ticks; never execute remote HTML.

    Only a FINISHED run is immutable. Stopped/errored runs can be resumed/retried, so their snapshots
    are fetched again. Missing artifacts and transfer/render failures are never cached.
    """
    path = cache.replay_dir(run_id, task_id) / "replay.msgpack"
    observations_path = path.with_suffix(".observations.json")

    def render(replay, observations):
        decisions, note = [], "No synchronized agent decisions were recorded for this replay."
        if observations:
            try:
                folder = fetch_task_files(remote, cache, run_id, task_id, final=final)
                if folder:
                    decisions = read_decisions(folder, observations)
                if decisions:
                    note = "Messages and tool calls are aligned to the board observation the agent received."
            except (ValkyrieError, OSError, ValueError, tarfile.TarError):
                note = "Agent decisions could not be loaded. Close and reopen the replay to try again."
        return _render(replay, task_id, decisions, note)

    # Older caches only saved the game. Refresh those once to collect the observations.
    if final and path.is_file() and observations_path.is_file():
        return render(path, json.loads(observations_path.read_text(encoding="utf-8")))

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
            observations = []
            captures = [m for m in archive if m.name.removeprefix("./") == "royale/capture/observations.jsonl"]
            if len(captures) == 1 and captures[0].isfile() and captures[0].size <= MAX_REPLAY_BYTES:
                with archive.extractfile(captures[0]) as source:
                    for line in source:
                        if line.strip():
                            try:
                                record = json.loads(line)
                            except ValueError:
                                continue
                            data = record.get("data") if isinstance(record, dict) else None
                            if isinstance(data, dict):
                                observations.append({k: data.get(k) for k in ("text", "tick", "team")})
        rendered = render(incoming, observations)
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
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as staged:
                staged_path = Path(staged.name)
                try:
                    json.dump(observations, staged)
                    staged.close()
                    os.replace(staged_path, observations_path)
                finally:
                    staged_path.unlink(missing_ok=True)
        return rendered
