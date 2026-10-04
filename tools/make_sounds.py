"""Synthesise LAIN's sounds: looping ambiences and short interface effects.

Pure Python (math, random, wave), deterministic, no samples from anyone else:
    python tools/make_sounds.py        # writes client/audio/*.wav

Ambiences loop seamlessly (their tail is cross-faded into their head). Levels
are normalised here; the game mixes them per place (AudioDirector.gd).
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parents[1] / "client" / "audio"
TAU = 2 * math.pi


def seconds(value):
    return int(value * RATE)


class Lowpass:
    def __init__(self, cutoff):
        self.a = 1 - math.exp(-TAU * cutoff / RATE)
        self.y = 0.0

    def __call__(self, x):
        self.y += self.a * (x - self.y)
        return self.y


class Highpass:
    def __init__(self, cutoff):
        self.low = Lowpass(cutoff)

    def __call__(self, x):
        return x - self.low(x)


def pink(rng, count):
    """Paul Kellet's economy pink noise."""
    b0 = b1 = b2 = 0.0
    out = []
    for _ in range(count):
        white = rng.uniform(-1, 1)
        b0 = 0.99765 * b0 + white * 0.0990460
        b1 = 0.96300 * b1 + white * 0.2965164
        b2 = 0.57000 * b2 + white * 1.0526913
        out.append((b0 + b1 + b2 + white * 0.1848) * 0.2)
    return out


def brown(rng, count, leak=0.995):
    y, out = 0.0, []
    for _ in range(count):
        y = y * leak + rng.uniform(-1, 1) * 0.06
        out.append(y)
    return out


def loop(samples, fade):
    """Cross-fade the extra tail into the head so the sound repeats without a seam."""
    body = samples[:-fade]
    for i in range(fade):
        w = i / fade
        body[i] = body[i] * w + samples[len(body) + i] * (1 - w)
    return body


def normalise(samples, peak):
    top = max(abs(s) for s in samples) or 1.0
    return [s * peak / top for s in samples]


def add(target, start, sound, gain=1.0, grow=False):
    """Mixes sound into target at start; one-shots grow to fit, loops keep their length."""
    if grow and start + len(sound) > len(target):
        target.extend([0.0] * (start + len(sound) - len(target)))
    for i, s in enumerate(sound):
        if 0 <= start + i < len(target):
            target[start + i] += s * gain


def tone(freq, length, shape="sine", decay=8.0, attack=0.004):
    out = []
    for i in range(seconds(length)):
        t = i / RATE
        phase = (freq * t) % 1.0
        if shape == "square":
            v = 1.0 if phase < 0.5 else -1.0
        elif shape == "triangle":
            v = 4 * abs(phase - 0.5) - 1
        elif shape == "saw":
            v = 2 * phase - 1
        else:
            v = math.sin(TAU * phase)
        env = min(1.0, t / attack) * math.exp(-decay * t)
        out.append(v * env)
    return out


def echo(samples, delay, feedback, taps=4):
    out = samples + [0.0] * (seconds(delay) * taps)
    for tap in range(1, taps + 1):
        add(out, seconds(delay) * tap, samples, feedback ** tap, grow=True)
    return out


def write(name, samples):
    OUT.mkdir(parents=True, exist_ok=True)
    data = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(data)
    print(f"{name}.wav  {len(samples) / RATE:.2f} s")


# ------------------------------------------------------------------ ambiences

def rain(rng, length=8.0, muffled=False):
    count = seconds(length) + seconds(0.5)
    body = pink(rng, count)
    low, hiss = Lowpass(900 if muffled else 3200), Highpass(2500)
    out = [low(s) * (1.0 if muffled else 0.8) + (0.0 if muffled else hiss(s) * 0.35) for s in body]
    drop_filter = Lowpass(1500 if muffled else 5000)
    for _ in range(int(length * (14 if muffled else 38))):
        start = rng.randrange(count)
        size = rng.uniform(0.2, 1.0)
        click = [drop_filter(rng.uniform(-1, 1)) * size * math.exp(-i / 60) for i in range(seconds(0.02))]
        add(out, start, click, 0.9)
    return normalise(loop(out, seconds(0.5)), 0.5)


def hum(rng, length=8.0):
    out = []
    for i in range(seconds(length)):
        t = i / RATE
        flicker = 1 + 0.06 * math.sin(TAU * 0.25 * t) + 0.02 * math.sin(TAU * 3.0 * t)
        v = (0.5 * math.sin(TAU * 50 * t) + 0.35 * math.sin(TAU * 100 * t)
             + 0.15 * math.sin(TAU * 150 * t) + 0.08 * math.sin(TAU * 200 * t)) * flicker
        out.append(v + rng.uniform(-1, 1) * 0.015)
    return normalise(out, 0.45)


def room(rng, length=8.0):
    count = seconds(length) + seconds(0.5)
    low = Lowpass(380)
    out = [low(s) for s in brown(rng, count)]
    return normalise(loop(out, seconds(0.5)), 0.4)


