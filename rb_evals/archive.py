"""Durable evidence collection and offline analysis for newly enrolled runs.

    uv run python -m rb_evals.archive enroll RUN_ID
    uv run python -m rb_evals.archive watch
    uv run python -m rb_evals.archive export PATH
    uv run python -m rb_evals.archive verify PATH
    uv run python -m rb_evals.archive mirror PATH DEST
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tarfile
import tempfile
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

import msgspec

from cr_arena.telemetry import (
    TABLES,
    VERSION,
    Record,
    atomic_json,
    digest,
    file_hash,
    provenance,
    usage_metrics,
    utc,
)

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"FINISHED", "ERROR", "STOPPED", "CANCELLED", "FAILED"}


def archive_root() -> Path:
    return Path(os.environ.get("ROYALEBENCH_ANALYSIS_DIR", ROOT / "runs" / "analysis"))


def durable_root() -> Path:
    return Path(os.environ.get("ROYALEBENCH_ARCHIVE_DIR", Path.home() / ".local/share/royalebench/archive"))


def safe_part(text: str) -> str:
    # IDs are never allowed to select a path outside the archive.
    if not text or text in (".", "..") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in text):
        raise ValueError(f"unsafe archive id: {text!r}")
    return text


def read_jsonl(path: Path):
    with path.open() as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError as exc:
                    raise ValueError(f"{path}:{i}: {exc}") from exc


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    os.replace(tmp, path)


def enroll(run_id: str, *, root: Path | None = None, config: dict | None = None) -> Path:
    """Explicit enrollment means watch never backfills the organization's old runs."""
    folder = (root or archive_root()) / safe_part(run_id)
    if not (folder / "manifest.json").exists():
        atomic_json(folder / "manifest.json", {"schema_version": VERSION, "run_id": run_id,
            "source": "valkyrie", "enrolled_at": utc(), "planned": config or {}, "status": "enrolled",
            "software": provenance(), "capture_errors": []})
    elif config:
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["planned"].update(config)
        atomic_json(folder / "manifest.json", manifest)
    return folder


def extract(archive: Path, target: Path):
    """Keep the original tar; safely extract regular data with no links or devices."""
    with tarfile.open(archive) as tar:
        for member in tar:
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"unsupported archive member: {member.name}")
        tar.extractall(target, filter="data")


