"""World content: custom biome (with Vibrant Visuals per-biome settings), fogs, structures, features."""
from __future__ import annotations

from tools.content.common import FEATURE_FMT, NS, ident
from tools.content.registry import REG
from tools.lib.mcstructure import write_structure

BIOME = "blighted_wilds"


# ================================================================================================
# custom biome — partial replacement of vanilla forests (stable since 1.21.110)
# ================================================================================================

def biome():
    REG.add_bp(f"biomes/{BIOME}.biome.json", {
        "format_version": "1.26.0",
        "minecraft:biome": {
            "description": {"identifier": ident(BIOME)},
            "components": {
                "minecraft:climate": {"downfall": 0.6, "snow_accumulation": [0.0, 0.125], "temperature": 0.6},
                "minecraft:humidity": {"is_humid": True},
                "minecraft:surface_builder": {"builder": {
                    "type": "minecraft:overworld",
                    "sea_floor_depth": 7,
                    "sea_floor_material": "minecraft:gravel",
                    "foundation_material": "minecraft:stone",
                    "mid_material": ident("blighted_soil"),
                    "top_material": ident("blighted_grass"),
                    "sea_material": "minecraft:water"}},
                "minecraft:replace_biomes": {"replacements": [
                    {"dimension": "minecraft:overworld", "targets": ["roofed_forest", "forest", "birch_forest"],
                     "amount": 0.22, "noise_frequency_scale": 14.0}]},
                "minecraft:tags": {"tags": ["overworld", "monster", "forest", "apocalypse_blight"]},
            },
        },
    })
    REG.add_rp(f"biomes/{BIOME}.client_biome.json", {
        "format_version": "1.21.120",
        "minecraft:client_biome": {
            "description": {"identifier": ident(BIOME)},
            "components": {
                "minecraft:fog_appearance": {"fog_identifier": f"{NS}:fog_blight"},
                "minecraft:water_appearance": {"surface_color": "#3A5A4A"},
                "minecraft:foliage_appearance": {"color": "#4E3F5E"},
                "minecraft:grass_appearance": {"color": "#5A4A6A"},
                "minecraft:atmosphere_identifier": {"atmosphere_identifier": f"{NS}:blight_atmospherics"},
                "minecraft:color_grading_identifier": {"color_grading_identifier": f"{NS}:blight_color_grading"},
                "minecraft:lighting_identifier": {"lighting_identifier": f"{NS}:blight_lighting"},
                "minecraft:water_identifier": {"water_identifier": "minecraft:default_water"},
            },
        },
    })
    REG.name(f"biome.{ident(BIOME)}.name", "Blighted Wilds")
    # Vibrant Visuals per-biome configuration (only used when the player enables Vibrant Visuals)
    REG.add_rp(f"atmospherics/{NS}_blight_atmospherics.json", {
        "format_version": "1.21.40",
        "minecraft:atmosphere_settings": {
            "description": {"identifier": f"{NS}:blight_atmospherics"},
            "sky_zenith_color": {"0.0": [52, 40, 78], "0.25": [92, 74, 120], "0.5": [24, 16, 36], "0.75": [92, 74, 120], "1.0": [52, 40, 78]},
            "sky_horizon_color": {"0.0": [150, 168, 110], "0.22": [220, 160, 120], "0.3": [120, 90, 140], "0.5": [40, 30, 60],
                                  "0.7": [120, 90, 140], "0.78": [220, 160, 120], "1.0": [150, 168, 110]},
            "horizon_blend_stops": {"min": {"0.0": 0.0, "1.0": 0.0}, "start": {"0.0": 0.7, "0.5": 0.3, "1.0": 0.7},
                                    "mie_start": {"0.0": 0.5, "1.0": 0.5}, "max": {"0.0": 0.3, "1.0": 0.3}},
            "rayleigh_strength": {"0.0": 6.0, "0.5": 3.0, "1.0": 6.0},
            "sun_mie_strength": {"0.0": 0.0, "0.25": 0.9, "0.5": 0.0, "0.75": 0.9, "1.0": 0.0},
            "moon_mie_strength": {"0.0": 0.2, "1.0": 0.2},
            "sun_glare_shape": {"0.0": 0.0, "0.25": 0.08, "0.5": 0.0, "0.75": 0.08, "1.0": 0.0},
        }})
    REG.add_rp(f"color_grading/{NS}_blight_color_grading.json", {
        "format_version": "1.21.90",
        "minecraft:color_grading_settings": {
            "description": {"identifier": f"{NS}:blight_color_grading"},
            "color_grading": {
                "midtones": {"contrast": [1.18, 1.14, 1.2], "gain": [0.98, 1.0, 1.04], "gamma": [2.2, 2.2, 2.2],
                             "offset": [0.0, 0.0, 0.01], "saturation": [0.86, 0.9, 0.95]},
                "temperature": {"enabled": True, "temperature": 7200, "type": "color_temperature"},
            },
        }})
    REG.add_rp(f"lighting/{NS}_blight_lighting.json", {
        "format_version": "1.21.70",
        "minecraft:lighting_settings": {
            "description": {"identifier": f"{NS}:blight_lighting"},
            "directional_lights": {
                "sun": {"illuminance": {"0.0": 55.0, "0.282": 1.0, "0.2915": 0.01, "0.292": 0.0, "0.709": 0.0,
                                        "0.719": 1.0, "0.95": 55.0, "1.0": 55.0},
                        "color": {"0.0": [214, 255, 176], "0.25": [255, 170, 120], "0.5": [210, 160, 255],
                                  "0.75": [255, 170, 120], "1.0": [214, 255, 176]}},
                "moon": {"illuminance": {"0.0": 0.0, "0.2": 0.0, "0.225": 0.5, "0.735": 0.5, "0.75": 0.0, "1.0": 0.0},
                         "color": {"0.0": [190, 160, 255], "1.0": [190, 160, 255]}},
            },
        }})
    # decorations restricted to the custom biome tag
    REG.add_bp(f"features/{NS}/blight_sprout_feature.json", {
        "format_version": FEATURE_FMT,
        "minecraft:single_block_feature": {
            "description": {"identifier": ident("blight_sprout_feature")},
            "places_block": ident("blight_sprout"),
            "enforce_placement_rules": True,
            "enforce_survivability_rules": True,
            "may_attach_to": {"bottom": [ident("blighted_grass"), ident("blighted_soil")]},
        }})
    REG.add_bp(f"feature_rules/{NS}/blight_sprout_rule.json", {
        "format_version": FEATURE_FMT,
        "minecraft:feature_rules": {
            "description": {"identifier": ident("blight_sprout_rule"), "places_feature": ident("blight_sprout_feature")},
            "conditions": {"placement_pass": "surface_pass",
                           "minecraft:biome_filter": [{"test": "has_biome_tag", "operator": "==", "value": "apocalypse_blight"}]},
            "distribution": {"iterations": 8, "coordinate_eval_order": "zxy",
                             "x": {"distribution": "uniform", "extent": [0, 16]},
                             "y": "query.heightmap(variable.worldx, variable.worldz)",
                             "z": {"distribution": "uniform", "extent": [0, 16]}},
        }})
    REG.add_bp(f"features/{NS}/aether_cluster_feature.json", {
        "format_version": FEATURE_FMT,
        "minecraft:single_block_feature": {
            "description": {"identifier": ident("aether_cluster_feature")},
            "places_block": ident("aether_cluster"),
            "enforce_placement_rules": True,
            "enforce_survivability_rules": True,
            "may_attach_to": {"bottom": [ident("blighted_grass"), ident("blighted_soil"), "minecraft:stone"]},
        }})
    REG.add_bp(f"feature_rules/{NS}/aether_cluster_rule.json", {
        "format_version": FEATURE_FMT,
        "minecraft:feature_rules": {
            "description": {"identifier": ident("aether_cluster_rule"), "places_feature": ident("aether_cluster_feature")},
            "conditions": {"placement_pass": "surface_pass",
                           "minecraft:biome_filter": [{"test": "has_biome_tag", "operator": "==", "value": "apocalypse_blight"}]},
            "distribution": {"iterations": 1, "scatter_chance": {"numerator": 1, "denominator": 3},
                             "coordinate_eval_order": "zxy",
                             "x": {"distribution": "uniform", "extent": [0, 16]},
                             "y": "query.heightmap(variable.worldx, variable.worldz)",
                             "z": {"distribution": "uniform", "extent": [0, 16]}},
        }})


