#!/usr/bin/env python3
"""Dev-only: synthesize the soundtrack of the overview film. Needs numpy.

Nothing is sampled or downloaded: every sound is computed here, so the track belongs to
the repository and comes out the same on every run. 128 beats a minute makes the film's
30 seconds exactly 16 bars, and film.html places its cuts on the same grid.

    bars  1-2    pad and a few plucked notes          the problem
    bars  3-5    pulse and arpeggio enter, one tick   the SOP is read
                 for each row that is read
    bars  6-12   kick, bass, hats: the full groove    the diagram is laid out, then repeated
    bars 13-14   drums out, a rise                    what it asks of you
    bars 15-16   one chord, left to ring              the name

    python3 tools/showreel/music.py out.wav
"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 128
BEAT = 60 / BPM
BAR = 4 * BEAT
DUR = 16 * BAR            # 30 s
N = int(round(DUR * SR))
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def spectral(x, lo=None, hi=None, order=4):
    """Zero-phase filter in the frequency domain: Butterworth-shaped low and/or high cut."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-9)) ** (2 * order))
    return np.fft.irfft(np.fft.rfft(x) * g, len(x))


def place(buf, sig, t0, gain=1.0, pan=0.0):
    """Add a mono signal at second t0. pan: -1 left … +1 right, constant power."""
    i = int(round(t0 * SR))
    if i >= N:
        return
    sig = sig[: N - i]
    a = (pan + 1) * np.pi / 4
    buf[i:i + len(sig), 0] += sig * gain * np.cos(a)
    buf[i:i + len(sig), 1] += sig * gain * np.sin(a)


def pluck(midi, dur=1.2, bright=1.0):
    """A soft mallet: a few harmonics, the higher ones dying sooner."""
    t = np.arange(int(dur * SR)) / SR
    f = hz(midi)
    out = np.zeros_like(t)
    for k, amp in ((1, 1.0), (2, 0.42 * bright), (3, 0.2 * bright), (4, 0.07 * bright)):
        out += amp * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (3.2 + 2.6 * k))
    return out * np.minimum(1, t / 0.004)


def kick():
    t = np.arange(int(0.34 * SR)) / SR
    freq = 46 + 95 * np.exp(-t / 0.032)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.13)
    return body * np.minimum(1, t / 0.002)


def noise_hit(dur, decay, lo=None, hi=None):
    t = np.arange(int(dur * SR)) / SR
    return spectral(rng.standard_normal(len(t)), lo, hi) * np.exp(-t / decay)


