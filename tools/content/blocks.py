"""Blocks: definitions, textures (with PBR normal + MER), loot, sounds, ore generation."""
from __future__ import annotations

import numpy as np

from tools.content.common import BLOCK_FMT, BLOCK_TEX, DENS_BLOCK, FEATURE_FMT, NS, ident, item_entry, loot_table
from tools.content.registry import REG, TexAsset
from tools.lib import tex

PICKAXE = {"condition": "match_tool", "minecraft:match_tool_filter_any": ["minecraft:is_pickaxe"]}
SILK = {"condition": "match_tool", "enchantments": [{"enchantment": "silk_touch", "levels": {"range_min": 1}}]}


# ------------------------------------------------------------------------------------------------
# texture painters (16*density px, tileable)
# ------------------------------------------------------------------------------------------------

def _cv_from(sw: tex.Swatch, s: int) -> tex.Canvas:
    cv = tex.Canvas(s, s)
    cv.paint(0, 0, sw.rgb, 1.0 if sw.alpha is None else sw.alpha, metal=sw.metal, emissive=sw.emissive,
             rough=sw.rough, height=sw.height)
    return cv


def _stone(s, seed, pal):
    sw = tex.material("stone", s, s, seed, pal, detail=0.9)
    return tex.shade_face(sw, top_light=0.0, edge_dark=0.0)


def _ore(s, seed, base_pal, gem_pal, glow=0.85):
    sw = _stone(s, seed, base_pal)
    rng = np.random.default_rng(seed)
    m = np.zeros((s, s), dtype=np.float32)
    for _ in range(5):
        cx, cy = rng.random() * s, rng.random() * s
        r = s * (0.08 + rng.random() * 0.07)
        pts = [(cx + np.cos(a) * r * (0.6 + rng.random() * 0.6), cy + np.sin(a) * r * (0.6 + rng.random() * 0.6))
               for a in np.linspace(0, 2 * np.pi, 6, endpoint=False)]
        m = np.maximum(m, tex.poly_mask(s, s, pts))
    gem = tex.material("crystal", s, s, seed + 3, gem_pal)
    rgb = sw.rgb * (1 - m[..., None]) + gem.rgb * m[..., None]
    sw = tex.Swatch(rgb, sw.height + m * 0.4, sw.metal, np.maximum(sw.emissive, m * glow), sw.rough * (1 - m) + 0.15 * m)
    return sw


def paint_rift_ore(d):
    s = 16 * d
    return _cv_from(_ore(s, 11, [(0, "#2c2a30"), (0.5, "#565360"), (1, "#7e7b88")],
                         [(0, "#06303a"), (0.5, "#1fc6dc"), (1, "#c8ffff")]), s)


def paint_deepslate_rift_ore(d):
    s = 16 * d
    sw = _ore(s, 12, [(0, "#121116"), (0.5, "#2a2830"), (1, "#45424e")],
              [(0, "#06303a"), (0.5, "#1fc6dc"), (1, "#c8ffff")])
    layers = tex.stripes_mask(s, s, max(2, s // 4), max(1, s // 16), horizontal=True)
    sw.rgb = sw.rgb * (1 - 0.18 * layers[..., None])
    return _cv_from(sw, s)


def paint_meteorite(d):
    s = 16 * d
    sw = tex.material("stone", s, s, 21, [(0, "#0b0705"), (0.5, "#2a1c14"), (1, "#4f3a2c")], detail=0.8)
    cr = tex.crack_mask(s, s, 22, points=5, width=0.06)
    sw = tex.add_glow(sw, cr, "#ff7a1a", 0.9)
    specks = tex.spots_mask(s, s, 23, 5, max(1.0, s / 26))
    sw = tex.add_glow(sw, specks, "#ffd36a", 1.0)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.0), s)


def paint_aether_block(d):
    s = 16 * d
    sw = tex.material("crystal", s, s, 31, [(0, "#0a2f3d"), (0.45, "#2fd6e8"), (0.8, "#a8fbff"), (1, "#ffffff")])
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.25, bevel_px=d), s)


