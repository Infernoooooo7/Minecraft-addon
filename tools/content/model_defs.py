"""Original entity models for APOCALYPSE ENGINE (geometry + paint specs).

Each builder returns a geo.Model. Units: 16 = one block, entity faces north (-Z), feet at y=0.
"""
from __future__ import annotations

from tools.lib import geo
from tools.lib.geo import combine, emblem, eyes, mouth

# ------------------------------------------------------------------------------------------------
# shared material presets
# ------------------------------------------------------------------------------------------------

BONE = {"kind": "bone", "ops": [{"op": "cracks", "points": 4, "width": 0.04}]}
BONE_DARK = {"kind": "bone", "palette": [(0.0, "#4a4238"), (0.5, "#8c8170"), (1.0, "#b9ae96")],
             "ops": [{"op": "cracks", "points": 3, "width": 0.05}]}
ROYAL_CLOTH = {"kind": "cloth", "palette": [(0.0, "#0e0718"), (0.55, "#2c1650"), (1.0, "#53308c")],
               "ops": [{"op": "rim", "color": "#c9a24a", "width": 1, "metal": 1.0}]}
ROYAL_CLOTH_RUNES = {"kind": "cloth", "palette": [(0.0, "#0e0718"), (0.55, "#2c1650"), (1.0, "#53308c")],
                     "ops": [{"op": "rim", "color": "#c9a24a", "width": 1, "metal": 1.0},
                             {"op": "runes", "color": "#b98cff", "size": 3, "faces": ["north", "south"]}]}
CROWN_BRONZE = {"kind": "bronze", "ops": [{"op": "rim", "color": "#ffe08a", "width": 1}]}
SPECTRAL = {"kind": "crystal", "palette": [(0.0, "#1b0d3a"), (0.5, "#6d4bd8"), (0.85, "#c7b3ff"), (1.0, "#ffffff")]}
SOUL_GLASS = {"kind": "crystal", "palette": [(0.0, "#08303a"), (0.5, "#25c9e0"), (1.0, "#e8ffff")]}


