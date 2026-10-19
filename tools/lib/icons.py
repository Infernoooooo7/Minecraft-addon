"""Procedural item-icon painter.

Icons are composed on a 16-unit design grid and rendered at 16*density px (density 1/2/4 =>
16/32/64 px). Each layer is a polygon/disc filled with a shaded material, lit from the top-left,
then the whole icon gets a dark outline (vanilla-style readability) and a PBR side-channel so items
can glow under Vibrant Visuals.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from . import tex


class Icon:
    def __init__(self, density: int, seed: int = 1):
        self.d = density
        self.s = 16 * density
        self.cv = tex.Canvas(self.s, self.s)
        self.seed = seed

    # coordinate helpers (design grid 0..16)
    def P(self, pts):
        return [(x * self.d, y * self.d) for x, y in pts]

    def _fill(self, mask: np.ndarray, kind: str, palette=None, glow: float = 0.0, light=True,
              metal: float | None = None, rough: float | None = None, seed_off: int = 0):
        s = self.s
        sw = tex.material(kind, s, s, self.seed * 31 + seed_off, palette=palette, detail=0.6)
        rgb = sw.rgb
        if light:
            yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) / s
            shade = 1.18 - 0.42 * (xx * 0.45 + yy * 0.55)
            rgb = np.clip(rgb * shade[..., None], 0, 1)
            # inner highlight along mask edge facing light
            m_shift = np.roll(np.roll(mask, self.d, axis=0), self.d, axis=1)
            rim = np.clip(mask - m_shift, 0, 1)
            rgb = np.clip(rgb + rim[..., None] * 0.28, 0, 1)
            m_shift2 = np.roll(np.roll(mask, -self.d, axis=0), -self.d, axis=1)
            dark = np.clip(mask - m_shift2, 0, 1)
            rgb = rgb * (1 - dark[..., None] * 0.35)
        emis = np.maximum(sw.emissive, glow) if glow else sw.emissive
        self.cv.paint(0, 0, rgb, mask, metal=sw.metal if metal is None else metal,
                      emissive=emis, rough=sw.rough if rough is None else rough, height=sw.height)

    def poly(self, pts, kind, palette=None, **kw):
        m = tex.poly_mask(self.s, self.s, self.P(pts))
        self._fill(m, kind, palette, **kw)
        return m

    def disc(self, cx, cy, r, kind, palette=None, **kw):
        m = tex.disc_mask(self.s, self.s, cx * self.d, cy * self.d, r * self.d, soft=max(0.6, self.d * 0.5))
        self._fill(m, kind, palette, **kw)
        return m

    def ring(self, cx, cy, r, th, kind, palette=None, **kw):
        m = tex.ring_mask(self.s, self.s, cx * self.d, cy * self.d, r * self.d, th * self.d, soft=max(0.6, self.d * 0.5))
        self._fill(m, kind, palette, **kw)
        return m

    def line(self, p0, p1, width, kind, palette=None, **kw):
        m = tex.line_mask(self.s, self.s, (p0[0] * self.d, p0[1] * self.d), (p1[0] * self.d, p1[1] * self.d), width * self.d)
        self._fill(m, kind, palette, **kw)
        return m

    def sparkle(self, cx, cy, r, color, glow=1.0):
        s = self.s
        c = tex.hex_rgb(color)
        m = np.maximum(tex.line_mask(s, s, ((cx - r) * self.d, cy * self.d), ((cx + r) * self.d, cy * self.d), max(1, self.d * 0.6)),
                       tex.line_mask(s, s, (cx * self.d, (cy - r) * self.d), (cx * self.d, (cy + r) * self.d), max(1, self.d * 0.6)))
        self.cv.paint(0, 0, np.broadcast_to(c, (s, s, 3)).copy(), m, emissive=glow, metal=0.0, rough=0.2)

    def glyph(self, cx, cy, size, color, seed=0):
        gs = max(4, int(size * self.d))
        g = tex.glyph(gs, self.seed + seed)
        m = np.zeros((self.s, self.s), dtype=np.float32)
        x0 = int(cx * self.d - gs / 2)
        y0 = int(cy * self.d - gs / 2)
        m[max(0, y0):y0 + gs, max(0, x0):x0 + gs] = g[:min(gs, self.s - y0), :min(gs, self.s - x0)]
        c = tex.hex_rgb(color)
        self.cv.paint(0, 0, np.broadcast_to(c, (self.s, self.s, 3)).copy(), m, emissive=1.0, rough=0.3)

    def finish(self) -> tex.Canvas:
        img = self.cv.image()
        img = tex.outline(img)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        self.cv.rgba = arr
        return self.cv


# ------------------------------------------------------------------------------------------------
# reusable icon archetypes
# ------------------------------------------------------------------------------------------------

def crystal_cluster(ic: Icon, pal, glow=0.8, kind="crystal"):
    ic.poly([(4, 15), (2.5, 9), (5, 6), (7, 14)], kind, pal, glow=glow * 0.7, seed_off=1)
    ic.poly([(11, 15), (13.5, 8), (11.5, 5), (9, 14)], kind, pal, glow=glow * 0.7, seed_off=2)
    ic.poly([(6, 15), (6.5, 4), (8.5, 1), (10.5, 4), (10.5, 15)], kind, pal, glow=glow, seed_off=3)


def gem(ic: Icon, pal, glow=0.6):
    ic.poly([(8, 1.5), (13.5, 6), (8, 14.5), (2.5, 6)], "crystal", pal, glow=glow)
    ic.poly([(8, 1.5), (10.5, 6), (8, 14.5), (5.5, 6)], "crystal", [(0, "#ffffff"), (1, pal[-1][1])], glow=glow, seed_off=5)


def ingot(ic: Icon, kind, pal, glow=0.0):
    ic.poly([(2, 10), (5, 6), (14, 6), (11, 10)], kind, [(0, pal[1][1]), (1, pal[-2][1])], glow=glow, seed_off=1)
    ic.poly([(2, 10), (11, 10), (11, 13), (2, 13)], kind, pal, glow=glow, seed_off=2)
    ic.poly([(11, 10), (14, 6), (14, 9), (11, 13)], kind, [(0, pal[0][1]), (1, pal[1][1])], glow=glow, seed_off=3)


def vial(ic: Icon, liquid_pal, glow=0.8):
    ic.poly([(6.5, 1.5), (9.5, 1.5), (9.5, 3), (6.5, 3)], "bronze", None, seed_off=1)
    ic.poly([(7, 3), (9, 3), (9, 6), (12.5, 9), (12.5, 13.5), (11, 15), (5, 15), (3.5, 13.5), (3.5, 9), (7, 6)],
            "glass", [(0, "#22303f"), (1, "#c8ecff")], seed_off=2)
    ic.poly([(4.2, 10), (11.8, 10), (11.8, 13.2), (10.6, 14.3), (5.4, 14.3), (4.2, 13.2)], "crystal", liquid_pal,
            glow=glow, seed_off=3)
    ic.sparkle(6, 8, 0.8, "#ffffff", glow=0.4)


def orb(ic: Icon, pal, glow=0.9, ring_pal=None):
    ic.disc(8, 8, 5.5, "crystal", pal, glow=glow)
    if ring_pal:
        ic.ring(8, 8, 6.8, 1.2, "bronze", ring_pal)
    ic.disc(6.3, 6.3, 1.6, "crystal", [(0, "#ffffff"), (1, "#ffffff")], glow=glow)


def blade(ic: Icon, blade_kind, blade_pal, guard_pal, grip_pal, glow=0.5, width=2.6, length=1.0, curved=False):
    # diagonal: handle bottom-left -> tip top-right
    tip = (14.5 - (1 - length) * 6, 1.5 + (1 - length) * 6)
    ic.line((2.5, 13.5), (5.0, 11.0), 1.8, "bark", grip_pal, seed_off=1)
    ic.line((3.2, 9.8), (6.2, 12.8), 1.6, "bronze", guard_pal, seed_off=2)
    if curved:
        ic.poly([(5.5, 10.5), (7, 9), (13, 3.5), (tip[0], tip[1]), (9, 9), (6.8, 11.6)], blade_kind, blade_pal, glow=glow)
    else:
        w = width / 2
        ic.poly([(5.6 - w * 0.7, 10.4 - w * 0.7), (tip[0] - 1.2, tip[1] - 0.2), (tip[0], tip[1]),
                 (tip[0] + 0.2, tip[1] + 1.2), (5.6 + w * 0.7, 10.4 + w * 0.7)], blade_kind, blade_pal, glow=glow)
    ic.line((6.5, 9.5), (tip[0] - 1.5, tip[1] + 1.5), 0.6, "crystal", [(0, "#ffffff"), (1, "#ffffff")], glow=glow, seed_off=4)


def staff(ic: Icon, shaft_pal, head_pal, glow=0.9, head="orb"):
    ic.line((2.5, 14), (10.5, 6), 1.4, "bark", shaft_pal, seed_off=1)
    ic.ring(11.5, 4.5, 2.6, 1.0, "bronze", None, seed_off=2)
    if head == "orb":
        ic.disc(11.5, 4.5, 1.9, "crystal", head_pal, glow=glow, seed_off=3)
    else:
        ic.poly([(11.5, 1), (13.5, 4.5), (11.5, 8), (9.5, 4.5)], "crystal", head_pal, glow=glow, seed_off=3)
    ic.sparkle(13.8, 2.0, 1.0, head_pal[-1][1], glow=1.0)


def armor_piece(ic: Icon, piece: str, kind: str, pal, trim: str, glow_trim=0.6):
    trim_pal = [(0, trim), (1, "#ffffff")]
    if piece == "helmet":
        ic.poly([(3, 12), (3, 6), (5, 3), (11, 3), (13, 6), (13, 12), (10.5, 12), (10.5, 8), (5.5, 8), (5.5, 12)], kind, pal)
        ic.poly([(5.5, 8), (10.5, 8), (10.5, 9), (5.5, 9)], "crystal", trim_pal, glow=glow_trim, seed_off=7)
    elif piece == "chestplate":
        ic.poly([(2, 4), (5.5, 2.5), (6.5, 4), (9.5, 4), (10.5, 2.5), (14, 4), (14, 8), (12, 8), (12, 14.5),
                 (4, 14.5), (4, 8), (2, 8)], kind, pal)
        ic.poly([(7, 6), (9, 6), (9, 12), (7, 12)], "crystal", trim_pal, glow=glow_trim, seed_off=7)
    elif piece == "leggings":
        ic.poly([(4, 2), (12, 2), (12, 15), (9, 15), (8.5, 6.5), (7.5, 6.5), (7, 15), (4, 15)], kind, pal)
        ic.poly([(4, 2), (12, 2), (12, 3.5), (4, 3.5)], "crystal", trim_pal, glow=glow_trim, seed_off=7)
    elif piece == "boots":
        ic.poly([(2.5, 6), (6.5, 6), (6.5, 13.5), (1.5, 13.5), (1.5, 11.5), (2.5, 11)], kind, pal)
        ic.poly([(9.5, 6), (13.5, 6), (13.5, 11), (14.5, 11.5), (14.5, 13.5), (9.5, 13.5)], kind, pal, seed_off=3)
        ic.poly([(2.5, 6), (6.5, 6), (6.5, 7.2), (2.5, 7.2)], "crystal", trim_pal, glow=glow_trim, seed_off=7)
        ic.poly([(9.5, 6), (13.5, 6), (13.5, 7.2), (9.5, 7.2)], "crystal", trim_pal, glow=glow_trim, seed_off=8)


def scythe(ic: Icon, blade_pal, shaft_pal, glow=0.8):
    """Long diagonal shaft with a crescent blade sweeping from the top."""
    ic.line((3, 15), (11.5, 2.5), 1.3, "bark", shaft_pal, seed_off=1)
    ic.poly([(11.5, 2.5), (9, 1.2), (5.5, 1.0), (2.2, 2.4), (1.2, 4.6), (4, 3.4), (7.5, 3.0), (10.5, 3.9)],
            "crystal", blade_pal, glow=glow, seed_off=2)
    ic.disc(11.5, 2.6, 1.0, "bronze", None, seed_off=3)
    ic.line((2.0, 3.6), (9.5, 2.0), 0.4, "crystal", [(0, "#ffffff"), (1, "#ffffff")], glow=glow, seed_off=4)