def _bricks(s, seed, pal, mortar="#07050a", glow_mortar=None):
    sw = tex.material("stone", s, s, seed, pal, detail=1.2)
    m = np.zeros((s, s), dtype=np.float32)
    row = s // 4
    for r in range(4):
        y = r * row
        m[y:y + max(1, s // 32), :] = 1
        off = (row * 2 if r % 2 else 0)
        for x in range(off % (s // 2), s, s // 2):
            m[y:y + row, x:x + max(1, s // 32)] = 1
    c = tex.hex_rgb(mortar)
    rgb = sw.rgb * (1 - m[..., None]) + c * m[..., None]
    out = tex.Swatch(rgb, sw.height - m * 0.5, sw.metal, sw.emissive, sw.rough)
    if glow_mortar:
        out = tex.add_glow(out, m * 0.3, glow_mortar, 0.3)
    return out


def paint_runestone_bricks(d):
    s = 16 * d
    return _cv_from(_bricks(s, 41, [(0, "#1a1722"), (0.5, "#34303f"), (1, "#57506a")], glow_mortar="#7d45e8"), s)


def paint_chiseled_runestone(d):
    s = 16 * d
    sw = tex.material("rune_stone", s, s, 42, [(0, "#1a1722"), (0.5, "#34303f"), (1, "#57506a")])
    frame = np.zeros((s, s), dtype=np.float32)
    b = max(1, s // 8)
    frame[:b, :] = frame[-b:, :] = 1
    frame[:, :b] = frame[:, -b:] = 1
    sw.rgb = sw.rgb * (1 - 0.35 * frame[..., None])
    g = tex.glyph(s - 4 * b, 77)
    m = np.zeros((s, s), dtype=np.float32)
    m[2 * b:s - 2 * b, 2 * b:s - 2 * b] = g
    sw = tex.add_glow(sw, m, "#b98cff", 1.0)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.3, bevel_px=d), s)


def paint_blighted_soil(d):
    s = 16 * d
    sw = tex.material("soil", s, s, 51, [(0, "#2a1e1a"), (0.5, "#4a3a34"), (1, "#6e5850")])
    sw = tex.add_glow(sw, tex.spots_mask(s, s, 52, 4, max(1.0, s / 30)), "#8cff6a", 0.5)
    return _cv_from(sw, s)


def paint_blighted_grass_top(d):
    s = 16 * d
    sw = tex.material("moss", s, s, 53, [(0, "#2a2034"), (0.5, "#4a3a5e"), (0.85, "#6f8f3a"), (1, "#b6ff7a")])
    return _cv_from(sw, s)


def paint_blighted_grass_side(d):
    s = 16 * d
    soil = tex.material("soil", s, s, 51, [(0, "#2a1e1a"), (0.5, "#4a3a34"), (1, "#6e5850")])
    top = tex.material("moss", s, s, 53, [(0, "#2a2034"), (0.5, "#4a3a5e"), (0.85, "#6f8f3a"), (1, "#b6ff7a")])
    n = tex.fbm(s, 4, 54, base_cells=4, octaves=2)[1]
    yy = (np.arange(s) + 0.5) / s
    m = (yy[:, None] < (0.22 + 0.15 * n[None, :])).astype(np.float32)
    rgb = soil.rgb * (1 - m[..., None]) + top.rgb * m[..., None]
    sw = tex.Swatch(rgb, soil.height * (1 - m) + top.height * m, soil.metal, top.emissive * m, soil.rough)
    return _cv_from(sw, s)


def paint_shattered_stone(d):
    s = 16 * d
    sw = tex.material("stone", s, s, 61, [(0, "#2e2b3a"), (0.5, "#5e5a78"), (1, "#a49ec2")], detail=1.0)
    sw = tex.add_glow(sw, tex.crack_mask(s, s, 62, points=4, width=0.04), "#3ff3ff", 0.7)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.0), s)


def paint_void_moss_top(d):
    s = 16 * d
    sw = tex.material("moss", s, s, 63, [(0, "#0e1a22"), (0.5, "#1f4a55"), (0.85, "#2f8f99"), (1, "#8ff8ff")])
    return _cv_from(sw, s)


def paint_void_moss_side(d):
    s = 16 * d
    stone = tex.material("stone", s, s, 61, [(0, "#2e2b3a"), (0.5, "#5e5a78"), (1, "#a49ec2")], detail=1.0)
    top = tex.material("moss", s, s, 63, [(0, "#0e1a22"), (0.5, "#1f4a55"), (0.85, "#2f8f99"), (1, "#8ff8ff")])
    n = tex.fbm(s, 4, 64, base_cells=4, octaves=2)[1]
    yy = (np.arange(s) + 0.5) / s
    m = (yy[:, None] < (0.25 + 0.2 * n[None, :])).astype(np.float32)
    rgb = stone.rgb * (1 - m[..., None]) + top.rgb * m[..., None]
    return _cv_from(tex.Swatch(rgb, stone.height, stone.metal, top.emissive * m, stone.rough), s)


def paint_cache_side(d):
    s = 16 * d
    sw = tex.material("bronze", s, s, 71, [(0, "#1e1206"), (0.5, "#5b3d16"), (0.85, "#a07834"), (1, "#e6c27a")])
    band = np.zeros((s, s), dtype=np.float32)
    b = max(1, s // 8)
    band[:b, :] = band[-b:, :] = 1
    band[:, :b] = band[:, -b:] = 1
    sw.rgb = sw.rgb * (1 - 0.4 * band[..., None])
    seal = np.maximum(tex.ring_mask(s, s, s / 2, s / 2, s * 0.25, max(1.0, s / 16)),
                      tex.disc_mask(s, s, s / 2, s / 2, s * 0.1))
    sw = tex.add_glow(sw, seal, "#3ff3ff", 0.9)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.3, bevel_px=d), s)


def paint_cache_top(d):
    s = 16 * d
    sw = tex.material("rune_stone", s, s, 72, [(0, "#1a1722"), (0.5, "#34303f"), (1, "#57506a")])
    g = tex.glyph(s, 99)
    sw = tex.add_glow(sw, g, "#3ff3ff", 0.9)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.35, bevel_px=d), s)