def hollow_king() -> geo.Model:
    """THE HOLLOW KING — a hunched skeletal monarch in a tattered royal robe, ~4.5 blocks tall."""
    m = geo.Model("geometry.apocalypse.hollow_king", 128, 128, bounds_w=4, bounds_h=5.5, bounds_off=(0, 2.6, 0))
    bone = {"kind": "bone", "palette": [(0.0, "#1f1b16"), (0.45, "#5b5245"), (0.8, "#8f8571"), (1.0, "#b8ad94")],
            "ops": [{"op": "cracks", "points": 4, "width": 0.05},
                    {"op": "gradient", "color": "#0c0a08", "amount": 0.45}]}
    bone_dark = {"kind": "bone", "palette": [(0.0, "#141110"), (0.5, "#3d362e"), (1.0, "#6e6555")],
                 "ops": [{"op": "cracks", "points": 3, "width": 0.06}]}
    ribs = {"kind": "bone", "palette": [(0.0, "#1f1b16"), (0.5, "#6a6050"), (1.0, "#a99e86")],
            "ops": [{"op": "stripes", "color": "#07050a", "period": 3, "thickness": 1, "amount": 0.85}]}
    robe = {"kind": "cloth", "palette": [(0.0, "#07040c"), (0.6, "#24123f"), (1.0, "#43256f")],
            "ops": [{"op": "rim", "color": "#a8822f", "width": 1, "metal": 1.0},
                    {"op": "gradient", "color": "#030205", "amount": 0.5}]}
    robe_runes = {"kind": "cloth", "palette": [(0.0, "#07040c"), (0.6, "#24123f"), (1.0, "#43256f")],
                  "ops": [{"op": "rim", "color": "#a8822f", "width": 1, "metal": 1.0},
                          {"op": "runes", "color": "#a77bff", "size": 4, "faces": ["north", "south", "east", "west"]},
                          {"op": "gradient", "color": "#030205", "amount": 0.35}]}
    crown = {"kind": "bronze", "palette": [(0.0, "#1e1206"), (0.5, "#6b4a1b"), (0.85, "#b78a3a"), (1.0, "#f0cf7a")],
             "ops": [{"op": "rim", "color": "#ffe39a", "width": 1}]}
    spectral = {"kind": "crystal", "palette": [(0.0, "#140a2e"), (0.5, "#5f3fd0"), (0.85, "#b9a2ff"), (1.0, "#ffffff")]}

    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 26, 0), parent="root", rotation=(8, 0, 0))
    body.cube((-6, 24, -4), (12, 6, 8), bone_dark)                                     # pelvis
    body.cube((-1.5, 30, 0), (3, 9, 3), bone)                                          # spine
    body.cube((-7.5, 38, -4.5), (15, 13, 9), ribs,
              deco={"north": emblem("#b98cff", "core", 0.5)})                          # ribcage + soul core
    body.cube((-9.5, 14, 4), (19, 37, 1), robe_runes)                                  # cloak back
    body.cube((-10.5, 16, -2), (1, 34, 6), robe)                                       # cloak right drape
    body.cube((9.5, 16, -2), (1, 34, 6), robe)                                         # cloak left drape
    body.cube((-12, 47, -5), (6, 5, 10), crown)                                        # right pauldron
    body.cube((6, 47, -5), (6, 5, 10), crown)                                          # left pauldron
    body.cube((-10, 45, 1), (20, 6, 4), robe)                                          # mantle collar
    body.cube((-7, 12, -5), (14, 14, 10), robe_runes)                                  # robe skirt
    body.locators["core"] = (0, 44, -5)

    head = m.bone("head", (0, 51, -1), parent="body")
    head.cube((-4, 52, -6), (8, 9, 8), bone,
              deco={"north": combine(eyes("#7ff6ff", spacing=0.46, y=0.42, size=0.1, socket="#020104"),
                                     mouth(y=0.86, width=0.62, teeth="#7d735f"))})
    head.cube((-3.5, 49, -6.5), (7, 3, 6), bone_dark, pivot=(0, 52, -1), rotation=(18, 0, 0))   # hanging jaw
    head.cube((-5, 60, -6.5), (10, 3, 10), crown)                                      # crown band
    spikes = [(-4.5, -6.5, 7), (-1, -7, 10), (2.5, -6.5, 7), (-4.5, 1.5, 6), (2.5, 1.5, 6), (-1, 2, 8)]
    for i, (x, z, hgt) in enumerate(spikes):
        head.cube((x, 62, z), (2, hgt, 2), crown, pivot=(x + 1, 62, z + 1), rotation=(-14 if z < 0 else 14, 0, 0))
    head.cube((-1, 64, -7.3), (2, 2, 1), spectral)                                     # crown jewel
    head.locators["crown"] = (0, 72, -1)

    halo = m.bone("halo", (0, 66, -1), parent="head")
    for i, (x, z) in enumerate([(-11, -2), (9, -2), (-1, 8), (-1, -12)]):
        halo.cube((x, 64, z), (2, 6, 2), spectral, pivot=(x + 1, 67, z + 1), rotation=(0, 45, 25))

    r_arm = m.bone("right_arm", (-10, 49, -1), parent="body")
    r_arm.cube((-12.5, 30, -2.5), (4, 19, 4), bone)
    r_arm.cube((-13.5, 25, -3.5), (6, 5, 6), bone_dark)                                # hand
    for dx in (-13.5, -11.5, -9.5):
        r_arm.cube((dx, 21, -3.5), (1, 4, 2), bone_dark)                               # claws
    sword = m.bone("sword", (-10.5, 27, -1), parent="right_arm")
    sword.cube((-12, 24, -2.5), (3, 5, 3), crown)                                      # grip
    sword.cube((-14.5, 22, -2.5), (8, 2, 3), crown)                                    # crossguard
    sword.cube((-11.5, -6, -1.5), (2, 28, 1), spectral)                                # blade pointing down
    sword.cube((-12, -6, -1.5), (3, 2, 1), spectral)                                   # tip flare
    sword.locators["blade_tip"] = (-10.5, -6, -1)

    l_arm = m.bone("left_arm", (10, 49, -1), parent="body")
    l_arm.cube((8.5, 30, -2.5), (4, 19, 4), bone)
    l_arm.cube((7.5, 25, -3.5), (6, 5, 6), bone_dark)
    for dx in (7.5, 9.5, 11.5):
        l_arm.cube((dx, 21, -3.5), (1, 4, 2), bone_dark)
    l_arm.locators["hand_l"] = (10.5, 25, -1)

    r_leg = m.bone("right_leg", (-3, 24, 0), parent="root")
    r_leg.cube((-5, 3, -2), (4, 22, 4), bone)
    r_leg.cube((-6, 0, -5), (6, 3, 7), bone_dark)
    l_leg = m.bone("left_leg", (3, 24, 0), parent="root")
    l_leg.cube((1, 3, -2), (4, 22, 4), bone)
    l_leg.cube((0, 0, -5), (6, 3, 7), bone_dark)
    m.pack_uv()
    return m


