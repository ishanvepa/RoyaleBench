"""Freeze public writeup evidence without credentials or new model calls.

python tools/build_writeup.py --refresh       # requires the local Evals cache
uv run python tools/build_writeup.py --replays # requires the archived demo traces
python tools/build_writeup.py --check         # works from a fresh checkout
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs/writeup.html"
ASSETS = ROOT / "docs/writeup-assets"
DATA = ASSETS / "results.json"
DATASET = "royalebench/royalebench-v9@1"
CASE = "04-critical-cycle-and-connect"
NAMES = {
    "anthropic/claude-opus-5-5": ("Claude Opus 5.5", "Opus", "Anthropic"),
    "anthropic/claude-fable-5-2": ("Claude Fable 5.2", "Fable 5.2", "Anthropic"),
    "anthropic/claude-fable-5-1": ("Claude Fable 5.1", "Fable 5.1", "Anthropic"),
    "anthropic/claude-sonnet-5-5": ("Claude Sonnet 5.5", "Sonnet", "Anthropic"),
    "anthropic/claude-haiku-5-5": ("Claude Haiku 5.5", "Haiku", "Anthropic"),
    "openai/gpt-6.1-sol": ("GPT-6.1 Sol", "Sol", "OpenAI"),
    "openai/gpt-6-astra": ("GPT-6 Astra", "Astra", "OpenAI"),
    "openai/gpt-6-luna": ("GPT-6 Luna", "Luna", "OpenAI"),
    "openai/kimi-k3.1-pro": ("Kimi K3.1 Pro", "Kimi", "Moonshot AI"),
    "openai/inkling-2-small": ("Inkling 2 Small", "Inkling", "Inkling"),
    "openai/Qwen/Qwen3.8-2.4T-A95B": ("Qwen 3.8", "Qwen", "Alibaba"),
    "openai/deepseek-v4.1-flash-1017": ("DeepSeek V4.1 Flash", "DeepSeek", "DeepSeek"),
}
TASKS = {
    "01-critical-cycle-conversion": ("Critical cycle conversion", "Conversion"),
    "01-cycle-and-connect": ("Cycle and connect", "Conversion"),
    "01-timed-spell-a": ("Timed spell", "Timing"),
    "02-reserve-counter-a": ("Reserve the counter", "Timing"),
    "02-second-wave-air-race": ("Second-wave air race", "Conversion"),
    "02-sustained-tower-race": ("Sustained tower race", "Conversion"),
    "03-bait-damage-sequence": ("Bait damage sequence", "Conversion"),
    "03-spell-placement": ("Spell placement", "Placement"),
    "03-supported-tank-conversion": ("Supported tank conversion", "Conversion"),
    "03-tower-race-b": ("Tower race: defend first", "Timing"),
    "04-critical-cycle-and-connect": ("Critical cycle and connect", "Conversion"),
    "04-split-lane-conversion": ("Split-lane conversion", "Conversion"),
    "05-successive-threats-mirror": ("Successive threats", "Resource allocation"),
    "06-unequal-threats": ("Unequal threats", "Resource allocation"),
    "07-counterpush": ("Counterpush", "Conversion"),
    "08-cycle-to-lethal-plus": ("Cycle to lethal", "Conversion"),
    "09-tower-race-defend": ("Tower-race defense", "Conversion"),
    "10-protect-the-lead": ("Protect the lead", "Resource allocation"),
    "05-hog-body-block": ("Hog body-block", "Placement"),
    "06-mini-pekka-kite": ("Mini P.E.K.K.A. kite", "Placement"),
    "07-balloon-fireball": ("Balloon Fireball", "Timing"),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(folder):
    """Use persisted prices, never a fallback zero or a newly invented rate."""
    for filename, key, source in [
        ("inference_cost.json", "cost_usd", "Persisted Modal token pricing"),
        ("token_cost.json", "cost_usd", "Persisted Codex token pricing"),
        ("logs/metrics_total.json", "cost", "Harness-reported API cost"),
    ]:
        path = folder / filename
        if path.exists():
            data = read(path)
            if data.get(key) is not None:
                return float(data[key]), source, path
    return None, "Unavailable", None


def refresh():
    manifest_path = ROOT / "benchmarks/royalebench-v9/manifest.json"
    manifest = read(manifest_path)
    difficulty_path = ROOT / "runs/royalebench-v9/difficulty.json"
    difficulty = read(difficulty_path)
    tasks = {t["task"]: dict(t) for t in manifest["tasks"]}
    expected = set(tasks)
    assert expected == set(TASKS)
    models = []
    for path in sorted((ROOT / "runs/evals").glob("*/results.json")):
        raw = read(path)
        args = raw.get("benchmark_arguments") or {}
        if (args.get("dataset_version") or {}).get("id") != DATASET:
            continue
        assert raw["status"] == "FINISHED"
        assert not raw.get("task_errors") and not raw.get("tasks_stopped")
        evaluations = raw["evaluation_results"]
        assert set(evaluations) == expected, "Partial runs cannot enter this snapshot"
        contract = args["contract"]
        model = contract["model"]
        name, short, family = NAMES[model]
        entries = {}
        for task_id, entry in sorted(evaluations.items()):
            rewards = entry["rewards"]
            assert rewards["reward"] in (0, 1)
            cost, source, cost_file = metrics(path.parent / "tasks" / task_id)
            entries[task_id] = {
                "reward": int(rewards["reward"]), "integrity": rewards.get("integrity"),
                "completed": int(rewards["completed"]),
                "rejected_actions": rewards.get("rejected_actions"), "decisions": rewards.get("decisions"),
                "agent_seconds": entry["task_breakdown"].get("agent_run_duration"),
                "cost_usd": cost, "cost_source": source,
                "cost_source_sha256": digest(cost_file) if cost_file else None,
            }
        costs = [t["cost_usd"] for t in entries.values() if t["cost_usd"] is not None]
        durations = [t["agent_seconds"] for t in entries.values() if t["agent_seconds"] is not None]
        models.append({
            "id": model, "name": name, "short": short, "family": family,
            "harness": contract["name"], "run_id": path.parent.name,
            "dataset": DATASET, "provider": args["sandbox_provider"],
            "concurrency": args["concurrency"], "started_at": raw["started_at"],
            "finished_at": raw["finished_at"], "source_sha256": digest(path),
            "inference_overrides": {k: v for k, v in (contract.get("kwargs") or {}).items()
                                    if k in {"step_limit", "cost_tracking", "reasoning_effort", "max_tokens", "temperature"}},
            "solved": sum(t["reward"] for t in entries.values()), "attempts": len(entries),
            "incomplete": sum(not t["completed"] for t in entries.values()),
            "cost_total_usd": sum(costs) if costs else None,
            "cost_per_task_usd": mean(costs) if costs else None, "cost_known": len(costs),
            "mean_agent_seconds": mean(durations) if durations else None, "tasks": entries,
        })
    models.sort(key=lambda m: (-m["solved"], m["name"]))
    assert len(models) == difficulty["runs_considered"] == 12
    for observed in difficulty["tasks"]:
        task_id = observed["task"]
        solved = sum(m["tasks"][task_id]["reward"] for m in models)
        assert solved == observed["solved"] and len(models) == observed["attempts"]
        title, capability = TASKS[task_id]
        tasks[task_id] = {k: tasks[task_id][k] for k in ("task", "source", "digest", "grading", "objective", "protocol_sha256")}
        tasks[task_id].update(title=title, capability=capability, solved=solved,
                              attempts=len(models), difficulty=observed["difficulty"])
    data = {
        "schema_version": 1, "dataset": DATASET,
        "dataset_digest": read(ROOT / "runs/royalebench-v9/checks.json")["digest"],
        "observed_at": difficulty["observed_at"],
        "selection": "All 12 locally cached FINISHED full runs on v9@1 at the recorded difficulty snapshot; one attempt per model per task; no task errors.",
        "score": "Mean binary objective reward over 21 equally weighted tasks.",
        "task_manifest_sha256": digest(manifest_path), "difficulty_snapshot_sha256": digest(difficulty_path),
        "models": models, "tasks": sorted(tasks.values(), key=lambda t: (t["solved"], t["task"])),
        "summary": {
            "runs": len(models), "tasks": len(tasks), "attempts": len(models) * len(tasks),
            "successes": sum(m["solved"] for m in models),
            "incomplete": sum(m["incomplete"] for m in models),
            "integrity_passes": sum(t["integrity"] == 1 for m in models for t in m["tasks"].values()),
            "rejected_actions": sum(t["rejected_actions"] or 0 for m in models for t in m["tasks"].values()),
            "decisions": sum(t["decisions"] or 0 for m in models for t in m["tasks"].values()),
            "difficulty": dict(Counter(t["difficulty"] for t in tasks.values())),
        },
    }
    ASSETS.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    page = SITE.read_text(encoding="utf-8")
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page, count = re.subn(r'(<script type="application/json" id="benchmark-data">).*?(</script>)',
                          lambda m: m[1] + embedded + m[2], page, flags=re.S)
    assert count == 1
    SITE.write_text(page, encoding="utf-8", newline="\n")
    print(f"Frozen {len(models)} full runs / {data['summary']['attempts']} task attempts; {sum(m['cost_known'] for m in models)} priced tasks.")


def style_replay(page: str) -> str:
    """Apply the public site's shared theme without changing recorded frames."""
    page = page.replace('<html lang="en">', '<html lang="en" class="writeup-replay">')
    page = page.replace('name="theme-color" content="#0e1420"', 'name="theme-color" content="#ffffff"')
    if 'href="theme.css"' not in page:
        page = page.replace('</head>', '<link rel="stylesheet" href="theme.css">\n</head>')
    return page


