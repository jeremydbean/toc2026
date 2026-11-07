#!/usr/bin/env python3
"""Build the game's sounds, mudlet/media/toc-<name>.wav (2026-11-07).

The game asks a client that plays Client.Media (Mudlet) to play these at a
level, a finished quest, an achievement, a tell, a death and a Hyrule
secret (gmcp_play_sound in src/gmcp.c). They are synthesized here from
plain tones -- nothing anybody else owns, and nothing borrowed from any
game's music -- and the build is deterministic, so a change to a sound is
a change to this file and tests/test_mudlet_media.py holds the committed
files to it byte for byte.

    python3 tools/build_sounds.py           # write the files
    python3 tools/build_sounds.py --check   # fail if they differ
"""

from __future__ import annotations

import argparse
import io
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "mudlet" / "media"
RATE = 22050


def note(name: str) -> float:
    """A note name like C5 or F#4 as a frequency (A4 = 440)."""
    steps = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    letter, rest = name[0], name[1:]
    shift = 0
    if rest.startswith("#"):
        shift, rest = 1, rest[1:]
    elif rest.startswith("b"):
        shift, rest = -1, rest[1:]
    octave = int(rest)
    semis = steps[letter] + shift + (octave - 4) * 12
    return 440.0 * 2 ** (semis / 12)


def tone(freqs, start: float, length: float, gain: float, buf: list[float],
         attack: float = 0.01, decay: float = 4.0) -> None:
    """Add a chord of sines (with a soft second harmonic) to buf."""
    first = int(start * RATE)
    count = int(length * RATE)
    for i in range(count):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t)
        sample = 0.0
        for f in freqs:
            sample += math.sin(2 * math.pi * f * t) + 0.25 * math.sin(4 * math.pi * f * t)
        index = first + i
        if index < len(buf):
            buf[index] += gain * env * sample / max(1, len(freqs))


def render(events, total: float) -> bytes:
    buf = [0.0] * int(total * RATE)
    for freqs, start, length, gain, decay in events:
        tone([note(n) for n in freqs], start, length, gain, buf, decay=decay)
    peak = max(1e-9, max(abs(s) for s in buf))
    scale = 0.7 / peak
    frames = b"".join(struct.pack("<h", int(round(s * scale * 32767))) for s in buf)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return out.getvalue()


# name: ([(notes, start s, length s, gain, decay)], total s)
SOUNDS = {
    # A bright rising arpeggio.
    "levelup": ([(["C5"], 0.00, 0.30, 1.0, 6), (["E5"], 0.10, 0.30, 1.0, 6),
                 (["G5"], 0.20, 0.30, 1.0, 6), (["C6"], 0.30, 0.60, 1.0, 4)], 0.95),
    # Two shimmering chords.
    "achievement": ([(["G5", "B5", "D6"], 0.00, 0.35, 1.0, 6),
                     (["C6", "E6", "G6"], 0.18, 0.70, 1.0, 4)], 0.95),
    # A short three-note fanfare.
    "quest": ([(["E5"], 0.00, 0.20, 1.0, 7), (["G5"], 0.14, 0.20, 1.0, 7),
               (["C6", "E6"], 0.28, 0.60, 1.0, 4)], 0.92),
    # Slow, low and falling.
    "death": ([(["A3", "C4"], 0.00, 0.55, 1.0, 3), (["F3", "A3"], 0.45, 0.55, 1.0, 3),
               (["D3", "F3"], 0.90, 0.90, 1.0, 2.5)], 1.85),
    # A soft two-note ping.
    "tell": ([(["A5"], 0.00, 0.25, 0.8, 10), (["E6"], 0.09, 0.30, 0.8, 9)], 0.42),
    # A quick pentatonic run upward.
    "secret": ([(["C5"], 0.00, 0.18, 1.0, 9), (["D5"], 0.07, 0.18, 1.0, 9),
                (["E5"], 0.14, 0.18, 1.0, 9), (["G5"], 0.21, 0.18, 1.0, 9),
                (["A5"], 0.28, 0.18, 1.0, 9), (["C6"], 0.35, 0.50, 1.0, 5)], 0.88),
}


def build() -> dict[str, bytes]:
    return {f"toc-{name}.wav": render(events, total) for name, (events, total) in SOUNDS.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed files differ")
    args = parser.parse_args()
    built = build()
    if args.check:
        stale = [n for n, data in built.items()
                 if not (OUT / n).is_file() or (OUT / n).read_bytes() != data]
        extra = sorted(p.name for p in OUT.glob("toc-*.wav") if p.name not in built)
        if stale or extra:
            print("stale sounds: " + ", ".join(stale + extra), file=sys.stderr)
            return 1
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, data in built.items():
        (OUT / n).write_bytes(data)
        print(f"{n}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
