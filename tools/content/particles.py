"""Particle effects (Snowstorm format 1.10.0) + one shared original sprite atlas.

Each effect is emitted three times: base (balanced density) in the resource pack root, and density
overrides in subpacks/potato (sparse) and subpacks/enhanced (dense).
"""
from __future__ import annotations

import copy

import numpy as np

from tools.content.common import NS, PARTICLE_TEX
from tools.content.registry import REG, TexAsset
from tools.lib import tex

CELL = 16          # atlas cell size in UV units
ATLAS = 128        # atlas size in UV units (8x8 cells)
SPRITES = ["glow", "wisp", "spark", "ring", "shockwave", "shard", "rune", "smoke",
           "ember", "spore", "star", "beam", "swirl", "crack", "plus", "flake"]


def _sprite(name: str, s: int, seed: int) -> np.ndarray:
    """Return (s,s,4) float RGBA white-ish sprite (tinted at runtime)."""
    c = s / 2
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) + 0.5
    d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / c
    a = np.zeros((s, s), dtype=np.float32)
    lum = np.ones((s, s), dtype=np.float32)
    if name == "glow":
        a = np.clip(1 - d, 0, 1) ** 2
    elif name == "wisp":
        dy = (yy - c * 1.2) / (c * 1.0)
        dx = (xx - c) / (c * 0.45 * np.clip(1 - (yy / s) * 0.6, 0.2, 1))
        a = np.clip(1 - np.sqrt(dx ** 2 + dy ** 2), 0, 1) ** 1.5
    elif name == "spark":
        a = np.maximum(np.clip(1 - np.abs(xx - c) / (c * 0.12), 0, 1) * np.clip(1 - np.abs(yy - c) / c, 0, 1),
                       np.clip(1 - np.abs(yy - c) / (c * 0.12), 0, 1) * np.clip(1 - np.abs(xx - c) / c, 0, 1))
        a = np.maximum(a, np.clip(1 - d * 2.5, 0, 1))
    elif name == "ring":
        a = np.clip(1 - np.abs(d - 0.85) / 0.07, 0, 1)
        lum = 1 - 0.3 * np.clip((0.85 - d) * 3, 0, 1)
    elif name == "shockwave":
        a = np.clip(1 - np.abs(d - 0.78) / 0.2, 0, 1) ** 1.5
    elif name == "shard":
        a = tex.poly_mask(s, s, [(c, s * 0.05), (s * 0.72, c), (c, s * 0.95), (s * 0.3, c * 0.9)])
        lum = 0.7 + 0.3 * (xx / s)
    elif name == "rune":
        a = tex.glyph(s, seed + 7, stroke=1.2)
    elif name == "smoke":
        n = tex.fbm(s, s, seed, base_cells=3, octaves=3)
        a = np.clip(1 - d, 0, 1) * (0.5 + 0.5 * n)
        lum = 0.6 + 0.4 * n
    elif name == "ember":
        a = np.clip(1 - d * 1.6, 0, 1) ** 1.2
    elif name == "spore":
        a = np.clip(1 - d * 1.3, 0, 1) * (0.6 + 0.4 * np.clip(1 - np.abs(d - 0.5) * 4, 0, 1))
    elif name == "star":
        pts = []
        for i in range(10):
            ang = -np.pi / 2 + i * np.pi / 5
            rr = c * 0.95 if i % 2 == 0 else c * 0.4
            pts.append((c + np.cos(ang) * rr, c + np.sin(ang) * rr))
        a = tex.poly_mask(s, s, pts)
    elif name == "beam":
        a = np.clip(1 - np.abs(xx - c) / (c * 0.45), 0, 1) ** 1.5
    elif name == "swirl":
        ang = np.arctan2(yy - c, xx - c)
        spiral = np.sin(ang * 2 + d * 9)
        a = np.clip(spiral, 0, 1) * np.clip(1 - d, 0, 1)
    elif name == "crack":
        a = np.maximum(tex.line_mask(s, s, (s * 0.1, s * 0.2), (s * 0.55, s * 0.6), max(1, s / 12)),
                       tex.line_mask(s, s, (s * 0.55, s * 0.6), (s * 0.9, s * 0.35), max(1, s / 14)))
        a = np.maximum(a, tex.line_mask(s, s, (s * 0.55, s * 0.6), (s * 0.6, s * 0.95), max(1, s / 14)))
    elif name == "plus":
        a = np.maximum((np.abs(xx - c) < s * 0.14) & (np.abs(yy - c) < s * 0.42),
                       (np.abs(yy - c) < s * 0.14) & (np.abs(xx - c) < s * 0.42)).astype(np.float32)
    elif name == "flake":
        a = tex.poly_mask(s, s, [(s * 0.2, s * 0.4), (s * 0.7, s * 0.2), (s * 0.85, s * 0.6), (s * 0.35, s * 0.8)])
        lum = np.full((s, s), 0.35, dtype=np.float32)
    rgba = np.stack([lum, lum, lum, np.clip(a, 0, 1)], axis=-1)
    return rgba.astype(np.float32)