def replays():
    # Import only for rebuilding media. A clean checkout can inspect the frozen page without RoyaleGym.
    import sys
    sys.path.insert(0, str(ROOT))
    from cr_arena.replay import patched_html
    from royalegym.replay import load_trace, verify_trace
    from royalegym import RustEngine

    evidence = read(ROOT / "demo/evidence.json")
    archive = ROOT / "runs/recent/v7-design/opus" / CASE
    candidates = list(archive.rglob("replay.msgpack"))
    assert len(candidates) == 1
    sources = {"opus": candidates[0], "reference": ROOT / "runs/royalebench-v6/docker" / CASE / "replay.msgpack"}
    provenance = {"case": CASE, "dataset": "royalebench/royalebench-v6@1", "model": evidence["run"]["model"],
                  "run_id": evidence["headliner"]["run_id"], "presentation": "Current shared renderer, original recorded frames. No model calls or gameplay changes.", "replays": {}}
    deploys = {}
    for name, path in sources.items():
        trace = load_trace(path)
        problems = verify_trace(trace, RustEngine())
        assert not problems, str(problems[:3])
        page = patched_html(path, title="Claude Opus 5.5" if name == "opus" else "Validated reference",
                            scenario_success=name == "reference")
        payload = json.loads(re.search(r'<script type="application/json" id="replay-data">(.*?)</script>', page, re.S)[1])
        plays = [p for p in payload["deploys"] if p["team"] == 0]
        deploys[name] = [(p["tick"], p["card"]) for p in plays]
        assert [(p["x"], p["y"]) for p in plays] == [(p["x"], p["y"]) for p in evidence["model_attempt" if name == "opus" else "validated_reference"]["outcome"]["plays"]]
        # The parent owns playback so both independent recordings share one elapsed-time cursor.
        hook = '''
  var writeupEmbedded = new URLSearchParams(location.search).has("embed");
  var writeupOrigin = location.protocol === "file:" ? "null" : location.origin;
  var writeupTargetOrigin = location.protocol === "file:" ? "*" : location.origin;
  window.addEventListener("message", function(e) {
    if (!writeupEmbedded || e.source !== parent || e.origin !== writeupOrigin || !e.data) return;
    if (e.data.type === "royalebench-ping") { parent.postMessage({type:"royalebench-ready"}, writeupTargetOrigin); return; }
    if (e.data.type !== "royalebench-seek") return;
    var seconds = Number(e.data.seconds);
    if (!Number.isFinite(seconds)) return;
    playing = false;
    var target = tick(0) + Math.max(0, seconds) * 1000 / TICK_MS;
    var i = 0;
    while (i + 1 < N && tick(i + 1) <= target) i++;
    if (i < cur) { renderer.reset(); observed = -1; }
    cur = i; simTick = target; interpBox.checked = true; draw();
  });
'''
        assert "  function frameLoop(t) {" in page
        page = page.replace("  function frameLoop(t) {", hook + "\n  function frameLoop(t) {")
        # Embedded boards have no surrounding HUD. Fit the actual iframe in both
        # dimensions instead of keeping the full viewer's minimum 320px height.
        for old, new in [
            ("var availH = Math.max(320, window.innerHeight - 190);",
             'var embed = document.documentElement.classList.contains("embedded");\n    var availH = embed ? Math.max(1, window.innerHeight - 2) : Math.max(320, window.innerHeight - 190);'),
            ("var availW = Math.max(240, wrap.clientWidth - 4);",
             "var availW = Math.max(embed ? 1 : 240, wrap.clientWidth - 4);"),
            ("scale = Math.max(8, Math.floor(Math.min(availW / TX, availH / TY)));",
             "scale = Math.max(embed ? 1 : 8, Math.floor(Math.min(availW / TX, availH / TY)));"),
        ]:
            assert page.count(old) == 1
            page = page.replace(old, new)
        ready_at = "  layout();\n  window.requestAnimationFrame(frameLoop);"
        assert page.count(ready_at) == 1
        page = page.replace(ready_at, "  layout();\n  if (writeupEmbedded) parent.postMessage({type:'royalebench-ready'}, writeupTargetOrigin);\n  window.requestAnimationFrame(frameLoop);")
        css = '''<script>if(new URLSearchParams(location.search).has('embed'))document.documentElement.classList.add('embedded');</script>
<style>.embedded body{overflow:hidden}.embedded header,.embedded #warn,.embedded .team-panels,.embedded .decision-panel,.embedded #controls,.embedded #result,.embedded .legend,.embedded footer{display:none!important}.embedded main{padding:0;display:block}.embedded #boardwrap{min-width:0;width:100%}.embedded canvas{box-shadow:none;border-radius:0;max-width:100%}</style>'''
        page = style_replay(page.replace("</head>", css + "</head>"))
        output = ASSETS / f"{name}-replay.html"
        output.write_text(page, encoding="utf-8", newline="\n")
        provenance["replays"][name] = {"source": path.relative_to(ROOT).as_posix(), "source_sha256": digest(path),
                                        "export_sha256": digest(output), "frames": len(trace.frames),
                                        "result": payload["result"], "deploys": plays}
    assert deploys["opus"] == deploys["reference"] and len(deploys["opus"]) == 6
    provenance["same_cards_and_deployment_ticks"] = True
    (ASSETS / "replay-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Rebuilt both frame-verified recordings; all six card IDs and deployment ticks match.")


