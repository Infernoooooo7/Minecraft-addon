"""Original synthesized sound effects and their registration (sound_definitions.json / sounds.json)."""
from __future__ import annotations

import numpy as np

from tools.content.common import NS
from tools.content.registry import REG
from tools.lib import sound as S

# ------------------------------------------------------------------------------------------------
# sound recipes
# ------------------------------------------------------------------------------------------------

def growl(base: float, dur: float, seed: int, bend: float = 0.7, rough: float = 0.5, formant=(300, 1800)):
    f = S.sweep(base, base * bend, dur) * (1 + 0.04 * np.sin(2 * np.pi * 7 * S.time(dur)))
    tone = S.saw(f) * 0.8 + S.square(f * 0.5) * 0.3
    n = S.noise(dur, seed, "pink") * rough
    sig = S.band(tone + n, formant[0], formant[1])
    return S.drive(sig * S.env(dur, 0.05, 0.2, 0.75, dur * 0.4), 2.5)


def roar(base, dur, seed, formant=(250, 2200), bend=0.6):
    body = growl(base, dur, seed, bend, 0.7, formant)
    hi = growl(base * 2.01, dur, seed + 1, bend, 0.5, (900, 4200)) * 0.35
    return S.reverb(S.mix(body, hi), 1.4, 0.35, seed)


def boom(dur=1.6, f0=110, f1=32, seed=5, crack=0.6):
    sub = S.sine(S.sweep(f0, f1, dur)) * S.decay(dur, 3.0)
    n = S.band(S.noise(dur, seed, "brown"), hi=900) * S.decay(dur, 6.0) * crack
    return S.reverb(S.drive(S.mix(sub, n), 1.8), 1.6, 0.3, seed)


def whoosh(dur=0.5, f0=400, f1=3000, seed=7):
    n = S.noise(dur, seed)
    parts = []
    steps = 16
    seg = len(n) // steps
    for i in range(steps):
        fc = f0 * (f1 / f0) ** (i / (steps - 1))
        chunk = n[i * seg:(i + 1) * seg]
        parts.append(S.band(chunk, fc * 0.6, fc * 1.6))
    sig = np.concatenate(parts)
    e = np.sin(np.linspace(0, np.pi, len(sig))) ** 1.5
    return sig * e


def zap(f0=1800, f1=200, dur=0.35, seed=9):
    f = S.sweep(f0, f1, dur)
    mod = S.sine(f * 2.7) * f * 0.8
    sig = S.sine(f + mod) * S.decay(dur, 9.0)
    return S.mix(sig, S.band(S.noise(dur, seed), 2000) * S.decay(dur, 20) * 0.4)


def chime(freqs, dur=1.6, seed=11, rev=0.4):
    sig = S.mix(*[S.sine(f, dur) * S.decay(dur, 2.5 + i) * (0.8 ** i) for i, f in enumerate(freqs)])
    return S.reverb(sig, 1.8, rev, seed)


def drone(freqs, dur=3.0, seed=13, lp=900):
    sig = S.mix(*[S.saw(f * (1 + 0.003 * k), dur) for k, f in enumerate(freqs)])
    sig = S.band(sig, hi=lp)
    lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 0.6 * S.time(dur))
    return sig * lfo * S.env(dur, 0.4, 0.2, 0.9, 0.8)


def creak(dur=0.9, seed=15, rate=45):
    t = S.time(dur)
    r = rate * (1 + 0.5 * np.sin(2 * np.pi * 1.3 * t))
    pulses = (np.diff(np.floor(np.cumsum(r) / S.SR), prepend=0) > 0).astype(float)
    sig = S.band(pulses + S.noise(dur, seed) * 0.05, 250, 1600)
    return sig * S.env(dur, 0.05, 0.1, 0.8, 0.3)


def clank(dur=0.8, seed=17, base=320):
    ratios = [1.0, 2.76, 5.40, 8.93, 13.34]
    sig = S.mix(*[S.sine(base * r, dur) * S.decay(dur, 4 + 3 * i) * (0.7 ** i) for i, r in enumerate(ratios)])
    return S.reverb(sig, 1.0, 0.25, seed)


def hiss(dur=1.2, seed=19):
    return S.band(S.noise(dur, seed), 3000) * S.env(dur, 0.05, 0.2, 0.7, 0.6)