def pad_note(midi, dur):
    """Three detuned saws, low-passed, with a slow attack and release."""
    n = int((dur + 0.9) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for cents, pan in ((-8, -0.7), (0, 0.0), (8, 0.7)):
        f = hz(midi) * 2 ** (cents / 1200)
        saw = 2 * ((f * t + rng.random()) % 1) - 1
        a = (pan + 1) * np.pi / 4
        out[:, 0] += saw * np.cos(a)
        out[:, 1] += saw * np.sin(a)
    env = np.minimum(1, t / 0.5) * np.clip((dur + 0.9 - t) / 0.9, 0, 1)
    return out * env[:, None] / 3


# ---------- the score ----------
# one chord for every two bars: (bass note, pad notes, arpeggio notes)
F = (41, [53, 57, 60, 64], [69, 72, 76, 72, 77, 76, 72, 69])       # Fmaj7
Am = (45, [57, 60, 64, 67], [69, 72, 76, 72, 79, 76, 72, 67])      # Am7
C = (36, [55, 60, 64, 67], [67, 72, 76, 72, 79, 76, 74, 72])       # C
G = (43, [55, 59, 62, 67], [67, 71, 74, 71, 79, 74, 71, 67])       # G
CADD9 = (36, [48, 55, 62, 64, 67], [])
CHORDS = [F, Am, C, G, F, Am]            # bars 1-12, two bars each
RISE = [(41, F[1]), (43, G[1])]          # bars 13 and 14, one bar each

pads = np.zeros((N, 2))
bass = np.zeros((N, 2))
drums = np.zeros((N, 2))
keys = np.zeros((N, 2))      # plucks: these go to the reverb

kicks = []                    # times, for ducking the pad and bass


def bar(n):                   # start of bar n, counted from 1
    return (n - 1) * BAR


def add_pad(notes, t0, dur, gain=1.0):
    for m in notes:
        sig = pad_note(m, dur)
        i = int(round(t0 * SR))
        seg = sig[: N - i]
        pads[i:i + len(seg)] += seg * gain


def bass_note(midi, dur, soft=False):
    t = np.arange(int(dur * SR)) / SR
    f = hz(midi)
    sig = np.sin(2 * np.pi * f * t) + (0.0 if soft else 0.28) * np.sin(4 * np.pi * f * t)
    rel = 0.25 if soft else 0.04
    return sig * np.minimum(1, t / (0.3 if soft else 0.008)) * np.clip((dur - t) / rel, 0, 1)


KICK, HAT, CLAP = kick(), noise_hit(0.09, 0.016, lo=7500), noise_hit(0.3, 0.07, lo=900, hi=4200)

for i, (root, chord, arp) in enumerate(CHORDS):
    first = 2 * i + 1                               # this chord's first bar
    add_pad(chord, bar(first), 2 * BAR, gain=0.8 if first < 3 else 1.0)
    for n in (first, first + 1):
        t0 = bar(n)
        if n <= 2:                                  # the opening: four notes a bar, nothing else
            for k, step in enumerate((0, 1.5, 2.5, 3.5)):
                place(keys, pluck(arp[(k * 2 + n) % 8], 1.6, 0.7), t0 + step * BEAT, 0.20, (-0.4, 0.4)[k % 2])
            continue
        for k in range(8):                          # eighth-note arpeggio, accents on the beat
            vel = (0.30, 0.17, 0.24, 0.17)[k % 4] * (0.75 if n <= 5 else 1.0)
            place(keys, pluck(arp[k], 0.9), t0 + k * BEAT / 2, vel, 0.45 * (-1) ** k)
        if n <= 5:                                  # the pulse: a held bass note, kick on 1 and 3
            place(bass, bass_note(root, BAR, soft=True), t0, 0.15)
            for beat in (0, 2):
                place(drums, KICK, t0 + beat * BEAT, 0.5)
                kicks.append(t0 + beat * BEAT)
        else:                                       # the groove
            for beat in range(4):
                place(drums, KICK, t0 + beat * BEAT, 0.78)
                kicks.append(t0 + beat * BEAT)
                place(bass, bass_note(root + (12 if beat == 3 else 0), BEAT * 0.42), t0 + (beat + 0.5) * BEAT, 0.42)
                place(drums, HAT, t0 + (beat + 0.5) * BEAT, 0.085, 0.25)
                if n >= 8:
                    place(drums, HAT, t0 + (beat + 0.75) * BEAT, 0.035, -0.25)
            if n >= 7:
                for beat in (1, 3):
                    place(drums, CLAP, t0 + beat * BEAT, 0.11)

# one tick for each SOP row as it is read (film.html: beat 12, every beat and a half)
for i in range(5):
    place(keys, pluck(88, 0.5, 0.4), (12 + 1.5 * i) * BEAT, 0.13, -0.5 + 0.25 * i)

# "Same input. Same diagram. Every time." — one chord for each (beats 40, 42, 44)
for beat, top in ((40, 76), (42, 79), (44, 81)):
    for m in (57, 64, top - 12, top):
        place(keys, pluck(m, 1.4), beat * BEAT, 0.20, 0.0)

# bars 13-14: the drums stop and the harmony climbs
for i, (root, chord) in enumerate(RISE):
    add_pad(chord, bar(13 + i), BAR, gain=1.1)
    place(bass, bass_note(root, BAR, soft=True), bar(13 + i), 0.17)
    for k, m in enumerate((72, 76, 79, 84)):
        place(keys, pluck(m + (2 if i else 0) - 12, 1.0), bar(13 + i) + k * BEAT, 0.20, 0.3 * (-1) ** k)
t = np.arange(int(2 * BAR * SR)) / SR
rise = spectral(rng.standard_normal(len(t)), lo=2500, hi=11000) * (t / t[-1]) ** 3
place(drums, rise, bar(13), 0.07)

# bars 15-16: the name. One chord and one low note, left to ring out.
add_pad(CADD9[1], bar(15), 1.2 * BAR, gain=1.15)
place(bass, bass_note(CADD9[0], 1.6 * BAR, soft=True), bar(15), 0.2)
place(drums, KICK, bar(15), 0.7)
kicks.append(bar(15))
for k, m in enumerate((60, 67, 72, 74, 76, 79, 84)):
    place(keys, pluck(m, 2.6, 0.8), bar(15) + k * 0.035, 0.22, (k % 3 - 1) * 0.5)

# ---------- the mix ----------
tt = np.arange(N) / SR
duck = np.ones(N)                                   # the pad and bass make room for each kick
for k in kicks:
    i = int(round(k * SR))
    seg = np.arange(N - i) / SR
    duck[i:] = np.minimum(duck[i:], 1 - 0.55 * np.exp(-seg / 0.11))

pads = np.stack([spectral(pads[:, c], lo=140, hi=1500, order=2) for c in (0, 1)], axis=1) * duck[:, None]
bass = np.stack([spectral(bass[:, c], hi=320, order=3) for c in (0, 1)], axis=1) * (0.4 + 0.6 * duck)[:, None]

# a small room: decaying noise as the impulse response, different in each ear
ir_t = np.arange(int(1.9 * SR)) / SR
send = keys * 0.9 + pads * 0.35 + drums * 0.06
wet = np.zeros((N, 2))
for c in (0, 1):
    ir = spectral(rng.standard_normal(len(ir_t)), lo=250, hi=5200, order=2) * np.exp(-ir_t / 0.42)
    ir[: int(0.012 * SR)] = 0
    size = N + len(ir)
    wet[:, c] = np.fft.irfft(np.fft.rfft(send[:, c], size) * np.fft.rfft(ir, size), size)[:N]
wet /= 55

mix = 0.22 * pads + bass + drums + 1.15 * keys + 0.5 * wet
mix *= np.minimum(1, tt / 0.03)[:, None]            # no click at the start
mix *= np.clip((DUR - tt) / 2.2, 0, 1)[:, None] ** 1.5      # the last chord fades to nothing
mix = np.tanh(1.1 * mix / np.max(np.abs(mix)))      # gentle saturation instead of hard peaks
mix *= 0.7 / np.max(np.abs(mix))                    # about -3 dBFS: it sits under the picture


def main(argv=None):
    out = (argv or sys.argv[1:] or ["showreel.wav"])[0]
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