def paint_atlas(density: int) -> tex.Canvas:
    s = CELL * density
    cv = tex.Canvas(ATLAS * density, ATLAS * density)
    for i, name in enumerate(SPRITES):
        x, y = (i % 8) * s, (i // 8) * s
        spr = _sprite(name, s, 31 + i)
        cv.rgba[y:y + s, x:x + s] = spr
        cv.emissive[y:y + s, x:x + s] = spr[..., 3]
    return cv


def uv(sprite: str) -> dict:
    i = SPRITES.index(sprite)
    return {"texture_width": ATLAS, "texture_height": ATLAS, "uv": [(i % 8) * CELL, (i // 8) * CELL], "uv_size": [CELL, CELL]}


def grad(*stops):
    """stops: (t, '#rrggbb', alpha) -> tinting gradient keyed by normalised age."""
    g = {}
    for t, col, a in stops:
        c = tex.hex_rgb(col)
        g[f"{t:.2f}"] = [round(float(c[0]), 3), round(float(c[1]), 3), round(float(c[2]), 3), a]
    return {"color": {"gradient": g, "interpolant": "variable.particle_age / variable.particle_lifetime"}}


AGE = "(variable.particle_age / variable.particle_lifetime)"


def effect(name: str, material: str, components: dict) -> dict:
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": f"{NS}:{name}",
                        "basic_render_parameters": {"material": material, "texture": PARTICLE_TEX}},
        "components": components}}


def aura(name, sprite, color, rate, radius, rise=0.6, size=0.14, life=1.4, material="particles_add"):
    return effect(name, material, {
        "minecraft:emitter_rate_steady": {"spawn_rate": rate, "max_particles": int(rate * life * 2) + 4},
        "minecraft:emitter_lifetime_looping": {"active_time": 1},
        "minecraft:emitter_shape_sphere": {"radius": radius, "direction": "outwards", "surface_only": False},
        "minecraft:particle_lifetime_expression": {"max_lifetime": f"{life} + variable.particle_random_1 * 0.6"},
        "minecraft:particle_initial_speed": 0.15,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, rise, 0], "linear_drag_coefficient": 1.5},
        "minecraft:particle_appearance_billboard": {
            "size": [f"{size} * (1 - {AGE} * 0.7)", f"{size} * (1 - {AGE} * 0.7)"],
            "facing_camera_mode": "rotate_xyz", "uv": uv(sprite)},
        "minecraft:particle_appearance_tinting": grad((0.0, color, 0.0), (0.15, color, 0.9), (1.0, color, 0.0)),
    })


def burst(name, sprite, color, count, speed, gravity=-6.0, size=0.18, life=0.8, material="particles_add", radius=0.4,
          color2=None):
    return effect(name, material, {
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_sphere": {"radius": radius, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": f"{life} * (0.6 + variable.particle_random_1 * 0.6)"},
        "minecraft:particle_initial_speed": f"{speed} * (0.5 + variable.particle_random_2)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, gravity, 0], "linear_drag_coefficient": 1.2},
        "minecraft:particle_motion_collision": {"collision_drag": 4, "coefficient_of_restitution": 0.2, "collision_radius": 0.05},
        "minecraft:particle_appearance_billboard": {
            "size": [f"{size} * (1 - {AGE} * 0.5)", f"{size} * (1 - {AGE} * 0.5)"],
            "facing_camera_mode": "rotate_xyz", "uv": uv(sprite)},
        "minecraft:particle_appearance_tinting": grad((0.0, color, 1.0), (0.6, color2 or color, 0.8), (1.0, color2 or color, 0.0)),
    })