# ================================================================================================
# fogs (distance fog for every renderer + volumetric for Vibrant Visuals)
# ================================================================================================

def _fog(fid: str, color: str, start: float, end: float, density: float, scatter: list, absorb: list):
    return {
        "format_version": "1.21.90",
        "minecraft:fog_settings": {
            "description": {"identifier": f"{NS}:{fid}"},
            "distance": {
                "air": {"fog_start": start, "fog_end": end, "fog_color": color, "render_distance_type": "fixed"},
                "weather": {"fog_start": start * 0.7, "fog_end": end * 0.75, "fog_color": color, "render_distance_type": "fixed"},
            },
            "volumetric": {
                "density": {"air": {"max_density": density, "zero_density_height": 140.0, "max_density_height": 62.0}},
                "media_coefficients": {"air": {"scattering": scatter, "absorption": absorb}},
                "henyey_greenstein_g": {"air": {"henyey_greenstein_g": 0.6}},
            },
        },
    }


FOGS = {
    "fog_blight": ("#3b3046", 12.0, 110.0, 0.12, [0.05, 0.06, 0.04], [0.01, 0.0, 0.02]),
    "fog_blood_moon": ("#4a0b14", 6.0, 72.0, 0.22, [0.09, 0.01, 0.015], [0.0, 0.03, 0.03]),
    "fog_void_storm": ("#1c1032", 4.0, 56.0, 0.28, [0.04, 0.02, 0.09], [0.02, 0.03, 0.0]),
    "fog_eclipse": ("#0b0a10", 2.0, 44.0, 0.3, [0.02, 0.02, 0.025], [0.03, 0.03, 0.02]),
    "fog_fracture": ("#123a3e", 8.0, 80.0, 0.18, [0.02, 0.07, 0.08], [0.02, 0.0, 0.0]),
    "fog_expanse": ("#0a0716", 24.0, 180.0, 0.08, [0.03, 0.025, 0.07], [0.0, 0.01, 0.0]),
    "fog_awakening": ("#4a3a1c", 10.0, 96.0, 0.14, [0.07, 0.055, 0.025], [0.0, 0.01, 0.03]),
}