# ================================================================================================
# THE STAR EATER — flying cosmic leviathan
# ================================================================================================
VOID_SKIN = {"kind": "void", "palette": [(0.0, "#04020a"), (0.5, "#160c2c"), (0.8, "#3a2370"), (1.0, "#9a7cff")],
             "ops": [{"op": "veins", "color": "#ffd36a", "width": 0.035, "cells": 3, "emissive": 0.9}]}
VOID_PLATE = {"kind": "chitin", "palette": [(0.0, "#05040a"), (0.5, "#1b1433"), (0.85, "#3f2f73"), (1.0, "#8f74e8")],
              "ops": [{"op": "rim", "color": "#d9a646", "width": 1}]}
STAR_GOLD = {"kind": "star"}
MEMBRANE = {"kind": "void", "palette": [(0.0, "#0a0418"), (0.6, "#2d1a5c"), (1.0, "#7b5bd6")],
            "ops": [{"op": "stripes", "color": "#ffd36a", "period": 5, "thickness": 1, "horizontal": False,
                     "glow": True, "amount": 0.7, "emissive": 0.6}]}


def star_eater() -> geo.Model:
    m = geo.Model("geometry.apocalypse.star_eater", 128, 128, bounds_w=8, bounds_h=5, bounds_off=(0, 1.5, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 20, 0), parent="root")
    body.cube((-7, 13, -8), (14, 14, 12), VOID_SKIN)
    body.locators["core"] = (0, 20, 0)
    head = m.bone("head", (0, 20, -8), parent="body")
    head.cube((-8, 12, -24), (16, 16, 16), VOID_PLATE,
              deco={"north": combine(emblem("#ffcf5a", "core", 0.62), mouth(y=0.5, width=0.8, teeth="#f3e3b5", glow="#ff7a1a")),
                    "east": eyes("#ffe27a", spacing=0.3, y=0.35, size=0.07, count=3),
                    "west": eyes("#ffe27a", spacing=0.3, y=0.35, size=0.07, count=3)})
    for i, x in enumerate((-4, -1, 2)):
        head.cube((x, 28, -20 + i * 3), (2, 6 - i, 2), STAR_GOLD, pivot=(x + 1, 28, -19 + i * 3), rotation=(-25, 0, 0))
    head.locators["maw"] = (0, 20, -26)
    jaw_l = m.bone("jaw_l", (6, 16, -22), parent="head")
    jaw_l.cube((6, 10, -32), (4, 6, 10), VOID_PLATE, pivot=(8, 13, -22), rotation=(0, -12, 0))
    jaw_r = m.bone("jaw_r", (-6, 16, -22), parent="head")
    jaw_r.cube((-10, 10, -32), (4, 6, 10), VOID_PLATE, pivot=(-8, 13, -22), rotation=(0, 12, 0))
    prev = "body"
    segs = [((-6, 14, 4), (12, 12, 12)), ((-5, 15, 16), (10, 10, 12)), ((-3.5, 16.5, 28), (7, 7, 12)),
            ((-2, 18, 40), (4, 4, 10))]
    for i, (o, s) in enumerate(segs):
        b = m.bone(f"tail{i}", (0, 20, o[2]), parent=prev)
        b.cube(o, s, VOID_SKIN if i % 2 == 0 else VOID_PLATE)
        prev = b.name
    tail_fin = m.bone("tail_fin", (0, 20, 50), parent=prev)
    tail_fin.cube((-8, 19.5, 48), (16, 1, 10), MEMBRANE)
    fin_l = m.bone("fin_l", (7, 22, -2), parent="body")
    fin_l.cube((7, 22, -8), (24, 1, 14), MEMBRANE)
    fin_r = m.bone("fin_r", (-7, 22, -2), parent="body")
    fin_r.cube((-31, 22, -8), (24, 1, 14), MEMBRANE)
    fin_l2 = m.bone("fin_l2", (6, 21, 10), parent="tail0")
    fin_l2.cube((6, 21, 6), (14, 1, 9), MEMBRANE)
    fin_r2 = m.bone("fin_r2", (-6, 21, 10), parent="tail0")
    fin_r2.cube((-20, 21, 6), (14, 1, 9), MEMBRANE)
    tend = m.bone("tendrils", (0, 13, -6), parent="body")
    for x in (-5, -1, 3):
        tend.cube((x, 0, -6), (2, 13, 2), VOID_PLATE)
    m.pack_uv()
    return m


