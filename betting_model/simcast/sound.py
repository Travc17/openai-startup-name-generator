"""Original soundtrack for a SizzleSims clip, synthesized from scratch (no samples, no licensed music).

    python simcast/sound.py cues.json OFFSET_S TOTAL_S END_CARD_S out.wav

* Music bed: 124 BPM stadium beat (kick, clap, hats, synth bass, chord pad, brass stabs) on a I-V-vi-IV loop in D;
  drums only before kickoff, full band during play, lower and fading under the end card.
* Referee whistle: two short blasts at kickoff, one long at the final.
* Fireworks on scores (Travis): two shells on touchdowns, one on field goals, a small crackle on extra points;
  music dips slightly. A crowd cheer only at the final whistle.
Cue times come from the recorder (seconds since the page opened); OFFSET_S maps them onto the video timeline.
"""
from __future__ import annotations

import json
import sys

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
RNG = np.random.default_rng(7)


def t_axis(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def env(n: int, a: float, d: float) -> np.ndarray:
    """Attack / exponential decay envelope, times in seconds."""
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-np.maximum(t - a, 0) / max(d, 1e-4))


def band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return sosfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), x)


def saw(f: float, n: int, harm: int = 8) -> np.ndarray:
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harm + 1))


def add(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    if i >= len(buf) or i + len(x) <= 0:
        return
    j = min(len(buf), i + len(x))
    buf[max(i, 0):j] += gain * x[max(0, -i):j - i]


# ---------------- instruments ----------------
def kick() -> np.ndarray:
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12)


def clap() -> np.ndarray:
    n = int(0.22 * SR)
    x = band(RNG.standard_normal(n), 900, 3500) * env(n, 0.001, 0.07)
    return x / np.abs(x).max()


def hat(open_: bool = False) -> np.ndarray:
    n = int((0.25 if open_ else 0.06) * SR)
    x = sosfilt(butter(4, 7000, btype="high", fs=SR, output="sos"), RNG.standard_normal(n)) * env(n, 0.001, 0.08 if open_ else 0.02)
    return x / np.abs(x).max()


def bass(f: float, sec: float) -> np.ndarray:
    n = int(sec * SR)
    x = sosfilt(butter(2, 900, fs=SR, output="sos"), saw(f, n, 10)) * env(n, 0.005, sec * 0.6)
    return x / np.abs(x).max()


def pad(freqs: list[float], sec: float) -> np.ndarray:
    n = int(sec * SR); t = np.arange(n) / SR
    x = sum(saw(f * (1 + d), n, 6) for f in freqs for d in (-0.004, 0.004))
    x = sosfilt(butter(2, 2200, fs=SR, output="sos"), x)
    shape = np.minimum(1, t / 0.25) * np.minimum(1, (sec - t) / 0.2)
    return x / np.abs(x).max() * shape


def stab(freqs: list[float]) -> np.ndarray:
    n = int(0.32 * SR); t = np.arange(n) / SR
    x = sum(np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + saw(f, n, 12) for f in freqs)
    x = sosfilt(butter(2, 3500, fs=SR, output="sos"), x) * env(n, 0.01, 0.11)
    return x / np.abs(x).max()


def whistle(sec: float) -> np.ndarray:
    n = int(sec * SR); t = np.arange(n) / SR
    trill = 0.55 + 0.45 * np.sin(2 * np.pi * 28 * t)            # pea-whistle flutter
    x = (np.sin(2 * np.pi * 3150 * t) + 0.5 * np.sin(2 * np.pi * 3290 * t)) * trill
    shape = np.minimum(1, t / 0.02) * np.minimum(1, (sec - t) / 0.06)
    return x / np.abs(x).max() * shape


def crowd(sec: float, size: float) -> np.ndarray:
    """Roar: layered band-limited noise with a swelling then fading envelope, plus a few higher 'whoo' bands."""
    n = int(sec * SR); t = np.arange(n) / SR
    x = band(RNG.standard_normal(n), 250, 2600) + 0.6 * band(RNG.standard_normal(n), 900, 4200)
    for _ in range(int(3 * size)):                               # rising voices
        f0 = RNG.uniform(500, 900)
        f = f0 * (1 + 0.35 * np.minimum(1, t / (0.4 + RNG.uniform(0, 0.4))))
        x += 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR) * band(RNG.standard_normal(n), 3, 18) * 3
    shape = np.minimum(1, t / 0.35) * np.where(t < sec * 0.45, 1.0, np.exp(-(t - sec * 0.45) / (sec * 0.25)))
    x = x * shape
    return x / np.abs(x).max()


def launch() -> np.ndarray:
    """Rising whistle of a firework shell going up (0.7 s)."""
    n = int(0.7 * SR); t = np.arange(n) / SR
    f = 700 + 1900 * (t / 0.7) ** 1.4
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.6 + 0.4 * band(RNG.standard_normal(n), 1500, 6000)
    return x / np.abs(x).max() * np.minimum(1, t / 0.08) * (0.35 + 0.65 * t / 0.7) * np.minimum(1, (0.7 - t) / 0.05)


def burst(size: float = 1.0) -> np.ndarray:
    """Boom (low thump + noise) followed by a sparkling crackle that fades out."""
    sec = 1.2 + 0.8 * size
    n = int(sec * SR); t = np.arange(n) / SR
    boom = sosfilt(butter(2, 700, fs=SR, output="sos"), RNG.standard_normal(n)) * env(n, 0.003, 0.18)
    boom = boom / np.abs(boom).max() + 0.8 * np.sin(2 * np.pi * 58 * t) * env(n, 0.002, 0.25)
    crackle = np.zeros(n)
    for _ in range(int(140 * size)):                            # sparse tiny pops, denser early
        at = int(SR * (0.12 + RNG.exponential(0.45 * size)))
        if at >= n - 400:
            continue
        m = int(SR * RNG.uniform(0.002, 0.006))
        crackle[at:at + m] += RNG.uniform(0.3, 1.0) * band(RNG.standard_normal(m + 200), 2500, 9000)[200:]
    crackle *= np.exp(-t / (0.9 * size))
    x = 0.9 * boom / np.abs(boom).max() + 0.55 * crackle / max(1e-9, np.abs(crackle).max())
    return x / np.abs(x).max()


