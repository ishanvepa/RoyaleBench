"""Generate a quiet, original effects bed for the 67-second silent-caption edit."""

from __future__ import annotations

import math
import struct
import wave
from array import array
from pathlib import Path

RATE = 48_000
DURATION = 67
SAMPLES = RATE * DURATION
mix = array("f", [0.0]) * SAMPLES


def tone(start: float, duration: float, frequency: float, amplitude: float, *, fall: float = 2.0) -> None:
    offset = round(start * RATE)
    length = round(duration * RATE)
    for i in range(length):
        t = i / RATE
        attack = min(1.0, t / 0.006)
        envelope = attack * (1.0 - i / length) ** fall
        mix[offset + i] += amplitude * envelope * (
            math.sin(2 * math.pi * frequency * t)
            + 0.18 * math.sin(2 * math.pi * frequency * 2 * t)
        )


def click(start: float, pitch: float = 1.0) -> None:
    tone(start, 0.10, 650 * pitch, 0.035, fall=3.5)
    tone(start + 0.022, 0.10, 930 * pitch, 0.016, fall=3.5)


def thump(start: float) -> None:
    offset = round(start * RATE)
    length = round(0.42 * RATE)
    for i in range(length):
        t = i / RATE
        freq = 120 - 65 * (i / length)
        envelope = (1 - i / length) ** 3
        mix[offset + i] += 0.095 * envelope * math.sin(2 * math.pi * freq * t)


def chime(start: float) -> None:
    for delay, frequency, amplitude in [(0.0, 523.25, 0.030), (0.07, 659.25, 0.028), (0.15, 783.99, 0.027)]:
        tone(start + delay, 0.58, frequency, amplitude, fall=2.4)


# Scene changes and the six matched deployment times. No unrelated soundtrack.
click(0.0, 0.8)
thump(2.45)
click(4.0, 1.05)
click(8.5, 1.1)
click(13.0, 1.05)
click(18.0, 1.25)
for index, cost in enumerate([1, 3, 4, 4, 2, 1]):
    click(24.0 + 2.0 * index, 0.93 + cost * 0.045)
thump(34.35)
chime(35.22)
click(37.0, 1.15)
click(43.0, 0.92)
chime(50.0)
click(59.0, 0.9)
chime(62.7)

peak = max(abs(value) for value in mix)
if peak > 0.45:
    mix = array("f", (value * 0.45 / peak for value in mix))

out = Path(__file__).resolve().parent / "public/media/sfx-v04.wav"
out.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(out), "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(RATE)
    wav.writeframes(b"".join(struct.pack("<h", round(max(-1, min(1, value)) * 32767)) for value in mix))
print(f"Generated {out.name}: {DURATION}s, 48 kHz mono, peak {peak:.3f}.")
