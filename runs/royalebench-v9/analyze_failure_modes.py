"""Summarize cached v9 outcomes and command traces without launching evaluations."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

from valkyrie.sdk.task_content import task_digest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("failure-analysis.json")


def flatten(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(flatten(v.get("text", "")) for v in value if isinstance(v, dict))
    return ""


def trace_data(folder):
    path = next(folder.rglob("trajectory.jsonl"), None)
    commands, outputs, messages = [], [], []
    info = {}
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            item = e.get("item", {})
            if e.get("type") == "item.completed":
                if item.get("type") == "command_execution":
                    commands.append(item.get("command", ""))
                    outputs.append(item.get("aggregated_output", ""))
                elif item.get("type") == "agent_message":
                    messages.append(item.get("text", ""))
            message = e.get("message")
            content = message.get("content", []) if isinstance(message, dict) else []
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    inputs = b.get("input") or {}
                    if inputs.get("command"):
                        commands.append(inputs["command"])
                elif b.get("type") == "tool_result":
                    outputs.append(flatten(b.get("content")))
                elif b.get("type") == "text" and e.get("type") == "assistant":
                    messages.append(b.get("text", ""))
    else:
        path = next(folder.rglob("trajectory.json"), None)
        if path:
            data = json.loads(path.read_text(encoding="utf-8"))
            info = data.get("info") or {}
            for e in data.get("messages", []):
                if e.get("role") == "assistant":
                    messages.append(flatten(e.get("content")))
                    for call in e.get("tool_calls") or []:
                        try:
                            args = json.loads(call.get("function", {}).get("arguments", "{}"))
                        except ValueError:
                            continue
                        if args.get("command"):
                            commands.append(args["command"])
                elif e.get("role") == "tool":
                    raw = (e.get("extra") or {}).get("raw_output")
                    if raw is None:
                        try:
                            raw = json.loads(e.get("content", "{}")).get("output", "")
                        except ValueError:
                            raw = flatten(e.get("content"))
                    outputs.append(raw)
    boards = [s for s in outputs if "YOUR TOWERS:" in s]
    config = info.get("config") or {}
    return {
        "path": str(path.relative_to(ROOT)) if path else None,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path else None,
        "exit_status": info.get("exit_status"),
        "api_calls": (info.get("model_stats") or {}).get("api_calls"),
        "step_limit": (config.get("agent") or {}).get("step_limit"),
        "commands": commands,
        "game_commands": [s for s in commands if "cr" in s],
        "initial_observation": boards[0] if boards else None,
        "last_observation": boards[-1] if boards else None,
        "last_game_over": next((s for s in reversed(outputs) if "GAME OVER" in s), None),
        "final_message": messages[-1] if messages else None,
    }


def main():
    runs, attempts = [], []
    for path in sorted((ROOT / "runs/evals").glob("*/results.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        args = d.get("benchmark_arguments") or {}
        if args.get("dataset") != "royalebench-v9" or d.get("status") != "FINISHED":
            continue
        contract = args["contract"]
        run = dict(run_id=path.parent.name, model=contract.get("model"),
                   harness=contract.get("name"), revision=args.get("dataset_version"),
                   started_at=d.get("started_at"), finished_at=d.get("finished_at"),
                   score=(d.get("final_evaluation") or {}).get("final_score"),
                   results_path=str(path.relative_to(ROOT)),
                   results_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   task_errors=d.get("task_errors"), failure_categories=d.get("task_failure_categories"))
        rows = []
        for task, e in sorted(d.get("evaluation_results", {}).items()):
            r = e.get("rewards") or {}
            try:
                verifier = json.loads(e.get("metadata", {}).get("verifier_output", "{}"))
            except ValueError:
                verifier = {}
            row = dict(run_id=run["run_id"], model=run["model"], harness=run["harness"],
                       task=task, rewards=r, outcome=verifier.get("outcome"),
                       agent_caused_exit_reason=e.get("agent_caused_exit_reason"),
                       verifier_exit_code=e.get("metadata", {}).get("verifier_exit_code"),
                       trace=trace_data(path.parent / "tasks" / task))
            attempts.append(row)
            rows.append(row)
        run["summary"] = {
            "attempts": len(rows),
            "passed": sum(x["rewards"].get("reward", 0) == 1 for x in rows),
            "incomplete": sum(x["rewards"].get("completed") == 0 for x in rows),
            "integrity_failures": sum(x["rewards"].get("integrity") != 1 for x in rows),
            "with_rejections": sum(x["rewards"].get("rejected_actions", 0) > 0 for x in rows),
            "trace_exit_status": dict(Counter(x["trace"]["exit_status"] for x in rows)),
        }
        assert abs(run["score"] - 100 * run["summary"]["passed"] / len(rows)) < 1e-8
        runs.append(run)
    tasks = []
    manifest = json.loads((ROOT / "benchmarks/royalebench-v9/manifest.json").read_text())
    expected = {r["task"]:r["digest"] for r in manifest["tasks"]}
    for task in sorted({r["task"] for r in attempts}):
        rows = [r for r in attempts if r["task"] == task]
        current_digest = task_digest(ROOT / "benchmarks/royalebench-v9" / task)
        assert current_digest == expected[task], f"Source task package changed: {task}"
        tasks.append(dict(task=task, attempts=len(rows),
                          passed=sum(r["rewards"].get("reward") == 1 for r in rows),
                          incomplete=sum(r["rewards"].get("completed") == 0 for r in rows),
                          task_digest=current_digest, matches_v9_manifest=True))
    result = dict(observed_at=datetime.now(timezone.utc).isoformat(),
                  scope="Local cached FINISHED royalebench-v9 runs; no new evaluations or inference.",
                  runs=runs, tasks=tasks, attempts=attempts)
    if "--check-live" in sys.argv:
        endpoint = "http://127.0.0.1:8000/api/evals/benchmarks/royalebench-v9/ranking"
        with urllib.request.urlopen(endpoint, timeout=30) as response:
            live = json.load(response)
        assert live["runs_considered"] == len(runs)
        assert {r["task"]:(r["attempts"],r["solved"]) for r in live["rows"]} == {
            r["task"]:(r["attempts"],r["passed"]) for r in tasks}
        result["live_verification"] = dict(endpoint=endpoint, all_task_counts_match=True,
                                            runs_considered=live["runs_considered"])
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "runs": len(runs), "attempts": len(attempts),
                      "passed": sum(t["passed"] for t in tasks),
                      "incomplete": sum(t["incomplete"] for t in tasks)}, indent=2))


if __name__ == "__main__":
    main()
