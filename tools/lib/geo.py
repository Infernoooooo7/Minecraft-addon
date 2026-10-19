"""Bedrock entity geometry builder with automatic box-UV packing and per-face texture painting.

Model units: 16 units = 1 block. Bedrock entities face north (-Z). Box UV layout for a cube of
size (w, h, d) placed at (u, v):

    up    (u+d,       v,     w, d)      down  (u+d+w,     v,     w, d)
    east  (u,         v+d,   d, h)      north (u+d,       v+d,   w, h)   <- front
    west  (u+d+w,     v+d,   d, h)      south (u+2d+w,    v+d,   w, h)   <- back

Textures are painted at an integer texel density (texels per model unit) so the same geometry can
ship 1x / 2x / 4x images (Bedrock normalises UVs by texture_width/height).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import tex

FACES = ("up", "down", "east", "north", "west", "south")


@dataclass
class Cube:
    origin: tuple[float, float, float]
    size: tuple[int, int, int]
    mat: dict
    pivot: tuple[float, float, float] | None = None
    rotation: tuple[float, float, float] | None = None
    inflate: float = 0.0
    mirror: bool = False
    deco: dict = field(default_factory=dict)  # face -> callable(canvas_patch_ctx)
    uv: tuple[int, int] | None = None

    @property
    def uv_size(self) -> tuple[int, int]:
        w, h, d = self.size
        return (2 * (w + d), d + h)

    def face_rects(self) -> dict[str, tuple[int, int, int, int]]:
        u, v = self.uv
        w, h, d = self.size
        return {
            "up": (u + d, v, w, d),
            "down": (u + d + w, v, w, d),
            "east": (u, v + d, d, h),
            "north": (u + d, v + d, w, h),
            "west": (u + d + w, v + d, d, h),
            "south": (u + 2 * d + w, v + d, w, h),
        }


@dataclass
class Bone:
    name: str
    pivot: tuple[float, float, float]
    parent: str | None = None
    rotation: tuple[float, float, float] | None = None
    cubes: list[Cube] = field(default_factory=list)
    locators: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    def cube(self, origin, size, mat, **kw) -> "Bone":
        self.cubes.append(Cube(tuple(origin), tuple(int(s) for s in size), mat, **kw))
        return self


class Model:
    def __init__(self, identifier: str, tex_w: int = 64, tex_h: int = 64,
                 bounds_w: float = 2.0, bounds_h: float = 3.0, bounds_off=(0, 1.5, 0)):
        self.identifier = identifier
        self.tex_w = tex_w
        self.tex_h = tex_h
        self.bounds_w = bounds_w
        self.bounds_h = bounds_h
        self.bounds_off = bounds_off
        self.bones: list[Bone] = []

    def bone(self, name, pivot, parent=None, rotation=None) -> Bone:
        b = Bone(name, tuple(pivot), parent, tuple(rotation) if rotation else None)
        self.bones.append(b)
        return b

    def get(self, name: str) -> Bone:
        for b in self.bones:
            if b.name == name:
                return b
        raise KeyError(name)

    # -------------------------------------------------------------------------------- uv packing
    def pack_uv(self, gap: int = 1):
        cubes = [c for b in self.bones for c in b.cubes]
        order = sorted(cubes, key=lambda c: (-c.uv_size[1], -c.uv_size[0]))
        width = self.tex_w
        while True:
            x = y = row_h = 0
            ok = True
            for c in order:
                cw, ch = c.uv_size
                if cw > width:
                    ok = False
                    break
                if x + cw > width:
                    x = 0
                    y += row_h + gap
                    row_h = 0
                c.uv = (x, y)
                x += cw + gap
                row_h = max(row_h, ch)
            needed_h = y + row_h
            if ok and needed_h <= self.tex_h:
                return
            if ok and needed_h <= width * 2 and self.tex_h < needed_h:
                # grow height to the next power of two first, then width
                nh = self.tex_h
                while nh < needed_h:
                    nh *= 2
                if nh <= width:
                    self.tex_h = nh
                    return
            width *= 2
            self.tex_w = width
            self.tex_h = max(self.tex_h, width)

    # -------------------------------------------------------------------------------- json
    def to_json(self) -> dict:
        bones_json = []
        for b in self.bones:
            bj: dict = {"name": b.name}
            if b.parent:
                bj["parent"] = b.parent
            bj["pivot"] = list(b.pivot)
            if b.rotation:
                bj["rotation"] = list(b.rotation)
            if b.cubes:
                cl = []
                for c in b.cubes:
                    cj = {"origin": [round(v, 4) for v in c.origin], "size": list(c.size), "uv": list(c.uv)}
                    if c.inflate:
                        cj["inflate"] = c.inflate
                    if c.pivot is not None:
                        cj["pivot"] = [round(v, 4) for v in c.pivot]
                    if c.rotation is not None:
                        cj["rotation"] = list(c.rotation)
                    if c.mirror:
                        cj["mirror"] = True
                    cl.append(cj)
                bj["cubes"] = cl
            if b.locators:
                bj["locators"] = {k: list(v) for k, v in b.locators.items()}
            bones_json.append(bj)
        return {
            "format_version": "1.12.0",
            "minecraft:geometry": [
                {
                    "description": {
                        "identifier": self.identifier,
                        "texture_width": self.tex_w,
                        "texture_height": self.tex_h,
                        "visible_bounds_width": self.bounds_w,
                        "visible_bounds_height": self.bounds_h,
                        "visible_bounds_offset": list(self.bounds_off),
                    },
                    "bones": bones_json,
                }
            ],
        }

    # -------------------------------------------------------------------------------- painting
    def paint(self, density: int, seed: int = 1) -> tex.Canvas:
        """Paint every cube face at `density` texels per unit; returns canvas with PBR layers."""
        cv = tex.Canvas(self.tex_w * density, self.tex_h * density)
        k = 0
        for b in self.bones:
            for c in b.cubes:
                k += 1
                for face, (fx, fy, fw, fh) in c.face_rects().items():
                    if fw <= 0 or fh <= 0:
                        continue
                    pw, ph = fw * density, fh * density
                    m = dict(c.mat)
                    face_override = m.pop("faces", {}).get(face)
                    if face_override:
                        m.update(face_override)
                    sw = tex.material(m.get("kind", "stone"), pw, ph,
                                      seed=seed * 1000 + k * 17 + FACES.index(face),
                                      palette=m.get("palette"), detail=m.get("detail", 1.0))
                    for op in m.get("ops", []):
                        sw = apply_op(op, sw, pw, ph, seed * 7 + k, density, face)
                    sw = tex.shade_face(sw, top_light=m.get("top_light", 0.28),
                                        edge_dark=m.get("edge_dark", 0.32), bevel_px=density,
                                        face=face if face in ("up", "down") else "side")
                    deco = c.deco.get(face) or c.deco.get("*")
                    if deco:
                        sw = deco(sw, pw, ph, density)
                    alpha = sw.alpha if sw.alpha is not None else 1.0
                    cv.paint(fx * density, fy * density, sw.rgb, alpha, metal=sw.metal,
                             emissive=sw.emissive, rough=sw.rough, height=sw.height)
        return cv


# ------------------------------------------------------------------------------------------------
# reusable paint operations (declared in cube material dicts as "ops")
# ------------------------------------------------------------------------------------------------

def apply_op(op: dict, sw: tex.Swatch, w: int, h: int, seed: int, density: int, face: str) -> tex.Swatch:
    t = op["op"]
    if op.get("faces") and face not in op["faces"]:
        return sw
    if t == "veins":
        m = tex.vein_mask(w, h, seed + op.get("seed", 0), width=op.get("width", 0.05), cells=op.get("cells", 3))
        return tex.add_glow(sw, m * op.get("amount", 1.0), op["color"], op.get("emissive", 0.9))
    if t == "cracks":
        m = tex.crack_mask(w, h, seed + op.get("seed", 0), points=op.get("points", 5), width=op.get("width", 0.05))
        if op.get("glow"):
            return tex.add_glow(sw, m, op["color"], op.get("emissive", 0.8))
        rgb = sw.rgb * (1 - 0.6 * m[..., None])
        return tex.Swatch(rgb, sw.height - 0.3 * m, sw.metal, sw.emissive, sw.rough, sw.alpha)
    if t == "spots":
        m = tex.spots_mask(w, h, seed + op.get("seed", 0), op.get("count", 4), op.get("radius", 1.5) * density)
        return tex.add_glow(sw, m, op["color"], op.get("emissive", 1.0))
    if t == "stripes":
        m = tex.stripes_mask(w, h, op.get("period", 4) * density, op.get("thickness", 1) * density,
                             horizontal=op.get("horizontal", True))
        if op.get("glow"):
            return tex.add_glow(sw, m * op.get("amount", 1.0), op["color"], op.get("emissive", 0.7))
        c = tex.hex_rgb(op["color"])
        a = m[..., None] * op.get("amount", 0.6)
        return tex.Swatch(sw.rgb * (1 - a) + c * a, sw.height + 0.2 * m, sw.metal, sw.emissive, sw.rough, sw.alpha)
    if t == "runes":
        gs = max(4, int(op.get("size", 3) * density))
        m = tex.rune_band(w, h, seed + op.get("seed", 0), glyph_size=min(gs, h, w))
        return tex.add_glow(sw, m, op["color"], op.get("emissive", 1.0))
    if t == "tint":
        c = tex.hex_rgb(op["color"])
        a = op.get("amount", 0.3)
        return tex.Swatch(sw.rgb * (1 - a) + c * a, sw.height, sw.metal, sw.emissive, sw.rough, sw.alpha)
    if t == "gradient":
        yy = (np.arange(h, dtype=np.float32) + 0.5) / h
        g = yy if op.get("down", True) else 1 - yy
        c = tex.hex_rgb(op["color"])
        a = (g[:, None] * op.get("amount", 0.5))[..., None] * np.ones((1, w, 1), dtype=np.float32)
        return tex.Swatch(sw.rgb * (1 - a) + c * a, sw.height, sw.metal, sw.emissive, sw.rough, sw.alpha)
    if t == "rim":
        # bright trim along face border (armor plates, ornate edges)
        ex = np.minimum(np.arange(w) + 0.5, w - np.arange(w) - 0.5)
        ey = np.minimum(np.arange(h) + 0.5, h - np.arange(h) - 0.5)
        e = np.minimum(ex[None, :], ey[:, None])
        m = (e < op.get("width", 1) * density).astype(np.float32)
        c = tex.hex_rgb(op["color"])
        rgb = sw.rgb * (1 - m[..., None]) + c * m[..., None]
        metal = np.maximum(sw.metal, m * op.get("metal", 1.0))
        if op.get("glow"):
            return tex.add_glow(tex.Swatch(rgb, sw.height + 0.3 * m, metal, sw.emissive, sw.rough, sw.alpha), m, op["color"], op.get("emissive", 0.8))
        return tex.Swatch(rgb, sw.height + 0.3 * m, metal, sw.emissive, sw.rough * (1 - m) + 0.3 * m, sw.alpha)
    if t == "tatter":
        # jagged, torn lower edge: alpha 0 below a noisy line
        rng = np.random.default_rng(seed + op.get("seed", 0))
        depth = op.get("depth", 0.3)
        cols = np.linspace(0, 1, w)
        noise = tex.fbm(w, 4, seed + 77, base_cells=max(2, w // (3 * density)), octaves=3)[1]
        cut = (1.0 - depth) + depth * noise * 0.9 + rng.random(w) * depth * 0.1
        yy = (np.arange(h, dtype=np.float32) + 0.5) / h
        a = (yy[:, None] < cut[None, :]).astype(np.float32)
        a = a if sw.alpha is None else a * sw.alpha
        return tex.Swatch(sw.rgb, sw.height, sw.metal, sw.emissive, sw.rough, a)
    if t == "oval":
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx = (xx + 0.5) / w * 2 - 1
        ny = (yy + 0.5) / h * 2 - 1
        r = np.sqrt(nx ** 2 + ny ** 2)
        wob = tex.fbm(w, h, seed + 5, base_cells=3, octaves=2) * op.get("wobble", 0.25)
        a = (r < (op.get("radius", 0.95) - wob)).astype(np.float32)
        rim = ((r < op.get("radius", 0.95) - wob) & (r > op.get("radius", 0.95) - wob - op.get("rim", 0.12))).astype(np.float32)
        sw2 = tex.add_glow(sw, rim, op.get("color", "#d8b8ff"), 1.0) if op.get("color") else sw
        return tex.Swatch(sw2.rgb, sw2.height, sw2.metal, sw2.emissive, sw2.rough, a)
    if t == "fade":
        yy = (np.arange(h, dtype=np.float32) + 0.5) / h
        a = np.clip((1 - yy) / max(1e-3, op.get("over", 0.5)), 0, 1)[:, None] * np.ones((1, w), np.float32)
        a = (a > 0.35).astype(np.float32) if op.get("hard", True) else a
        return tex.Swatch(sw.rgb, sw.height, sw.metal, sw.emissive, sw.rough, a)
    raise ValueError(f"unknown op {t}")


# ------------------------------------------------------------------------------------------------
# common face decorations
# ------------------------------------------------------------------------------------------------

def eyes(color: str, spacing: float = 0.28, y: float = 0.42, size: float = 0.13, slit: bool = False,
         count: int = 2, socket: str = "#050308") -> Callable:
    """Glowing eyes centred on a face; sizes are fractions of face width."""

    def deco(sw: tex.Swatch, w: int, h: int, density: int) -> tex.Swatch:
        rgb = sw.rgb.copy()
        emis = sw.emissive.copy()
        r = max(1.0, size * w)
        xs = [0.5] if count == 1 else [0.5 - spacing / 2, 0.5 + spacing / 2] if count == 2 else \
            [0.5 - spacing, 0.5, 0.5 + spacing]
        sock = tex.hex_rgb(socket)
        col = tex.hex_rgb(color)
        for ex in xs:
            cx, cy = ex * w, y * h
            if slit:
                m_s = tex.poly_mask(w, h, [(cx - r * 1.3, cy), (cx, cy - r * 0.7), (cx + r * 1.3, cy), (cx, cy + r * 0.7)])
                m_e = tex.poly_mask(w, h, [(cx - r, cy), (cx, cy - r * 0.35), (cx + r, cy), (cx, cy + r * 0.35)])
            else:
                m_s = tex.disc_mask(w, h, cx, cy, r * 1.35, soft=max(0.6, density * 0.4))
                m_e = tex.disc_mask(w, h, cx, cy, r * 0.8, soft=max(0.6, density * 0.4))
            rgb = rgb * (1 - m_s[..., None]) + sock * m_s[..., None]
            rgb = rgb * (1 - m_e[..., None]) + col * m_e[..., None]
            emis = np.maximum(emis, m_e)
        return tex.Swatch(np.clip(rgb, 0, 1), sw.height, sw.metal, emis, sw.rough, sw.alpha)

    return deco


def mouth(color: str = "#050308", y: float = 0.75, width: float = 0.5, teeth: str | None = "#e8dcc4",
          glow: str | None = None) -> Callable:
    def deco(sw: tex.Swatch, w: int, h: int, density: int) -> tex.Swatch:
        rgb = sw.rgb.copy()
        emis = sw.emissive.copy()
        x0, x1 = (0.5 - width / 2) * w, (0.5 + width / 2) * w
        cy = y * h
        hh = max(1.0, 0.09 * h)
        m = tex.poly_mask(w, h, [(x0, cy - hh * 0.4), (x1, cy - hh * 0.4), (x1 - hh, cy + hh), (x0 + hh, cy + hh)])
        c = tex.hex_rgb(glow or color)
        rgb = rgb * (1 - m[..., None]) + c * m[..., None]
        if glow:
            emis = np.maximum(emis, m * 0.8)
        if teeth:
            tc = tex.hex_rgb(teeth)
            n = max(3, int(width * w / max(2, density * 1.5)))
            for i in range(n):
                tx = x0 + (i + 0.5) * (x1 - x0) / n
                tm = tex.poly_mask(w, h, [(tx - hh * 0.4, cy - hh * 0.4), (tx + hh * 0.4, cy - hh * 0.4), (tx, cy + hh * 0.5)])
                rgb = rgb * (1 - tm[..., None]) + tc * tm[..., None]
        return tex.Swatch(np.clip(rgb, 0, 1), sw.height, sw.metal, emis, sw.rough, sw.alpha)

    return deco


def combine(*decos: Callable) -> Callable:
    def deco(sw, w, h, density):
        for d in decos:
            sw = d(sw, w, h, density)
        return sw
    return deco


def emblem(color: str, kind: str = "eye", scale: float = 0.6) -> Callable:
    """Large glowing sigil on a face (chest cores, shields)."""

    def deco(sw: tex.Swatch, w: int, h: int, density: int) -> tex.Swatch:
        cx, cy = w / 2, h / 2
        r = min(w, h) * scale / 2
        if kind == "eye":
            m = np.maximum(tex.ring_mask(w, h, cx, cy, r, max(1.0, r * 0.22)), tex.disc_mask(w, h, cx, cy, r * 0.38))
        elif kind == "star":
            pts = []
            for i in range(10):
                ang = -np.pi / 2 + i * np.pi / 5
                rr = r if i % 2 == 0 else r * 0.42
                pts.append((cx + np.cos(ang) * rr, cy + np.sin(ang) * rr))
            m = tex.poly_mask(w, h, pts)
        elif kind == "core":
            m = np.maximum(tex.disc_mask(w, h, cx, cy, r * 0.7, soft=r * 0.4), tex.ring_mask(w, h, cx, cy, r, max(1.0, r * 0.15)))
        elif kind == "diamond":
            m = tex.poly_mask(w, h, [(cx, cy - r), (cx + r * 0.7, cy), (cx, cy + r), (cx - r * 0.7, cy)])
        else:
            m = tex.disc_mask(w, h, cx, cy, r)
        return tex.add_glow(sw, m, color, 1.0)

    return deco