def paint_gate_top(d):
    s = 16 * d
    sw = tex.material("chitin", s, s, 81, [(0, "#020205"), (0.5, "#0e0d18"), (0.85, "#24223a"), (1, "#4a4670")])
    sig = np.maximum(tex.ring_mask(s, s, s / 2, s / 2, s * 0.38, max(1.0, s / 14)),
                     tex.poly_mask(s, s, [(s / 2, s * 0.2), (s * 0.75, s / 2), (s / 2, s * 0.8), (s * 0.25, s / 2)]))
    sw = tex.add_glow(sw, sig, "#3ff3ff", 1.0)
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.3, bevel_px=d), s)


def paint_gate_side(d):
    s = 16 * d
    sw = _bricks(s, 82, [(0, "#0c0c16"), (0.5, "#262438"), (1, "#4a4670")], mortar="#05050a", glow_mortar="#1f8f99")
    return _cv_from(tex.shade_face(sw, top_light=0.0, edge_dark=0.2, bevel_px=d), s)


def _cross_sprite(d, seed, pal, shape="cluster", glow=0.9):
    s = 16 * d
    cv = tex.Canvas(s, s)
    rng = np.random.default_rng(seed)
    if shape == "cluster":
        shards = [(0.5, 0.08, 0.13), (0.28, 0.32, 0.09), (0.72, 0.28, 0.1), (0.4, 0.45, 0.07), (0.62, 0.5, 0.08)]
        for cx, top, w in shards:
            pts = [((cx - w) * s, s), ((cx - w * 0.9) * s, (top + 0.12) * s), (cx * s, top * s),
                   ((cx + w * 0.9) * s, (top + 0.12) * s), ((cx + w) * s, s)]
            m = tex.poly_mask(s, s, pts)
            sw = tex.material("crystal", s, s, seed + int(cx * 100), pal)
            cv.paint(0, 0, sw.rgb, m, metal=0.0, emissive=np.maximum(sw.emissive, glow * 0.8), rough=0.1, height=sw.height)
    else:  # sprout: curling blighted stalks
        for i in range(4):
            x0 = s * (0.2 + 0.2 * i)
            pts = [(x0, s), (x0 + s * 0.05, s * 0.5), (x0 + s * (0.1 if i % 2 else -0.08), s * (0.25 + 0.1 * rng.random())),
                   (x0 + s * 0.08, s * 0.5), (x0 + s * 0.09, s)]
            m = tex.poly_mask(s, s, pts)
            sw = tex.material("moss", s, s, seed + i, pal)
            cv.paint(0, 0, sw.rgb, m, emissive=sw.emissive, rough=0.8, height=sw.height)
            bud = tex.disc_mask(s, s, x0 + s * (0.1 if i % 2 else -0.08), s * 0.27, s * 0.06)
            cv.paint(0, 0, np.broadcast_to(tex.hex_rgb("#c8ff7a"), (s, s, 3)).copy(), bud, emissive=1.0, rough=0.3)
    return cv


