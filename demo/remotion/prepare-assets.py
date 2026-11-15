"""Stage existing evidence footage for Remotion; never calls a model."""
import json
import shutil
from pathlib import Path

project = Path(__file__).resolve().parent
demo = project.parent
media = project / "public/media"
fonts = project / "public/fonts"
media.mkdir(parents=True, exist_ok=True)
fonts.mkdir(parents=True, exist_ok=True)
for name in ["opus", "reference"]:
    shutil.copyfile(demo / f"assets/captures/{name}-replay.mp4", media / f"{name}.mp4")
    for index in [0, 40, 60, 160, 180, 200, 207 if name == "opus" else 224]:
        source = demo / f"assets/captures/{name}-frames/{index:04d}.png"
        if source.exists():
            shutil.copyfile(source, media / f"{name}-{index:04d}.png")
shutil.copyfile(demo / "assets/captures/dashboard.png", media / "dashboard.png")
shutil.copyfile("/System/Library/Fonts/Supplemental/Impact.ttf", fonts / "impact.ttf")
evidence = json.loads((demo / "evidence.json").read_text())
assert evidence["run"]["successful_objectives"] == 10
assert evidence["model_attempt"]["outcome"]["result"] == "loss"
assert evidence["validated_reference"]["outcome"]["result"] == "win"
print("Staged recorded clips, selected freeze frames, local display font, and dashboard.")
