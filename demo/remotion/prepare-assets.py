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
    # Current renderer capture includes a presentation-only tail after the final tick.
    shutil.copyfile(demo / f"assets/captures/{name}-ending-replay.mp4", media / f"{name}-ending.mp4")
    shutil.copyfile(demo / f"assets/captures/{name}-impact-replay.mp4", media / f"{name}-impact.mp4")
    for index in [0, 40, 60, 160, 180, 200, 207 if name == "opus" else 224]:
        source = demo / f"assets/captures/{name}-ending-frames/{index:04d}.png"
        if source.exists():
            shutil.copyfile(source, media / f"{name}-{index:04d}.png")
    final = 243 if name == "opus" else 260
    shutil.copyfile(demo / f"assets/captures/{name}-ending-frames/{final:04d}.png", media / f"{name}-ending-final.png")
    shutil.copyfile(demo / f"assets/captures/{name}-impact-frames/{final:04d}.png", media / f"{name}-impact-final.png")
shutil.copyfile(demo / "assets/captures/dashboard.png", media / "dashboard.png")
shutil.copyfile("/System/Library/Fonts/Supplemental/Impact.ttf", fonts / "impact.ttf")
evidence = json.loads((demo / "evidence.json").read_text())
assert evidence["run"]["successful_objectives"] == 10
assert evidence["model_attempt"]["outcome"]["result"] == "loss"
assert evidence["validated_reference"]["outcome"]["result"] == "win"
print("Staged recorded clips, selected freeze frames, local display font, and dashboard.")