def collect(remote, run_id: str, *, root: Path | None = None) -> dict:
    import fcntl
    folder = enroll(run_id, root=root)
    with (folder / ".collection.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _collect(remote, run_id, root=root)


def _collect(remote, run_id: str, *, root: Path | None = None) -> dict:
    folder = enroll(run_id, root=root)
    manifest = json.loads((folder / "manifest.json").read_text())
    raw = folder / "raw"
    raw.mkdir(exist_ok=True)
    gaps, transfers = [], []
    run = remote.run(run_id)
    tasks = remote.run_tasks(run_id)
    metadata = remote.run_metadata(run_id)
    for name, obj in (("run.json", run), ("tasks.json", tasks), ("metadata.json", metadata)):
        # Keep immutable metadata snapshots when retry/resume changes the service's view.
        atomic_json(raw / "metadata" / f"{digest(obj)}-{name}", obj)
        atomic_json(raw / name, obj)
    try:
        atomic_json(raw / "results.json", remote.results(run_id))
    except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
        gaps.append({"role": "results", "reason": str(exc), "retryable": True})
    try:
        write_jsonl(raw / "service_logs.jsonl", remote.all_run_logs(run_id))
    except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
        gaps.append({"role": "service_logs", "reason": str(exc), "retryable": True})
    inventory = []
    for attempts in (False, True):
        try:
            entries = remote.artifacts(run_id, attempts=attempts)
        except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
            gaps.append({"role": "artifact_listing", "attempts": attempts, "reason": str(exc), "retryable": True})
            continue
        for entry in entries:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("remote artifact escaped run directory")
            base = raw / ("previous_attempts" if attempts else "current")
            path = base / relative
            inventory.append({**entry, "attempts": attempts})
            marker = path.with_name(path.name + ".download.json")
            signature = {"size": entry.get("size"), "last_modified": entry.get("last_modified")}
            previous = json.loads(marker.read_text()) if marker.exists() else {}
            valid = (path.is_file() and previous.get("remote") == signature
                     and previous.get("sha256") == file_hash(path))
            if not valid:
                try:
                    with tempfile.TemporaryDirectory(prefix="rb-archive-") as td:
                        downloaded = Path(remote.download_artifact_attempt(run_id, str(relative), Path(td) / "download",
                                                                           attempts=attempts))
                        candidates = [p for p in downloaded.rglob(relative.name) if p.is_file()]
                        if downloaded.is_file():
                            candidates = [downloaded]
                        if len(candidates) != 1:
                            raise ValueError(f"expected one file for {relative}, got {len(candidates)}")
                        incoming = candidates[0]
                        if entry.get("size") is not None and incoming.stat().st_size != entry["size"]:
                            raise ValueError("download size mismatch")
                        path.parent.mkdir(parents=True, exist_ok=True)
                        if path.exists():
                            old = raw / "replaced" / file_hash(path) / path.name
                            old.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(path, old)
                        shutil.copy2(incoming, path.with_name(path.name + ".part"))
                        os.replace(path.with_name(path.name + ".part"), path)
                    atomic_json(marker, {"remote": signature, "sha256": file_hash(path)})
                except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
                    gaps.append({"role": str(relative), "attempts": attempts, "reason": str(exc), "retryable": True})
                    continue
            if path.name.endswith((".tar.gz", ".tgz")):
                extracted = path.with_name(path.name + ".extracted")
                stamp = extracted / ".archive-sha256"
                if not stamp.exists() or stamp.read_text() != file_hash(path):
                    try:
                        with tempfile.TemporaryDirectory(dir=path.parent) as td:
                            extract(path, Path(td) / "data")
                            shutil.rmtree(extracted, ignore_errors=True)
                            shutil.move(Path(td) / "data", extracted)
                        stamp.write_text(file_hash(path))
                    except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
                        gaps.append({"role": str(relative), "reason": f"extraction: {exc}", "retryable": True})
            transfers.append(str(path.relative_to(folder)))
    atomic_json(raw / "artifact_listing.json", inventory)
    for task in tasks:
        if task.get("status") not in TERMINAL:
            continue
        paths = [e["path"] for e in inventory if not e["attempts"] and e["path"].startswith(task["task_id"] + "/")]
        for role in ("agent_output",):
            if not any(role in p for p in paths):
                gaps.append({"role": role, "task_id": task["task_id"],
                             "reason": "not present in service artifact listing", "retryable": True})
    manifest.update(status=run.get("status"), collected_at=utc(), task_count=len(tasks),
                    metadata=metadata, task_statuses=tasks, collection_gaps=gaps)
    atomic_json(folder / "manifest.json", manifest)
    return seal_bundle(folder)


def harness_records(trajectory: Path, identity: dict, observations: list[dict] | None = None):
    """Normalize Claude streams once per message, keeping latest cumulative usage.

    Unsupported harnesses retain raw output and produce explicit capability gaps.
    """
    messages, init = {}, {}
    by_text = defaultdict(list)
    for obs in observations or []:
        by_text[obs["data"]["text"].strip()].append(obs)
    active = None
    for event in read_jsonl(trajectory):
        tool_result = event.get("tool_use_result")
        if isinstance(tool_result, dict) and isinstance(tool_result.get("stdout"), str):
            candidates = by_text.get(tool_result["stdout"].strip(), [])
            decisions = {c["data"]["decision_id"] for c in candidates}
            if len(decisions) == 1:
                active = {"decision_id": next(iter(decisions)), "observation_ids": [c["record_id"] for c in candidates],
                          "team": candidates[0]["data"]["team"], "provenance": "exact_observation_text"}
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        message = event.get("message") or {}
        if event.get("type") != "assistant" or not isinstance(message, dict):
            continue
        mid = message.get("id")
        if not mid:
            continue
        item = messages.setdefault(mid, {"usage": {}, "events": [], "time": event.get("timestamp")})
        item.setdefault("decision_link", active)
        item["events"].append(event)
        for k, v in (message.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                item["usage"][k] = max(item["usage"].get(k, 0), v)
            else:
                item["usage"][k] = v
        item["model"] = message.get("model")
        item["request_id"] = event.get("request_id")
    totals_path = trajectory.with_name("metrics_total.json")
    totals = json.loads(totals_path.read_text()) if totals_path.exists() else {}
    stream_output = sum(item["usage"].get("output_tokens", 0) for item in messages.values())
    partial_output = isinstance(totals.get("output_tokens"), (int, float)) and totals["output_tokens"] != stream_output
    for sequence, (mid, item) in enumerate(messages.items()):
        usage = usage_metrics(item["usage"], provider="anthropic")
        if partial_output:
            usage.update(output_tokens_reported=usage["output_tokens"], output_tokens=None,
                         output_tokens_missing_reason="Claude stream per-message counters do not reconcile to final harness usage")
        yield {"schema_version": VERSION, "record_id": f"{identity['attempt_id']}:harness:{mid}",
            "table": "model_calls", "match_id": identity["match_id"], "attempt_id": identity["attempt_id"],
            "source": "harness", "segment_id": "harness", "sequence": sequence,
            "utc": item["time"], "monotonic_ns": None,
            "data": {"message_id": mid, "request_id": item["request_id"], "resolved_model": item["model"],
                "usage": usage, "raw_events": item["events"],
                "harness_version": init.get("claude_code_version"), "effective_settings": {
                    k: init.get(k) for k in ("per_turn_effort_active", "ultrathink_available")},
                "duration_s": None, "duration_missing_reason": "stream does not report full provider call duration",
                "decision_id": item["decision_link"]["decision_id"] if item["decision_link"] else None,
                "team": item["decision_link"]["team"] if item["decision_link"] else None,
                "decision_link": item["decision_link"],
                "decision_link_reason": None if item["decision_link"] else "no exact prior observation match; raw tool IDs retained"}}


def normalize(folder: Path) -> tuple[dict, list]:
    rows = {t: {} for t in TABLES}
    gaps = []
    run_manifest = json.loads((folder / "manifest.json").read_text())
    roots = [folder] if run_manifest.get("match_id") else []
    raw = folder / "raw"
    captures = []
    if raw.exists():
        roots += sorted({p.parent for p in raw.rglob("manifest.json") if "replaced" not in p.parts
                         and json.loads(p.read_text()).get("match_id")})
    for capture_root in roots:
        manifest_path = capture_root / "manifest.json"
        if not manifest_path.exists():
            gaps.append({"role": str(capture_root), "reason": "capture manifest missing"})
            continue
        identity = json.loads(manifest_path.read_text())
        captures.append({"path": str(capture_root.relative_to(folder)), **identity})
        gaps.extend({"role": "capture", "reason": e} for e in identity.get("capture_errors", []))
        if identity.get("source") in ("local", "verifier", "referee"):
            replay = capture_root / "replay.msgpack" if identity["source"] == "local" else capture_root.parent / "replay.msgpack"
            if not replay.exists():
                gaps.append({"role": "replay", "attempt_id": identity["attempt_id"], "reason": "attempt replay absent"})
        for table in TABLES:
            p = capture_root / f"{table}.jsonl"
            if p.exists():
                try:
                    for row in read_jsonl(p):
                        msgspec.convert(row, type=Record)
                        row["run_id"] = run_manifest.get("run_id")
                        row["task_id"] = identity.get("config", {}).get("task_id") or identity.get("config", {}).get("id")
                        if table == "matches":
                            row["data"]["capture_config"] = identity.get("config", {})
                        row["data"]["raw_path"] = str(p.relative_to(folder))
                        old = rows[table].get(row["record_id"])
                        if old is not None and old != row:
                            raise ValueError("conflicting record ID")
                        rows[table][row["record_id"]] = row
                except (ValueError, msgspec.ValidationError) as exc:
                    gaps.append({"role": str(p.relative_to(folder)), "reason": str(exc)})
    if raw.exists():
        for p in raw.rglob("trajectory.jsonl"):
            if "replaced" in p.parts:
                continue
            # Match the transcript to the referee/verifier capture inside this task/attempt directory.
            depth = 4 if p.relative_to(folder).parts[1] == "previous_attempts" else 3
            linked = [c for c in captures if Path(c["path"]).parts[:depth] == p.relative_to(folder).parts[:depth]]
            if not linked:
                gaps.append({"role": str(p.relative_to(folder)), "reason": "no capture identity for transcript"})
                continue
            observations = [r for r in rows["observations"].values() if r["attempt_id"] == linked[0]["attempt_id"]]
            calls = list(harness_records(p, linked[0], observations))
            if not calls:
                gaps.append({"role": "model_call_adapter", "raw_path": str(p.relative_to(folder)),
                             "reason": "no supported message records; full raw trajectory retained"})
            for row in calls:
                row["run_id"] = run_manifest.get("run_id")
                row["task_id"] = linked[0].get("config", {}).get("task_id") or linked[0].get("config", {}).get("id")
                rows["model_calls"][row["record_id"]] = row
    # Timing is authoritative in the online accepted-action log, not simulated replay.
    for c in captures:
        path = folder / c["path"]
        action_log = path.parent / "actions.jsonl"
        if c.get("source") != "referee" or not action_log.exists():
            continue
        timings = {e["tick"]: e for e in read_jsonl(action_log)}
        for r in rows["commands"].values():
            d = r["data"]
            if (r["attempt_id"] == c["attempt_id"] and d.get("kind") == "application"
                    and d["team"] == c["config"]["agent_team"] and (timing := timings.get(d["tick"]))):
                d.update(latency_s=timing.get("think_s"), wall=timing.get("wall"),
                         timing_source="first_observation_to_command_server_monotonic",
                         observation_id=timing.get("observation_id"))
    # Keep exact observation-to-action links separate from inferred model explanations.
    links = []
    for r in rows["commands"].values():
        if oid := r["data"].get("observation_id"):
            links.append({"command_id": r["record_id"], "observation_id": oid, "provenance": "recorded"})
    for r in rows["model_calls"].values():
        if link := r["data"].get("decision_link"):
            links.append({"model_call_id": r["record_id"], **link})
    if folder.joinpath("manifest.json").exists():
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest.get("source") == "valkyrie":
            available = {c["config"].get("task_id", c["config"].get("id")) for c in captures if c.get("source") in ("verifier", "referee")}
            for task in manifest.get("task_statuses", []):
                if task.get("status") in TERMINAL and task["task_id"] not in available:
                    gaps.append({"role": "telemetry", "task_id": task["task_id"], "reason": "trusted task capture absent"})
            for c in captures:
                if c.get("source") != "referee" or any(r["attempt_id"] == c["attempt_id"] for r in rows["matches"].values()):
                    continue
                task = next((t for t in manifest.get("task_statuses", []) if t["task_id"] == c["config"].get("task_id", c["config"].get("id"))), {})
                if task.get("status") not in TERMINAL:
                    continue
                states = [r for r in rows["states"].values() if r["attempt_id"] == c["attempt_id"]]
                if states:
                    last = max(states, key=lambda r: r["data"]["tick"])
                    rid = c["attempt_id"] + ":collector:termination"
                    rows["matches"][rid] = {**last, "table": "matches", "record_id": rid, "source": "collector",
                        "data": {"status": "partial", "provenance": "external_task_termination", "task": task,
                                 "termination_tick": last["data"]["tick"], "capture_config": c["config"],
                                 "original_reward": None, "reward_source": "raw/results.json"}}
    write_jsonl(folder / "normalized" / "links.jsonl", links)
    normalized = folder / "normalized"
    for table in TABLES:
        write_jsonl(normalized / f"{table}.jsonl", sorted(rows[table].values(), key=lambda r: r["record_id"]))
    return rows, gaps


def export_tables(folder: Path, rows: dict):
    out = folder / "derived" / "v1"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((folder / "manifest.json").read_text())
    args = (manifest.get("metadata") or {}).get("benchmark_arguments") or {}
    contract = args.get("contract") or {}
    context = {"run_id": manifest.get("run_id"), "dataset_version": (args.get("dataset_version") or {}).get("id"),
               "model": contract.get("model"), "harness": contract.get("name"),
               "analysis_version": "v1", "cohort_id": manifest.get("planned", {}).get("cohort_id")}
    configurations = {r["attempt_id"]: r["data"].get("capture_config", {}) for r in rows["matches"].values()}
    # Prefer trusted reconstructed gameplay over online diagnostic duplicates.
    verified = {r["attempt_id"] for r in rows["commands"].values() if r["source"] == "verifier"}
    commands = [r for r in rows["commands"].values() if r["data"].get("kind") == "application"
                and (r["source"] == "verifier" or r["attempt_id"] not in verified)]
    decisions = []
    groups = defaultdict(list)
    for r in commands:
        d, mv = r["data"], r["data"]["move"]
        item = {"match_id": r["match_id"], "attempt_id": r["attempt_id"], "decision_id": d["decision_id"],
            "team": d["team"], "tick": d["tick"], "end_tick": d.get("end_tick"),
            "card": mv["card"], "lane": mv["lane"], "kind": mv["kind"], "cost": mv["cost"],
            "x": mv["x"], "y": mv["y"], "accepted": d.get("accepted"),
            "action_source": d.get("action_source"), "latency_s": d.get("latency_s"),
            "ok": d.get("ok", True), "error": d.get("error"),
            "raw_path": d.get("raw_path")}
        decisions.append(item)
        groups[(r["match_id"], r["attempt_id"], d["team"])].append(item)
    timeline = []
    resource_totals = defaultdict(lambda: {"overflow_fine": 0, "at_cap_ticks": 0, "ticks": 0, "exact": True})
    for r in rows["events"].values():
        d = r["data"]
        if d.get("event") != "engine_tick" or (r["source"] != "verifier" and r["attempt_id"] in verified):
            continue
        for p, resource in zip(d["players"], d["resources"]):
            timeline.append({"match_id": r["match_id"], "attempt_id": r["attempt_id"], "team": p["team"],
                "tick": d["end_tick"], "game_s": d["end_tick"] * d["tick_ms"] / 1000,
                "elixir_milli": p["elixir_milli"], "tower_hp": sum(p["tower_hp"]), "crowns": p["crowns"]})
            key = (r["match_id"], r["attempt_id"], p["team"])
            total = resource_totals[key]
            total["exact"] &= resource["exact"]
            total["overflow_fine"] += resource["overflow_fine"] or 0
            total["at_cap_ticks"] += int(resource["at_cap"])
            total.update(ticks=total["ticks"] + 1, scale=resource["scale"], tick_ms=d["tick_ms"])
    players = []
    for key, ds in groups.items():
        asked = [d for d in ds if d["action_source"] not in ("forced_wait", "verifier_wait")]
        resource = resource_totals[key]
        players.append({"match_id": key[0], "attempt_id": key[1], "team": key[2], "intervals": len(ds),
            "choices": len(asked), "voluntary_waits": sum(d["kind"] == "WAIT" and d["ok"] for d in asked),
            "error_waits": sum(not d["ok"] for d in asked),
            "wait_rate": sum(d["kind"] == "WAIT" and d["ok"] for d in asked) / len(asked) if asked else None,
            "elixir_spent": sum(d["cost"] for d in ds if d["accepted"]),
            "overflow_elixir": resource["overflow_fine"] / resource["scale"] if resource["ticks"] and resource["exact"] else None,
            "at_cap_s": resource["at_cap_ticks"] * resource["tick_ms"] / 1000 if resource["ticks"] and resource["exact"] else None,
            "resource_exact": resource["exact"] if resource["ticks"] else None})
    matches = [{"run_id": r.get("run_id"), "task_id": r.get("task_id"),
                "match_id": r["match_id"], "attempt_id": r["attempt_id"], **r["data"]} for r in rows["matches"].values()]
    calls = [{"match_id": r["match_id"], "attempt_id": r["attempt_id"], "record_id": r["record_id"], **r["data"]}
             for r in rows["model_calls"].values()]
    # Harness totals are authoritative for billing; per-message counters are reconciled, never added to totals.
    usage = []
    candidates = sorted((folder / "raw").rglob("metrics_total.json")) if (folder / "raw").exists() else []
    candidates += [p for p in sorted((folder / "raw").rglob("summary.json"))
                   if not p.with_name("metrics_total.json").exists()] if (folder / "raw").exists() else []
    for p in candidates:
        if "replaced" in p.parts:
            continue
        data = json.loads(p.read_text())
        data = data.get("metrics", data)
        scope = p.relative_to(folder).parts[:4] if "previous_attempts" in p.parts else p.relative_to(folder).parts[:3]
        linked_calls = [c for c in calls if any(Path(e["data"].get("raw_path", "")).parts[:len(scope)] == scope
                       for e in rows["commands"].values() if e["attempt_id"] == c["attempt_id"])]
        normalized_usage = usage_metrics(data, provider="anthropic")
        reconciliation = {}
        for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
            known = [c["usage"][key] for c in linked_calls if (c.get("usage") or {}).get(key) is not None]
            total = sum(known) if known else None
            reconciliation[key] = {"calls": total, "harness": normalized_usage[key],
                                   "matches": total == normalized_usage[key] if total is not None else None}
        usage.append({"raw_path": str(p.relative_to(folder)), **normalized_usage,
                      "wall_s": data.get("wall_clock_duration"), "provenance": "harness_total",
                      "reconciliation": reconciliation, "message_count": len(linked_calls)})
    if not usage:
        for key, ds in groups.items():
            cs = [c for c in calls if c["attempt_id"] == key[1] and c.get("team") == key[2]]
            usage.append({"match_id": key[0], "attempt_id": key[1], "team": key[2],
                "cost_usd": sum(c["reported_cost_usd"] for c in cs if c.get("reported_cost_usd") is not None) if any(c.get("reported_cost_usd") is not None for c in cs) else None,
                "calls": len(cs), "cost_known_calls": sum(c.get("reported_cost_usd") is not None for c in cs),
                "provenance": "local_recorded_calls"})
    timings = [{"match_id": d["match_id"], "attempt_id": d["attempt_id"], "team": d["team"],
                "decision_id": d["decision_id"], "tick": d["tick"], "duration_s": d["latency_s"]}
               for d in decisions if d["latency_s"] is not None]
    behavior = Counter((d["attempt_id"], d["team"], d["card"], d["lane"]) for d in decisions if d["accepted"] and d["kind"] != "WAIT")
    placements = [{"attempt_id": a, "team": t, "card": c, "lane": l, "count": n} for (a,t,c,l),n in sorted(behavior.items())]
    outcomes = []
    results_path = folder / "raw" / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    evaluated = results.get("evaluation_results") or {}
    for task in manifest.get("task_statuses", []):
        tid = task["task_id"]
        e = evaluated.get(tid) or {}
        rewards = e.get("rewards") or {}
        outcomes.append({"task_id": tid, "status": task.get("status"), "error": task.get("error_message"),
            "failure_category": task.get("failure_category"), "reward": rewards.get("reward"),
            "crowns_for": rewards.get("crowns_for"), "crowns_against": rewards.get("crowns_against"),
            "integrity": rewards.get("integrity"), "completed": rewards.get("completed"),
            "enemy_tower_damage_frac": rewards.get("enemy_tower_damage_frac"),
            "own_tower_damage_frac": rewards.get("own_tower_damage_frac"),
            "agent_s": (e.get("task_breakdown") or {}).get("agent_run_duration")})
    for name, data in (("decisions", decisions), ("players", players), ("timeline", timeline), ("matches", matches),
                       ("model_calls", calls), ("usage", usage), ("timing", timings), ("placements", placements),
                       ("outcomes", outcomes)):
        if name == "model_calls":
            data = [{**{k: v for k, v in item.items() if k not in ("request", "response", "raw_events")},
                     **(item.get("usage") or {}), "raw_record": "normalized/model_calls.jsonl"} for item in data]
        enriched = []
        for item in data:
            actor = {}
            config = configurations.get(item.get("attempt_id"), {})
            team = item.get("team")
            if team in (0, 1) and "agent_team" in config:
                is_agent = team == config["agent_team"]
                actor = {"actor_role": "agent" if is_agent else "opponent",
                         "actor_name": context["model"] if is_agent else config.get("opponent"),
                         "actor_model": context["model"] if is_agent else None}
            elif team in (0, 1) and len(config.get("players", [])) == 2:
                spec = config["players"][team]
                actor = {"actor_role": "player", "actor_name": spec.get("name"), "actor_model": spec.get("model")}
            enriched.append({**context, **actor, **item})
        data = enriched
        write_jsonl(out / f"{name}.jsonl", data)
        fields = sorted({k for r in data for k in r})
        with (out / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fields)
            w.writeheader()
            w.writerows({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in data)
    atomic_json(out / "analysis.json", {"analysis_version": "v1", "schema_version": VERSION,
        "counts": {"matches": len(matches), "players": len(players), "decisions": len(decisions), "calls": len(calls)},
        "aggregation": "per attempt; no automatic pooling across datasets, cohorts, seeds or models",
        "missingness": "null means unavailable; no imputation; reasoning included in output where provider reports it"})


def seal_bundle(folder: Path) -> dict:
    folder = Path(folder)
    # Analysis must remain reproducible even while the implementation is uncommitted.
    sources = list(Path(__file__).resolve().parent.glob("*.py")) + [ROOT / "cr_arena/telemetry.py"]
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in sources}
    collector_hash = digest(hashes)
    collector = folder / "collector" / collector_hash
    if not collector.exists():
        for p in sources:
            target = collector / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
        for name in ("uv.lock", "pyproject.toml"):
            if (ROOT / name).exists():
                shutil.copy2(ROOT / name, collector / name)
    atomic_json(folder / "collector_manifest.json", {"analysis_version": "v1", "schema_version": VERSION,
                "source_directory": str(collector.relative_to(folder)), "source_sha256": hashes})
    rows, gaps = normalize(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    export_tables(folder, rows)
    gaps.extend(manifest.get("collection_gaps", []))
    for table in ("commands", "states"):
        if not rows[table]:
            gaps.append({"role": table, "reason": f"no {table} records"})
    if not rows["matches"]:
        gaps.append({"role": "matches", "reason": "no terminal gameplay record"})
    if not rows["observations"]:
        gaps.append({"role": "observations", "reason": "no captured observation"})
    if not any(folder.rglob("replay.msgpack")):
        gaps.append({"role": "replay", "reason": "full simulator replay absent"})
    artifacts = [{"path": str(p.relative_to(folder)), "size": p.stat().st_size, "sha256": file_hash(p)}
                 for p in sorted(folder.rglob("*")) if p.is_file()
                 and p.name not in ("artifacts.jsonl", "collection_report.json", ".collection.lock") and not p.name.endswith(".part")]
    report = {"schema_version": VERSION, "complete": not gaps, "gaps": gaps,
              "counts": {t: len(rs) for t, rs in rows.items()}, "artifact_count": len(artifacts) + 1}
    atomic_json(folder / "collection_report.json", report)
    artifacts.append({"path": "collection_report.json", "size": (folder / "collection_report.json").stat().st_size,
                      "sha256": file_hash(folder / "collection_report.json")})
    write_jsonl(folder / "artifacts.jsonl", artifacts)
    return report


def verify_bundle(folder: Path) -> list[str]:
    errors = []
    for item in read_jsonl(folder / "artifacts.jsonl"):
        p = folder / item["path"]
        if not p.resolve().is_relative_to(folder.resolve()) or not p.is_file() or p.stat().st_size != item["size"] or file_hash(p) != item["sha256"]:
            errors.append(item["path"])
    return errors


def mirror(folder: Path, destination: Path):
    errors = verify_bundle(folder)
    if errors:
        raise ValueError(f"source checksum failures: {errors}")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / folder.name
    if target.exists() and verify_bundle(target):
        raise ValueError(f"existing archive failed checksum verification: {target}")
    with tempfile.TemporaryDirectory(dir=destination) as tmp:
        staged = Path(tmp) / folder.name
        shutil.copytree(folder, staged)
        if verify_bundle(staged):
            raise ValueError("archive restore verification failed")
        if target.exists():
            # Never replace an existing durable snapshot with a different bundle.
            if file_hash(target / "artifacts.jsonl") == file_hash(folder / "artifacts.jsonl"):
                return target
            target = destination / f"{folder.name}-{file_hash(folder / 'artifacts.jsonl')[:12]}"
        if target.exists() and verify_bundle(target):
            raise ValueError(f"existing archive failed checksum verification: {target}")
        if not target.exists():
            shutil.move(staged, target)
    return target


class ArchiveWorker:
    """Watches only explicitly enrolled runs; works without a browser session."""
    def __init__(self, remote, root: Path | None = None):
        self.remote, self.root = remote, root or archive_root()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="rb-archive", daemon=True)
        self.last = {}
        self.mirrored = {}

    def run_once(self):
        for p in self.root.glob("*/manifest.json"):
            m = json.loads(p.read_text())
            if m.get("source") != "valkyrie":
                continue
            rid = m["run_id"]
            try:
                state = self.remote.run(rid)
                fingerprint = digest(state)
                report_path = p.parent / "collection_report.json"
                if self.last.get(rid) == fingerprint and report_path.exists():
                    previous = json.loads(report_path.read_text())
                    settled = previous.get("complete") or (state.get("status") in TERMINAL
                        and not any(g.get("retryable") for g in previous.get("gaps", [])))
                    if settled:
                        continue
                collect(self.remote, rid, root=self.root)
                self.last[rid] = fingerprint
                if state.get("status") in TERMINAL:
                    content = digest([a for a in read_jsonl(p.parent / "artifacts.jsonl") if a["path"] != "manifest.json"])
                    if self.mirrored.get(rid) != content:
                        mirror(p.parent, durable_root())
                        self.mirrored[rid] = content
            except Exception as exc:  # noqa: BLE001 - archive gaps must survive provider/codec failures
                atomic_json(p.parent / "collection_error.json", {"utc": utc(), "error": str(exc), "retryable": True})

    def run(self):
        while not self.stop.is_set():
            self.run_once()
            self.stop.wait(30)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=archive_root())
    sub = ap.add_subparsers(dest="command", required=True)
    for cmd in ("enroll", "collect"):
        sub.add_parser(cmd).add_argument("run_id")
    for cmd in ("export", "verify"):
        sub.add_parser(cmd).add_argument("path", type=Path)
    p = sub.add_parser("mirror")
    p.add_argument("path", type=Path)
    p.add_argument("destination", type=Path)
    p = sub.add_parser("watch")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=float, default=30)
    args = ap.parse_args()
    from .valkyrie import Valkyrie
    if args.command == "enroll":
        print(enroll(args.run_id, root=args.root))
    elif args.command == "collect":
        report = collect(Valkyrie(), args.run_id, root=args.root)
        print(json.dumps(report, indent=2))
        print("archive:", mirror(args.root / args.run_id, durable_root()))
    elif args.command == "export":
        print(json.dumps(seal_bundle(args.path), indent=2))
    elif args.command == "verify":
        errors = verify_bundle(args.path)
        print(json.dumps({"checksum_errors": errors}))
        raise SystemExit(bool(errors))
    elif args.command == "mirror":
        print(mirror(args.path, args.destination))
    else:
        worker = ArchiveWorker(Valkyrie(), args.root)
        while True:
            worker.run_once()
            if args.once:
                break
            time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