def fogs():
    for fid, args in FOGS.items():
        REG.add_rp(f"fogs/{NS}_{fid}.json", _fog(fid, *args))
        REG.ts("fogs", fid.upper(), f"{NS}:{fid}")


# ================================================================================================
# structures (.mcstructure written by tools/lib/mcstructure.py)
# ================================================================================================
KEY = {
    "R": (ident("runestone_bricks"), {}), "C": (ident("chiseled_runestone"), {}), "E": (ident("engine_cache"), {}),
    "A": (ident("aether_crystal_block"), {}), "a": (ident("aether_cluster"), {}), "S": (ident("shattered_stone"), {}),
    "M": (ident("void_moss"), {}), "G": (ident("null_gate"), {}), "b": ("minecraft:stone_bricks", {}),
    "m": ("minecraft:mossy_stone_bricks", {}), "k": ("minecraft:cracked_stone_bricks", {}),
    "c": ("minecraft:cobblestone", {}), ".": ("minecraft:air", {}),
}


def _structure(name: str, layers: list[list[str]]):
    """layers bottom->top; rows north->south; chars west->east. Space = structure void."""
    sy = len(layers)
    sz = max(len(l) for l in layers)
    sx = max(len(r) for l in layers for r in l)
    cells = {}
    for y, layer in enumerate(layers):
        for z, row in enumerate(layer):
            for x, ch in enumerate(row):
                if ch != " ":
                    cells[(x, y, z)] = KEY[ch]
    REG.bp_bin[f"structures/{NS}/{name}.mcstructure"] = write_structure((sx, sy, sz), cells)
    REG.ts("structures", name.upper(), f"{NS}:{name}")