def chirp(dur=0.25, seed=21, f0=3000):
    out = []
    rng = np.random.default_rng(seed)
    for i in range(3):
        d = 0.06
        f = S.sweep(f0 * (1 + rng.random() * 0.3), f0 * 1.8, d)
        out.append(S.at(S.sine(f) * S.decay(d, 30), i * 0.08))
    return S.mix(*out)


def clicks(dur=0.5, seed=23):
    rng = np.random.default_rng(seed)
    sig = np.zeros(int(dur * S.SR))
    for _ in range(9):
        i = int(rng.random() * (len(sig) - 400))
        sig[i:i + 300] += S.band(S.noise(300 / S.SR, int(rng.integers(1, 999))), 1500, 6000)
    return sig


def whisper(dur=1.2, seed=25):
    n = S.noise(dur, seed)
    a = S.band(n, 600, 1500) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * S.time(dur)))
    b = S.band(n, 1800, 3200) * (0.5 + 0.5 * np.sin(2 * np.pi * 4.3 * S.time(dur) + 1))
    return S.reverb(S.mix(a, b) * S.env(dur, 0.2, 0.2, 0.8, 0.5), 1.2, 0.4, seed)


def glitch(dur=1.0, seed=27):
    rng = np.random.default_rng(seed)
    out = np.zeros(int(dur * S.SR))
    pos = 0
    while pos < len(out) - 2000:
        seg = int(rng.integers(800, 4000))
        f = float(rng.choice([220, 330, 440, 660, 880, 1320]))
        piece = S.square(f, seg / S.SR) * (0.3 + rng.random() * 0.5)
        n = min(len(piece), len(out) - pos)
        out[pos:pos + n] += piece[:n]
        pos += seg + int(rng.integers(0, 1500))
    return S.band(out, 150, 6000)


def heartbeat(seed=29):
    thump = lambda: S.sine(S.sweep(70, 38, 0.18)) * S.decay(0.18, 14)
    return S.mix(S.at(thump(), 0.0), S.at(thump() * 0.7, 0.22), S.at(thump(), 0.9), S.at(thump() * 0.7, 1.12))


def stinger(chord, dur=3.5, seed=31, dark=True):
    pad = drone(chord, dur, seed, lp=1200 if dark else 3000)
    bell = chime([c * 4 for c in chord[:2]], dur, seed + 1, 0.5) * 0.4
    return S.reverb(S.mix(pad, bell), 2.2, 0.4, seed)


# ------------------------------------------------------------------------------------------------
# catalogue: id -> (category, generator list, volume, 3d)
# ------------------------------------------------------------------------------------------------

