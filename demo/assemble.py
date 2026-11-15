"""Build a captioned 90-second review cut from captured replay frames.

Requires Pillow, ffmpeg/ffprobe, and macOS `say` for the temporary voice.
Run `python demo/assemble.py`; use --preview to render only review stills.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEMO = Path(__file__).resolve().parent
CAP = DEMO / "assets/captures"
AUDIO = DEMO / "assets/audio"
EDIT = DEMO / "edit"
OUT = DEMO / "exports"
FPS = 20
SIZE = (1920, 1080)
BG, PANEL, LINE = "#0b1220", "#121f32", "#28394f"
WHITE, MUTED, CYAN, RED, GREEN = "#edf4ff", "#a6b7cb", "#6bdbf5", "#ff998b", "#93e3b0"
FONTS = Path("/System/Library/Fonts/Supplemental")
SCENES = [
    ("hook", 10, "Eighteen seconds left. Your tower has 250 health. The opponent's has 450. Can a frontier model find the win?"),
    ("attempt", 15, "Claude Opus freezes the Giant, pulls it with a Cannon, and sends a Hog Rider toward the enemy tower."),
    ("failure", 10, "But it spends its Log attacking. The Giant gets through first, before the Hog can connect."),
    ("comparison", 18, "This position is winnable. Our validated reference plays exactly the same cards, in exactly the same order. Different placements and a defensive Log keep the Giant occupied long enough for the Hog to finish the game."),
    ("method", 15, "RoyaleBench tests resource management, spatial reasoning, and planning through reproducible Clash Royale scenarios. Models read the battle state and choose card coordinates. The game pauses while they think."),
    ("results", 14, "Tasks run on Valkyrie using Modal, with independent replay verification. In this fourteen-task run, Opus completed ten objectives and failed this one. Every task has an explicit objective and a validated reference solution."),
    ("close", 8, "The right cards are only part of the answer. Where you play them can decide the game."),
]
CARDS = ["Ice Spirits", "Cannon", "Fireball", "Hog Rider", "Log", "Ice Spirits"]
META = json.loads((CAP / "capture-metadata.json").read_text())


@functools.lru_cache(maxsize=32)
def font(size: int, bold: bool = False, mono: bool = False):
    return ImageFont.truetype(str(FONTS / ("Andale Mono.ttf" if mono else "Arial Bold.ttf" if bold else "Arial.ttf")), size)


def text(draw, xy, value, size=28, fill=WHITE, bold=False, mono=False):
    draw.text(xy, value, font=font(size, bold, mono), fill=fill)


def wrap(draw, value, width, size=30, bold=False):
    lines, current = [], ""
    for word in value.split():
        trial = (current + " " + word).strip()
        if draw.textlength(trial, font=font(size, bold)) > width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    return lines + ([current] if current else [])


def paragraph(draw, xy, value, width=650, size=30, fill=MUTED, bold=False, leading=1.4):
    x, y = xy
    for line in wrap(draw, value, width, size, bold):
        text(draw, (x, y), line, size, fill, bold)
        y += round(size * leading)
    return y


@functools.lru_cache(maxsize=128)
def board(name, index):
    return Image.open(CAP / f"{name}-frames/{index:04d}.png").convert("RGB")


def frame_index(name, seconds):
    duration = META["replays"][name]["duration_s"]
    return min(round(max(0, seconds) * FPS), math.ceil(duration * FPS))


def get_board(name, seconds):
    return board(name, frame_index(name, seconds))


def base(section, number):
    im = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(im)
    d.line((64, 80, 1856, 80), fill=LINE, width=2)
    text(d, (64, 30), "ROYALEBENCH", 24, CYAN, True)
    text(d, (350, 32), section.upper(), 20, MUTED)
    text(d, (1540, 32), "REVIEW CUT · TEMP VOICE", 18, MUTED)
    d.line((64, 1034, 1856, 1034), fill=LINE, width=2)
    text(d, (64, 1050), "Clash Royale strategy · reproducible model evaluation", 17, MUTED)
    text(d, (1760, 1050), f"{number:02d} / 07", 17, MUTED)
    return im, d


def place_board(im, name, seconds, x, y=150, height=800):
    pic = get_board(name, seconds)
    width = round(pic.width * height / pic.height)
    im.paste(pic.resize((width, height), Image.Resampling.LANCZOS), (x, y))
    return x, y, width, height


def point(rect, x, y):
    bx, by, w, h = rect
    return bx + x / 18 * w, by + (32 - y) / 32 * h


def ring(d, rect, x, y, color, radius=24):
    cx, cy = point(rect, x, y)
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=color, width=4)


def tag(d, xy, label, color=CYAN, size=22):
    x, y = xy
    width = d.textlength(label, font=font(size, True)) + 28
    d.rounded_rectangle((x, y, x+width, y+size+20), radius=9, fill=PANEL, outline=color, width=1)
    text(d, (x+14, y+8), label, size, color, True)


def draw_frame(scene, t):
    name = SCENES[scene][0]
    im, d = base(["The challenge", "The model attempt", "The failure", "The winning comparison", "How it works", "The measured result", "Try RoyaleBench"][scene], scene+1)
    if name == "hook":
        r = place_board(im, "opus", 0, 1280, 124, 840)
        tag(d, (1290, 92), "OPENING REPLAY FRAME", MUTED, 18)
        text(d, (100, 160), "18 seconds.", 104, WHITE, True)
        text(d, (100, 280), "250 health.", 104, RED, True)
        paragraph(d, (105, 450), "Can a frontier model find the win?", 950, 66, WHITE, True, 1.15)
        tag(d, (108, 670), "OVERTIME · NEXT TOWER WINS", CYAN, 24)
        paragraph(d, (110, 760), "An incoming Giant. A vulnerable enemy tower. One chance to defend and connect.", 900, 32)
        ring(d, r, 3.5, 6.5, RED, 42)
        ring(d, r, 3.5, 25.5, CYAN, 42)
    elif name == "attempt":
        sim = min(t, 10.35)
        r = place_board(im, "opus", sim, 1260, 124, 840)
        text(d, (100, 135), "Claude Opus 5.5", 58, WHITE, True)
        paragraph(d, (104, 222), "Freeze. Pull. Push.", 1000, 47, CYAN, True)
        idx = min(int(sim // 2), 5)
        for i, card in enumerate(CARDS):
            yy = 345 + i * 77
            active = i == idx
            d.rounded_rectangle((100, yy-8, 1090, yy+54), radius=12, fill=PANEL if active else BG)
            text(d, (125, yy), f"{i+1:02d}", 30, CYAN if active else MUTED, True)
            text(d, (205, yy), card, 34, WHITE if i <= idx else MUTED, active)
            text(d, (875, yy+5), f"t + {i*2}s", 24, MUTED)
        tag(d, (105, 887), "RECORDED ATTEMPT" if t <= 10.35 else "FINAL FRAME · HELD", MUTED)
        if t > 10.35:
            tag(d, (1580, 930), "LOSS · 0–1", RED)
    elif name == "failure":
        sim = 8 + t * 0.5 if t < 4.7 else 10.35
        r = place_board(im, "opus", sim, 1260, 124, 840)
        text(d, (100, 145), "The Giant gets", 72, WHITE, True)
        text(d, (100, 235), "there first.", 72, RED, True)
        paragraph(d, (105, 395), "Opus sends Log toward the enemy tower while its own tower is still under threat.", 940, 40, WHITE)
        paragraph(d, (105, 585), "The Hog is still approaching when the Giant destroys the 250-HP tower.", 940, 35)
        tag(d, (108, 780), "LOSS AT 10.35s", RED, 30)
        tag(d, (108, 864), "SLOW REPLAY · 0.5×" if t < 4.7 else "FINAL FRAME · HELD", MUTED)
        if t < 1.8:
            ring(d, r, 3.5, 24.5, RED, 38)
    elif name == "comparison":
        text(d, (82, 102), "Same cards. Same order. Different placements.", 49, WHITE, True)
        sim = min(max(0, t-1), 11.2)
        left = place_board(im, "opus", min(sim, 10.35), 100, 225, 745)
        right = place_board(im, "reference", sim, 680, 225, 745)
        text(d, (100, 180), "Claude Opus 5.5", 29, RED, True)
        text(d, (680, 180), "Validated reference", 29, GREEN, True)
        if sim >= 2 and sim < 5:
            ring(d, left, 7.5, 10.5, RED)
            ring(d, right, 7, 11.5, GREEN)
        if sim >= 8 and sim < 10:
            ring(d, left, 3.5, 24.5, RED)
            ring(d, right, 89676/18000, 155214/18000, GREEN)
        text(d, (1210, 245), "15 elixir each.", 48, CYAN, True)
        paragraph(d, (1215, 345), "The reference changes defensive placements and uses Log to control the Giant.", 590, 35, WHITE)
        paragraph(d, (1215, 545), "That buys enough time for the Hog to connect.", 590, 35)
        if sim >= 10.35:
            tag(d, (1208, 730), "OPUS · LOSS AT 10.35s", RED)
        if sim >= 11.2:
            tag(d, (1208, 800), "REFERENCE · WIN AT 11.2s", GREEN)
            text(d, (1215, 878), "Zero tower damage taken.", 29, GREEN, True)
        text(d, (1215, 950), f"Elapsed simulation time: {sim:.2f}s", 23, MUTED)
    elif name == "method":
        text(d, (100, 125), "RoyaleBench", 88, WHITE, True)
        paragraph(d, (105, 255), "Resource management. Spatial reasoning. Planning.", 1600, 40, CYAN, True)
        d.rounded_rectangle((100, 370, 1080, 830), radius=22, fill=PANEL, outline=LINE, width=2)
        text(d, (135, 405), "MODEL OBSERVATION", 23, MUTED, True)
        for j, line in enumerate(["TIME LEFT: 0:18 · OVERTIME", "YOUR ELIXIR: 7.0 / 10", "YOUR LEFT TOWER: 250 HP", "ENEMY LEFT TOWER: 450 HP", "ENEMY: Giant at (3.5, 12.0)"]):
            text(d, (135, 465+j*51), line, 28, WHITE, mono=True)
        text(d, (135, 755), "$ cr play 0 3.5 11", 32, CYAN, mono=True)
        text(d, (1200, 405), "OBSERVE", 38, WHITE, True)
        text(d, (1200, 505), "CHOOSE CARD + COORDINATES", 28, CYAN, True)
        text(d, (1200, 605), "ADVANCE THE SIMULATION", 28, WHITE, True)
        tag(d, (105, 900), "THE GAME PAUSES WHILE THE MODEL THINKS", CYAN, 25)
        text(d, (1200, 735), "14 reproducible tasks", 32, MUTED)
        text(d, (1200, 795), "Explicit, verifiable objectives", 29, MUTED)
    elif name == "results":
        text(d, (100, 135), "10 / 14", 156, WHITE, True)
        text(d, (110, 320), "objectives completed", 48, CYAN, True)
        text(d, (112, 405), "Claude Opus 5.5 · RoyaleBench v6@1", 30, MUTED)
        for i in range(14):
            x = 110+i*72
            d.rounded_rectangle((x, 495, x+52, 565), radius=8, fill=GREEN if i<10 else LINE)
        text(d, (112, 610), "71.4% task objective success", 38, WHITE, True)
        text(d, (112, 680), "Single run · one attempt per task", 28, MUTED)
        text(d, (1120, 150), "Valkyrie + Modal", 47, WHITE, True)
        paragraph(d, (1125, 245), "Independent replay verification checks the recorded actions and outcome.", 660, 34)
        dashboard = CAP / "dashboard.png"
        if dashboard.exists():
            pic = Image.open(dashboard).convert("RGB")
            pic = pic.crop((0, 0, pic.width, min(pic.height, 590)))
            pic.thumbnail((680, 385))
            im.paste(pic, (1120, 445))
            text(d, (1125, 850), "Recorded run dashboard", 23, MUTED)
        paragraph(d, (112, 805), "This headliner: loss, valid replay, zero rejected actions.", 880, 30, RED)
        text(d, (112, 925), "The aggregate includes objectives beyond match wins.", 25, MUTED)
    elif name == "close":
        sim = min(9 + t, 11.2)
        r = place_board(im, "reference", sim, 1280, 124, 840)
        text(d, (100, 155), "The right cards.", 80, WHITE, True)
        text(d, (100, 255), "The right place.", 80, CYAN, True)
        paragraph(d, (108, 410), "Where you play them can decide the game.", 970, 49, WHITE, True)
        text(d, (108, 650), "RoyaleBench", 68, WHITE, True)
        text(d, (111, 760), "github.com/ishanvepa/RoyaleBench", 31, CYAN)
        text(d, (111, 833), "Built on RoyaleGym / RoyaleSim", 24, MUTED)
        text(d, (111, 880), "Evaluated with Valkyrie and Modal", 24, MUTED)
        tag(d, (1280, 94), "VALIDATED REFERENCE · REPLAY", GREEN, 18)
    return im


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]))


def make_audio():
    segments = []
    audit = []
    for i, (name, seconds, narration) in enumerate(SCENES):
        aiff, wav = AUDIO/f"{i+1:02d}-{name}-temp.aiff", AUDIO/f"{i+1:02d}-{name}.wav"
        words = len(narration.split())
        rate = max(150, math.ceil(words*60/(seconds-0.8)))
        for attempt in range(3):
            subprocess.run(["say", "-v", "Samantha", "-r", str(rate), "-o", str(aiff), narration], check=True)
            actual = duration(aiff)
            if actual <= seconds-0.3:
                break
            rate = math.ceil(rate*actual/(seconds-0.6))
        if actual > seconds-0.3:
            raise ValueError(f"Narration too long for {name}: {actual}")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(aiff), "-af", "adelay=250|250,apad", "-t", str(seconds), "-ar", "48000", "-ac", "2", str(wav)], check=True)
        segments.append(wav)
        audit.append({"scene":name,"allocated_s":seconds,"voice_s":actual,"rate_wpm":rate,"voice":"macOS Samantha (temporary)"})
    listing = EDIT/"audio-concat.txt"
    listing.write_text("".join("file '"+str(p).replace("'", "'\\''")+"'\n" for p in segments))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(AUDIO/"temp-narration.wav")], check=True)
    return audit


def captions(audit):
    cues, offset = [], 0
    for (_, seconds, narration), record in zip(SCENES, audit):
        words = narration.split()
        for index in range(0, len(words), 11):
            chunk = words[index:index+11]
            start = offset + 0.25 + index/len(words)*record["voice_s"]
            end = offset + 0.25 + (index+len(chunk))/len(words)*record["voice_s"]
            cues.append((start, end, " ".join(chunk)))
        offset += seconds
    def timestamp(seconds):
        millis = round(seconds*1000)
        return f"{millis//3600000:02d}:{millis//60000%60:02d}:{millis//1000%60:02d},{millis%1000:03d}"
    (OUT/"royalebench-demo-v01.srt").write_text("\n\n".join(
        f"{i+1}\n{timestamp(start)} --> {timestamp(end)}\n{line}"
        for i, (start, end, line) in enumerate(cues)) + "\n")
    return cues


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    for folder in [AUDIO, EDIT, OUT]:
        folder.mkdir(parents=True, exist_ok=True)
    for i, (_, seconds, _) in enumerate(SCENES):
        draw_frame(i, min(seconds-0.1, [0,4,6,12.5,5,5,4][i])).save(OUT/f"scene-{i+1:02d}.jpg", quality=90)
    contact = Image.new("RGB", (1440, 1080), BG)
    for i in range(7):
        thumb = Image.open(OUT/f"scene-{i+1:02d}.jpg").resize((480,270))
        contact.paste(thumb, ((i%3)*480, (i//3)*270))
    contact.save(OUT/"storyboard-contact-sheet.jpg", quality=92)
    if args.preview:
        print("Rendered scene previews and contact sheet.")
        return
    audit = make_audio()
    cues = captions(audit)
    output = OUT/"royalebench-demo-v01.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", str(FPS), "-i", "pipe:0", "-i", str(AUDIO/"temp-narration.wav"), "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", "90", str(output)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        offset = 0
        for i, (name, seconds, _) in enumerate(SCENES):
            print(f"Rendering {name} ({seconds}s)", flush=True)
            for frame in range(seconds*FPS):
                image = draw_frame(i, frame/FPS)
                caption = next((line for start, end, line in cues if start <= offset+frame/FPS < end), None)
                if caption:
                    draw = ImageDraw.Draw(image)
                    draw.rounded_rectangle((64, 977, 1856, 1030), radius=8, fill="#060b13")
                    x = (1920-draw.textlength(caption, font=font(27)))/2
                    text(draw, (x, 989), caption, 27, WHITE)
                process.stdin.write(image.tobytes())
            offset += seconds
    finally:
        process.stdin.close()
    if process.wait():
        raise RuntimeError("ffmpeg failed")
    (EDIT/"render-report.json").write_text(json.dumps({"output":str(output.relative_to(DEMO)),"duration_s":duration(output),"resolution":list(SIZE),"output_fps":30,"composition_fps":FPS,"voice":"Temporary macOS Samantha; replace with human narration.","audio_scenes":audit}, indent=2)+"\n")
    print(f"Saved {output}", flush=True)


if __name__ == "__main__":
    main()
