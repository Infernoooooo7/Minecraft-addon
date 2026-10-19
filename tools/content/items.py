"""Items: materials, relics, weapons, armor, utilities — behavior JSON, icons, attachables, recipes."""
from __future__ import annotations

import numpy as np

from tools.content.common import (ARMOR_TEX, DENS_ARMOR, DENS_ICON, ITEM_FMT, ITEM_TEX, NS, RECIPE_FMT, ident)
from tools.content.registry import REG, TexAsset
from tools.lib import geo, icons, tex

# ------------------------------------------------------------------------------------------------
# palettes
# ------------------------------------------------------------------------------------------------
P_RIFT = [(0, "#062a33"), (0.5, "#18b4c9"), (0.85, "#7ff6ff"), (1, "#eaffff")]
P_AETHER = [(0, "#0a2f3d"), (0.45, "#2fd6e8"), (0.8, "#a8fbff"), (1, "#ffffff")]
P_SOUL = [(0, "#1a0838"), (0.5, "#7d45e8"), (0.85, "#c9a8ff"), (1, "#ffffff")]
P_ICHOR = [(0, "#0c0418"), (0.5, "#4a1a8c"), (1, "#b56bff")]
P_STAR = [(0, "#3a2002"), (0.5, "#d99a28"), (0.85, "#ffe58a"), (1, "#ffffff")]
P_BLOOD = [(0, "#2a0208"), (0.5, "#b3122c"), (0.85, "#ff5a6e"), (1, "#ffd0d6")]
P_BARK = [(0, "#1a110a"), (0.5, "#4c3620"), (1, "#7d6038")]
P_LIFE = [(0, "#0d2a08"), (0.5, "#4fbf2a"), (1, "#d4ff9a")]
P_NULL = [(0, "#020205"), (0.5, "#16142a"), (0.85, "#3a3760"), (1, "#7a74b8")]
P_NULL_GLOW = [(0, "#062a33"), (0.5, "#3ff3ff"), (1, "#ffffff")]
P_FRACTURE = [(0, "#2a0a3a"), (0.3, "#ff5ad6"), (0.6, "#5affd8"), (1, "#ffffff")]
P_ECLIPSE = [(0, "#050307"), (0.6, "#1a1426"), (1, "#3d3354")]
P_GOLD = [(0, "#3a2408"), (0.5, "#b9853d"), (0.85, "#f0cf7a"), (1, "#fff6d6")]
P_BRONZE = [(0, "#2a1606"), (0.5, "#7a4f22"), (1, "#d6a35a")]
P_STEEL = [(0, "#1e2028"), (0.5, "#5b6070"), (0.85, "#a9b0c2"), (1, "#eef2ff")]
P_CORE_V = [(0, "#1a0533"), (0.5, "#8a3dff"), (0.85, "#e0c4ff"), (1, "#ffffff")]

ITEMS: dict[str, dict] = {}


def icon_asset(name: str, painter):
    """Register an HD icon (16/32/64 px per tier) and its item_texture key."""
    REG.add_texture(TexAsset(f"{ITEM_TEX}/{name}", lambda d, p=painter, n=name: _paint_icon(p, d, n), DENS_ICON, pbr=True))
    REG.item_textures[f"{NS}_{name}"] = f"{ITEM_TEX}/{name}"


