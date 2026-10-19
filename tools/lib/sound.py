"""Original sound-effect synthesis (numpy) + OGG Vorbis encoding (ffmpeg/libvorbis).

All sounds are synthesized from scratch: oscillators with frequency sweeps, filtered noise,
FFT band filters, a convolution reverb built from a decaying noise impulse, and envelopes.
Output: mono 44.1 kHz (Bedrock positional sounds should be mono).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import wave

import numpy as np

SR = 44100


def _rng(seed: int):
    return np.random.default_rng(seed)


def time(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def phase(freq) -> np.ndarray:
    f = np.asarray(freq, dtype=np.float64)
    return 2 * np.pi * np.cumsum(f) / SR


def sine(freq, dur=None):
    if dur is not None and np.isscalar(freq):
        freq = np.full(int(dur * SR), freq)
    return np.sin(phase(freq))


def saw(freq, dur=None):
    if dur is not None and np.isscalar(freq):
        freq = np.full(int(dur * SR), freq)
    p = phase(freq) / (2 * np.pi)
    return 2 * (p - np.floor(p + 0.5))


def square(freq, dur=None, duty=0.5):
    if dur is not None and np.isscalar(freq):
        freq = np.full(int(dur * SR), freq)
    p = (phase(freq) / (2 * np.pi)) % 1.0
    return np.where(p < duty, 1.0, -1.0)


def noise(dur, seed=1, color="white"):
    n = int(dur * SR)
    w = _rng(seed).standard_normal(n)
    if color == "white":
        return w / 3
    spec = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = 1
    if color == "pink":
        spec /= np.sqrt(f)
    elif color == "brown":
        spec /= f
    out = np.fft.irfft(spec, n)
    return out / (np.abs(out).max() + 1e-9)


def sweep(f0, f1, dur, curve="exp"):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    if curve == "exp":
        return f0 * (f1 / f0) ** t
    return f0 + (f1 - f0) * t


def band(x, lo=None, hi=None, soft=0.15):
    """FFT band-pass/low-pass/high-pass with smooth edges."""
    n = len(x)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + np.exp(-(f - lo) / (lo * soft + 1e-9)))
    if hi:
        g *= 1 / (1 + np.exp((f - hi) / (hi * soft + 1e-9)))
    return np.fft.irfft(spec * g, n)


def env(dur, a=0.01, d=0.1, s=0.7, r=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = np.empty(n)
    rs = dur - r
    for_attack = t < a
    e[for_attack] = t[for_attack] / max(a, 1e-6)
    dec = (t >= a) & (t < a + d)
    e[dec] = 1 - (1 - s) * (t[dec] - a) / max(d, 1e-6)
    sus = (t >= a + d) & (t < rs)
    e[sus] = s
    rel = t >= rs
    e[rel] = s * np.clip(1 - (t[rel] - rs) / max(r, 1e-6), 0, 1)
    return e


def decay(dur, k=6.0, a=0.005):
    t = time(dur)
    return np.clip(t / a, 0, 1) * np.exp(-k * t)


def reverb(x, seconds=1.2, mix=0.3, seed=3, damp=4000):
    ir = noise(seconds, seed) * np.exp(-np.linspace(0, 6, int(seconds * SR)))
    ir = band(ir, hi=damp)
    n = len(x) + len(ir)
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    wet /= np.abs(wet).max() + 1e-9
    dry = np.concatenate([x, np.zeros(len(ir))])
    return dry * (1 - mix) + wet * mix * np.abs(x).max()


def drive(x, amount=2.0):
    return np.tanh(x * amount) / np.tanh(amount)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def at(x, offset_s, total=None):
    pad = np.zeros(int(offset_s * SR))
    y = np.concatenate([pad, x])
    if total:
        y = np.pad(y, (0, max(0, int(total * SR) - len(y))))
    return y


def normalize(x, peak=0.89):
    m = np.abs(x).max()
    return x if m < 1e-9 else x / m * peak


def fade(x, fin=0.005, fout=0.03):
    n = len(x)
    a = np.ones(n)
    i = int(fin * SR)
    o = int(fout * SR)
    if i:
        a[:i] = np.linspace(0, 1, i)
    if o:
        a[-o:] *= np.linspace(1, 0, o)
    return x * a


def encode_ogg(x: np.ndarray, quality: int = 3) -> bytes:
    x = fade(normalize(x))
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "s.wav")
        ogg = os.path.join(td, "s.ogg")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        # bitexact + fixed serial keeps the encoded bytes reproducible between builds
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", str(quality),
                        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
                        "-serial_offset", "0", ogg], check=True)
        with open(ogg, "rb") as f:
            return f.read()