def catalogue() -> dict:
    C = {}

    def add(sid, cat, gens, vol=1.0, is3d=True, max_dist=48.0):
        C[sid] = (cat, gens, vol, is3d, max_dist)

    # bosses -------------------------------------------------------------------------------
    add("mob.apocalypse.hollow_king.ambient", "hostile", [lambda: whisper(1.6, 101)], 0.8)
    add("mob.apocalypse.hollow_king.hurt", "hostile", [lambda: growl(95, 0.35, 102), lambda: growl(105, 0.3, 103)])
    add("mob.apocalypse.hollow_king.death", "hostile", [lambda: roar(90, 2.6, 104, bend=0.35)], 1.2, max_dist=96)
    add("mob.apocalypse.hollow_king.roar", "hostile", [lambda: roar(80, 1.8, 105)], 1.3, max_dist=96)
    add("apocalypse.hollow_king.slash", "hostile", [lambda: whoosh(0.35, 600, 4500, 106)])
    add("apocalypse.hollow_king.quake", "hostile", [lambda: boom(1.8, 90, 28, 107)], 1.3, max_dist=72)
    add("apocalypse.hollow_king.summon", "hostile", [lambda: S.mix(chime([196, 233, 277, 311], 2.2, 108), whisper(2.0, 109) * 0.6)])
    add("apocalypse.hollow_king.teleport", "hostile", [lambda: whoosh(0.5, 3000, 300, 110)])
    add("apocalypse.hollow_king.chains", "hostile", [lambda: S.mix(clank(0.9, 111, 260), clank(0.9, 112, 340) * 0.6)])

    add("mob.apocalypse.star_eater.ambient", "hostile", [lambda: drone([55, 82.5, 110], 2.5, 120, lp=700)], 0.8)
    add("mob.apocalypse.star_eater.hurt", "hostile", [lambda: zap(900, 300, 0.4, 121)])
    add("mob.apocalypse.star_eater.death", "hostile", [lambda: S.mix(boom(2.8, 140, 20, 122), zap(2400, 60, 2.6, 123) * 0.5)], 1.3, max_dist=96)
    add("mob.apocalypse.star_eater.roar", "hostile", [lambda: S.reverb(S.mix(zap(400, 1600, 1.6, 124), growl(70, 1.6, 125) * 0.7), 1.6, 0.4, 125)], 1.3, max_dist=96)
    add("apocalypse.star_eater.bolt", "hostile", [lambda: zap(2200, 500, 0.3, 126)])
    add("apocalypse.star_eater.charge", "hostile", [lambda: S.mix(S.sine(S.sweep(80, 900, 3.0)) * S.env(3.0, 2.5, 0.1, 1, 0.2) * 0.6,
                                                                  S.band(S.noise(3.0, 127), 2000) * S.env(3.0, 2.8, 0.1, 1, 0.1) * 0.3)], 1.2, max_dist=80)
    add("apocalypse.star_eater.nova", "hostile", [lambda: boom(2.6, 180, 25, 128, crack=1.0)], 1.4, max_dist=96)
    add("apocalypse.star_eater.gravity", "hostile", [lambda: S.sine(S.sweep(60, 30, 2.0)) * (0.6 + 0.4 * np.sin(2 * np.pi * 6 * S.time(2.0))) * S.env(2.0, 0.2, 0.2, 0.8, 0.6)])

    add("mob.apocalypse.root_titan.ambient", "hostile", [lambda: creak(1.4, 130, 30)], 0.9)
    add("mob.apocalypse.root_titan.hurt", "hostile", [lambda: S.mix(creak(0.35, 131, 90), growl(70, 0.35, 132) * 0.5)])
    add("mob.apocalypse.root_titan.death", "hostile", [lambda: S.mix(boom(2.4, 80, 25, 133), creak(2.4, 134, 60) * 0.8)], 1.3, max_dist=96)
    add("mob.apocalypse.root_titan.roar", "hostile", [lambda: S.mix(roar(60, 2.0, 135, formant=(150, 1400)), creak(2.0, 136, 40) * 0.5)], 1.3, max_dist=96)
    add("apocalypse.root_titan.slam", "hostile", [lambda: boom(1.6, 100, 30, 137)], 1.3, max_dist=72)
    add("apocalypse.root_titan.eruption", "hostile", [lambda: S.mix(boom(1.2, 140, 50, 138, 0.9), creak(1.0, 139, 120) * 0.6)], 1.1)

    add("mob.apocalypse.null_colossus.ambient", "hostile", [lambda: drone([41.2, 61.7, 82.4, 123.5], 3.0, 140, lp=600)], 0.9)
    add("mob.apocalypse.null_colossus.hurt", "hostile", [lambda: clank(0.5, 141, 180)])
    add("mob.apocalypse.null_colossus.death", "hostile", [lambda: S.mix(boom(3.2, 70, 18, 142, 1.0), clank(3.0, 143, 90) * 0.7)], 1.4, max_dist=128)
    add("mob.apocalypse.null_colossus.roar", "hostile", [lambda: S.reverb(S.drive(S.mix(drone([36.7, 55, 73.4], 2.2, 144, lp=1500), growl(55, 2.2, 145) * 0.8), 3.0), 2.0, 0.4, 145)], 1.4, max_dist=128)
    add("apocalypse.null_colossus.beam", "hostile", [lambda: S.mix(S.saw(S.sweep(220, 260, 2.0)) * 0.3, zap(3000, 1500, 2.0, 146) * 0.4)], 1.2, max_dist=80)
    add("apocalypse.null_colossus.gravity", "hostile", [lambda: S.mix(S.sine(S.sweep(90, 25, 1.8)) * S.decay(1.8, 1.5), whoosh(1.8, 2000, 200, 147) * 0.5)], 1.3, max_dist=80)
    add("apocalypse.null_colossus.vent", "hostile", [lambda: S.mix(hiss(1.5, 148), clank(1.0, 149, 400) * 0.4)], 1.2)

    # mobs ---------------------------------------------------------------------------------
    for mob, amb, hurt_f, death_f in (
            ("hollow_shade", lambda: whisper(1.2, 150), lambda: growl(180, 0.3, 151, formant=(500, 3000)), lambda: S.mix(whisper(1.5, 152), growl(150, 1.2, 153, 0.4) * 0.6)),
            ("void_crawler", lambda: clicks(0.6, 154), lambda: S.mix(clicks(0.3, 155), chirp(0.25, 156, 1800)), lambda: S.mix(clicks(0.8, 157), growl(130, 0.8, 158) * 0.4)),
            ("astral_mite", lambda: chirp(0.3, 159, 3200), lambda: chirp(0.2, 160, 4200), lambda: chime([1760, 2217], 0.8, 161, 0.2)),
            ("thornling", lambda: creak(0.6, 162, 70), lambda: creak(0.25, 163, 140), lambda: creak(0.9, 164, 90)),
            ("rift_sentinel", lambda: drone([110, 165], 1.5, 165, lp=1200) * 0.6, lambda: clank(0.35, 166, 520), lambda: S.mix(clank(1.0, 167, 300), zap(1200, 100, 1.0, 168) * 0.5))):
        add(f"mob.apocalypse.{mob}.ambient", "hostile", [amb], 0.7, max_dist=24)
        add(f"mob.apocalypse.{mob}.hurt", "hostile", [hurt_f], 0.9, max_dist=24)
        add(f"mob.apocalypse.{mob}.death", "hostile", [death_f], 1.0, max_dist=32)
    add("apocalypse.rift_sentinel.shoot", "hostile", [lambda: zap(1600, 600, 0.25, 169)], 0.9)

    # events (non-positional stingers) -------------------------------------------------------
    add("apocalypse.event.blood_moon", "weather", [lambda: S.mix(stinger([55, 65.4, 82.4], 4.0, 170), heartbeat(171) * 0.9)], 0.9, is3d=False)
    add("apocalypse.event.void_storm", "weather", [lambda: S.mix(stinger([49, 58.3, 73.4], 4.0, 172), whoosh(4.0, 200, 1200, 173) * 0.5)], 0.9, is3d=False)
    add("apocalypse.event.meteor_shower", "weather", [lambda: S.mix(stinger([65.4, 98, 130.8], 4.0, 174, dark=False), chime([1046, 1318, 1568], 3.0, 175) * 0.5)], 0.9, is3d=False)
    add("apocalypse.event.reality_fracture", "weather", [lambda: S.mix(stinger([61.7, 87.3, 92.5], 3.5, 176), glitch(3.0, 177) * 0.4)], 0.9, is3d=False)
    add("apocalypse.event.eclipse", "weather", [lambda: S.mix(chime([65.4, 98.0, 131.0, 164.8], 4.5, 178, 0.6), drone([32.7, 49], 4.5, 179, lp=400) * 0.6)], 0.9, is3d=False)
    add("apocalypse.event.end", "weather", [lambda: chime([523, 659, 784, 1046], 2.5, 180, 0.5)], 0.7, is3d=False)

    # world / abilities ----------------------------------------------------------------------
    add("apocalypse.meteor.whistle", "weather", [lambda: S.mix(S.sine(S.sweep(2400, 500, 2.2)) * S.env(2.2, 0.3, 0.2, 0.8, 0.3) * 0.4,
                                                                 whoosh(2.2, 4000, 600, 181) * 0.5)], 1.0, max_dist=96)
    add("apocalypse.meteor.impact", "weather", [lambda: boom(2.2, 130, 25, 182, crack=1.0)], 1.4, max_dist=128)
    add("apocalypse.rift.hum", "hostile", [lambda: drone([73.4, 110, 146.8], 2.0, 183, lp=1600)], 0.7, max_dist=24)
    add("apocalypse.rift.close", "hostile", [lambda: S.mix(whoosh(0.8, 3000, 200, 184), chime([392, 587], 1.0, 185) * 0.5)])
    add("apocalypse.portal.open", "player", [lambda: S.mix(chime([261.6, 392, 523.3, 784], 2.4, 186), whoosh(1.5, 300, 3000, 187) * 0.5)], 1.0)
    add("apocalypse.portal.travel", "player", [lambda: S.mix(whoosh(1.2, 200, 5000, 188), chime([523, 1046], 1.4, 189) * 0.6)], 1.0, is3d=False)
    add("apocalypse.ability.dash", "player", [lambda: whoosh(0.4, 500, 5000, 190)])
    add("apocalypse.ability.reap", "player", [lambda: S.mix(whoosh(0.6, 2500, 300, 191), whisper(0.8, 192) * 0.7)])
    add("apocalypse.ability.gravity", "player", [lambda: S.mix(S.sine(S.sweep(70, 35, 1.4)) * S.decay(1.4, 1.2), whoosh(1.4, 3000, 300, 193) * 0.4)])
    add("apocalypse.ability.slam", "player", [lambda: boom(1.2, 120, 40, 194)])
    add("apocalypse.ability.bolt", "player", [lambda: zap(2600, 700, 0.3, 195)])
    add("apocalypse.ability.crush", "player", [lambda: S.mix(boom(1.4, 90, 22, 196, 0.8), clank(1.0, 197, 150) * 0.4)])
    add("apocalypse.ability.lifesteal", "player", [lambda: chime([880, 1320], 0.6, 198, 0.2)], 0.6)
    add("apocalypse.relic.use", "player", [lambda: S.mix(stinger([73.4, 110, 138.6], 2.5, 199), boom(2.0, 70, 30, 200) * 0.5)], 1.1, max_dist=64)
    add("apocalypse.codex.open", "ui", [lambda: chime([659, 988, 1318], 0.9, 201, 0.3)], 0.6, is3d=False)
    add("apocalypse.boss.phase", "hostile", [lambda: S.mix(boom(1.4, 80, 30, 202, 0.4), chime([110, 116.5, 164.8], 1.8, 203) * 0.7)], 1.2, max_dist=96)
    add("apocalypse.boss.defeat", "player", [lambda: chime([523, 659, 784, 1046, 1318], 3.0, 204, 0.5)], 1.0, is3d=False)
    add("apocalypse.boss.warn", "hostile", [lambda: S.mix(S.square(S.sweep(440, 330, 0.5)) * S.decay(0.5, 3) * 0.3, chime([220, 233], 0.6, 205) * 0.6)], 1.0, max_dist=48)
    return C


