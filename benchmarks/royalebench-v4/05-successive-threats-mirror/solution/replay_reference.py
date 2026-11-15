"""Protected coordinate reference; never installed in the player environment."""
import json
import subprocess
from pathlib import Path

subprocess.check_output(["cr"], text=True)
for line in Path("/solution/reference.jsonl").read_text().splitlines():
    a = json.loads(line)["action"]
    args = ["wait"] if a["cmd"] == "wait" else ["play", str(a["slot"]), str(a["x"]), str(a["y"])]
    text = subprocess.check_output(["cr", *args], text=True)
if "GAME OVER: scenario SUCCESS" not in text:
    raise SystemExit(text)
print(text)