# ------------------------------------------------------------------------------------------------
# registration helpers
# ------------------------------------------------------------------------------------------------

def tex_key(name: str) -> str:
    return f"{NS}_{name}"


def block_texture(name: str, painter, normal: bool = True):
    REG.add_texture(TexAsset(f"{BLOCK_TEX}/{name}", painter, DENS_BLOCK, pbr=True, normal=normal))
    REG.terrain_textures[tex_key(name)] = f"{BLOCK_TEX}/{name}"


def block(name: str, display: str, components: dict, sound: str, loot: dict | None, category: str = "construction",
          group: str | None = None, traits: dict | None = None):
    desc: dict = {"identifier": ident(name), "menu_category": {"category": category}}
    if group:
        desc["menu_category"]["group"] = group
    if traits:
        desc["traits"] = traits
    comps = dict(components)
    if loot is not None:
        comps["minecraft:loot"] = f"loot_tables/blocks/{NS}/{name}.json"
        REG.add_bp(f"loot_tables/blocks/{NS}/{name}.json", loot)
    REG.add_bp(f"blocks/{NS}/{name}.json", {"format_version": BLOCK_FMT, "minecraft:block": {"description": desc,
                                                                                           "components": comps}})
    REG.blocks_json[ident(name)] = {"sound": sound}
    REG.name(f"tile.{ident(name)}.name", display)
    REG.ts("blocks", name.upper(), ident(name))


def mats(all_key: str, up: str | None = None, down: str | None = None, render="opaque", ao=1.0) -> dict:
    mi = {"*": {"texture": tex_key(all_key), "render_method": render, "ambient_occlusion": ao}}
    if up:
        mi["up"] = {"texture": tex_key(up), "render_method": render, "ambient_occlusion": ao}
    if down:
        mi["down"] = {"texture": tex_key(down), "render_method": render, "ambient_occlusion": ao}
    return {"minecraft:material_instances": mi}


def self_drop(name: str) -> dict:
    return loot_table([{"rolls": 1, "entries": [item_entry(ident(name))]}])


def ore_loot(name: str, drop: str, count: tuple[int, int], extra: list | None = None) -> dict:
    pools = [{"rolls": 1, "entries": [item_entry(ident(name))], "conditions": [SILK]},
             {"rolls": 1, "conditions": [PICKAXE],
              "entries": [{"type": "item", "name": drop, "weight": 1,
                           "functions": [{"function": "set_count", "count": {"min": count[0], "max": count[1]}},
                                         {"function": "explosion_decay"}]}]}]
    if extra:
        pools.extend(extra)
    return loot_table(pools)