def structures():
    _structure("ancient_ruin_a", [
        ["bRRmRRRkb", "R.......R", "m.......m", "R.......R", "R...E...R", "k.......k", "R.......R", "m.......R", "bRRkRRmRb"],
        ["C   R   C", "    .    ", "    .    ", "  a . a  ", "R...E...R", "  a . a  ", "         ", "         ", "C       C"],
        ["R       R", "         ", "         ", "         ", "         ", "         ", "         ", "         ", "R       k"],
        ["C       C", "         ", "         ", "         ", "         ", "         ", "         ", "         ", "        "],
        ["A        ", "         ", "         ", "         ", "         ", "         ", "         ", "         ", "        A"],
    ])
    _structure("ancient_ruin_b", [
        ["ccRRRRRRRcc", "c.........c", "R....E....R", "c.........c", "ccRRmRRkRcc"],
        ["R    .    R", "           ", "a         a", "           ", "R         R"],
        ["R         R", "           ", "           ", "           ", "k         R"],
        ["C         C", "           ", "           ", "           ", "R         C"],
        ["RRRkRRRmRRR", "           ", "           ", "           ", "           "],
        ["  C  A  C  ", "           ", "           ", "           ", "           "],
    ])
    _structure("nexus_shrine", [
        ["  SSSSSSSSS  ", " SSSSSSSSSSS ", "SSSSSRRRSSSSS", "SSSRRRRRRRSSS", "SSSRRRRRRRSSS", "SSRRRRRRRRRSS",
         "SSRRRRRRRRRSS", "SSRRRRRRRRRSS", "SSSRRRRRRRSSS", "SSSRRRRRRRSSS", "SSSSSRRRSSSSS", " SSSSSSSSSSS ", "  SSSSSSSSS  "],
        ["  MMMMMMMMM  ", " MCM.....MCM ", "MCM.......MCM", "MM.........MM", "M...........M", "M...........M",
         "M...........M", "M...........M", "M...........M", "MM.........MM", "MCM.......MCM", " MCM.....MCM ", "  MMMMMMMMM  "],
        ["             ", "  A       A  ", " A         A ", "             ", "             ", "             ",
         "             ", "             ", "             ", "             ", " A         A ", "  A       A  ", "             "],
        ["             ", "  C       C  ", "             ", "             ", "             ", "             ",
         "             ", "             ", "             ", "             ", "             ", "  C       C  ", "             "],
        ["             ", "  a       a  ", "             ", "             ", "             ", "             ",
         "             ", "             ", "             ", "             ", "             ", "  a       a  ", "             "],
    ])
    _structure("colossus_altar", [
        ["RRRRRRRRR", "RCRRRRRCR", "RRRRRRRRR", "RRRRRRRRR", "RRRRRRRRR", "RRRRRRRRR", "RRRRRRRRR", "RCRRRRRCR", "RRRRRRRRR"],
        ["A       A", "         ", "   RRR   ", "   RRR   ", "   RRR   ", "   RRR   ", "   RRR   ", "         ", "A       A"],
        ["C       C", "         ", "         ", "         ", "    G    ", "         ", "         ", "         ", "C       C"],
        ["a       a", "         ", "         ", "         ", "         ", "         ", "         ", "         ", "a       a"],
    ])
    # surface ruins in the overworld (rare)
    for name, rule_chance in (("ancient_ruin_a", 90), ("ancient_ruin_b", 110)):
        REG.add_bp(f"features/{NS}/{name}_feature.json", {
            "format_version": "1.26.30",
            "minecraft:structure_template_feature": {
                "description": {"identifier": ident(f"{name}_feature")},
                "structure_name": ident(name),
                "adjustment_radius": 4,
                "facing_direction": "random",
                "constraints": {"grounded": {}, "unburied": {},
                                "block_intersection": {"block_allowlist": [
                                    "minecraft:air", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
                                    "minecraft:large_fern", "minecraft:dandelion", "minecraft:poppy", "minecraft:snow_layer",
                                    "minecraft:deadbush", ident("blight_sprout")]}},
            }})
        REG.add_bp(f"feature_rules/{NS}/{name}_rule.json", {
            "format_version": FEATURE_FMT,
            "minecraft:feature_rules": {
                "description": {"identifier": ident(f"{name}_rule"), "places_feature": ident(f"{name}_feature")},
                "conditions": {"placement_pass": "surface_pass",
                               "minecraft:biome_filter": [
                                   {"test": "has_biome_tag", "operator": "==", "value": "overworld"},
                                   {"any_of": [{"test": "has_biome_tag", "value": "forest"},
                                               {"test": "has_biome_tag", "value": "plains"},
                                               {"test": "has_biome_tag", "value": "taiga"},
                                               {"test": "has_biome_tag", "value": "savanna"},
                                               {"test": "has_biome_tag", "value": "desert"},
                                               {"test": "has_biome_tag", "value": "apocalypse_blight"}]}]},
                "distribution": {"iterations": 1, "scatter_chance": {"numerator": 1, "denominator": rule_chance},
                                 "coordinate_eval_order": "zxy",
                                 "x": {"distribution": "uniform", "extent": [0, 16]},
                                 "y": "query.heightmap(variable.worldx, variable.worldz)",
                                 "z": {"distribution": "uniform", "extent": [0, 16]}},
            }})


def build():
    biome()
    fogs()
    structures()