# ================================================================================================
# THE ROOT TITAN — colossal blighted treant
# ================================================================================================
BARK = {"kind": "bark", "palette": [(0.0, "#100a06"), (0.45, "#2e2013"), (0.8, "#4c3620"), (1.0, "#6a4f30")],
        "ops": [{"op": "veins", "color": "#9cff5a", "width": 0.03, "cells": 2, "emissive": 0.7}]}
BARK_PLAIN = {"kind": "bark", "palette": [(0.0, "#100a06"), (0.45, "#2e2013"), (0.8, "#4c3620"), (1.0, "#6a4f30")]}
MOSS = {"kind": "moss"}
CANOPY = {"kind": "leaf", "palette": [(0.0, "#08140a"), (0.5, "#1f3d17"), (0.8, "#3f6b22"), (1.0, "#8fd14a")],
          "ops": [{"op": "spots", "color": "#c8ff7a", "count": 5, "radius": 0.8, "emissive": 0.8}]}
STONE_FIST = {"kind": "stone", "palette": [(0.0, "#16140f"), (0.5, "#3b382f"), (1.0, "#69645a")],
              "ops": [{"op": "cracks", "glow": True, "color": "#9cff5a", "points": 4, "width": 0.04, "emissive": 0.7}]}


def root_titan() -> geo.Model:
    m = geo.Model("geometry.apocalypse.root_titan", 128, 128, bounds_w=7, bounds_h=7, bounds_off=(0, 3, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 36, 0), parent="root")
    body.cube((-16, 34, -10), (32, 32, 20), BARK, deco={"north": emblem("#b6ff5c", "core", 0.45)})
    body.cube((-21, 60, -11), (12, 9, 22), MOSS)
    body.cube((9, 60, -11), (12, 9, 22), MOSS)
    body.cube((-18, 64, 0), (36, 18, 14), CANOPY)
    body.cube((-12, 80, -2), (24, 10, 12), CANOPY)
    body.locators["heart"] = (0, 50, -11)
    head = m.bone("head", (0, 66, -6), parent="body")
    head.cube((-8, 66, -16), (16, 15, 14), BARK_PLAIN,
              deco={"north": combine(eyes("#c8ff5a", spacing=0.45, y=0.38, size=0.1, slit=True), mouth(y=0.78, width=0.55, teeth="#3b2a18", glow="#6dff3a"))})
    for x, rz in ((-10, 25), (8, -25)):
        head.cube((x, 80, -10), (2, 12, 2), BARK_PLAIN, pivot=(x + 1, 80, -9), rotation=(0, 0, rz))
        head.cube((x + (-3 if x < 0 else 3), 88, -10), (2, 7, 2), BARK_PLAIN, pivot=(x + 1, 88, -9), rotation=(0, 0, rz * 2))
    r_arm = m.bone("right_arm", (-18, 62, 0), parent="body")
    r_arm.cube((-29, 28, -6), (11, 34, 12), BARK)
    r_arm.cube((-31, 16, -9), (15, 12, 18), STONE_FIST)
    l_arm = m.bone("left_arm", (18, 62, 0), parent="body")
    l_arm.cube((18, 28, -6), (11, 34, 12), BARK)
    l_arm.cube((16, 16, -9), (15, 12, 18), STONE_FIST)
    r_leg = m.bone("right_leg", (-8, 34, 0), parent="root")
    r_leg.cube((-14, 4, -6), (11, 30, 12), BARK_PLAIN)
    r_leg.cube((-17, 0, -12), (16, 4, 18), BARK)
    l_leg = m.bone("left_leg", (8, 34, 0), parent="root")
    l_leg.cube((3, 4, -6), (11, 30, 12), BARK_PLAIN)
    l_leg.cube((1, 0, -12), (16, 4, 18), BARK)
    m.pack_uv()
    return m


