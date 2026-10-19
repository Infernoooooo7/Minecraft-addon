"""Procedural texture painting toolkit for APOCALYPSE ENGINE.

Everything here is original procedural art: tileable value-noise / fBm, Voronoi cells, palette
ramps, baked top-light shading, panel lines, runic glyphs and emissive masks. Canvases are float32
RGBA numpy arrays in [0, 1]. A parallel "PBR" layer stack (metalness, emissive, roughness, height)
is carried alongside the colour so Vibrant Visuals texture sets can be produced from the same paint.

All functions are deterministic for a given seed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

# ----------------------------------------------------------------------------------------------
# colour helpers
# ----------------------------------------------------------------------------------------------

def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def ramp(values: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """Map a scalar field in [0,1] to RGB through colour stops [(pos, '#hex'), ...]."""
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.stack([hex_rgb(c) for _, c in stops])
    v = np.clip(values, 0.0, 1.0)
    out = np.empty(v.shape + (3,), dtype=np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(v, pos, cols[:, ch])
    return out


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------------------------
# noise
# ----------------------------------------------------------------------------------------------

def _value_noise(w: int, h: int, cells_x: int, cells_y: int, rng: np.random.Generator) -> np.ndarray:
    """Tileable value noise with quintic interpolation; cells wrap around the edges."""
    cells_x = max(1, cells_x)
    cells_y = max(1, cells_y)
    lattice = rng.random((cells_y, cells_x), dtype=np.float32)
    ys = (np.arange(h, dtype=np.float32) + 0.5) / h * cells_y
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * cells_x
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = ys - y0
    fx = xs - x0
    fy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    fx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    y0m = y0 % cells_y
    y1m = (y0 + 1) % cells_y
    x0m = x0 % cells_x
    x1m = (x0 + 1) % cells_x
    a = lattice[np.ix_(y0m, x0m)]
    b = lattice[np.ix_(y0m, x1m)]
    c = lattice[np.ix_(y1m, x0m)]
    d = lattice[np.ix_(y1m, x1m)]
    fx2 = fx[None, :]
    fy2 = fy[:, None]
    top = a + (b - a) * fx2
    bot = c + (d - c) * fx2
    return top + (bot - top) * fy2


def fbm(w: int, h: int, seed: int, base_cells: int = 4, octaves: int = 4, gain: float = 0.5,
        aspect: float | None = None) -> np.ndarray:
    """Tileable fractal noise normalised to [0,1]."""
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w), dtype=np.float32)
    amp = 1.0
    norm = 0.0
    if aspect is None:
        aspect = w / max(1, h)
    for o in range(octaves):
        cx = int(round(base_cells * (2 ** o) * max(1.0, aspect)))
        cy = int(round(base_cells * (2 ** o) / min(1.0, aspect) if aspect < 1 else base_cells * (2 ** o)))
        total += _value_noise(w, h, cx, cy, rng) * amp
        norm += amp
        amp *= gain
    total /= norm
    lo, hi = float(total.min()), float(total.max())
    return (total - lo) / (hi - lo + 1e-9)


def ridged(w: int, h: int, seed: int, base_cells: int = 4, octaves: int = 4) -> np.ndarray:
    n = fbm(w, h, seed, base_cells, octaves)
    r = 1.0 - np.abs(n * 2.0 - 1.0)
    return r ** 2


def voronoi(w: int, h: int, seed: int, points: int = 12, tile: bool = True):
    """Return (f1, f2, cell_id) distance fields (pixels normalised by cell size)."""
    rng = np.random.default_rng(seed)
    pts = rng.random((points, 2)) * np.array([w, h])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    best1 = np.full((h, w), 1e9, dtype=np.float32)
    best2 = np.full((h, w), 1e9, dtype=np.float32)
    ids = np.zeros((h, w), dtype=np.int32)
    offsets = [(ox, oy) for ox in (-w, 0, w) for oy in (-h, 0, h)] if tile else [(0, 0)]
    for i, (px, py) in enumerate(pts):
        for ox, oy in offsets:
            d = np.sqrt((xx - (px + ox)) ** 2 + (yy - (py + oy)) ** 2)
            closer = d < best1
            best2 = np.where(closer, best1, np.minimum(best2, d))
            ids = np.where(closer, i, ids)
            best1 = np.where(closer, d, best1)
    cell = math.sqrt(w * h / points)
    return best1 / cell, best2 / cell, ids


# ----------------------------------------------------------------------------------------------
# canvas with PBR side-channels
# ----------------------------------------------------------------------------------------------

@dataclass
class Canvas:
    w: int
    h: int
    rgba: np.ndarray = field(init=False)
    metal: np.ndarray = field(init=False)
    emissive: np.ndarray = field(init=False)
    rough: np.ndarray = field(init=False)
    height: np.ndarray = field(init=False)

    def __post_init__(self):
        self.rgba = np.zeros((self.h, self.w, 4), dtype=np.float32)
        self.metal = np.zeros((self.h, self.w), dtype=np.float32)
        self.emissive = np.zeros((self.h, self.w), dtype=np.float32)
        self.rough = np.full((self.h, self.w), 0.85, dtype=np.float32)
        self.height = np.full((self.h, self.w), 0.5, dtype=np.float32)

    # region painting ---------------------------------------------------------------------------
    def paint(self, x: int, y: int, rgb: np.ndarray, alpha: np.ndarray | float = 1.0,
              metal: float | np.ndarray | None = None, emissive: float | np.ndarray | None = None,
              rough: float | np.ndarray | None = None, height: np.ndarray | None = None,
              mask: np.ndarray | None = None):
        """Composite an RGB patch (h,w,3) at (x,y). Optional mask (h,w) in [0,1]."""
        ph, pw = rgb.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + pw), min(self.h, y + ph)
        if x1 <= x0 or y1 <= y0:
            return
        sx0, sy0 = x0 - x, y0 - y
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
        m = np.ones((ph, pw), dtype=np.float32) if mask is None else mask.astype(np.float32)
        if not np.isscalar(alpha):
            a = np.asarray(alpha, dtype=np.float32)
        else:
            a = np.full((ph, pw), float(alpha), dtype=np.float32)
        m = (m * a)[sy0:sy1, sx0:sx1]
        dst = self.rgba[y0:y1, x0:x1]
        src = rgb[sy0:sy1, sx0:sx1]
        dst[..., :3] = dst[..., :3] * (1 - m[..., None]) + src * m[..., None]
        dst[..., 3] = np.maximum(dst[..., 3], m)

        def _blend(chan, val):
            if val is None:
                return
            region = chan[y0:y1, x0:x1]
            v = val if np.isscalar(val) else np.asarray(val, dtype=np.float32)[sy0:sy1, sx0:sx1]
            region[...] = region * (1 - m) + v * m

        _blend(self.metal, metal)
        _blend(self.emissive, emissive)
        _blend(self.rough, rough)
        _blend(self.height, height)

    # export ---------------------------------------------------------------------------------------
    def image(self) -> Image.Image:
        arr = np.clip(self.rgba * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, "RGBA")

    def mer_image(self) -> Image.Image:
        mer = np.stack([self.metal, self.emissive, self.rough], axis=-1)
        arr = np.clip(mer * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, "RGB")

    def normal_image(self, strength: float = 2.0) -> Image.Image:
        hgt = self.height
        gx = (np.roll(hgt, -1, axis=1) - np.roll(hgt, 1, axis=1)) * strength
        gy = (np.roll(hgt, -1, axis=0) - np.roll(hgt, 1, axis=0)) * strength
        nz = np.ones_like(hgt)
        n = np.stack([-gx, gy, nz], axis=-1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        arr = np.clip((n * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, "RGB")

    def emissive_overlay(self, threshold: float = 0.25) -> Image.Image:
        """Classic-renderer glow layer: emissive pixels keep colour, alpha marks glow strength.

        Used with the documented `entity_emissive_alpha` material: alpha 0 => transparent,
        partial alpha => glowing pixel.
        """
        glow = np.clip((self.emissive - threshold) / (1 - threshold), 0, 1)
        rgb = np.clip(self.rgba[..., :3] * 1.15, 0, 1)
        alpha = np.where(glow > 0, 0.25 + 0.55 * glow, 0.0)
        arr = np.concatenate([rgb, alpha[..., None]], axis=-1)
        return Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")


# ----------------------------------------------------------------------------------------------
# material swatches: return (rgb, height, metal, emissive, rough) patches of size (h, w)
# ----------------------------------------------------------------------------------------------

@dataclass
class Swatch:
    rgb: np.ndarray
    height: np.ndarray
    metal: np.ndarray
    emissive: np.ndarray
    rough: np.ndarray
    alpha: np.ndarray | None = None


def _const(h, w, v):
    return np.full((h, w), v, dtype=np.float32)


def material(kind: str, w: int, h: int, seed: int, palette: list[tuple[float, str]] | None = None,
             detail: float = 1.0) -> Swatch:
    """Paint a tileable material patch.

    kinds: stone, bone, cloth, metal, bronze, crystal, flesh, bark, leaf, void, ember, rune_stone,
           chitin, star, moss, soil, glass
    """
    w = max(1, int(w))
    h = max(1, int(h))
    base_cells = max(2, int(round(max(w, h) / 8 * detail)))
    n = fbm(w, h, seed, base_cells=base_cells, octaves=4)
    n2 = fbm(w, h, seed + 101, base_cells=max(2, base_cells // 2), octaves=3)
    metal = _const(h, w, 0.0)
    emis = _const(h, w, 0.0)
    rough = _const(h, w, 0.85)

    if kind == "stone":
        pal = palette or [(0.0, "#2b2733"), (0.45, "#4a4552"), (0.75, "#6b6574"), (1.0, "#8a8494")]
        f1, f2, _ = voronoi(w, h, seed + 7, points=max(3, (w * h) // 90))
        cracks = smoothstep(0.0, 0.12, f2 - f1)
        val = n * 0.65 + n2 * 0.35
        rgb = ramp(val, pal) * (0.55 + 0.45 * cracks[..., None])
        height = val * 0.6 + cracks * 0.4
        rough = 0.9 - 0.1 * val
    elif kind == "rune_stone":
        pal = palette or [(0.0, "#1d1a24"), (0.5, "#3a3445"), (1.0, "#5d5470")]
        val = n * 0.7 + n2 * 0.3
        rgb = ramp(val, pal)
        height = val
        rough = _const(h, w, 0.8)
    elif kind == "bone":
        pal = palette or [(0.0, "#8d8070"), (0.5, "#c9bfa8"), (1.0, "#efe7d2")]
        grain = fbm(w, h, seed + 3, base_cells=max(2, base_cells), octaves=3, aspect=4.0)
        val = n * 0.5 + grain * 0.5
        rgb = ramp(val, pal)
        height = val
        rough = _const(h, w, 0.6)
    elif kind == "cloth":
        pal = palette or [(0.0, "#1a0f2e"), (0.6, "#3b2163"), (1.0, "#5e3a96")]
        yy, xx = np.mgrid[0:h, 0:w]
        weave = (np.sin(xx * 2.1) * np.sin(yy * 2.1)) * 0.5 + 0.5
        folds = fbm(w, h, seed + 9, base_cells=max(2, base_cells // 2), octaves=2, aspect=4.0)
        val = folds * 0.75 + weave * 0.1 + n * 0.15
        rgb = ramp(val, pal)
        height = folds
        rough = _const(h, w, 0.95)
    elif kind == "metal":
        pal = palette or [(0.0, "#2a2d36"), (0.5, "#5b6070"), (0.85, "#9aa1b3"), (1.0, "#d8deeb")]
        brushed = fbm(w, h, seed + 5, base_cells=max(2, base_cells * 2), octaves=2, aspect=6.0)
        val = n * 0.5 + brushed * 0.5
        rgb = ramp(val, pal)
        height = val * 0.5 + 0.25
        metal = _const(h, w, 1.0)
        rough = 0.35 + 0.25 * n
    elif kind == "bronze":
        pal = palette or [(0.0, "#3a2414"), (0.45, "#7a4f22"), (0.8, "#b9853d"), (1.0, "#e6c27a")]
        patina = smoothstep(0.62, 0.8, n2)
        val = n
        rgb = ramp(val, pal)
        rgb = rgb * (1 - patina[..., None]) + hex_rgb("#3f8f7a") * patina[..., None] * (0.6 + 0.4 * n[..., None])
        height = val * 0.6 + 0.2
        metal = 1.0 - patina
        rough = 0.4 + 0.4 * patina
    elif kind == "crystal":
        pal = palette or [(0.0, "#0b3d4a"), (0.5, "#20b3c8"), (0.85, "#7ff6ff"), (1.0, "#e8ffff")]
        f1, f2, ids = voronoi(w, h, seed + 11, points=max(3, (w * h) // 60))
        facet = (ids * 0.6180339) % 1.0
        edge = 1.0 - smoothstep(0.0, 0.09, f2 - f1)
        val = np.clip(facet * 0.55 + n * 0.3 + edge * 0.4, 0, 1)
        rgb = ramp(val, pal)
        height = 1.0 - f1 * 0.5
        emis = np.clip(0.35 + 0.65 * val, 0, 1)
        rough = _const(h, w, 0.12)
    elif kind == "flesh":
        pal = palette or [(0.0, "#2a0b12"), (0.5, "#6b1a2b"), (1.0, "#b8394f")]
        veins = 1.0 - smoothstep(0.0, 0.07, np.abs(fbm(w, h, seed + 13, base_cells, 3) - 0.5))
        val = n * 0.8 + veins * 0.2
        rgb = ramp(val, pal)
        height = val
        rough = _const(h, w, 0.55)
    elif kind == "bark":
        pal = palette or [(0.0, "#1e140c"), (0.45, "#3d2a18"), (0.8, "#5f4426"), (1.0, "#7d6038")]
        grooves = fbm(w, h, seed + 17, base_cells=max(3, base_cells * 2), octaves=3, aspect=8.0)
        val = grooves * 0.7 + n * 0.3
        rgb = ramp(val, pal)
        height = grooves
        rough = _const(h, w, 0.95)
    elif kind == "leaf":
        pal = palette or [(0.0, "#10220e"), (0.5, "#2e5a1e"), (0.85, "#5f9a2e"), (1.0, "#9de05a")]
        f1, f2, ids = voronoi(w, h, seed + 19, points=max(4, (w * h) // 30))
        val = np.clip(((ids * 0.37) % 1.0) * 0.5 + n * 0.5, 0, 1)
        rgb = ramp(val, pal)
        height = 1 - f1
        rough = _const(h, w, 0.8)
    elif kind == "moss":
        pal = palette or [(0.0, "#141f12"), (0.5, "#3b5e2b"), (1.0, "#8cff6a")]
        val = n * 0.6 + n2 * 0.4
        rgb = ramp(val ** 1.3, pal)
        height = val
        emis = smoothstep(0.82, 1.0, val) * 0.6
        rough = _const(h, w, 0.9)
    elif kind == "soil":
        pal = palette or [(0.0, "#1a120d"), (0.5, "#3b2a1f"), (1.0, "#5e4532")]
        val = n * 0.7 + n2 * 0.3
        rgb = ramp(val, pal)
        height = val
        rough = _const(h, w, 0.95)
    elif kind == "void":
        pal = palette or [(0.0, "#05030b"), (0.5, "#1a0f2e"), (0.8, "#4b2a85"), (1.0, "#b98cff")]
        swirl = fbm(w, h, seed + 23, base_cells=max(2, base_cells // 2), octaves=5)
        stars = (np.random.default_rng(seed + 29).random((h, w)) > 0.985).astype(np.float32)
        val = swirl ** 1.6
        rgb = ramp(val, pal) + stars[..., None] * 0.8
        height = swirl
        emis = np.clip(val * 0.5 + stars, 0, 1)
        rough = _const(h, w, 0.5)
    elif kind == "ember":
        pal = palette or [(0.0, "#1a0503"), (0.4, "#6b1206"), (0.7, "#e0401a"), (0.9, "#ffb347"), (1.0, "#fff2c0")]
        val = n ** 1.4
        rgb = ramp(val, pal)
        height = val
        emis = smoothstep(0.45, 1.0, val)
        rough = _const(h, w, 0.7)
    elif kind == "chitin":
        pal = palette or [(0.0, "#07060c"), (0.5, "#1e1733"), (0.8, "#3e2e6b"), (1.0, "#7c5cd6")]
        f1, f2, ids = voronoi(w, h, seed + 31, points=max(3, (w * h) // 70))
        plate = smoothstep(0.0, 0.1, f2 - f1)
        val = np.clip(n * 0.5 + plate * 0.5, 0, 1)
        rgb = ramp(val, pal)
        height = plate
        rough = 0.3 + 0.3 * n
        metal = _const(h, w, 0.15)
    elif kind == "star":
        pal = palette or [(0.0, "#140b02"), (0.4, "#5a3a0a"), (0.75, "#d99a28"), (1.0, "#fff4c2")]
        val = n ** 1.2
        rgb = ramp(val, pal)
        height = val
        emis = smoothstep(0.55, 1.0, val)
        metal = _const(h, w, 0.6)
        rough = _const(h, w, 0.35)
    elif kind == "glass":
        pal = palette or [(0.0, "#1a2a3a"), (1.0, "#9fd8ff")]
        val = n * 0.3 + 0.5
        rgb = ramp(val, pal)
        height = _const(h, w, 0.5)
        rough = _const(h, w, 0.05)
    else:
        raise ValueError(f"unknown material {kind}")

    return Swatch(rgb.astype(np.float32), np.asarray(height, dtype=np.float32), np.asarray(metal, dtype=np.float32),
                  np.asarray(emis, dtype=np.float32), np.asarray(rough, dtype=np.float32))


# ----------------------------------------------------------------------------------------------
# shading and decoration operators on swatches
# ----------------------------------------------------------------------------------------------

def shade_face(sw: Swatch, top_light: float = 0.25, edge_dark: float = 0.35, bevel_px: int = 1,
               face: str = "side") -> Swatch:
    """Bake Minecraft-style lighting: brighter top edge, darker bottom and borders."""
    h, w = sw.rgb.shape[:2]
    yy = (np.arange(h, dtype=np.float32) + 0.5) / h
    xx = (np.arange(w, dtype=np.float32) + 0.5) / w
    grad = 1.0 + top_light * (0.5 - yy)[:, None]
    if face == "up":
        grad = np.full((h, w), 1.0 + top_light * 0.6, dtype=np.float32)
    elif face == "down":
        grad = np.full((h, w), 1.0 - top_light * 1.2, dtype=np.float32)
    ex = np.minimum(xx, 1 - xx) * w
    ey = np.minimum(yy, 1 - yy) * h
    edge = np.minimum(ex[None, :], ey[:, None])
    border = 1.0 - edge_dark * (1.0 - smoothstep(0.0, max(1.0, bevel_px * 1.5), edge))
    rgb = sw.rgb * (grad * border)[..., None]
    # simple height-based embossing
    hgt = sw.height
    gx = np.roll(hgt, 1, axis=1) - hgt
    gy = np.roll(hgt, 1, axis=0) - hgt
    emb = 1.0 + (gx + gy) * 0.6
    rgb = rgb * emb[..., None]
    out = Swatch(np.clip(rgb, 0, 1), sw.height, sw.metal, sw.emissive, sw.rough, sw.alpha)
    return out


def add_glow(sw: Swatch, mask: np.ndarray, color: str, strength: float = 1.0) -> Swatch:
    c = hex_rgb(color)
    m = np.clip(mask, 0, 1)[..., None]
    rgb = sw.rgb * (1 - m) + (c * (0.75 + 0.25 * m)) * m
    emis = np.maximum(sw.emissive, np.clip(mask, 0, 1) * strength)
    rough = sw.rough * (1 - np.clip(mask, 0, 1)) + 0.2 * np.clip(mask, 0, 1)
    return Swatch(np.clip(rgb, 0, 1), sw.height, sw.metal, emis, rough, sw.alpha)


def vein_mask(w: int, h: int, seed: int, width: float = 0.06, cells: int = 3) -> np.ndarray:
    n = fbm(w, h, seed, base_cells=cells, octaves=4)
    return 1.0 - smoothstep(0.0, width, np.abs(n - 0.5))


def crack_mask(w: int, h: int, seed: int, points: int = 6, width: float = 0.05) -> np.ndarray:
    f1, f2, _ = voronoi(w, h, seed, points=max(2, points))
    return 1.0 - smoothstep(0.0, width, f2 - f1)


def spots_mask(w: int, h: int, seed: int, count: int, radius: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.zeros((h, w), dtype=np.float32)
    for _ in range(count):
        cx, cy = rng.random() * w, rng.random() * h
        r = radius * (0.6 + 0.8 * rng.random())
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        m = np.maximum(m, 1.0 - smoothstep(r * 0.5, r, d))
    return m


def stripes_mask(w: int, h: int, period: float, thickness: float, horizontal: bool = True,
                 offset: float = 0.0) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    coord = yy if horizontal else xx
    phase = ((coord + offset) % period) / period
    return (phase < thickness / period).astype(np.float32)


# ----------------------------------------------------------------------------------------------
# runic glyphs (procedural line-art symbols)
# ----------------------------------------------------------------------------------------------

def glyph(size: int, seed: int, stroke: float = 1.0) -> np.ndarray:
    """A procedural rune: a few strokes on a 3x3 node lattice, anti-aliased, returns mask."""
    rng = np.random.default_rng(seed)
    nodes = [(x, y) for y in range(3) for x in range(3)]
    strokes = []
    current = nodes[rng.integers(0, 9)]
    for _ in range(int(rng.integers(3, 6))):
        nxt = nodes[rng.integers(0, 9)]
        if nxt != current:
            strokes.append((current, nxt))
            current = nxt
    # always a spine for legibility
    strokes.append(((1, 0), (1, 2)))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    m = np.zeros((size, size), dtype=np.float32)
    pad = size * 0.18
    scale = (size - 2 * pad) / 2.0
    for (ax, ay), (bx, by) in strokes:
        p0 = np.array([pad + ax * scale, pad + ay * scale])
        p1 = np.array([pad + bx * scale, pad + by * scale])
        d = p1 - p0
        L2 = float((d ** 2).sum()) + 1e-9
        t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / L2, 0, 1)
        px = p0[0] + t * d[0]
        py = p0[1] + t * d[1]
        dist = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
        m = np.maximum(m, 1.0 - smoothstep(stroke * 0.35 * size / 8, stroke * 0.8 * size / 8, dist))
    return m


def rune_band(w: int, h: int, seed: int, glyph_size: int | None = None) -> np.ndarray:
    gs = glyph_size or max(4, min(h, w // 2))
    m = np.zeros((h, w), dtype=np.float32)
    x = 0
    k = 0
    while x + gs <= w:
        g = glyph(gs, seed + k)
        y = (h - gs) // 2
        m[y:y + gs, x:x + gs] = np.maximum(m[y:y + gs, x:x + gs], g)
        x += gs + max(1, gs // 4)
        k += 1
    return m


# ----------------------------------------------------------------------------------------------
# shapes
# ----------------------------------------------------------------------------------------------

def disc_mask(w: int, h: int, cx: float, cy: float, r: float, soft: float = 1.0) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2)
    return 1.0 - smoothstep(r - soft, r + soft * 0.25, d)


def ring_mask(w: int, h: int, cx: float, cy: float, r: float, thickness: float, soft: float = 1.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.abs(np.sqrt((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2) - r)
    return 1.0 - smoothstep(thickness * 0.5 - soft * 0.5, thickness * 0.5 + soft * 0.5, d)


def poly_mask(w: int, h: int, pts: list[tuple[float, float]], ss: int = 4) -> np.ndarray:
    """Anti-aliased polygon mask via supersampling (pts in pixel coords)."""
    from PIL import ImageDraw
    img = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(img).polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    img = img.resize((w, h), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def line_mask(w: int, h: int, p0, p1, width: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    d = np.array(p1, dtype=np.float32) - np.array(p0, dtype=np.float32)
    L2 = float((d ** 2).sum()) + 1e-9
    t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / L2, 0, 1)
    px = p0[0] + t * d[0]
    py = p0[1] + t * d[1]
    dist = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    return 1.0 - smoothstep(width * 0.5 - 0.5, width * 0.5 + 0.5, dist)


# ----------------------------------------------------------------------------------------------
# post / export helpers
# ----------------------------------------------------------------------------------------------

def quantize(img: Image.Image, colors: int = 48) -> Image.Image:
    """Palette-reduce while keeping alpha (crisper pixel-art look at low resolutions)."""
    alpha = img.getchannel("A")
    q = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = q.convert("RGB")
    out.putalpha(alpha)
    return out


def downscale(img: Image.Image, factor: int) -> Image.Image:
    if factor == 1:
        return img.copy()
    w, h = img.size
    return img.resize((max(1, w // factor), max(1, h // factor)), Image.BOX)


def save_png(img: Image.Image, path: str):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG", optimize=True)


def outline(img: Image.Image, color=(12, 8, 18, 255)) -> Image.Image:
    """Add a 1px dark outline around opaque pixels (icon readability)."""
    a = np.asarray(img.getchannel("A"), dtype=np.uint8) > 40
    grown = a.copy()
    grown[1:, :] |= a[:-1, :]
    grown[:-1, :] |= a[1:, :]
    grown[:, 1:] |= a[:, :-1]
    grown[:, :-1] |= a[:, 1:]
    edge = grown & ~a
    arr = np.asarray(img, dtype=np.uint8).copy()
    arr[edge] = color
    return Image.fromarray(arr, "RGBA")