def check():
    data = read(DATA)
    assert data["dataset"] == DATASET
    assert len(data["models"]) == 12 and len(data["tasks"]) == 21
    assert data["task_manifest_sha256"] == digest(ROOT / "benchmarks/royalebench-v9/manifest.json")
    assert data["difficulty_snapshot_sha256"] == digest(ROOT / "runs/royalebench-v9/difficulty.json")
    task_ids = {t["task"] for t in data["tasks"]}
    assert len({m["id"] for m in data["models"]}) == 12
    for model in data["models"]:
        assert model["dataset"] == DATASET and model["provider"] == "modal"
        assert set(model["tasks"]) == task_ids and model["attempts"] == 21
        assert model["solved"] == sum(t["reward"] for t in model["tasks"].values())
        assert model["incomplete"] == sum(not t["completed"] for t in model["tasks"].values())
        costs = [t["cost_usd"] for t in model["tasks"].values() if t["cost_usd"] is not None]
        assert model["cost_known"] == len(costs) == 21
        assert abs(sum(costs) - model["cost_total_usd"]) < 1e-9
    for task in data["tasks"]:
        assert task["solved"] == sum(m["tasks"][task["task"]]["reward"] for m in data["models"])
    assert data["summary"]["incomplete"] == 34
    assert data["summary"]["successes"] == 91
    assert data["summary"]["integrity_passes"] == data["summary"]["attempts"] == 252
    assert sum(m["incomplete"] for m in data["models"] if m["harness"] == "mini_swe_agent") == 33
    page = SITE.read_text(encoding="utf-8")
    embedded = re.search(r'<script type="application/json" id="benchmark-data">(.*?)</script>', page, re.S)
    assert embedded and json.loads(embedded[1]) == data
    ids = re.findall(r'\bid="([^"]+)"', page)
    assert len(ids) == len(set(ids)), "Duplicate HTML IDs"
    for ref in re.findall(r'href="#([^"]+)"', page):
        assert ref in ids, f"Missing anchor {ref}"
    for ref in re.findall(r'(?:href|src)="(writeup-assets/[^"?#]+)', page):
        assert (ROOT / "docs" / html.unescape(ref)).is_file(), ref
    for ref in re.findall(r'href="([^"/]+\.md)"', page):
        assert (ROOT / "docs" / ref).is_file(), ref
    assert "localhost:8000" not in page and "127.0.0.1" not in page
    assert not any(key in DATA.read_text(encoding="utf-8") for key in ['"secrets"', '"org_id"', '"install_cmd"', '"run_cmd"', '"sandbox_provider_secret_name"'])
    provenance = read(ASSETS / "replay-provenance.json")
    for name, replay in provenance["replays"].items():
        assert replay["export_sha256"] == digest(ASSETS / f"{name}-replay.html")
    print("Checked dataset identity, all 252 rewards and costs, embedded evidence, links and replay checksums.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--replays", action="store_true")
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    if options.refresh:
        refresh()
    if options.replays:
        replays()
    check()