# ================================================================================================
# THE NULL COLOSSUS — ancient gravity construct (endgame)
# ================================================================================================
NULL_STONE = {"kind": "chitin", "palette": [(0.0, "#020205"), (0.5, "#0e0d18"), (0.85, "#24223a"), (1.0, "#4a4670")],
              "ops": [{"op": "cracks", "glow": True, "color": "#3ff3ff", "points": 5, "width": 0.035, "emissive": 0.9}]}
NULL_BRONZE = {"kind": "bronze", "palette": [(0.0, "#140c05"), (0.5, "#4f3515"), (0.85, "#93692c"), (1.0, "#d6ad5c")],
               "ops": [{"op": "rim", "color": "#3ff3ff", "width": 1, "glow": True, "emissive": 0.6},
                       {"op": "runes", "color": "#3ff3ff", "size": 4, "faces": ["north"]}]}
NULL_CORE = {"kind": "crystal", "palette": [(0.0, "#1a0533"), (0.5, "#8a3dff"), (0.85, "#e0c4ff"), (1.0, "#ffffff")]}
ORBITAL = {"kind": "stone", "palette": [(0.0, "#05050a"), (0.5, "#1c1b2b"), (1.0, "#3d3a5c")],
           "ops": [{"op": "veins", "color": "#3ff3ff", "width": 0.06, "cells": 2}]}


def null_colossus() -> geo.Model:
    m = geo.Model("geometry.apocalypse.null_colossus", 128, 128, bounds_w=9, bounds_h=9, bounds_off=(0, 4, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 46, 0), parent="root")
    body.cube((-14, 38, -9), (28, 10, 18), NULL_STONE)                                 # pelvis
    body.cube((-20, 48, -12), (40, 36, 24), NULL_STONE)                                # torso
    body.cube((-24, 78, -10), (12, 10, 20), NULL_BRONZE)                               # shoulder r
    body.cube((12, 78, -10), (12, 10, 20), NULL_BRONZE)                                # shoulder l
    for i, x in enumerate((-10, -2, 6)):
        body.cube((x, 84, 6), (4, 14 - i * 2 if i != 1 else 18, 3), NULL_CORE, pivot=(x + 2, 84, 7), rotation=(18, 0, 0))
    core = m.bone("core", (0, 66, -12), parent="body")
    core.cube((-7, 58, -14), (14, 16, 3), NULL_CORE, deco={"north": emblem("#ffffff", "diamond", 0.7)})
    core.locators["core"] = (0, 66, -15)
    vent_r = m.bone("vent_r", (-18, 66, -13), parent="body")
    vent_r.cube((-18, 54, -16), (17, 26, 3), NULL_BRONZE)
    vent_l = m.bone("vent_l", (18, 66, -13), parent="body")
    vent_l.cube((1, 54, -16), (17, 26, 3), NULL_BRONZE)
    head = m.bone("head", (0, 84, -2), parent="body")
    head.cube((-7, 84, -9), (14, 12, 14), NULL_STONE, deco={"north": eyes("#3ff3ff", count=1, size=0.22, y=0.48)})
    head.cube((-9, 92, -6), (18, 2, 8), NULL_BRONZE)
    head.locators["eye"] = (0, 90, -10)
    r_arm = m.bone("right_arm", (-26, 80, 0), parent="body")
    r_arm.cube((-36, 40, -8), (14, 40, 16), NULL_STONE)
    r_arm.cube((-38, 26, -10), (18, 14, 20), NULL_BRONZE)
    l_arm = m.bone("left_arm", (26, 80, 0), parent="body")
    l_arm.cube((22, 40, -8), (14, 40, 16), NULL_STONE)
    l_arm.cube((20, 26, -10), (18, 14, 20), NULL_BRONZE)
    r_leg = m.bone("right_leg", (-9, 40, 0), parent="root")
    r_leg.cube((-17, 4, -8), (13, 36, 16), NULL_STONE)
    r_leg.cube((-19, 0, -12), (17, 4, 22), NULL_BRONZE)
    l_leg = m.bone("left_leg", (9, 40, 0), parent="root")
    l_leg.cube((4, 4, -8), (13, 36, 16), NULL_STONE)
    l_leg.cube((2, 0, -12), (17, 4, 22), NULL_BRONZE)
    orb = m.bone("orbitals", (0, 72, 0), parent="root")
    for x, z in ((-40, 0), (34, 0), (0, -38), (0, 32)):
        orb.cube((x, 69, z), (6, 6, 6), ORBITAL)
    m.pack_uv()
    return m


