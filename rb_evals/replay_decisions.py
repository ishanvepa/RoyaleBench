"""Link recorded agent messages to exact referee observations for replay playback."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(v.get("text", v) if isinstance(v, dict) else v) for v in value)
    return ""


def _outputs(value) -> list[str]:
    """Unwrap mini-SWE shell results while retaining Claude's plain stdout."""
    text = _text(value).strip()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    return [text] + ([data[k].strip() for k in ("output", "stdout") if isinstance(data.get(k), str)]
                     if isinstance(data, dict) else [])


def read_decisions(root: Path, observations: list[dict]) -> list[dict]:
    """Only exact observed text establishes a simulation tick; never guess from wall time.

    Handles stock mini-SWE trajectories and Claude Code JSONL streams. Session/setup
    messages and unmatched output are not presented as synchronized game decisions.
    """
    by_text: dict[str, set[tuple[int, int]]] = {}
    for obs in observations:
        text, tick, team = obs.get("text"), obs.get("tick"), obs.get("team")
        if isinstance(text, str) and text.strip() and type(tick) is int and team in (0, 1):
            by_text.setdefault(text.strip(), set()).add((tick, team))

    groups: dict[tuple[int, int], dict] = {}
    active = None
    seen = set()

    def observe(content):
        nonlocal active
        outputs = _outputs(content)
        matches = {identity for text, ids in by_text.items()
                   if any(text == output or text in output for output in outputs) for identity in ids}
        if len(matches) == 1:
            active = next(iter(matches))
        elif matches or any(re.search(r"(?:^|\n)(?:DECISION \d+|GAME OVER)", output) for output in outputs):
            # Repeated text from different ticks/attempts is ambiguous. A game-over
            # response also ends the decision; final commentary has no earlier tick.
            active = None

    def add(kind, title, text, message_id=None):
        if active is None or not isinstance(text, str) or not text.strip():
            return
        key = (active, message_id, kind, text)
        if key in seen:
            return
        seen.add(key)
        tick, team = active
        group = groups.setdefault(active, {"tick": tick, "team": team, "steps": []})
        group["steps"].append({"kind": kind, "title": title, "text": text})

    candidates = sorted(set(root.rglob("trajectory.json")) | set(root.rglob("*.traj.json")))
    for path in candidates:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not str(data.get("trajectory_format", "")).startswith("mini-swe-agent"):
            continue
        for i, message in enumerate(data.get("messages", [])):
            if not isinstance(message, dict):
                continue
            if message.get("role") in ("tool", "user"):
                observe(message.get("content"))
            elif message.get("role") == "assistant":
                add("thinking", "Recorded reasoning", _text(message.get("reasoning_content")), i)
                add("text", "Agent", _text(message.get("content")), i)
                calls = message.get("tool_calls") or []
                if message.get("function_call"):
                    calls = [*calls, {"function": message["function_call"]}]
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function") or {}
                    if not isinstance(function, dict):
                        continue
                    arguments = function.get("arguments") or ""
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            pass
                    command = arguments.get("command") if isinstance(arguments, dict) else None
                    add("tool_use", f"Tool: {function.get('name', 'shell')}",
                        command or (json.dumps(arguments, ensure_ascii=False) if not isinstance(arguments, str) else arguments), i)
        return sorted(groups.values(), key=lambda d: (d["tick"], d["team"]))

    path = next(iter(sorted(root.rglob("trajectory.jsonl"))), None)
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            message = event.get("message") or {}
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if event.get("type") == "user":
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            observe(block.get("content"))
                if isinstance(event.get("tool_use_result"), dict):
                    observe(event["tool_use_result"].get("stdout"))
            elif event.get("type") == "assistant":
                if isinstance(content, str):
                    add("text", "Agent", content, message.get("id"))
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict):
                        continue
                    kind = block.get("type")
                    if kind in ("text", "thinking"):
                        add(kind, "Recorded reasoning" if kind == "thinking" else "Agent",
                            block.get(kind, ""), message.get("id"))
                    elif kind == "tool_use":
                        inputs = block.get("input") or {}
                        add(kind, f"Tool: {block.get('name', '?')}", (inputs.get("command") if isinstance(inputs, dict) else None) or
                            json.dumps(inputs, ensure_ascii=False), block.get("id"))
    return sorted(groups.values(), key=lambda d: (d["tick"], d["team"]))