def _paint_icon(painter, density: int, name: str):
    ic = icons.Icon(density * 4 // 4, seed=sum(map(ord, name)))
    ic.d = density
    ic.s = 16 * density
    ic.cv = tex.Canvas(ic.s, ic.s)
    painter(ic)
    return ic.finish()


def item(name: str, display: str, components: dict, painter, category: str = "items", group: str | None = None,
         hover_color: str | None = None):
    comps = {
        "minecraft:icon": {"textures": {"default": f"{NS}_{name}"}},
        "minecraft:display_name": {"value": f"item.{ident(name)}.name"},
    }
    if hover_color:
        comps["minecraft:hover_text_color"] = hover_color
    comps.update(components)
    desc: dict = {"identifier": ident(name), "menu_category": {"category": category}}
    if group:
        desc["menu_category"]["group"] = group
    REG.add_bp(f"items/{NS}/{name}.json", {"format_version": ITEM_FMT, "minecraft:item": {"description": desc,
                                                                                          "components": comps}})
    REG.name(f"item.{ident(name)}.name", display)
    REG.ts("items", name.upper(), ident(name))
    icon_asset(name, painter)
    ITEMS[name] = comps


def recipe_shaped(name: str, pattern: list[str], key: dict[str, str], result: str, count: int = 1,
                  unlock: list[str] | None = None):
    REG.add_bp(f"recipes/{NS}/{name}.json", {
        "format_version": RECIPE_FMT,
        "minecraft:recipe_shaped": {
            "description": {"identifier": ident(name)},
            "tags": ["crafting_table"],
            "pattern": pattern,
            "key": {k: {"item": v} for k, v in key.items()},
            "unlock": [{"item": u} for u in (unlock or [next(iter(key.values()))])],
            "result": {"item": result, "count": count},
        }})


def recipe_shapeless(name: str, ingredients: list[str], result: str, count: int = 1, unlock: list[str] | None = None):
    REG.add_bp(f"recipes/{NS}/{name}.json", {
        "format_version": RECIPE_FMT,
        "minecraft:recipe_shapeless": {
            "description": {"identifier": ident(name)},
            "tags": ["crafting_table"],
            "ingredients": [{"item": i} for i in ingredients],
            "unlock": [{"item": u} for u in (unlock or [ingredients[0]])],
            "result": {"item": result, "count": count},
        }})


def recipe_furnace(name: str, inp: str, out: str):
    REG.add_bp(f"recipes/{NS}/{name}.json", {
        "format_version": RECIPE_FMT,
        "minecraft:recipe_furnace": {
            "description": {"identifier": ident(name)},
            "unlock": [{"item": inp}],
            "tags": ["furnace", "blast_furnace"],
            "input": inp, "output": out,
        }})


# ================================================================================================
# materials
# ================================================================================================

def materials():
    stack = {"minecraft:max_stack_size": 64}
    item("rift_shard", "Rift Shard", dict(stack), lambda ic: icons.crystal_cluster(ic, P_RIFT, 0.7))
    item("aether_crystal", "Aether Crystal", {**stack, "minecraft:rarity": "uncommon"},
         lambda ic: icons.gem(ic, P_AETHER, 0.9))
    item("soul_essence", "Soul Essence", dict(stack), lambda ic: (icons.orb(ic, P_SOUL, 0.9), ic.glyph(8, 8, 5, "#ffffff", 3)))
    item("void_ichor", "Void Ichor", dict(stack), lambda ic: icons.vial(ic, P_ICHOR, 0.7))
    item("stardust", "Stardust", dict(stack), _paint_stardust)
    item("star_metal_chunk", "Star Metal Chunk", dict(stack), _paint_chunk)
    item("star_metal_ingot", "Star Metal Ingot", {**stack, "minecraft:rarity": "uncommon"},
         lambda ic: icons.ingot(ic, "star", P_STAR, 0.3))
    item("blood_crystal", "Blood Crystal", dict(stack), lambda ic: icons.gem(ic, P_BLOOD, 0.7))
    item("living_bark", "Living Bark", dict(stack), _paint_bark)
    item("null_fragment", "Null Fragment", dict(stack), _paint_null_fragment)
    item("fracture_shard", "Fracture Shard", dict(stack), lambda ic: icons.crystal_cluster(ic, P_FRACTURE, 0.8))
    item("eclipse_shard", "Eclipse Shard", dict(stack), _paint_eclipse)
    rare = {"minecraft:max_stack_size": 16, "minecraft:rarity": "rare", "minecraft:glint": True}
    item("hollow_crown_shard", "Hollow Crown Shard", dict(rare), _paint_crown_shard)
    item("star_eater_core", "Star Eater Core", {**rare, "minecraft:rarity": "epic"},
         lambda ic: icons.orb(ic, P_STAR, 1.0, ring_pal=P_GOLD))
    item("titan_heartwood", "Titan Heartwood", {**rare, "minecraft:rarity": "epic"}, _paint_heartwood)
    item("null_heart", "Null Heart", {**rare, "minecraft:rarity": "epic"},
         lambda ic: (icons.gem(ic, P_CORE_V, 1.0), ic.ring(8, 8, 6.6, 1.0, "chitin", P_NULL)))


def _paint_stardust(ic):
    rng = np.random.default_rng(4)
    ic.poly([(2, 14), (5, 10), (8, 9), (11, 10), (14, 14)], "star", P_STAR, glow=0.6)
    for _ in range(5):
        ic.sparkle(2 + rng.random() * 12, 2 + rng.random() * 8, 0.9 + rng.random(), "#fff2c0")


def _paint_chunk(ic):
    ic.poly([(3, 11), (4, 5), (8, 3), (12.5, 5), (13.5, 10), (9.5, 13.5), (5, 13.5)], "stone",
            [(0, "#0b0705"), (0.5, "#2a1c14"), (1, "#4f3a2c")])
    ic.poly([(6, 7), (9, 5.5), (11, 8), (8.5, 10.5)], "star", P_STAR, glow=0.8, seed_off=4)


def _paint_bark(ic):
    ic.poly([(3, 13), (2.5, 6), (5, 2.5), (11.5, 3), (13.5, 7), (12.5, 13.5), (8, 14.5)], "bark", P_BARK)
    ic.line((5, 12), (10, 4), 0.8, "crystal", P_LIFE, glow=0.9, seed_off=3)
    ic.line((8, 13), (12, 8), 0.6, "crystal", P_LIFE, glow=0.9, seed_off=4)


def _paint_null_fragment(ic):
    ic.poly([(4, 14), (3, 7), (8, 1.5), (13, 6), (11, 14)], "chitin", P_NULL)
    ic.line((4, 13.5), (8, 2), 0.7, "crystal", P_NULL_GLOW, glow=1.0, seed_off=2)
    ic.line((8, 2), (12.6, 6.5), 0.7, "crystal", P_NULL_GLOW, glow=1.0, seed_off=3)


def _paint_eclipse(ic):
    ic.disc(8, 8, 6.2, "star", P_GOLD, glow=0.9)
    ic.disc(8.6, 7.4, 5.2, "void", P_ECLIPSE, glow=0.0, seed_off=2)
    ic.sparkle(4, 4, 1.2, "#ffe58a")


def _paint_crown_shard(ic):
    ic.poly([(2, 13), (2, 8), (4, 10), (6, 5), (8, 9.5), (10, 4), (12, 10), (14, 7), (14, 13)], "bronze", P_GOLD)
    ic.disc(8, 11, 1.6, "crystal", P_SOUL, glow=1.0, seed_off=5)


def _paint_heartwood(ic):
    ic.poly([(8, 14.5), (2.5, 8.5), (2.5, 5), (5, 2.5), (8, 4.5), (11, 2.5), (13.5, 5), (13.5, 8.5)], "bark", P_BARK)
    ic.poly([(8, 12), (5, 8.5), (5, 6.5), (6.5, 5.5), (8, 7), (9.5, 5.5), (11, 6.5), (11, 8.5)], "crystal", P_LIFE,
            glow=1.0, seed_off=2)


# ================================================================================================
# relics and utilities
# ================================================================================================

def relics():
    relic = lambda boss: {"minecraft:max_stack_size": 16, "minecraft:rarity": "epic", "minecraft:glint": True,
                          f"{NS}:relic": {"boss": boss}}
    item("cursed_crown", "Cursed Crown", relic("hollow_king"), _paint_cursed_crown)
    item("astral_lure", "Astral Lure", relic("star_eater"), _paint_lure)
    item("heartseed", "Heartseed", relic("root_titan"), _paint_heartseed)
    item("engine_key", "Engine Key", {"minecraft:max_stack_size": 1, "minecraft:rarity": "epic", "minecraft:glint": True,
                                      "minecraft:cooldown": {"category": f"{NS}_engine_key", "duration": 3.0, "type": "use"},
                                      f"{NS}:engine_key": {}}, _paint_key)
    item("engine_codex", "Engine Codex", {"minecraft:max_stack_size": 1, "minecraft:rarity": "rare",
                                          f"{NS}:codex": {}}, _paint_codex)
    item("aether_elixir", "Aether Elixir", {
        "minecraft:max_stack_size": 16, "minecraft:rarity": "uncommon",
        "minecraft:food": {"nutrition": 2, "saturation_modifier": 0.6, "can_always_eat": True,
                           "using_converts_to": "minecraft:glass_bottle"},
        "minecraft:use_animation": "drink",
        "minecraft:use_modifiers": {"use_duration": 1.6, "movement_modifier": 0.35, "start_using": "if_first"},
        f"{NS}:elixir": {}}, lambda ic: icons.vial(ic, P_AETHER, 0.9))


def _paint_cursed_crown(ic):
    ic.poly([(2, 13), (2, 6), (4.5, 9), (6, 3.5), (8, 8), (10, 3.5), (11.5, 9), (14, 6), (14, 13)], "bronze", P_GOLD)
    ic.poly([(2, 11), (14, 11), (14, 13), (2, 13)], "bronze", P_BRONZE, seed_off=3)
    for x in (4.5, 8, 11.5):
        ic.disc(x, 12, 0.9, "crystal", P_SOUL, glow=1.0, seed_off=int(x))


def _paint_lure(ic):
    ic.line((8, 1), (8, 5), 0.6, "metal", P_GOLD)
    ic.ring(8, 5, 1.2, 0.5, "metal", P_GOLD)
    icons.orb(ic, P_STAR, 1.0)


def _paint_heartseed(ic):
    ic.poly([(8, 15), (4, 11), (4.5, 7.5), (8, 6), (11.5, 7.5), (12, 11)], "bark", P_BARK)
    ic.line((8, 7), (8, 3), 0.8, "leaf", P_LIFE, glow=0.6, seed_off=2)
    ic.poly([(8, 4), (5, 1.5), (4.5, 3.5)], "leaf", P_LIFE, glow=0.5, seed_off=3)
    ic.poly([(8, 3.5), (11.5, 1.5), (11.5, 3.5)], "leaf", P_LIFE, glow=0.5, seed_off=4)
    ic.disc(8, 11, 1.4, "crystal", P_LIFE, glow=1.0, seed_off=5)


def _paint_key(ic):
    ic.ring(5, 5, 3.2, 1.4, "bronze", P_GOLD)
    ic.disc(5, 5, 1.6, "crystal", P_NULL_GLOW, glow=1.0, seed_off=2)
    ic.line((7.2, 7.2), (13.5, 13.5), 1.4, "bronze", P_GOLD, seed_off=3)
    ic.line((11, 11), (9.5, 12.5), 1.2, "bronze", P_GOLD, seed_off=4)
    ic.line((13, 13), (11.5, 14.5), 1.2, "bronze", P_GOLD, seed_off=5)


def _paint_codex(ic):
    ic.poly([(2.5, 3), (12.5, 2), (13.5, 13), (3.5, 14.5)], "cloth", [(0, "#120a20"), (0.6, "#3b2163"), (1, "#5e3a96")])
    ic.poly([(3.5, 14.5), (13.5, 13), (13.5, 14), (3.8, 15.5)], "bone", None, seed_off=2)
    ic.glyph(8.2, 8.2, 7, "#7ff6ff", 11)


# ================================================================================================
# weapons (Custom Components V2: apocalypse:ability / apocalypse:on_hit)
# ================================================================================================

def weapon(name, display, dmg, dura, repair, ability, painter, on_hit=None, cooldown=None, rarity="rare",
           enchant_slot="sword", tags=("minecraft:is_sword",)):
    comps = {
        "minecraft:max_stack_size": 1,
        "minecraft:hand_equipped": True,
        "minecraft:damage": dmg,
        "minecraft:durability": {"max_durability": dura},
        "minecraft:enchantable": {"slot": enchant_slot, "value": 15},
        "minecraft:repairable": {"repair_items": [{"items": [repair], "repair_amount": "query.max_durability * 0.25"},
                                                  {"items": [ident(name)], "repair_amount": "context.other->query.remaining_durability + 0.05 * context.other->query.max_durability"}]},
        "minecraft:can_destroy_in_creative": False,
        "minecraft:rarity": rarity,
        "minecraft:tags": {"tags": list(tags)},
    }
    if ability:
        comps[f"{NS}:ability"] = ability
        comps["minecraft:cooldown"] = {"category": f"{NS}_{name}", "duration": cooldown or ability.get("cooldown", 5),
                                       "type": "use"}
    if on_hit:
        comps[f"{NS}:on_hit"] = {**on_hit, "base": dmg}
    item(name, display, comps, painter, category="equipment", group="minecraft:itemGroup.name.sword")


def weapons():
    weapon("rift_blade", "Rift Blade", 8, 900, ident("rift_shard"), {"kind": "rift_dash", "cooldown": 5},
           lambda ic: icons.blade(ic, "crystal", P_RIFT, P_BRONZE, P_BARK, 0.6))
    weapon("bloodfang_cleaver", "Bloodfang Cleaver", 9, 1100, ident("blood_crystal"), None,
           lambda ic: icons.blade(ic, "crystal", P_BLOOD, P_STEEL, P_BARK, 0.5, width=3.6, length=0.9),
           on_hit={"kind": "lifesteal", "ratio": 0.25, "bleed": True})
    weapon("soulreaver_scythe", "Soulreaver Scythe", 10, 1800, ident("soul_essence"), {"kind": "soul_reap", "cooldown": 10},
           lambda ic: icons.scythe(ic, P_SOUL, P_BARK, 0.8), rarity="epic",
           on_hit={"kind": "lifesteal", "ratio": 0.1, "bleed": False})
    weapon("titans_wrath", "Titan's Wrath", 11, 2000, ident("living_bark"), {"kind": "earthsplitter", "cooldown": 10},
           _paint_maul, rarity="epic", enchant_slot="axe", tags=("minecraft:is_axe",))
    weapon("null_edge", "Null Edge", 13, 3000, ident("null_fragment"), {"kind": "gravity_crush", "cooldown": 14},
           lambda ic: icons.blade(ic, "chitin", P_NULL, P_NULL_GLOW, P_BARK, 0.9, width=3.4),
           on_hit={"kind": "null_mark"}, rarity="epic")
    # staffs: low melee damage, strong abilities
    weapon("starfall_scepter", "Starfall Scepter", 4, 800, ident("star_metal_ingot"), {"kind": "star_bolt", "cooldown": 1.5},
           lambda ic: icons.staff(ic, P_BARK, P_STAR, 1.0), tags=("minecraft:is_tool",))
    weapon("event_horizon", "Event Horizon", 5, 1500, ident("stardust"), {"kind": "gravity_well", "cooldown": 12},
           lambda ic: icons.staff(ic, P_NULL, P_CORE_V, 1.0, head="diamond"), rarity="epic", tags=("minecraft:is_tool",))


def _paint_maul(ic):
    ic.line((2.5, 14), (9.5, 7), 1.6, "bark", P_BARK)
    ic.poly([(7, 3.5), (10.5, 0.8), (15, 5.5), (12, 8.5)], "stone", [(0, "#16140f"), (0.5, "#3b382f"), (1, "#69645a")], seed_off=2)
    ic.line((8.5, 2.5), (13.5, 7.5), 0.8, "crystal", P_LIFE, glow=1.0, seed_off=3)


# ================================================================================================
# armor sets: items + attachables + 64x32-layout armor textures
# ================================================================================================
ARMOR_SETS = {
    "riftwalker": {"display": "Riftwalker", "prot": (2, 6, 5, 2), "dura": (260, 380, 350, 310), "repair": ident("rift_shard"),
                   "kind": "metal", "pal": [(0, "#0e2a33"), (0.5, "#2b6f80"), (0.85, "#6fd8e8"), (1, "#d8fbff")],
                   "trim": "#7ff6ff", "rarity": "uncommon"},
    "starforged": {"display": "Starforged", "prot": (3, 8, 6, 3), "dura": (420, 610, 570, 500), "repair": ident("star_metal_ingot"),
                   "kind": "star", "pal": P_STAR, "trim": "#fff2c0", "rarity": "rare"},
    "null_aegis": {"display": "Null Aegis", "prot": (3, 8, 6, 3), "dura": (560, 820, 760, 660), "repair": ident("null_fragment"),
                   "kind": "chitin", "pal": P_NULL, "trim": "#3ff3ff", "rarity": "epic"},
}
PIECES = [("helmet", "slot.armor.head", "armor_head", "Helmet", "geometry.humanoid.armor.helmet", "helmet_layer_visible", 1),
          ("chestplate", "slot.armor.chest", "armor_torso", "Chestplate", "geometry.humanoid.armor.chestplate", "chest_layer_visible", 1),
          ("leggings", "slot.armor.legs", "armor_legs", "Leggings", "geometry.humanoid.armor.leggings", "leg_layer_visible", 2),
          ("boots", "slot.armor.feet", "armor_feet", "Boots", "geometry.humanoid.armor.boots", "boot_layer_visible", 1)]


def armor():
    for set_id, s in ARMOR_SETS.items():
        for i, (piece, slot, ench, pdisplay, geom, layer_var, layer) in enumerate(PIECES):
            name = f"{set_id}_{piece}"
            comps = {
                "minecraft:max_stack_size": 1,
                "minecraft:wearable": {"slot": slot, "protection": s["prot"][i]},
                "minecraft:durability": {"max_durability": s["dura"][i]},
                "minecraft:enchantable": {"slot": ench, "value": 12},
                "minecraft:repairable": {"repair_items": [{"items": [s["repair"]], "repair_amount": "query.max_durability * 0.25"}]},
                "minecraft:rarity": s["rarity"],
                "minecraft:tags": {"tags": ["minecraft:is_armor", f"{NS}:armor_{set_id}"]},
            }
            item(name, f"{s['display']} {pdisplay}", comps,
                 lambda ic, p=piece, st=s: icons.armor_piece(ic, p, st["kind"], st["pal"], st["trim"]),
                 category="equipment", group=f"minecraft:itemGroup.name.{piece}")
            REG.add_rp(f"attachables/{NS}/{name}.json", {
                "format_version": "1.10.0",
                "minecraft:attachable": {"description": {
                    "identifier": ident(name),
                    "materials": {"default": "armor", "enchanted": "armor_enchanted"},
                    "textures": {"default": f"{ARMOR_TEX}/{set_id}_{layer}", "enchanted": "textures/misc/enchanted_actor_glint"},
                    "geometry": {"default": geom},
                    "scripts": {"parent_setup": f"variable.{layer_var} = 0.0;"},
                    "render_controllers": [f"controller.render.{NS}.armor"],
                }}})
        for layer in (1, 2):
            REG.add_texture(TexAsset(f"{ARMOR_TEX}/{set_id}_{layer}",
                                     lambda d, st=s, sid=set_id, ly=layer: _paint_armor_layer(d, st, sid, ly),
                                     DENS_ARMOR, pbr=False))
    REG.add_rp(f"render_controllers/{NS}_armor.render_controllers.json", {
        "format_version": "1.8.0",
        "render_controllers": {f"controller.render.{NS}.armor": {
            "geometry": "Geometry.default",
            "materials": [{"*": "variable.is_enchanted ? Material.enchanted : Material.default"}],
            "textures": ["Texture.default", "Texture.enchanted"]}}})


def _armor_model(layer: int, st: dict) -> geo.Model:
    """Vanilla-compatible 64x32 armor UV layout, painted with set materials."""
    m = geo.Model("armor_paint", 64, 32)
    plate = {"kind": st["kind"], "palette": st["pal"], "ops": [{"op": "rim", "color": st["trim"], "width": 1, "glow": True, "emissive": 0.6}]}
    plain = {"kind": st["kind"], "palette": st["pal"]}

    def cube(u, v, size, mat, deco=None):
        c = geo.Cube((0, 0, 0), size, mat, deco=deco or {})
        c.uv = (u, v)
        m.bone(f"b{len(m.bones)}", (0, 0, 0)).cubes.append(c)

    if layer == 1:
        cube(0, 0, (8, 8, 8), plate, {"north": _visor(st["trim"])})        # helmet
        cube(16, 16, (8, 12, 4), plate, {"north": geo.emblem(st["trim"], "diamond", 0.45)})  # chestplate
        cube(40, 16, (4, 12, 4), plate)                                       # arms
        cube(0, 16, (4, 12, 4), {**plain, "ops": [{"op": "fade", "over": 0.0, "hard": True}]},
             {"*": _keep_bottom(0.42)})                                       # boots (lower leg only)
    else:
        cube(16, 16, (8, 12, 4), plain, {"*": _keep_bottom(0.34, rim=st["trim"])})  # belt
        cube(0, 16, (4, 12, 4), plate)                                        # leggings
    return m


def _visor(color):
    def deco(sw, w, h, d):
        a = np.ones((h, w), dtype=np.float32) if sw.alpha is None else sw.alpha.copy()
        y0, y1 = int(h * 0.38), int(h * 0.52)
        a[y0:y1, int(w * 0.15):int(w * 0.85)] = 0.0
        return tex.Swatch(sw.rgb, sw.height, sw.metal, sw.emissive, sw.rough, a)
    return deco


def _keep_bottom(frac, rim=None):
    def deco(sw, w, h, d):
        a = np.zeros((h, w), dtype=np.float32)
        a[int(h * (1 - frac)):, :] = 1.0
        rgb = sw.rgb
        if rim:
            band = np.zeros((h, w), dtype=np.float32)
            band[int(h * (1 - frac)):int(h * (1 - frac)) + max(1, d), :] = 1.0
            sw = tex.add_glow(sw, band, rim, 0.6)
            rgb = sw.rgb
        return tex.Swatch(rgb, sw.height, sw.metal, sw.emissive, sw.rough, a)
    return deco


def _paint_armor_layer(density, st, set_id, layer):
    m = _armor_model(layer, st)
    return m.paint(density, seed=sum(map(ord, set_id)) + layer)


# ================================================================================================
# recipes
# ================================================================================================

def recipes():
    I = ident
    recipe_shapeless("aether_crystal", [I("rift_shard"), I("rift_shard"), I("rift_shard"), I("rift_shard"),
                                        "minecraft:amethyst_shard"], I("aether_crystal"))
    recipe_furnace("star_metal_ingot_from_chunk", I("star_metal_chunk"), I("star_metal_ingot"))
    recipe_shapeless("engine_codex", ["minecraft:book", I("rift_shard")], I("engine_codex"))
    recipe_shapeless("aether_elixir", ["minecraft:glass_bottle", I("aether_crystal"), "minecraft:glow_berries"],
                     I("aether_elixir"), unlock=[I("aether_crystal")])
    # event materials: alternative routes that reward surviving world events
    recipe_shapeless("aether_elixir_from_ichor", ["minecraft:glass_bottle", "minecraft:glass_bottle", I("aether_crystal"),
                                                  I("void_ichor")], I("aether_elixir"), count=2, unlock=[I("void_ichor")])
    recipe_shapeless("cursed_crown_from_eclipse", [I("eclipse_shard"), I("eclipse_shard"), I("soul_essence"),
                                                   I("soul_essence"), "minecraft:gold_ingot"], I("cursed_crown"),
                     unlock=[I("eclipse_shard")])
    recipe_shapeless("astral_lure_from_fracture", [I("fracture_shard"), I("fracture_shard"), I("stardust"), I("stardust"),
                                                   I("stardust"), I("aether_crystal")], I("astral_lure"),
                     unlock=[I("fracture_shard")])
    # weapons
    recipe_shaped("rift_blade", ["A", "R", "S"], {"A": I("aether_crystal"), "R": I("rift_shard"), "S": "minecraft:stick"},
                  I("rift_blade"), unlock=[I("rift_shard")])
    recipe_shaped("bloodfang_cleaver", ["BB", "BI", " S"], {"B": I("blood_crystal"), "I": "minecraft:iron_ingot",
                                                             "S": "minecraft:stick"}, I("bloodfang_cleaver"),
                  unlock=[I("blood_crystal")])
    recipe_shaped("starfall_scepter", ["DID", " S ", " S "], {"D": I("stardust"), "I": I("star_metal_ingot"),
                                                                "S": "minecraft:stick"}, I("starfall_scepter"),
                  unlock=[I("star_metal_ingot")])
    recipe_shaped("soulreaver_scythe", ["HHE", " S ", "S  "], {"H": I("hollow_crown_shard"), "E": I("soul_essence"),
                                                                 "S": "minecraft:stick"}, I("soulreaver_scythe"),
                  unlock=[I("hollow_crown_shard")])
    recipe_shaped("event_horizon", ["DCD", " I ", " I "], {"D": I("stardust"), "C": I("star_eater_core"),
                                                            "I": I("star_metal_ingot")}, I("event_horizon"),
                  unlock=[I("star_eater_core")])
    recipe_shaped("titans_wrath", ["BWB", "BIB", " L "], {"B": I("living_bark"), "W": I("titan_heartwood"),
                                                           "I": "minecraft:iron_block", "L": "minecraft:oak_log"},
                  I("titans_wrath"), unlock=[I("titan_heartwood")])
    recipe_shaped("null_edge", ["NNN", "NHN", " R "], {"N": I("null_fragment"), "H": I("null_heart"),
                                                        "R": I("rift_blade")}, I("null_edge"), unlock=[I("null_heart")])
    # relics
    recipe_shaped("cursed_crown", ["S S", "SGS", "ERE"], {"S": I("soul_essence"), "G": "minecraft:gold_ingot",
                                                           "E": I("soul_essence"), "R": I("rift_shard")},
                  I("cursed_crown"), unlock=[I("soul_essence")])
    recipe_shaped("astral_lure", ["DDD", "DAD", "DID"], {"D": I("stardust"), "A": I("aether_crystal"),
                                                          "I": I("star_metal_ingot")}, I("astral_lure"),
                  unlock=[I("stardust")])
    recipe_shaped("heartseed", ["BLB", "LAL", "BLB"], {"B": I("living_bark"), "L": "minecraft:oak_sapling",
                                                        "A": I("aether_crystal")}, I("heartseed"),
                  unlock=[I("living_bark")])
    recipe_shaped("engine_key", ["HCT", " A ", " A "], {"H": I("hollow_crown_shard"), "C": I("star_eater_core"),
                                                         "T": I("titan_heartwood"), "A": I("aether_crystal")},
                  I("engine_key"), unlock=[I("star_eater_core")])
    # armor
    patterns = {"helmet": ["XXX", "X X"], "chestplate": ["X X", "XXX", "XXX"], "leggings": ["XXX", "X X", "X X"],
                "boots": ["X X", "X X"]}
    for piece, pat in patterns.items():
        recipe_shaped(f"riftwalker_{piece}", pat, {"X": I("rift_shard")}, I(f"riftwalker_{piece}"))
        recipe_shaped(f"starforged_{piece}", pat, {"X": I("star_metal_ingot")}, I(f"starforged_{piece}"))
        recipe_shaped(f"null_aegis_{piece}", ["NNN", "NPN", "NNN"], {"N": I("null_fragment"), "P": I(f"starforged_{piece}")},
                      I(f"null_aegis_{piece}"), unlock=[I("null_fragment")])


def build():
    materials()
    relics()
    weapons()
    armor()
    recipes()