def build():
    pick_tag = {"minecraft:tags": ["minecraft:is_pickaxe_item_destructible"]}
    shovel_tag = {"minecraft:tags": ["minecraft:is_shovel_item_destructible"]}

    block_texture("rift_ore", paint_rift_ore)
    block("rift_ore", "Rift Ore", {
        **mats("rift_ore"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 3.0},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 3.0},
        "minecraft:light_emission": 3,
        "minecraft:map_color": "#2a8c99",
        f"{NS}:ore_xp": {"min": 2, "max": 5},
    }, "stone", ore_loot("rift_ore", ident("rift_shard"), (1, 3)), category="nature", group="minecraft:itemGroup.name.ore")

    block_texture("deepslate_rift_ore", paint_deepslate_rift_ore)
    block("deepslate_rift_ore", "Deepslate Rift Ore", {
        **mats("deepslate_rift_ore"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 4.5},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 3.0},
        "minecraft:light_emission": 3,
        "minecraft:map_color": "#1d5f69",
        f"{NS}:ore_xp": {"min": 3, "max": 6},
    }, "deepslate", ore_loot("deepslate_rift_ore", ident("rift_shard"), (2, 4)), category="nature",
        group="minecraft:itemGroup.name.ore")

    block_texture("meteorite", paint_meteorite)
    block("meteorite", "Meteorite", {
        **mats("meteorite"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 3.5},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 9.0},
        "minecraft:light_emission": 6,
        "minecraft:map_color": "#5a2a12",
        f"{NS}:ore_xp": {"min": 3, "max": 7},
    }, "stone", ore_loot("meteorite", ident("star_metal_chunk"), (1, 2),
                         extra=[{"rolls": 1, "conditions": [PICKAXE],
                                 "entries": [item_entry(ident("stardust"), count=(1, 3))]}]), category="nature",
        group="minecraft:itemGroup.name.ore")

    block_texture("aether_crystal_block", paint_aether_block)
    block("aether_crystal_block", "Block of Aether Crystal", {
        **mats("aether_crystal_block"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 1.5},
        "minecraft:light_emission": 12,
        "minecraft:map_color": "#5cf0ff",
    }, "amethyst_block", self_drop("aether_crystal_block"))

    block_texture("runestone_bricks", paint_runestone_bricks)
    block("runestone_bricks", "Runestone Bricks", {
        **mats("runestone_bricks"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 2.0},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 6.0},
        "minecraft:map_color": "#34303f",
    }, "stone", self_drop("runestone_bricks"))

    block_texture("chiseled_runestone", paint_chiseled_runestone)
    block("chiseled_runestone", "Chiseled Runestone", {
        **mats("chiseled_runestone"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 2.0},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 6.0},
        "minecraft:light_emission": 7,
        "minecraft:map_color": "#4a3a70",
    }, "stone", self_drop("chiseled_runestone"))

    block_texture("blighted_soil", paint_blighted_soil)
    block("blighted_soil", "Blighted Soil", {
        **mats("blighted_soil"), **shovel_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.7},
        "minecraft:map_color": "#2b1f1c",
    }, "gravel", self_drop("blighted_soil"), category="nature")

    block_texture("blighted_grass_top", paint_blighted_grass_top)
    block_texture("blighted_grass_side", paint_blighted_grass_side)
    block("blighted_grass", "Blighted Grass", {
        **mats("blighted_grass_side", up="blighted_grass_top", down="blighted_soil"), **shovel_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.8},
        "minecraft:map_color": "#3b2a4a",
    }, "grass", loot_table([{"rolls": 1, "entries": [item_entry(ident("blighted_soil"))]}]), category="nature")

    block_texture("shattered_stone", paint_shattered_stone)
    block("shattered_stone", "Shattered Stone", {
        **mats("shattered_stone"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 2.0},
        "minecraft:light_emission": 1,
        "minecraft:map_color": "#4a4660",
    }, "stone", self_drop("shattered_stone"), category="nature")

    block_texture("void_moss_top", paint_void_moss_top)
    block_texture("void_moss_side", paint_void_moss_side)
    block("void_moss", "Void Moss", {
        **mats("void_moss_side", up="void_moss_top", down="shattered_stone"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 1.2},
        "minecraft:light_emission": 4,
        "minecraft:map_color": "#1f6b75",
    }, "moss_block", self_drop("void_moss"), category="nature")

    # cross-model decorations (vanilla geometry.cross)
    REG.add_texture(TexAsset(f"{BLOCK_TEX}/aether_cluster",
                             lambda d: _cross_sprite(d, 91, [(0, "#0a2f3d"), (0.45, "#2fd6e8"), (0.85, "#a8fbff"), (1, "#ffffff")]),
                             DENS_BLOCK, pbr=True))
    REG.terrain_textures[tex_key("aether_cluster")] = f"{BLOCK_TEX}/aether_cluster"
    cross = lambda key: {"minecraft:geometry": "minecraft:geometry.cross",
                         "minecraft:material_instances": {"*": {"texture": tex_key(key), "render_method": "alpha_test",
                                                                "ambient_occlusion": 0.0, "face_dimming": False}},
                         "minecraft:collision_box": False,
                         "minecraft:selection_box": {"origin": [-6, 0, -6], "size": [12, 12, 12]},
                         "minecraft:light_dampening": 0}
    block("aether_cluster", "Aether Cluster", {
        **cross("aether_cluster"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.8},
        "minecraft:light_emission": 9,
        "minecraft:map_color": "#5cf0ff",
        "minecraft:placement_filter": {"conditions": [{"allowed_faces": ["up"]}]},
    }, "amethyst_cluster", loot_table([
        {"rolls": 1, "entries": [item_entry(ident("aether_cluster"))], "conditions": [SILK]},
        {"rolls": 1, "entries": [item_entry(ident("rift_shard"), count=(1, 2))], "conditions": [PICKAXE]},
    ]), category="nature")

    REG.add_texture(TexAsset(f"{BLOCK_TEX}/blight_sprout",
                             lambda d: _cross_sprite(d, 92, [(0, "#0f0a14"), (0.5, "#3b2a4a"), (0.85, "#6b8f2a"), (1, "#c8ff7a")], "sprout"),
                             DENS_BLOCK, pbr=True))
    REG.terrain_textures[tex_key("blight_sprout")] = f"{BLOCK_TEX}/blight_sprout"
    block("blight_sprout", "Blight Sprout", {
        **cross("blight_sprout"),
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.0},
        "minecraft:light_emission": 4,
        "minecraft:map_color": "#3b2a4a",
        "minecraft:replaceable": {},
        "minecraft:placement_filter": {"conditions": [{"allowed_faces": ["up"],
                                                       "block_filter": [ident("blighted_grass"), ident("blighted_soil"),
                                                                        "minecraft:grass_block", "minecraft:dirt"]}]},
    }, "grass", loot_table([]), category="nature")

    # functional blocks
    block_texture("engine_cache_side", paint_cache_side)
    block_texture("engine_cache_top", paint_cache_top)
    block("engine_cache", "Sealed Engine Cache", {
        **mats("engine_cache_side", up="engine_cache_top", down="engine_cache_top"), **pick_tag,
        "minecraft:destructible_by_mining": {"seconds_to_destroy": 2.5},
        "minecraft:destructible_by_explosion": {"explosion_resistance": 12.0},
        "minecraft:light_emission": 5,
        "minecraft:map_color": "#a07834",
        f"{NS}:cache": {},
    }, "metal", loot_table([
        {"rolls": {"min": 2, "max": 4}, "entries": [
            item_entry(ident("rift_shard"), 30, (2, 6)), item_entry(ident("aether_crystal"), 18, (1, 2)),
            item_entry(ident("soul_essence"), 14, (1, 3)), item_entry(ident("stardust"), 12, (2, 4)),
            item_entry(ident("star_metal_ingot"), 8, (1, 2)), item_entry("minecraft:diamond", 5, (1, 2)),
            item_entry("minecraft:gold_ingot", 10, (2, 5)), item_entry(ident("aether_elixir"), 6)]},
        {"rolls": 1, "entries": [item_entry(ident("cursed_crown"), 3), item_entry(ident("heartseed"), 3),
                                 item_entry(ident("astral_lure"), 2), {"type": "empty", "weight": 22}]},
    ]))

    block_texture("null_gate_top", paint_gate_top)
    block_texture("null_gate_side", paint_gate_side)
    block("null_gate", "Null Gate", {
        **mats("null_gate_side", up="null_gate_top", down="null_gate_side"),
        "minecraft:destructible_by_mining": False,
        "minecraft:destructible_by_explosion": False,
        "minecraft:light_emission": 10,
        "minecraft:map_color": "#3ff3ff",
        f"{NS}:null_gate": {},
    }, "stone", None)

    # ---------------------------------------------------------------- ore generation (overworld)
    REG.add_bp(f"features/{NS}/rift_ore_feature.json", {
        "format_version": FEATURE_FMT,
        "minecraft:ore_feature": {
            "description": {"identifier": ident("rift_ore_feature")},
            "count": 6,
            "replace_rules": [
                {"places_block": ident("rift_ore"),
                 "may_replace": ["minecraft:stone", "minecraft:andesite", "minecraft:diorite", "minecraft:granite"]},
                {"places_block": ident("deepslate_rift_ore"), "may_replace": ["minecraft:deepslate", "minecraft:tuff"]},
            ],
        }})
    REG.add_bp(f"feature_rules/{NS}/rift_ore_rule.json", {
        "format_version": FEATURE_FMT,
        "minecraft:feature_rules": {
            "description": {"identifier": ident("rift_ore_rule"), "places_feature": ident("rift_ore_feature")},
            "conditions": {"placement_pass": "underground_pass",
                           "minecraft:biome_filter": [{"test": "has_biome_tag", "operator": "==", "value": "overworld"}]},
            "distribution": {
                "iterations": 5,
                "coordinate_eval_order": "zyx",
                "x": {"distribution": "uniform", "extent": [0, 16]},
                "y": {"distribution": "uniform", "extent": [-56, 40]},
                "z": {"distribution": "uniform", "extent": [0, 16]},
            },
        }})
