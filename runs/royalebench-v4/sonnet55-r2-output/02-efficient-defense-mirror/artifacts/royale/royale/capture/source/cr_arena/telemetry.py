"""Versioned, referee-private evidence for new matches. No provider credentials live here.

The accepted-action log remains the scoring authority. This recorder is diagnostic:
an I/O failure marks capture incomplete without changing game decisions or rewards.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import msgspec

VERSION = "1.0"
TABLES = ("matches", "observations", "commands", "states", "events", "model_calls")


class Record(msgspec.Struct, forbid_unknown_fields=True):
    schema_version: Literal["1.0"]
    record_id: str
    table: Literal["matches", "observations", "commands", "states", "events", "model_calls"]
    match_id: str
    attempt_id: str
    source: str
    segment_id: str
    sequence: int
    utc: str | None
    monotonic_ns: int | None
    data: dict[str, Any]
    run_id: str | None = None
    task_id: str | None = None


def value(obj):
    """Named structs even for msgspec array-like engine structs; lossless bytes."""
    if isinstance(obj, msgspec.Struct):
        return {k: value(getattr(obj, k)) for k in obj.__struct_fields__}
    if dataclasses.is_dataclass(obj):
        return value(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [value(v) for v in obj]
    if isinstance(obj, bytes):
        return {"base64": base64.b64encode(obj).decode()}
    return obj


def canonical(obj) -> bytes:
    return json.dumps(value(obj), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def public_settings(obj):
    """Retain request options, excluding authentication values from custom overrides."""
    if isinstance(obj, dict):
        return {k: ("[redacted]" if any(word in k.lower() for word in
                ("api_key", "authorization", "password", "secret", "credential")) else public_settings(v))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [public_settings(v) for v in obj]
    return obj


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(canonical(obj) + b"\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def utc() -> str:
    return datetime.now(UTC).isoformat()


def provenance() -> dict:
    versions = {}
    for name in ("royalegym", "royalesim", "msgspec", "anthropic", "openai", "valkyrie-sdk"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    root = Path(__file__).resolve().parents[1]
    sources = {str(p.relative_to(root)): file_hash(p) for p in sorted((root / "cr_arena").rglob("*.py"))}
    def git(*args):
        try:
            r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5, check=False)
            return r.stdout.strip() if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    return {"python": platform.python_version(), "versions": versions, "commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain")), "source_sha256": sources,
            "lock_sha256": file_hash(root / "uv.lock") if (root / "uv.lock").exists() else None,
            "image_digest": os.getenv("ROYALEBENCH_IMAGE_DIGEST"),
            "effective_settings": None, "effective_settings_reason": "provider must report effective settings"}


def move_data(game, team: int, move) -> dict:
    data = value(move)
    data.update(team=team, label=move.label(), coordinate_frame="engine_subtiles", subtile=game.sub,
                own_tiles=list(game.own_tiles(team, move.x, move.y)) if move.slot >= 0 else None)
    return data


def state_data(game) -> dict:
    return {"tick": game.state.tick, "state_hash": digest(game.state), "state": value(game.state)}


class Capture:
    def __init__(self, root: Path, *, source: str, config: dict, match_id: str | None = None,
                 attempt_id: str | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = self.root / "manifest.json"
        self.manifest = json.loads(manifest.read_text()) if manifest.exists() else {
            "schema_version": VERSION, "match_id": match_id or uuid.uuid4().hex,
            "attempt_id": attempt_id or uuid.uuid4().hex, "source": source, "created_at": utc(),
            "config": value(config), "config_hash": digest(config), "software": provenance(),
            "status": "running", "capabilities": {"causal_damage": False,
                "causal_damage_reason": "engine does not export complete causal damage events",
                "compute_cost": False, "compute_cost_reason": "not reported by match runtime"},
            "capture_errors": [], "segments": []}
        if self.manifest["config_hash"] != digest(config):
            raise ValueError("capture configuration changed while resuming a match")
        self.segment = uuid.uuid4().hex
        self.manifest["segments"].append({"id": self.segment, "started_at": utc()})
        self.counts = {t: sum(1 for _ in (self.root / f"{t}.jsonl").open())
                       if (self.root / f"{t}.jsonl").exists() else 0 for t in TABLES}
        self._files = {}
        self._lock = threading.RLock()
        if not (self.root / "source").exists():
            package = Path(__file__).parent
            for path in package.rglob("*"):
                if path.is_file() and path.suffix in (".py", ".js", ".html") and "__pycache__" not in path.parts:
                    target = self.root / "source" / "cr_arena" / path.relative_to(package)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
            for name in ("uv.lock", "pyproject.toml"):
                if (package.parent / name).is_file():
                    shutil.copy2(package.parent / name, self.root / "source" / name)
        atomic_json(manifest, self.manifest)
        self.emit("events", {"event": "segment_started"})

    def emit(self, table: str, data: dict) -> str | None:
        with self._lock:
            return self._emit(table, data)

    def _emit(self, table: str, data: dict) -> str | None:
        try:
            seq = self.counts[table]
            identity = f"{self.manifest['attempt_id']}:{self.manifest['source']}:{table}:{seq}"
            record = Record(VERSION, identity, table, self.manifest["match_id"], self.manifest["attempt_id"],
                            self.manifest["source"], self.segment, seq, utc(), time.monotonic_ns(), value(data))
            f = self._files.get(table)
            if f is None:
                f = self._files[table] = (self.root / f"{table}.jsonl").open("ab", buffering=0)
            f.write(msgspec.json.encode(record) + b"\n")
            self.counts[table] += 1
            return identity
        except (OSError, TypeError, ValueError) as exc:
            self.manifest["capture_errors"].append(f"{table}: {type(exc).__name__}: {exc}")
            return None

    def snapshot(self, game, *, phase: str, decision_id=None):
        return self.emit("states", {**state_data(game), "phase": phase, "decision_id": decision_id})

    def observe(self, game, team, decision_id, text, moves, **extra):
        return self.emit("observations", {"decision_id": decision_id, "team": team, **state_data(game),
                         "text": text, "moves": [move_data(game, team, m) for m in moves],
                         "delivery": "server_response_created", **extra})

    def command(self, game, team, decision_id, move, **extra):
        return self.emit("commands", {"decision_id": decision_id, "tick": game.state.tick,
                         "move": move_data(game, team, move), "team": team, **extra})

    def finish(self, game, *, status: str, result=None, error=None):
        self.snapshot(game, phase="final")
        self.emit("matches", {"status": status, "result": result, "error": error, **state_data(game)})
        self.manifest.update(status=status, finished_at=utc(), counts=self.counts)
        self.close()

    def close(self):
        for f in self._files.values():
            f.close()
        self._files.clear()
        atomic_json(self.root / "manifest.json", self.manifest)


class GameTelemetry:
    """Observer used identically by the local loop and trusted hosted replay."""
    def __init__(self, capture: Capture, game):
        from royalegym.protocol import ElixirLaw
        self.capture, self.game = capture, game
        self.law = ElixirLaw.load()
        self.fine = [self.law.seed_fine(p.elixir_milli) for p in game.state.players]
        self.exact = not bool(game.command_delay_ticks)
        capture.manifest["engine"] = {"arena": value(game.arena), "rules": value(game.rules),
                                       "cards": value(game.cards), "elixir_law": value(self.law)}
        capture.snapshot(game, phase="initial")

    def tick(self, before, after, commands, results):
        from royalegym.protocol import DeployStatus
        law = self.law
        spent = [0, 0]
        for cmd, res in zip(commands, results):
            p = before.players[cmd.team]
            cost = p.hand_costs[cmd.hand_slot] if hasattr(cmd, "hand_slot") else None
            # DeployCommand uses slot in the current protocol.
            if cost is None:
                cost = p.hand_costs[cmd.slot]
            if res.status == DeployStatus.OK:
                spent[cmd.team] += cost
            self.capture.emit("events", {"event": "deployment", "tick": before.tick,
                "application_tick": after.tick, "command": value(cmd), "result": value(res), "cost": cost})
        resources = []
        for team in (0, 1):
            gain = law.gain(law.rate_at(before.tick, before.regular_ticks, before.overtime))
            uncapped = self.fine[team] - spent[team] * law.scale + gain
            overflow = max(0, uncapped - law.cap_fine)
            fine = min(law.cap_fine, uncapped)
            matches = law.to_milli(fine) == after.players[team].elixir_milli
            self.exact = self.exact and matches
            resources.append({"team": team, "spent_elixir": spent[team], "gain_fine": gain,
                "overflow_fine": overflow if self.exact else None, "scale": law.scale,
                "elixir_milli": after.players[team].elixir_milli, "at_cap": fine == law.cap_fine,
                "exact": self.exact, "missing_reason": None if self.exact else "resource law did not match engine"})
            self.fine[team] = fine
        self.capture.emit("events", {"event": "engine_tick", "tick": before.tick,
            "end_tick": after.tick, "tick_ms": before.tick_ms, "resources": resources,
            "players": value(after.players), "game_over": after.game_over, "winner": after.winner})


def schema() -> dict:
    return msgspec.json.schema(Record)


def usage_metrics(data: dict, *, provider: str = "") -> dict:
    """Normalize without assuming unavailable counts are zero or adding nested totals."""
    def pick(*keys):
        return next((data[k] for k in keys if isinstance(data.get(k), (int, float))), None)
    details = data.get("output_tokens_details") or data.get("completion_tokens_details") or {}
    prompt = data.get("prompt_tokens_details") or {}
    return {"input_tokens": pick("input_tokens", "prompt_tokens", "in"),
            "output_tokens": pick("output_tokens", "completion_tokens", "out"),
            "cache_read_tokens": pick("cache_read_input_tokens", "cache_read")
                                  if "cache_read_input_tokens" in data or "cache_read" in data else prompt.get("cached_tokens"),
            "cache_write_tokens": pick("cache_creation_input_tokens", "cache_write"),
            "reasoning_tokens": details.get("thinking_tokens", details.get("reasoning_tokens")),
            "input_includes_cache": provider in ("openai", "openai_compat") if provider else None,
            "output_includes_reasoning": True,
            "cost_usd": pick("cost", "total_cost_usd"), "cost_source": "provider_reported",
            "compute_cost_usd": None, "missing_reason": "fields not reported by provider remain null"}