ENTITY_SOUNDS = {
    "hollow_king": ("ambient", "hurt", "death"),
    "star_eater": ("ambient", "hurt", "death"),
    "root_titan": ("ambient", "hurt", "death"),
    "null_colossus": ("ambient", "hurt", "death"),
    "hollow_shade": ("ambient", "hurt", "death"),
    "void_crawler": ("ambient", "hurt", "death"),
    "astral_mite": ("ambient", "hurt", "death"),
    "thornling": ("ambient", "hurt", "death"),
    "rift_sentinel": ("ambient", "hurt", "death"),
}


def build():
    cat = catalogue()
    for sid, (category, gens, vol, is3d, max_dist) in cat.items():
        files = []
        for i, g in enumerate(gens):
            rel = "sounds/" + sid.replace(".", "/") + (f"_{i + 1}" if len(gens) > 1 else "")
            REG.rp_bin[rel + ".ogg"] = S.encode_ogg(g())
            files.append({"name": rel, "volume": vol, "is3D": is3d})
        REG.sound_defs[sid] = {"category": category, "min_distance": 2.0, "max_distance": max_dist, "sounds": files}
        REG.ts("sounds", sid.replace("mob.apocalypse.", "").replace("apocalypse.", "").replace(".", "_").upper(), sid)
    for ent, events in ENTITY_SOUNDS.items():
        ev = {e: f"mob.apocalypse.{ent}.{e}" for e in events}
        if ent == "rift_sentinel":
            ev["shoot"] = "apocalypse.rift_sentinel.shoot"
        REG.entity_sounds[f"{NS}:{ent}"] = {"volume": 1.0, "pitch": [0.9, 1.1], "events": ev}
