"""One-off generator for the silent-ish startup cue WAV (assets/cue.wav)."""
import math
import struct
import sys
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "scheduler" / "assets" / "cue.wav"


def make_cue(path: Path, rate=22050, duration=0.18, freq=880.0, volume=12000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_count = int(rate * duration)
    frames = bytearray()
    for i in range(sample_count):
        t = i / rate
        envelope = 1.0 - (t / duration)
        value = volume * math.sin(2 * math.pi * freq * t) * envelope
        value = max(-32767, min(32767, int(value)))
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))


if __name__ == "__main__":
    make_cue(OUT)
    print(f"cue.wav written ({OUT.stat().st_size} bytes)")
    sys.exit(0)