# ================================================================================================
# HOLLOW SHADE — floating spectral wraith (variants via texture)
# ================================================================================================
SHADE_ROBE = {"kind": "cloth", "palette": [(0.0, "#030206"), (0.6, "#140b24"), (1.0, "#2d1a52")],
              "ops": [{"op": "runes", "color": "#a77bff", "size": 3, "faces": ["north"]},
                      {"op": "tatter", "depth": 0.35}]}
SHADE_BONE = {"kind": "bone", "palette": [(0.0, "#2a2620"), (0.6, "#7a7262"), (1.0, "#b3a990")]}
SHADE_HOOD = {"kind": "cloth", "palette": [(0.0, "#030206"), (0.6, "#140b24"), (1.0, "#2d1a52")]}


def hollow_shade() -> geo.Model:
    m = geo.Model("geometry.apocalypse.hollow_shade", 64, 64, bounds_w=2, bounds_h=3, bounds_off=(0, 1.3, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 20, 0), parent="root")
    body.cube((-5, 4, -3), (10, 20, 6), SHADE_ROBE)
    body.cube((-6, 20, -3.5), (12, 6, 7), SHADE_HOOD)
    body.locators["chest"] = (0, 22, -4)
    head = m.bone("head", (0, 26, 0), parent="body")
    head.cube((-4, 26, -4.5), (8, 8, 8), SHADE_HOOD,
              deco={"north": combine(eyes("#7ff6ff", spacing=0.4, y=0.55, size=0.12, socket="#000000"))})
    head.cube((-3, 27, -4.8), (6, 5, 1), SHADE_BONE, deco={"north": eyes("#7ff6ff", spacing=0.5, y=0.35, size=0.16)})
    for side, x in (("right_arm", -7), ("left_arm", 5)):
        a = m.bone(side, (x + 1, 24, 0), parent="body")
        a.cube((x, 12, -1), (2, 12, 2), SHADE_BONE)
        a.cube((x - 0.5, 9, -1.5), (3, 3, 3), SHADE_BONE)
    m.pack_uv()
    return m


# ================================================================================================
# VOID CRAWLER — eight-legged corrupted arachnid
# ================================================================================================
CRAWLER_SHELL = {"kind": "chitin", "ops": [{"op": "runes", "color": "#b98cff", "size": 3, "faces": ["up"]}]}
CRAWLER_LEG = {"kind": "chitin", "palette": [(0.0, "#040308"), (0.6, "#16112a"), (1.0, "#3a2d66")]}


def void_crawler() -> geo.Model:
    m = geo.Model("geometry.apocalypse.void_crawler", 64, 64, bounds_w=3, bounds_h=2, bounds_off=(0, 0.6, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 8, 0), parent="root")
    body.cube((-4, 5, -3), (8, 6, 7), CRAWLER_LEG)
    abd = m.bone("abdomen", (0, 9, 4), parent="body")
    abd.cube((-6, 5, 4), (12, 9, 12), CRAWLER_SHELL, deco={"south": emblem("#b98cff", "eye", 0.6)})
    head = m.bone("head", (0, 8, -3), parent="body")
    head.cube((-4, 4, -10), (8, 7, 7), CRAWLER_LEG,
              deco={"north": combine(eyes("#d6a8ff", spacing=0.5, y=0.3, size=0.09, count=3), eyes("#ff5ad6", spacing=0.3, y=0.55, size=0.11))})
    head.cube((-3, 2, -12), (2, 4, 2), CRAWLER_LEG)
    head.cube((1, 2, -12), (2, 4, 2), CRAWLER_LEG)
    for i in range(4):
        z = -3 + i * 2.5
        for side, sx in (("r", -1), ("l", 1)):
            leg = m.bone(f"leg_{side}{i}", (sx * 4, 9, z), parent="body")
            femur_x = 4 if sx > 0 else -12
            leg.cube((femur_x, 9, z - 1), (8, 2, 2), CRAWLER_LEG)                      # femur (outwards)
            tibia_x = 11 if sx > 0 else -13
            leg.cube((tibia_x, 0, z - 1), (2, 10, 2), CRAWLER_LEG)                     # tibia (down to ground)
    m.pack_uv()
    return m