def arcade(rng, length=8.0):
    out = hum(rng, length)
    out = [s * 0.25 for s in out]
    scale = [523.3, 587.3, 659.3, 784.0, 880.0, 1046.5, 1174.7, 1318.5, 1568.0]
    t = 0.0
    while t < length - 0.6:
        notes = rng.randint(3, 6)
        step = rng.choice([0.06, 0.08, 0.1])
        root = rng.randrange(len(scale) - 3)
        for n in range(notes):
            freq = scale[min(len(scale) - 1, root + rng.choice([0, 1, 2, 3]))]
            add(out, seconds(t + n * step), tone(freq, step * 0.9, "square", decay=18), 0.12)
        t += notes * step + rng.uniform(0.25, 0.7)
    return normalise(out, 0.5)


def club(rng, length=8.0):
    beat = 0.5          # 120 bpm: 16 beats in 8 s, so the loop is exact
    out = [0.0] * seconds(length)
    for b in range(int(length / beat)):
        start = seconds(b * beat)
        kick = []
        for i in range(seconds(0.3)):
            t = i / RATE
            freq = 45 + 85 * math.exp(-t * 28)
            kick.append(math.sin(TAU * freq * t) * math.exp(-t * 9))
        add(out, start, kick, 0.9)
        hat_filter = Highpass(6000)
        hat = [hat_filter(rng.uniform(-1, 1)) * math.exp(-i / 300) for i in range(seconds(0.05))]
        add(out, start + seconds(beat / 2), hat, 0.25)
        bass_note = [55.0, 55.0, 65.4, 49.0][(b // 4) % 4]
        add(out, start + seconds(beat / 2), tone(bass_note, beat * 0.45, "saw", decay=5), 0.22)
    low = Lowpass(2400)
    return normalise([low(s) for s in out], 0.6)


def station(rng, length=10.0):
    count = seconds(length) + seconds(0.8)
    low = Lowpass(110)
    rumble = [low(s) for s in brown(rng, count, leak=0.998)]
    out = []
    for i, s in enumerate(rumble):
        t = i / RATE
        swell = 0.7 + 0.3 * math.sin(TAU * t / (length + 0.8))
        out.append(s * swell)
    out = loop(out, seconds(0.8))
    buzz = hum(rng, len(out) / RATE)
    return normalise([a + b * 0.15 for a, b in zip(out, buzz)], 0.5)


# --------------------------------------------------------------- one-shot effects

def static(rng):
    band_low, band_high = Lowpass(3500), Highpass(400)
    out = []
    for i in range(seconds(1.6)):
        t = i / RATE
        noise = band_high(band_low(rng.uniform(-1, 1)))
        pop = rng.uniform(-1, 1) if rng.random() < 0.002 else 0.0
        carrier = math.sin(TAU * 880 * t) * 0.25 * math.exp(-t * 2)
        env = min(1.0, t / 0.05) * min(1.0, (1.6 - t) / 0.4)
        out.append((noise * 0.6 + pop + carrier) * env)
    return normalise(out, 0.6)


def key(rng):
    high = Highpass(1800)
    out = [high(rng.uniform(-1, 1)) * math.exp(-i / 70) for i in range(seconds(0.03))]
    add(out, 0, tone(2100, 0.012, "sine", decay=300), 0.4)
    return normalise(out, 0.5)


def effects(rng):
    blip = tone(880, 0.05, decay=40)
    add(blip, seconds(0.05), tone(1320, 0.07, decay=35), grow=True)
    error = tone(140, 0.2, "square", decay=12)
    mail = tone(1318.5, 0.5, decay=7)
    add(mail, seconds(0.12), tone(1975.5, 0.5, decay=7), 0.8, grow=True)
    complete = []
    for n, freq in enumerate([523.3, 659.3, 784.0, 1046.5]):
        note = [a * 0.7 + b * 0.3 for a, b in zip(tone(freq, 0.9, decay=4), tone(freq, 0.9, "triangle", decay=4))]
        add(complete, seconds(n * 0.13), note, grow=True)
    complete = echo(complete, 0.18, 0.35)
    hint = tone(880, 0.6, decay=6)
    add(hint, seconds(0.15), tone(1318.5, 0.6, decay=6), 0.7, grow=True)
    door_filter = Lowpass(700)
    door = [door_filter(rng.uniform(-1, 1)) * math.sin(math.pi * i / seconds(0.45)) for i in range(seconds(0.45))]
    add(door, seconds(0.38), tone(220, 0.06, "square", decay=60), 0.3)
    return {"enter": blip, "error": error, "mail": mail, "complete": complete, "hint": echo(hint, 0.16, 0.3, 2),
            "door": door}


def main():
    rng = random.Random(7)
    write("rain", rain(rng))
    write("rain_window", rain(rng, muffled=True))
    write("hum", hum(rng))
    write("room", room(rng))
    write("arcade", arcade(rng))
    write("club", club(rng))
    write("station", station(rng))
    write("static", static(rng))
    write("key", key(rng))
    for name, samples in effects(rng).items():
        write(name, normalise(samples, 0.7))


if __name__ == "__main__":
    main()