def fireworks(pts: int) -> tuple[np.ndarray, float]:
    """Touchdown: two shells; field goal: one; extra point / two-point try: a small crackle. Returns (sound, lead):
    the sound starts `lead` seconds before the score so the first burst lands as the confetti flies."""
    if pts >= 6:
        x = np.zeros(int(3.6 * SR))
        add(x, launch(), 0.0, 0.35); add(x, burst(1.0), 0.65, 1.0)
        add(x, launch(), 0.3, 0.3); add(x, burst(0.8), 0.95, 0.8)
        return x, 0.45
    if pts >= 3:
        x = np.zeros(int(2.6 * SR))
        add(x, launch(), 0.0, 0.3); add(x, burst(0.8), 0.65, 0.85)
        return x, 0.45
    return burst(0.35) * 0.45, 0.0


# ---------------- arrangement ----------------
def build(cues: list[dict], offset: float, total: float, end_card: float) -> np.ndarray:
    L = np.zeros(int(total * SR) + SR)
    beat = 60 / 124
    kick_t = next((c["t"] + offset for c in cues if c["kind"] == "kickoff"), 2.0)
    final_t = next((c["t"] + offset for c in cues if c["kind"] == "final"), total - end_card)
    card_t = total - end_card
    D, A, B, G = 146.83, 110.0, 123.47, 98.0                     # D3 A2 B2 G2
    chords = [(D, [293.66, 369.99, 440.0]), (A, [220.0, 277.18, 329.63]), (B, [246.94, 293.66, 369.99]), (G, [196.0, 246.94, 293.66])]
    k, c, hc, ho = kick(), clap(), hat(), hat(True)
    music = np.zeros_like(L)
    bar = 4 * beat
    t0 = 0.0
    i = 0
    while t0 < total:
        root, triad = chords[i % 4]
        full = kick_t - 0.2 <= t0 < final_t + 2.5
        for b in range(4):
            tb = t0 + b * beat
            add(music, k, tb, 0.9)
            if b in (1, 3) and t0 >= kick_t - bar:
                add(music, c, tb, 0.35)
            add(music, hc, tb + beat / 2, 0.12)
            if b == 3:
                add(music, ho, tb + beat / 2, 0.10)
            if full:
                for e in range(2):
                    add(music, bass(root / 2 if e else root, beat / 2), tb + e * beat / 2, 0.42)
        if full:
            add(music, pad(triad, bar), t0, 0.16)
            if i % 2 == 0:
                add(music, stab([f * 2 for f in triad]), t0, 0.22)
        t0 += bar; i += 1
    # music level: lighter before kickoff, full in play, lower and fading under the end card
    tt = np.arange(len(L)) / SR
    lvl = np.where(tt < kick_t, 0.55, 1.0)
    lvl = np.where(tt >= card_t, 0.6 * np.clip((total - tt) / 3.0, 0, 1) + 0.0, lvl)
    lvl = np.where((tt >= card_t) & (tt < total - 3.0), 0.6, lvl)
    # crowd + whistles, with the music ducking under each roar
    sfx = np.zeros_like(L)
    duck = np.ones_like(L)
    add(sfx, whistle(0.28), kick_t - 0.05, 0.7); add(sfx, whistle(0.28), kick_t + 0.32, 0.7)
    add(sfx, whistle(1.1), final_t + 0.15, 0.55)
    add(sfx, crowd(5.0, 1.0), final_t + 0.3, 1.6)
    for cu in cues:
        if cu["kind"] != "score":
            continue
        at = cu["t"] + offset
        fw, lead = fireworks(cu["pts"])                         # Travis 2026-11-04: fireworks on scores, not a crowd roar
        add(sfx, fw, at - lead, 0.85 if cu["pts"] >= 6 else (0.7 if cu["pts"] >= 3 else 0.5))
        i0, i1 = int((at - lead) * SR), int((at - lead) * SR + len(fw))
        duck[max(i0, 0):i1] = np.minimum(duck[max(i0, 0):i1], 0.78)
    duck = np.convolve(duck, np.ones(2205) / 2205, mode="same")   # 50 ms smoothing so the ducking doesn't click
    mix = music * lvl * duck * 0.55 + sfx
    mix = mix[: int(total * SR)]
    mix *= 0.89 / max(1e-9, np.abs(mix).max())                  # peak about -1 dBFS
    fade = int(0.05 * SR)
    mix[:fade] *= np.linspace(0, 1, fade); mix[-fade:] *= np.linspace(1, 0, fade)
    return mix


def write_wav(path: str, x: np.ndarray) -> None:
    import wave
    st = np.stack([x, np.roll(x, 12)], axis=1)                   # a touch of width
    pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    cues_path, offset, total, card, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
    cues = json.load(open(cues_path))
    x = build(cues, offset, total, card)
    write_wav(out, x)
    n_score = sum(1 for c in cues if c["kind"] == "score")
    print(f"{out}: {total:.1f} s, {n_score} score cues (fireworks), peak {20 * np.log10(np.abs(x).max()):.1f} dBFS, "
          f"rms {20 * np.log10(np.sqrt((x ** 2).mean())):.1f} dBFS")