# ================================================================================================
# ASTRAL MITE — small star-shelled bug born from meteors
# ================================================================================================
def astral_mite() -> geo.Model:
    m = geo.Model("geometry.apocalypse.astral_mite", 64, 64, bounds_w=1.5, bounds_h=1.2, bounds_off=(0, 0.4, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 4, 0), parent="root")
    body.cube((-3, 2, -3), (6, 4, 7), {"kind": "chitin", "palette": [(0, "#0a0603"), (0.6, "#3a2608"), (1, "#8a5a14")]},
              deco={"north": eyes("#fff2a0", spacing=0.45, y=0.4, size=0.13)})
    shell = m.bone("shell", (0, 6, 0), parent="body")
    shell.cube((-4, 5, -2), (8, 4, 8), {"kind": "crystal", "palette": [(0, "#3a2002"), (0.5, "#d99a28"), (0.85, "#ffe58a"), (1, "#ffffff")]})
    shell.cube((-1, 9, 1), (2, 3, 2), {"kind": "crystal", "palette": [(0, "#3a2002"), (0.5, "#d99a28"), (1, "#ffffff")]})
    for i in range(3):
        for side, sx in (("r", -1), ("l", 1)):
            leg = m.bone(f"leg_{side}{i}", (sx * 3, 3, -1.5 + i * 2.5), parent="body")
            x0 = 3 if sx > 0 else -6
            leg.cube((x0, 2, -2 + i * 2.5), (3, 1, 1), {"kind": "chitin"})
            leg.cube((x0 + (2 if sx > 0 else 0), 0, -2 + i * 2.5), (1, 2, 1), {"kind": "chitin"})
    m.pack_uv()
    return m


# ================================================================================================
# THORNLING — small blighted treant
# ================================================================================================
def thornling() -> geo.Model:
    m = geo.Model("geometry.apocalypse.thornling", 64, 64, bounds_w=1.5, bounds_h=2, bounds_off=(0, 0.8, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 8, 0), parent="root")
    body.cube((-3.5, 6, -2.5), (7, 9, 5), BARK)
    head = m.bone("head", (0, 15, 0), parent="body")
    head.cube((-4, 15, -4), (8, 7, 8), BARK_PLAIN, deco={"north": eyes("#c8ff5a", spacing=0.45, y=0.5, size=0.11, slit=True)})
    head.cube((-5, 21, -5), (10, 4, 10), CANOPY)
    head.cube((-1, 25, -1), (2, 4, 2), BARK_PLAIN)
    for side, x in (("right_arm", -5.5), ("left_arm", 3.5)):
        a = m.bone(side, (x + 1, 14, 0), parent="body")
        a.cube((x, 6, -1), (2, 8, 2), BARK_PLAIN)
        a.cube((x - 0.5, 4, -1.5), (3, 2, 3), {"kind": "leaf"})
    for side, x in (("right_leg", -3), ("left_leg", 0.5)):
        l = m.bone(side, (x + 1.25, 6, 0), parent="root")
        l.cube((x, 0, -1.5), (2.5 if False else 3, 6, 3), BARK_PLAIN)
    m.pack_uv()
    return m


# ================================================================================================
# RIFT SENTINEL — floating guardian construct of the Shattered Expanse
# ================================================================================================
def rift_sentinel() -> geo.Model:
    m = geo.Model("geometry.apocalypse.rift_sentinel", 64, 64, bounds_w=3, bounds_h=3, bounds_off=(0, 1.2, 0))
    m.bone("root", (0, 0, 0))
    body = m.bone("body", (0, 18, 0), parent="root")
    body.cube((-5, 12, -5), (10, 12, 10), NULL_STONE, pivot=(0, 18, 0), rotation=(0, 45, 0),
              deco={"north": eyes("#3ff3ff", count=1, size=0.24, y=0.5)})
    body.cube((-2, 24, -2), (4, 6, 4), NULL_CORE)
    body.cube((-2, 6, -2), (4, 6, 4), NULL_BRONZE)
    body.locators["eye"] = (0, 18, -8)
    shards = m.bone("shards", (0, 18, 0), parent="body")
    for x, z in ((-12, 0), (10, 0), (0, -12), (0, 10)):
        shards.cube((x, 16, z), (2, 5, 2), NULL_CORE, pivot=(x + 1, 18, z + 1), rotation=(20, 45, 0))
    for side, x in (("right_hand", -12), ("left_hand", 8)):
        hnd = m.bone(side, (x + 2, 14, -2), parent="body")
        hnd.cube((x, 11, -4), (4, 5, 4), NULL_BRONZE)
    m.pack_uv()
    return m


