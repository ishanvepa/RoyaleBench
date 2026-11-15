"""Replay a protected reference through exactly the agent's cr socket interface."""
import json
import subprocess
from pathlib import Path

def call(*args):
    return subprocess.check_output(["cr", *args], text=True)

text = call()
for line in Path("/solution/reference.jsonl").read_text().splitlines():
    entry = json.loads(line)
    if entry["label"] not in text.splitlines():
        raise SystemExit("reference no longer matches the legal menu")
    text = call("act", str(entry["move"]))
if "GAME OVER: scenario SUCCESS" not in text:
    raise SystemExit(text)
print(text)
