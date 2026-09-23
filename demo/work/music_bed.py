"""Generate a gentle ambient music bed for the demo film.

Procedural, deterministic, royalty-free: a slow Am–F–C–G add9 pad loop with
detuned oscillators, soft attacks and a low-volume mix that sits under the
voiceover.  Written as a 48 kHz stereo WAV next to the other audio assets.
"""

import math
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "work" / "audio"
OUT = AUDIO / "bed.wav"

SR = 48000

# chord progressions (Hz): Am(add9) -> F(maj7) -> C(maj) -> G(sus4)
CHORDS = [
    [220.00, 261.63, 329.63, 246.94],   # A2 C4 E4 B3
    [174.61, 220.00, 261.63, 329.63],   # F3 A3 C4 E4
    [130.81, 164.81, 196.00, 246.94],   # C3 G3 B3 B4
    [196.00, 246.94, 293.66, 349.23],   # G3 B3 D4 F4
]
CHORD_SEC = 6.4          # each chord holds 6.4s -> 25.6s loop
LOOP_SEC = CHORD_SEC * len(CHORDS)


def tone(freq, detune, dur, gain):
    n = int(dur * SR)
    t = np.arange(n) / SR
    phase = 2 * math.pi * freq * (1 + detune) * t
    # blend a mild second partial for warmth
    sample = np.sin(phase) + 0.35 * np.sin(2 * phase + 0.4)
    attack = int(0.9 * SR)
    release = int(1.6 * SR)
    env = np.ones(n)
    env[:attack] = np.linspace(0, 1, attack) ** 1.6
    env[-release:] = np.linspace(1, 0, release) ** 1.8
    return sample * env * gain


def render(duration):
    """Render `duration` seconds of stereo pad (Am-F-C-G loop, lowpassed)."""
    loops = math.ceil(duration / LOOP_SEC) + 1
    seg = np.zeros((int(LOOP_SEC * loops * SR), 2), dtype=np.float64)
    tone_len = CHORD_SEC + 1.2          # each note bleeds 1.2s into the next chord
    n_tone = int(tone_len * SR)
    for li in range(loops):
        base = int(li * LOOP_SEC * SR)
        for ci, chord in enumerate(CHORDS):
            start = base + int(ci * CHORD_SEC * SR)
            for j, f in enumerate(chord):
                g = 0.028 if j % 2 == 0 else 0.020   # alternate register weight
                for ch, det in ((0, +0.0012), (1, -0.0010)):
                    s = tone(f, det, tone_len, g)[:n_tone]
                    stop = min(len(seg) - start, len(s))
                    if stop > 0:
                        seg[start:start + stop, ch] += s[:stop]
    seg = seg[:int(duration * SR)]

    # gentle tremolo so the pad breathes
    trem = 1 - 0.18 * np.sin(2 * math.pi * 0.07 * np.arange(len(seg)) / SR)
    seg *= trem[:, None]

    # cheap two-pass moving-average lowpass (~vectorised one-pole substitute)
    kernel = np.ones(96) / 96.0
    for c in range(2):
        seg[:, c] = np.convolve(seg[:, c], kernel, mode="same")

    # normalise so the pad stays well below the voiceover
    peak = np.max(np.abs(seg)) or 1.0
    seg = seg / peak * 0.09
    return seg


def write_wav(path, seg):
    pcm = (seg * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    print("wrote", path, f"dur={len(seg) / SR:.1f}s peak={np.max(np.abs(seg)):.3f}")


if __name__ == "__main__":
    write_wav(OUT, render(260.0))