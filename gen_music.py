#!/usr/bin/env python3
"""Synthesise a light, upbeat 'educational' background track (royalty-free, made from scratch).

Usage: python3 gen_music.py <out.wav> <duration_seconds>
Style: 100 BPM, C major, I-V-vi-IV progression, marimba-like arpeggio, soft pad,
gentle bass, light kick + shaker (drums enter after the intro bars).
"""
import sys
import wave

import numpy as np

OUT, DUR = sys.argv[1], float(sys.argv[2])
SR = 48000
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
N = int(SR * (DUR + 1.5))
L = np.zeros(N)
R = np.zeros(N)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def marimba(f, d=0.9):
    t = np.arange(int(SR * d)) / SR
    env = np.exp(-5.5 * t) * (1 - np.exp(-t * 400))
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-18 * t) \
        + 0.12 * np.sin(2 * np.pi * 10 * f * t) * np.exp(-40 * t)
    return s * env


def pad(freqs, d):
    t = np.arange(int(SR * d)) / SR
    env = np.minimum(1, t / 0.6) * np.minimum(1, (d - t) / 0.6)
    s = sum(np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.004 * t + 1.3)
            + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in freqs)
    return s * env / len(freqs)


def bass(f, d):
    t = np.arange(int(SR * d)) / SR
    env = np.exp(-2.5 * t) * (1 - np.exp(-t * 300)) * np.minimum(1, (d - t) / 0.05)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)) * env


def kick():
    t = np.arange(int(SR * 0.35)) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


rng = np.random.default_rng(7)


def shaker():
    t = np.arange(int(SR * 0.09)) / SR
    n = rng.standard_normal(len(t))
    n = n - np.convolve(n, np.ones(6) / 6, mode="same")  # crude high-pass
    return n * np.exp(-t * 55) * (1 - np.exp(-t * 900))


# C major: I - V - vi - IV  (root midi, triad)
CHORDS = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
ARP = [0, 1, 2, 3, 2, 1, 2, 3]  # index into chord tones + octave

nbars = int(np.ceil(DUR / BAR))
for b in range(nbars):
    root, tri = CHORDS[b % 4]
    t0 = b * BAR
    last = b == nbars - 1
    add(pad([midi(m - 12) for m in tri], BAR + 0.3), t0, 0, 0.16)
    tones = tri + [tri[0] + 12]
    if not last:
        for k in range(8):
            m = tones[ARP[k]] + 12
            add(marimba(midi(m)), t0 + k * BEAT / 2, pan=(-0.35 if k % 2 else 0.35), gain=0.22)
        # little melodic answer on the 2nd and 4th bar of each phrase
        if b % 2 == 1:
            add(marimba(midi(tones[2] + 24), 1.2), t0 + 3 * BEAT, 0.1, 0.12)
            add(marimba(midi(tones[3] + 24), 1.2), t0 + 3.5 * BEAT, -0.1, 0.12)
    else:
        for m in tones:
            add(marimba(midi(m + 12), 2.0), t0, 0, 0.2)
    add(bass(midi(root), BEAT * 1.9), t0, 0, 0.33)
    if not last:
        add(bass(midi(root), BEAT * 1.9), t0 + 2 * BEAT, 0, 0.28)
    if b >= 2 and not last:  # drums enter after the intro
        for k in range(4):
            if k in (0, 2):
                add(kick(), t0 + k * BEAT, 0, 0.35)
        for k in range(8):
            add(shaker(), t0 + k * BEAT / 2 + 0.0, pan=0.4, gain=0.05 if k % 2 else 0.025)

# simple stereo delay for space
d = int(SR * BEAT * 0.75)
for src, dst in ((L, R), (R, L)):
    dst[d:] += 0.18 * src[:-d]

st = np.stack([L, R], 1)[: int(SR * DUR)]
fade = int(SR * 2.5)
st[-fade:] *= np.linspace(1, 0, fade)[:, None]
st[: int(SR * 0.3)] *= np.linspace(0, 1, int(SR * 0.3))[:, None]
st /= np.max(np.abs(st)) / 0.8
pcm = (st * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("music:", OUT)