def ground_ring(name, color, sprite="ring", grow=False, life=1.0):
    size = "variable.radius" if not grow else f"0.5 + variable.radius * {AGE}"
    return effect(name, "particles_add", {
        "minecraft:emitter_initialization": {"creation_expression": "variable.radius = variable.radius ?? 3.0;"},
        "minecraft:emitter_rate_instant": {"num_particles": 1},
        "minecraft:emitter_lifetime_once": {"active_time": 0.05},
        "minecraft:emitter_shape_point": {"offset": [0, 0.15, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "variable.life ?? " + str(life)},
        "minecraft:particle_appearance_billboard": {
            "size": [size, size], "facing_camera_mode": "direction_y" if False else "emitter_transform_xz",
            "uv": uv(sprite)},
        "minecraft:particle_appearance_tinting": grad((0.0, color, 0.0), (0.12, color, 0.95), (0.8, color, 0.8), (1.0, color, 0.0)),
    })


EFFECTS: dict[str, dict] = {}


def define():
    E = EFFECTS
    E["soul_wisp"] = aura("soul_wisp", "wisp", "#b98cff", 4, 0.5, rise=0.9, size=0.16)
    E["boss_aura_violet"] = aura("boss_aura_violet", "glow", "#9b5cff", 12, 1.6, rise=0.5, size=0.22)
    E["boss_aura_crimson"] = aura("boss_aura_crimson", "ember", "#ff2a4a", 18, 1.9, rise=1.2, size=0.2)
    E["boss_aura_gold"] = aura("boss_aura_gold", "star", "#ffd36a", 12, 2.2, rise=0.3, size=0.2)
    E["boss_aura_green"] = aura("boss_aura_green", "spore", "#8cff6a", 12, 2.2, rise=0.4, size=0.22)
    E["boss_aura_cyan"] = aura("boss_aura_cyan", "shard", "#3ff3ff", 12, 2.4, rise=0.6, size=0.22)
    E["star_spark"] = aura("star_spark", "spark", "#ffe58a", 6, 0.5, rise=0.2, size=0.12)
    E["spore_drift"] = aura("spore_drift", "spore", "#b6ff5c", 5, 1.2, rise=0.25, size=0.14, life=2.4)
    E["null_mote"] = aura("null_mote", "glow", "#3ff3ff", 6, 0.4, rise=0.5, size=0.12)
    E["portal_glow"] = aura("portal_glow", "spark", "#7ff6ff", 14, 1.4, rise=1.0, size=0.16)
    E["crystal_glint"] = aura("crystal_glint", "spark", "#a8fbff", 2, 0.5, rise=0.1, size=0.14, life=0.8)
    E["blood_ember"] = aura("blood_ember", "ember", "#ff3045", 10, 7.0, rise=0.6, size=0.12, life=3.0)
    E["ash_fall"] = aura("ash_fall", "flake", "#2a2630", 12, 8.0, rise=-0.9, size=0.14, life=4.0, material="particles_blend")
    E["fracture_glitch"] = aura("fracture_glitch", "crack", "#5affd8", 6, 3.0, rise=0.0, size=0.35, life=0.5)
    E["bolt_trail"] = effect("bolt_trail", "particles_add", {
        "minecraft:emitter_rate_steady": {"spawn_rate": 30, "max_particles": 40},
        "minecraft:emitter_lifetime_looping": {"active_time": 1},
        "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.4},
        "minecraft:particle_appearance_billboard": {"size": [f"0.25 * (1 - {AGE})", f"0.25 * (1 - {AGE})"],
                                                    "facing_camera_mode": "rotate_xyz", "uv": uv("glow")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#fff2c0", 0.9), (1.0, "#ff9a28", 0.0)),
    })
    E["meteor_trail"] = effect("meteor_trail", "particles_blend", {
        "minecraft:emitter_rate_steady": {"spawn_rate": 40, "max_particles": 90},
        "minecraft:emitter_lifetime_looping": {"active_time": 1},
        "minecraft:emitter_shape_sphere": {"radius": 0.5},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "1.2 + variable.particle_random_1"},
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.0, 0], "linear_drag_coefficient": 0.8},
        "minecraft:particle_appearance_billboard": {"size": [f"0.3 + {AGE} * 0.8", f"0.3 + {AGE} * 0.8"],
                                                    "facing_camera_mode": "rotate_xyz", "uv": uv("smoke")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#fff2c0", 1.0), (0.15, "#ff7a1a", 0.95), (0.5, "#3a2a24", 0.6),
                                                      (1.0, "#1a1412", 0.0)),
    })
    E["void_swirl"] = effect("void_swirl", "particles_add", {
        "minecraft:emitter_rate_steady": {"spawn_rate": 14, "max_particles": 40},
        "minecraft:emitter_lifetime_looping": {"active_time": 1},
        "minecraft:emitter_shape_disc": {"radius": 1.6, "plane_normal": "z", "direction": "inwards", "surface_only": True,
                                         "offset": [0, 1.1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 1.2},
        "minecraft:particle_initial_speed": 1.2,
        "minecraft:particle_appearance_billboard": {"size": [0.14, 0.14], "facing_camera_mode": "rotate_xyz", "uv": uv("glow")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#d8a8ff", 0.0), (0.3, "#b98cff", 0.9), (1.0, "#4b2a85", 0.0)),
    })
    E["telegraph_ring"] = ground_ring("telegraph_ring", "#ff2a2a")
    E["telegraph_ring_violet"] = ground_ring("telegraph_ring_violet", "#b98cff")
    E["shockwave"] = ground_ring("shockwave", "#ffe0b0", sprite="shockwave", grow=True, life=0.6)
    E["rune_circle"] = effect("rune_circle", "particles_add", {
        "minecraft:emitter_initialization": {"creation_expression": "variable.radius = variable.radius ?? 3.0;"},
        "minecraft:emitter_rate_instant": {"num_particles": 10},
        "minecraft:emitter_lifetime_once": {"active_time": 0.05},
        "minecraft:emitter_shape_disc": {"radius": "variable.radius", "plane_normal": "y", "surface_only": True,
                                         "offset": [0, 0.2, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "variable.life ?? 1.5"},
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.4, 0]},
        "minecraft:particle_appearance_billboard": {"size": [0.4, 0.4], "facing_camera_mode": "rotate_xyz", "uv": uv("rune")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#b98cff", 0.0), (0.2, "#d8b8ff", 1.0), (1.0, "#7d45e8", 0.0)),
    })
    E["impact_burst"] = burst("impact_burst", "ember", "#ffe0a0", 22, 6.0, color2="#ff5a1a")
    E["spectral_burst"] = burst("spectral_burst", "wisp", "#d8b8ff", 18, 3.0, gravity=2.0, size=0.25, color2="#7d45e8")
    E["root_eruption"] = burst("root_eruption", "spore", "#6b4f30", 20, 7.0, gravity=-12.0, size=0.22,
                               material="particles_blend", color2="#2e5a1e")
    E["heal_motes"] = burst("heal_motes", "plus", "#8cff6a", 8, 0.8, gravity=1.5, size=0.16, life=1.0)
    E["blood_burst"] = burst("blood_burst", "ember", "#ff2a4a", 10, 1.5, gravity=-3.0, size=0.14, life=0.7)
    E["star_nova"] = burst("star_nova", "star", "#fff2c0", 40, 12.0, gravity=0.0, size=0.35, life=1.2, radius=1.0,
                           color2="#ff9a28")
    E["gravity_pull"] = effect("gravity_pull", "particles_add", {
        "minecraft:emitter_initialization": {"creation_expression": "variable.radius = variable.radius ?? 5.0;"},
        "minecraft:emitter_rate_instant": {"num_particles": 24},
        "minecraft:emitter_lifetime_once": {"active_time": 0.05},
        "minecraft:emitter_shape_sphere": {"radius": "variable.radius", "surface_only": True, "direction": "inwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.9},
        "minecraft:particle_initial_speed": "variable.radius * 1.1",
        "minecraft:particle_appearance_billboard": {"size": [0.16, 0.16], "facing_camera_mode": "rotate_xyz", "uv": uv("shard")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#b98cff", 0.0), (0.2, "#e0c4ff", 1.0), (1.0, "#3ff3ff", 0.2)),
    })
    E["null_beam"] = effect("null_beam", "particles_add", {
        "minecraft:emitter_rate_instant": {"num_particles": 3},
        "minecraft:emitter_lifetime_once": {"active_time": 0.05},
        "minecraft:emitter_shape_sphere": {"radius": 0.25},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.45},
        "minecraft:particle_appearance_billboard": {"size": [f"0.6 * (1 - {AGE})", f"0.6 * (1 - {AGE})"],
                                                    "facing_camera_mode": "rotate_xyz", "uv": uv("glow")},
        "minecraft:particle_appearance_tinting": grad((0.0, "#ffffff", 1.0), (0.4, "#3ff3ff", 0.9), (1.0, "#8a3dff", 0.0)),
    })


def build():
    define()
    REG.add_texture(TexAsset(PARTICLE_TEX, paint_atlas, {"base": 1, "balanced": 2, "enhanced": 2}, pbr=False))
    for name, doc in EFFECTS.items():
        REG.add_rp(f"particles/{NS}/{name}.particle.json", doc)
        REG.ts("particles", name.upper(), f"{NS}:{name}")
        for tier, mult in (("potato", 0.35), ("enhanced", 1.7)):
            REG.subpack_json[tier][f"particles/{NS}/{name}.particle.json"] = _scale_density(doc, mult)


def _scale_density(doc: dict, mult: float) -> dict:
    d = copy.deepcopy(doc)
    comps = d["particle_effect"]["components"]
    if "minecraft:emitter_rate_steady" in comps:
        r = comps["minecraft:emitter_rate_steady"]
        r["spawn_rate"] = max(1, round(r["spawn_rate"] * mult, 2))
        r["max_particles"] = max(2, int(round(r["max_particles"] * mult)))
    if "minecraft:emitter_rate_instant" in comps:
        r = comps["minecraft:emitter_rate_instant"]
        if isinstance(r["num_particles"], (int, float)) and r["num_particles"] > 1:
            r["num_particles"] = max(1, int(round(r["num_particles"] * mult)))
    return d