# ================================================================================================
# small entities
# ================================================================================================
def star_bolt() -> geo.Model:
    m = geo.Model("geometry.apocalypse.star_bolt", 32, 32, bounds_w=1, bounds_h=1, bounds_off=(0, 0.25, 0))
    b = m.bone("bolt", (0, 4, 0))
    b.cube((-2, 2, -2), (4, 4, 4), {"kind": "crystal", "palette": [(0, "#5a3a08"), (0.5, "#ffcf5a"), (1, "#ffffff")]})
    b.cube((-1, 3, -1), (2, 2, 6), {"kind": "crystal", "palette": [(0, "#7a4a08"), (1, "#fff2c0")]})
    m.pack_uv()
    return m


def meteor() -> geo.Model:
    m = geo.Model("geometry.apocalypse.meteor", 64, 64, bounds_w=2, bounds_h=2, bounds_off=(0, 0.5, 0))
    b = m.bone("rock", (0, 6, 0))
    b.cube((-6, 0, -6), (12, 12, 12), {"kind": "stone", "palette": [(0, "#0b0705"), (0.5, "#2a1c14"), (1, "#4f3a2c")],
                                        "ops": [{"op": "cracks", "glow": True, "color": "#ff7a1a", "points": 6, "width": 0.06}]})
    b.cube((-4, -2, -4), (8, 2, 8), {"kind": "ember"})
    b.cube((-4, 12, -4), (8, 2, 8), {"kind": "ember"})
    m.pack_uv()
    return m


def void_rift() -> geo.Model:
    m = geo.Model("geometry.apocalypse.void_rift", 64, 64, bounds_w=3, bounds_h=4, bounds_off=(0, 1.5, 0))
    b = m.bone("tear", (0, 16, 0))
    tear = {"kind": "void", "ops": [{"op": "oval", "radius": 0.92, "wobble": 0.3, "rim": 0.14, "color": "#d8a8ff"}]}
    b.cube((-10, 2, 0), (20, 30, 0), tear)
    b.cube((0, 2, -10), (0, 30, 20), tear)
    core = m.bone("core", (0, 17, 0), parent="tear")
    core.cube((-2, 15, -2), (4, 4, 4), NULL_CORE)
    m.pack_uv()
    return m


def rift_portal() -> geo.Model:
    m = geo.Model("geometry.apocalypse.rift_portal", 64, 64, bounds_w=4, bounds_h=5, bounds_off=(0, 2, 0))
    b = m.bone("gate", (0, 24, 0))
    swirl = {"kind": "void", "palette": [(0, "#020814"), (0.5, "#0c3a52"), (0.85, "#3ff3ff"), (1, "#ffffff")],
             "ops": [{"op": "oval", "radius": 0.95, "wobble": 0.12, "rim": 0.1, "color": "#9ff8ff"}]}
    b.cube((-14, 2, 0), (28, 40, 0), swirl)
    ring = m.bone("stones", (0, 24, 0), parent="gate")
    for x, y in ((-17, 6), (14, 6), (-17, 30), (14, 30), (-2, 44)):
        ring.cube((x, y, -2), (3 if x != -2 else 4, 6 if x != -2 else 3, 3), {"kind": "rune_stone", "ops": [{"op": "runes", "color": "#3ff3ff", "size": 2}]})
    m.pack_uv()
    return m


ALL_MODELS = {
    "hollow_king": hollow_king, "star_eater": star_eater, "root_titan": root_titan, "null_colossus": null_colossus,
    "hollow_shade": hollow_shade, "void_crawler": void_crawler, "astral_mite": astral_mite, "thornling": thornling,
    "rift_sentinel": rift_sentinel, "star_bolt": star_bolt, "meteor": meteor, "void_rift": void_rift,
    "rift_portal": rift_portal,
}
