"""All APOCALYPSE ENGINE entities: behavior JSON, client entities, animations, controllers, loot, spawns."""
from __future__ import annotations

import zlib

from tools.content import model_defs
from tools.content.common import (DENS_BOSS, DENS_MOB, ENT_TEX, ENTITY_FMT, NS, SPAWN_FMT, ident, is_family,
                                  item_entry, loot_table)
from tools.content.registry import REG, TexAsset
from tools.lib.anim import AnimSet, ControllerSet, bob, breathe, swing

# ------------------------------------------------------------------------------------------------
# action ids shared with the scripts (exported to src/scripts/generated/ids.ts)
# ------------------------------------------------------------------------------------------------
ACTIONS = {
    "hollow_king": {1: "summon", 2: "quake_windup", 3: "quake_slam", 4: "phantom_step", 5: "roar",
                    6: "soul_chains", 7: "crown_of_ruin"},
    "star_eater": {1: "bolt_volley", 2: "gravity_well", 3: "supernova_charge", 4: "supernova_release", 5: "roar",
                   6: "dive", 7: "brood"},
    "root_titan": {1: "eruption", 2: "brood", 3: "slam_windup", 4: "slam", 5: "roar", 6: "sap_shield",
                   7: "vine_pull"},
    "null_colossus": {1: "gravity_lift", 2: "gravity_slam", 3: "beam_charge", 4: "beam_fire", 5: "roar",
                      6: "vent", 7: "collapse"},
}

BOSS_PROPS = {
    f"{NS}:action": {"type": "int", "range": [0, 15], "default": 0, "client_sync": True},
    f"{NS}:phase": {"type": "int", "range": [1, 3], "default": 1, "client_sync": True},
}

RC_DEFAULT = f"controller.render.{NS}.default"
RC_GLOW = f"controller.render.{NS}.glow"


def tier_groups(base_hp: int) -> tuple[dict, dict]:
    """Health tiers chosen by script at spawn (players nearby x difficulty)."""
    groups, events = {}, {}
    for i, mult in enumerate((1.0, 1.5, 2.0, 2.6), start=1):
        hp = int(base_hp * mult)
        groups[f"{NS}:tier_{i}"] = {"minecraft:health": {"value": hp, "max": hp}}
        events[f"{NS}:tier_{i}"] = {"add": {"component_groups": [f"{NS}:tier_{i}"]}}
    return groups, events


def common_boss_components(name: str, hp: int, speed: float, width: float, height: float, families: list[str],
                           hud: int = 64) -> dict:
    return {
        "minecraft:type_family": {"family": [NS, "apocalypse_boss", "monster", "mob"] + families},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:movement": {"value": speed},
        "minecraft:follow_range": {"value": 64, "max": 64},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:boss": {"hud_range": hud, "should_darken_sky": True},
        "minecraft:persistent": {},
        "minecraft:physics": {},
        "minecraft:pushable_by_block": {},
        "minecraft:fire_immune": {},
        "minecraft:nameable": {},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:breathable": {"breathes_water": True, "suffocate_time": 0, "total_supply": 15},
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "fall", "deals_damage": "no"},
            {"cause": "suffocation", "deals_damage": "no"},
            {"cause": "drowning", "deals_damage": "no"},
            {"on_damage": {"filters": is_family("apocalypse_boss")}, "deals_damage": "no"},
            {"on_damage": {"filters": is_family(NS)}, "deals_damage": "no"},
        ]},
        "minecraft:mob_effect_immunity": {"mob_effects": ["poison", "wither", "slowness", "levitation", "weakness"]},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 48,
            "entity_types": [{"filters": is_family("player"), "max_dist": 48}]},
        "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 24, "look_time": {"min": 2, "max": 4}},
        "minecraft:behavior.random_look_around": {"priority": 9},
        "minecraft:experience_reward": {"on_death": "250"},
        "minecraft:loot": {"table": f"loot_tables/entities/{NS}/{name}.json"},
    }


def mob_components(name: str, hp: int, speed: float, width: float, height: float, families: list[str],
                   damage: float, despawn: bool = True) -> dict:
    c = {
        "minecraft:type_family": {"family": [NS, "monster", "mob"] + families},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:movement": {"value": speed},
        "minecraft:attack": {"damage": damage},
        "minecraft:physics": {},
        "minecraft:pushable_by_block": {},
        "minecraft:pushable_by_entity": {},
        "minecraft:nameable": {},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2, "must_see": True, "reselect_targets": True,
            "entity_types": [{"filters": is_family("player"), "max_dist": 24},
                             {"filters": is_family("irongolem"), "max_dist": 16}]},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.9},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8, "look_time": {"min": 2, "max": 4}},
        "minecraft:behavior.random_look_around": {"priority": 8},
        "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 6 + Math.die_roll(1, 4) : 0"},
        "minecraft:loot": {"table": f"loot_tables/entities/{NS}/{name}.json"},
    }
    if despawn:
        c["minecraft:despawn"] = {"despawn_from_distance": {"min_distance": 32, "max_distance": 96}}
    return c


def entity_doc(name: str, components: dict, groups: dict | None = None, events: dict | None = None,
               props: dict | None = None, spawnable: bool = True, summonable: bool = True,
               category: str = "monster") -> dict:
    desc = {"identifier": ident(name), "is_spawnable": spawnable, "is_summonable": summonable,
            "spawn_category": category}
    if props:
        desc["properties"] = props
    ent: dict = {"description": desc, "components": components}
    if groups:
        ent["component_groups"] = groups
    if events:
        ent["events"] = events
    return {"format_version": ENTITY_FMT, "minecraft:entity": ent}


def register_model(name: str, dens: dict, glow: bool = True, extra_textures: dict | None = None):
    """Register geometry + painted textures (base/balanced/enhanced) for an entity model."""
    model = model_defs.ALL_MODELS[name]()
    REG.add_rp(f"models/entity/{NS}/{name}.geo.json", model.to_json())
    REG.add_texture(TexAsset(f"{ENT_TEX}/{name}", lambda d, m=model, s=zlib.crc32(name.encode()) % 997: m.paint(d, seed=s),
                             dens, pbr=True, glow=glow))
    if extra_textures:
        for suffix, painter in extra_textures.items():
            REG.add_texture(TexAsset(f"{ENT_TEX}/{name}_{suffix}", painter, dens, pbr=True, glow=glow))
    return model


def client_entity(name: str, model, anims: AnimSet | None, controllers: ControllerSet | None,
                  animate: list, egg: tuple[str, str] | None, render_controllers: list | None = None,
                  textures: dict | None = None, particles: dict | None = None, pre_animation: list | None = None,
                  glow: bool = True, materials: dict | None = None, sounds: dict | None = None) -> dict:
    tex = {"default": f"{ENT_TEX}/{name}"}
    if glow:
        tex["glow"] = f"{ENT_TEX}/{name}_glow"
    if textures:
        tex.update(textures)
    mats = materials or {"default": "entity_alphatest"}
    if glow:
        mats.setdefault("glow", "entity_emissive_alpha")
    desc: dict = {
        "identifier": ident(name),
        "materials": mats,
        "textures": tex,
        "geometry": {"default": model.identifier},
        "render_controllers": render_controllers or ([RC_DEFAULT, RC_GLOW] if glow else [RC_DEFAULT]),
    }
    anim_map = {}
    if anims:
        for full in anims.anims:
            anim_map[full.split(".")[-1]] = full
    if controllers:
        for full in controllers.controllers:
            anim_map[full.split(".")[-1] + "_controller"] = full
    if anim_map:
        desc["animations"] = anim_map
    scripts: dict = {}
    if pre_animation:
        scripts["pre_animation"] = pre_animation
    if animate:
        scripts["animate"] = animate
    if scripts:
        desc["scripts"] = scripts
    if particles:
        desc["particle_effects"] = particles
    if sounds:
        desc["sound_effects"] = sounds
    if egg:
        desc["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def write_entity(name: str, bp: dict, rp: dict, anims: AnimSet | None, ctrls: ControllerSet | None,
                 display: str, loot: dict | None = None):
    REG.add_bp(f"entities/{NS}/{name}.json", bp)
    REG.add_rp(f"entity/{NS}/{name}.entity.json", rp)
    if anims and anims.anims:
        REG.add_rp(f"animations/{NS}/{name}.animation.json", anims.to_json())
    if ctrls and ctrls.controllers:
        REG.add_rp(f"animation_controllers/{NS}/{name}.animation_controllers.json", ctrls.to_json())
    if loot is not None:
        REG.add_bp(f"loot_tables/entities/{NS}/{name}.json", loot)
    REG.name(f"entity.{ident(name)}.name", display)
    REG.name(f"item.spawn_egg.entity.{ident(name)}.name", f"Spawn {display}")
    REG.ts("entities", name.upper(), ident(name))


def action_controller(ctrls: ControllerSet, anims: AnimSet, boss: str) -> str:
    states = {0: {"name": "default"}}
    for aid, aname in ACTIONS[boss].items():
        if anims.full(aname) in anims.anims:
            states[aid] = {"name": aname, "animations": [aname]}
    return ctrls.property_states("action", f"{NS}:action", states)


def phase_fx_controller(ctrls: ControllerSet, locator: str) -> str:
    states = {0: {"name": "default"},
              2: {"name": "phase2", "particles": [{"effect": "aura2", "locator": locator}]},
              3: {"name": "phase3", "particles": [{"effect": "aura3", "locator": locator}]}}
    return ctrls.property_states("phase", f"{NS}:phase", states, blend=0.0)


# ================================================================================================
# THE HOLLOW KING
# ================================================================================================

def hollow_king():
    name = "hollow_king"
    model = register_model(name, DENS_BOSS)
    comps = common_boss_components(name, 600, 0.27, 1.4, 4.4, ["undead", "hollow"], hud=72)
    comps.update({
        "minecraft:attack": {"damage": 11},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True, "avoid_damage_blocks": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:variable_max_auto_step": {"base_value": 1.0625, "jump_prevented_value": 1.0625},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.delayed_attack": {"priority": 3, "attack_duration": 1.0, "hit_delay_pct": 0.55,
                                               "reach_multiplier": 2.4, "speed_multiplier": 1.15, "track_target": True},
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.7, "xz_dist": 8},
    })
    groups, events = tier_groups(600)
    bp = entity_doc(name, comps, groups, events, BOSS_PROPS)

    a = AnimSet(name)
    a.add("idle", {
        "body": {"rotation": [breathe(1.5, 4.0), 0, 0]},
        "head": {"rotation": [breathe(2.0, 4.0, 40), breathe(4.0, 7.0), 0]},
        "halo": {"rotation": [0, "query.life_time * 45", 0], "position": [0, bob(1.0, 3.0), 0]},
        "right_arm": {"rotation": [breathe(2.0, 4.0, 90), 0, 3]},
        "left_arm": {"rotation": [breathe(2.0, 4.0, 180), 0, -3]},
    })
    a.add("walk", {
        "right_leg": {"rotation": [swing(28), 0, 0]},
        "left_leg": {"rotation": [swing(28, 180), 0, 0]},
        "left_arm": {"rotation": [swing(16), 0, 0]},
        "right_arm": {"rotation": [swing(8, 180), 0, 0]},
        "body": {"position": [0, "math.abs(math.cos(query.modified_distance_moved * 38.17)) * 0.8 * query.modified_move_speed", 0]},
    })
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation * 0.6", "query.target_y_rotation * 0.8", 0]}})
    a.add("attack", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.45": [-160, 10, 15], "0.6": [30, -10, -10], "1.0": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [8, 0, 0], "0.45": [0, 15, 0], "0.6": [18, -15, 0], "1.0": [8, 0, 0]}},
    }, loop=False, length=1.0)
    a.add("summon", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-130, 0, 50], "1.3": [-130, 0, 50], "1.6": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-130, 0, -50], "1.3": [-130, 0, -50], "1.6": [0, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.5": [-25, 0, 0], "1.3": [-25, 0, 0], "1.6": [0, 0, 0]}},
        "halo": {"rotation": [0, "query.anim_time * 720", 0], "scale": {"0.0": 1, "0.6": 1.6, "1.6": 1}},
    }, loop=False, length=1.6)
    a.add("quake_windup", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.8": [-175, 0, -20]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.8": [-175, 0, 20]}},
        "body": {"rotation": {"0.0": [8, 0, 0], "0.8": [-14, 0, 0]}},
    }, loop="hold_on_last_frame", length=0.8)
    a.add("quake_slam", {
        "right_arm": {"rotation": {"0.0": [-175, 0, -20], "0.15": [25, 0, -10], "0.6": [10, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [-175, 0, 20], "0.15": [25, 0, 10], "0.6": [10, 0, 0]}},
        "body": {"rotation": {"0.0": [-14, 0, 0], "0.15": [32, 0, 0], "0.6": [20, 0, 0]}},
    }, loop="hold_on_last_frame", length=0.6)
    a.add("phantom_step", {
        "root": {"scale": {"0.0": 1, "0.25": [0.15, 1.2, 0.15], "0.5": 1}},
    }, loop=False, length=0.5)
    a.add("roar", {
        "head": {"rotation": {"0.0": [0, 0, 0], "0.3": [-38, 0, 0], "1.2": [-38, 0, 0], "1.5": [0, 0, 0]}},
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.3": [-40, 0, 75], "1.2": [-40, 0, 75], "1.5": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.3": [-40, 0, -75], "1.2": [-40, 0, -75], "1.5": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [8, 0, 0], "0.3": [-12, 0, 0], "1.2": [-12, 0, 0], "1.5": [8, 0, 0]}},
    }, loop=False, length=1.5)
    a.add("soul_chains", {
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.3": [-95, -15, 0], "0.9": [-95, -15, 0], "1.0": [0, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.3": [10, -10, 0], "1.0": [0, 0, 0]}},
    }, loop=False, length=1.0)
    a.add("crown_of_ruin", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.6": [-165, 0, 25], "1.8": [-165, 0, 25], "2.0": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.6": [-165, 0, -25], "1.8": [-165, 0, -25], "2.0": [0, 0, 0]}},
        "halo": {"rotation": [0, "query.anim_time * 1080", 0], "scale": {"0.0": 1, "1.0": 2.2, "2.0": 1}},
    }, loop=False, length=2.0)
    c = ControllerSet(name)
    action_controller(c, a, name)
    c.controllers[c.full("attack")] = {"initial_state": "default", "states": {
        "default": {"transitions": [{"swing": "query.is_delayed_attacking"}]},
        "swing": {"animations": ["attack"], "transitions": [{"default": "!query.is_delayed_attacking && query.all_animations_finished"}],
                  "blend_transition": 0.1}}}
    phase_fx_controller(c, "core")
    c.always("ambient", particles=[{"effect": "aura1", "locator": "crown"}])
    rp = client_entity(name, model, a, c,
                       ["idle", {"walk": "query.modified_move_speed"}, "look_at_target", "action_controller",
                        "attack_controller", "phase_controller", "ambient_controller"],
                       ("#140a24", "#b98cff"),
                       render_controllers=[f"controller.render.{NS}.boss", RC_GLOW],
                       particles={"aura1": f"{NS}:soul_wisp", "aura2": f"{NS}:boss_aura_violet",
                                  "aura3": f"{NS}:boss_aura_crimson"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("hollow_crown_shard"), count=(2, 3))]},
        {"rolls": 1, "entries": [item_entry(ident("soul_essence"), count=(6, 10))]},
        {"rolls": 1, "entries": [item_entry(ident("soulreaver_scythe"), weight=1), {"type": "empty", "weight": 2}]},
    ])
    write_entity(name, bp, rp, a, c, "The Hollow King", loot)


# ================================================================================================
# THE STAR EATER
# ================================================================================================

def star_eater():
    name = "star_eater"
    model = register_model(name, DENS_BOSS)
    comps = common_boss_components(name, 750, 0.32, 3.0, 2.6, ["cosmic", "star_eater"], hud=80)
    comps.update({
        "minecraft:attack": {"damage": 9},
        "minecraft:scale": {"value": 1.5},
        "minecraft:can_fly": {},
        "minecraft:flying_speed": {"value": 0.18},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:navigation.hover": {"can_path_over_water": True, "can_path_from_air": True, "avoid_water": True,
                                        "avoid_damage_blocks": True, "can_sink": False},
        "minecraft:movement.hover": {},
        "minecraft:behavior.melee_box_attack": {"priority": 4, "speed_multiplier": 1.2, "track_target": True,
                                                "horizontal_reach": 2.5, "cooldown_time": 1.6},
        "minecraft:behavior.random_hover": {"priority": 7, "xz_dist": 12, "y_dist": 6, "y_offset": -1,
                                            "interval": 60, "hover_height": {"min": 6, "max": 12}},
    })
    groups, events = tier_groups(750)
    bp = entity_doc(name, comps, groups, events, BOSS_PROPS)
    a = AnimSet(name)
    tail_wave = lambda i, amp: f"math.sin(query.life_time * 120 - {i * 55}) * {amp}"
    a.add("idle", {
        "body": {"position": [0, bob(1.5, 3.0), 0]},
        "fin_l": {"rotation": [0, 0, breathe(18, 1.6)]},
        "fin_r": {"rotation": [0, 0, breathe(-18, 1.6)]},
        "fin_l2": {"rotation": [0, 0, breathe(14, 1.6, 60)]},
        "fin_r2": {"rotation": [0, 0, breathe(-14, 1.6, 60)]},
        "tail0": {"rotation": [0, tail_wave(0, 8), 0]},
        "tail1": {"rotation": [0, tail_wave(1, 10), 0]},
        "tail2": {"rotation": [0, tail_wave(2, 12), 0]},
        "tail3": {"rotation": [0, tail_wave(3, 14), 0]},
        "tail_fin": {"rotation": [tail_wave(4, 10), 0, 0]},
        "jaw_l": {"rotation": [0, breathe(-6, 2.5), 0]},
        "jaw_r": {"rotation": [0, breathe(6, 2.5), 0]},
        "tendrils": {"rotation": [breathe(12, 2.0), 0, breathe(6, 3.0)]},
    })
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.5", 0]}})
    a.add("bolt_volley", {
        "jaw_l": {"rotation": {"0.0": [0, 0, 0], "0.2": [0, -32, 0], "0.8": [0, -32, 0], "1.0": [0, 0, 0]}},
        "jaw_r": {"rotation": {"0.0": [0, 0, 0], "0.2": [0, 32, 0], "0.8": [0, 32, 0], "1.0": [0, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.25": [-12, 0, 0], "0.4": [6, 0, 0], "0.55": [-12, 0, 0], "0.7": [6, 0, 0], "1.0": [0, 0, 0]}},
    }, loop=False, length=1.0)
    a.add("gravity_well", {
        "body": {"rotation": [0, 0, "query.anim_time * 360"]},
        "fin_l": {"rotation": [0, 0, 40]}, "fin_r": {"rotation": [0, 0, -40]},
    }, loop=False, length=2.0)
    a.add("supernova_charge", {
        "head": {"rotation": {"0.0": [0, 0, 0], "1.5": [35, 0, 0]}},
        "tail0": {"rotation": {"0.0": [0, 0, 0], "1.5": [-30, 0, 0]}},
        "tail1": {"rotation": {"0.0": [0, 0, 0], "1.5": [-35, 0, 0]}},
        "tail2": {"rotation": {"0.0": [0, 0, 0], "1.5": [-40, 0, 0]}},
        "fin_l": {"rotation": {"0.0": [0, 0, 0], "1.5": [0, 0, -70]}},
        "fin_r": {"rotation": {"0.0": [0, 0, 0], "1.5": [0, 0, 70]}},
        "jaw_l": {"rotation": {"0.0": [0, 0, 0], "3.0": [0, -40, 0]}},
        "jaw_r": {"rotation": {"0.0": [0, 0, 0], "3.0": [0, 40, 0]}},
        "body": {"scale": {"0.0": 1, "3.0": 1.12}},
    }, loop="hold_on_last_frame", length=3.0)
    a.add("supernova_release", {
        "fin_l": {"rotation": {"0.0": [0, 0, -70], "0.15": [0, 0, 55], "0.8": [0, 0, 0]}},
        "fin_r": {"rotation": {"0.0": [0, 0, 70], "0.15": [0, 0, -55], "0.8": [0, 0, 0]}},
        "head": {"rotation": {"0.0": [35, 0, 0], "0.15": [-30, 0, 0], "0.8": [0, 0, 0]}},
        "body": {"scale": {"0.0": 1.12, "0.15": 1.25, "0.8": 1}},
    }, loop=False, length=0.8)
    a.add("roar", {
        "head": {"rotation": {"0.0": [0, 0, 0], "0.3": [-35, 0, 0], "1.2": [-35, 0, 0], "1.5": [0, 0, 0]}},
        "jaw_l": {"rotation": {"0.0": [0, 0, 0], "0.3": [0, -40, 0], "1.2": [0, -40, 0], "1.5": [0, 0, 0]}},
        "jaw_r": {"rotation": {"0.0": [0, 0, 0], "0.3": [0, 40, 0], "1.2": [0, 40, 0], "1.5": [0, 0, 0]}},
    }, loop=False, length=1.5)
    a.add("dive", {"body": {"rotation": {"0.0": [0, 0, 0], "0.3": [35, 0, 0], "0.8": [35, 0, 0], "1.0": [0, 0, 0]}}},
          loop=False, length=1.0)
    a.add("brood", {
        "head": {"rotation": {"0.0": [0, 0, 0], "0.2": [0, 15, 0], "0.4": [0, -15, 0], "0.6": [0, 15, 0], "0.8": [0, -15, 0], "1.2": [0, 0, 0]}},
        "jaw_l": {"rotation": [0, -25, 0]}, "jaw_r": {"rotation": [0, 25, 0]},
    }, loop=False, length=1.2)
    c = ControllerSet(name)
    action_controller(c, a, name)
    phase_fx_controller(c, "core")
    c.always("ambient", particles=[{"effect": "aura1", "locator": "maw"}])
    rp = client_entity(name, model, a, c,
                       ["idle", "look_at_target", "action_controller", "phase_controller", "ambient_controller"],
                       ("#05030b", "#ffd36a"),
                       render_controllers=[f"controller.render.{NS}.boss", RC_GLOW],
                       particles={"aura1": f"{NS}:star_spark", "aura2": f"{NS}:boss_aura_gold",
                                  "aura3": f"{NS}:boss_aura_crimson"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("star_eater_core"), count=(1, 1))]},
        {"rolls": 1, "entries": [item_entry(ident("stardust"), count=(8, 14))]},
        {"rolls": 1, "entries": [item_entry(ident("star_metal_ingot"), count=(3, 5))]},
        {"rolls": 1, "entries": [item_entry(ident("event_horizon"), weight=1), {"type": "empty", "weight": 2}]},
    ])
    write_entity(name, bp, rp, a, c, "The Star Eater", loot)


# ================================================================================================
# THE ROOT TITAN
# ================================================================================================

def root_titan():
    name = "root_titan"
    model = register_model(name, DENS_BOSS)
    comps = common_boss_components(name, 900, 0.21, 2.6, 5.8, ["plant", "root_titan"], hud=72)
    comps.update({
        "minecraft:attack": {"damage": 15},
        "minecraft:navigation.walk": {"can_path_over_water": False, "avoid_water": True, "avoid_damage_blocks": True,
                                       "can_break_doors": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:variable_max_auto_step": {"base_value": 1.5625, "jump_prevented_value": 1.5625},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.delayed_attack": {"priority": 3, "attack_duration": 1.3, "hit_delay_pct": 0.6,
                                               "reach_multiplier": 2.2, "speed_multiplier": 1.1, "track_target": True},
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.6, "xz_dist": 6},
    })
    comps["minecraft:fire_immune"] = {}
    groups, events = tier_groups(900)
    bp = entity_doc(name, comps, groups, events, BOSS_PROPS)
    a = AnimSet(name)
    a.add("idle", {
        "body": {"rotation": [breathe(1.2, 5.0), 0, breathe(1.0, 7.0)]},
        "head": {"rotation": [breathe(2.0, 5.0, 60), 0, 0]},
        "right_arm": {"rotation": [breathe(3.0, 5.0, 90), 0, 4]},
        "left_arm": {"rotation": [breathe(3.0, 5.0, 200), 0, -4]},
    })
    a.add("walk", {
        "right_leg": {"rotation": [swing(18, rate=24), 0, 0]},
        "left_leg": {"rotation": [swing(18, 180, rate=24), 0, 0]},
        "right_arm": {"rotation": [swing(12, 180, rate=24), 0, 0]},
        "left_arm": {"rotation": [swing(12, rate=24), 0, 0]},
        "body": {"rotation": [0, 0, swing(3, rate=24)]},
    })
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.6", 0]}})
    a.add("attack", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.6": [-150, 0, -10], "0.8": [15, 0, 0], "1.3": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.6": [-8, 10, 0], "0.8": [15, -10, 0], "1.3": [0, 0, 0]}},
    }, loop=False, length=1.3)
    a.add("eruption", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-120, 0, 0], "0.8": [30, 0, 0], "1.5": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-120, 0, 0], "0.8": [30, 0, 0], "1.5": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.5": [-10, 0, 0], "0.8": [22, 0, 0], "1.5": [0, 0, 0]}},
    }, loop=False, length=1.5)
    a.add("brood", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-60, 0, 60], "1.2": [-60, 0, 60], "1.5": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.5": [-60, 0, -60], "1.2": [-60, 0, -60], "1.5": [0, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.5": [-25, 0, 0], "1.5": [0, 0, 0]}},
    }, loop=False, length=1.5)
    a.add("slam_windup", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-170, 0, -15]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-170, 0, 15]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "1.0": [-15, 0, 0]}},
    }, loop="hold_on_last_frame", length=1.0)
    a.add("slam", {
        "right_arm": {"rotation": {"0.0": [-170, 0, -15], "0.15": [20, 0, -5], "0.6": [10, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [-170, 0, 15], "0.15": [20, 0, 5], "0.6": [10, 0, 0]}},
        "body": {"rotation": {"0.0": [-15, 0, 0], "0.15": [28, 0, 0], "0.6": [18, 0, 0]}},
    }, loop="hold_on_last_frame", length=0.6)
    a.add("roar", {
        "head": {"rotation": {"0.0": [0, 0, 0], "0.4": [-32, 0, 0], "1.6": [-32, 0, 0], "2.0": [0, 0, 0]}},
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-30, 0, 70], "1.6": [-30, 0, 70], "2.0": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-30, 0, -70], "1.6": [-30, 0, -70], "2.0": [0, 0, 0]}},
    }, loop=False, length=2.0)
    a.add("sap_shield", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.3": [-75, 35, 0], "0.9": [-75, 35, 0], "1.0": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.3": [-75, -35, 0], "0.9": [-75, -35, 0], "1.0": [0, 0, 0]}},
    }, loop=False, length=1.0)
    a.add("vine_pull", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.35": [-95, 0, 0], "0.6": [-20, 0, 0], "1.0": [0, 0, 0]}},
    }, loop=False, length=1.0)
    c = ControllerSet(name)
    action_controller(c, a, name)
    c.controllers[c.full("attack")] = {"initial_state": "default", "states": {
        "default": {"transitions": [{"swing": "query.is_delayed_attacking"}]},
        "swing": {"animations": ["attack"], "transitions": [{"default": "!query.is_delayed_attacking && query.all_animations_finished"}],
                  "blend_transition": 0.1}}}
    phase_fx_controller(c, "heart")
    c.always("ambient", particles=[{"effect": "aura1", "locator": "heart"}])
    rp = client_entity(name, model, a, c,
                       ["idle", {"walk": "query.modified_move_speed"}, "look_at_target", "action_controller",
                        "attack_controller", "phase_controller", "ambient_controller"],
                       ("#1e140c", "#9cff5a"),
                       render_controllers=[f"controller.render.{NS}.boss", RC_GLOW],
                       particles={"aura1": f"{NS}:spore_drift", "aura2": f"{NS}:boss_aura_green",
                                  "aura3": f"{NS}:boss_aura_crimson"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("titan_heartwood"), count=(1, 2))]},
        {"rolls": 1, "entries": [item_entry(ident("living_bark"), count=(8, 14))]},
        {"rolls": 1, "entries": [item_entry(ident("titans_wrath"), weight=1), {"type": "empty", "weight": 2}]},
    ])
    write_entity(name, bp, rp, a, c, "The Root Titan", loot)


# ================================================================================================
# THE NULL COLOSSUS
# ================================================================================================

def null_colossus():
    name = "null_colossus"
    model = register_model(name, DENS_BOSS)
    comps = common_boss_components(name, 1200, 0.2, 3.2, 6.8, ["construct", "null_colossus"], hud=96)
    comps.update({
        "minecraft:attack": {"damage": 18},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": False, "avoid_damage_blocks": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:variable_max_auto_step": {"base_value": 1.5625, "jump_prevented_value": 1.5625},
        "minecraft:behavior.delayed_attack": {"priority": 3, "attack_duration": 1.4, "hit_delay_pct": 0.6,
                                               "reach_multiplier": 2.0, "speed_multiplier": 1.0, "track_target": True},
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.5, "xz_dist": 5},
    })
    props = dict(BOSS_PROPS)
    props[f"{NS}:vented"] = {"type": "bool", "default": False, "client_sync": True}
    groups, events = tier_groups(1200)
    bp = entity_doc(name, comps, groups, events, props)
    a = AnimSet(name)
    a.add("idle", {
        "orbitals": {"rotation": [0, "query.life_time * 30", 0], "position": [0, bob(2.0, 4.0), 0]},
        "body": {"rotation": [breathe(1.0, 5.0), 0, 0]},
        "head": {"rotation": [0, breathe(12, 6.0), 0]},
        "core": {"scale": f"1 + math.sin(query.life_time * 240) * 0.04"},
    })
    a.add("walk", {
        "right_leg": {"rotation": [swing(15, rate=22), 0, 0]},
        "left_leg": {"rotation": [swing(15, 180, rate=22), 0, 0]},
        "right_arm": {"rotation": [swing(8, 180, rate=22), 0, 0]},
        "left_arm": {"rotation": [swing(8, rate=22), 0, 0]},
    })
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.5", 0]}})
    a.add("attack", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.7": [-60, 60, 0], "0.9": [-60, -40, 0], "1.4": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.7": [0, 25, 0], "0.9": [0, -20, 0], "1.4": [0, 0, 0]}},
    }, loop=False, length=1.4)
    a.add("gravity_lift", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.8": [-115, 0, 15], "1.5": [-115, 0, 15]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.8": [-115, 0, -15], "1.5": [-115, 0, -15]}},
        "orbitals": {"rotation": [0, "query.anim_time * 400", 0], "position": {"0.0": [0, 0, 0], "1.5": [0, 14, 0]}},
    }, loop="hold_on_last_frame", length=1.5)
    a.add("gravity_slam", {
        "right_arm": {"rotation": {"0.0": [-115, 0, 15], "0.2": [30, 0, 0], "0.7": [15, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [-115, 0, -15], "0.2": [30, 0, 0], "0.7": [15, 0, 0]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.2": [22, 0, 0], "0.7": [10, 0, 0]}},
        "orbitals": {"position": {"0.0": [0, 14, 0], "0.2": [0, -20, 0], "0.7": [0, 0, 0]}},
    }, loop="hold_on_last_frame", length=0.7)
    a.add("beam_charge", {
        "body": {"rotation": {"0.0": [0, 0, 0], "1.0": [-14, 0, 0]}},
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-20, 0, 30]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-20, 0, -30]}},
        "head": {"scale": {"0.0": 1, "2.0": 1.15}},
    }, loop="hold_on_last_frame", length=2.0)
    a.add("beam_fire", {
        "body": {"rotation": {"0.0": [-14, -45, 0], "2.0": [-14, 45, 0]}},
    }, loop="hold_on_last_frame", length=2.0)
    a.add("roar", {
        "head": {"rotation": {"0.0": [0, 0, 0], "0.4": [-30, 0, 0], "1.4": [-30, 0, 0], "1.8": [0, 0, 0]}},
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-40, 0, 65], "1.4": [-40, 0, 65], "1.8": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-40, 0, -65], "1.4": [-40, 0, -65], "1.8": [0, 0, 0]}},
        "orbitals": {"scale": {"0.0": 1, "0.6": 1.5, "1.8": 1}},
    }, loop=False, length=1.8)
    a.add("vent", {
        "vent_r": {"rotation": {"0.0": [0, 0, 0], "0.5": [0, 75, 0]}},
        "vent_l": {"rotation": {"0.0": [0, 0, 0], "0.5": [0, -75, 0]}},
        "core": {"scale": "1.1 + math.sin(query.anim_time * 540) * 0.08"},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.5": [12, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.5": [20, 0, 0]}},
    }, loop="hold_on_last_frame", length=0.5)
    a.add("collapse", {
        "right_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-90, 0, 70], "2.0": [-90, 0, 15], "2.5": [0, 0, 0]}},
        "left_arm": {"rotation": {"0.0": [0, 0, 0], "1.0": [-90, 0, -70], "2.0": [-90, 0, -15], "2.5": [0, 0, 0]}},
        "orbitals": {"scale": {"0.0": 1, "2.0": 0.4, "2.5": 1}, "rotation": [0, "query.anim_time * 600", 0]},
    }, loop=False, length=2.5)
    c = ControllerSet(name)
    action_controller(c, a, name)
    c.controllers[c.full("attack")] = {"initial_state": "default", "states": {
        "default": {"transitions": [{"swing": "query.is_delayed_attacking"}]},
        "swing": {"animations": ["attack"], "transitions": [{"default": "!query.is_delayed_attacking && query.all_animations_finished"}],
                  "blend_transition": 0.1}}}
    phase_fx_controller(c, "core")
    c.always("ambient", particles=[{"effect": "aura1", "locator": "eye"}])
    rp = client_entity(name, model, a, c,
                       ["idle", {"walk": "query.modified_move_speed"}, "look_at_target", "action_controller",
                        "attack_controller", "phase_controller", "ambient_controller"],
                       ("#020205", "#3ff3ff"),
                       render_controllers=[f"controller.render.{NS}.boss", RC_GLOW],
                       particles={"aura1": f"{NS}:null_mote", "aura2": f"{NS}:boss_aura_cyan",
                                  "aura3": f"{NS}:boss_aura_crimson"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("null_heart"), count=(1, 1))]},
        {"rolls": 1, "entries": [item_entry(ident("null_fragment"), count=(10, 16))]},
        {"rolls": 1, "entries": [item_entry(ident("null_edge"), weight=1), {"type": "empty", "weight": 2}]},
    ])
    write_entity(name, bp, rp, a, c, "The Null Colossus", loot)


# ================================================================================================
# mobs
# ================================================================================================

def hollow_shade():
    name = "hollow_shade"
    model = register_model(name, DENS_MOB)
    REG.add_texture(TexAsset(f"{ENT_TEX}/{name}_crimson",
                             lambda d, m=model: _recolor(m.paint(d, seed=91), "crimson"), DENS_MOB, pbr=True, glow=True))
    comps = mob_components(name, 24, 0.27, 0.7, 2.1, ["undead", "hollow", "shade"], 5)
    comps.update({
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True, "avoid_damage_blocks": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:behavior.melee_box_attack": {"priority": 3, "speed_multiplier": 1.2, "track_target": True},
        "minecraft:fire_immune": {},
        "minecraft:damage_sensor": {"triggers": [{"cause": "fall", "deals_damage": "no"}]},
    })
    groups = {
        f"{NS}:crimson": {"minecraft:attack": {"damage": 7}, "minecraft:movement": {"value": 0.31},
                          "minecraft:health": {"value": 30, "max": 30},
                          "minecraft:loot": {"table": f"loot_tables/entities/{NS}/{name}_crimson.json"}},
    }
    events = {f"{NS}:become_crimson": {"add": {"component_groups": [f"{NS}:crimson"]},
                                       "set_property": {f"{NS}:variant": "crimson"}}}
    props = {f"{NS}:variant": {"type": "enum", "values": ["hollow", "crimson"], "default": "hollow", "client_sync": True}}
    bp = entity_doc(name, comps, groups, events, props)
    a = AnimSet(name)
    a.add("idle", {
        "root": {"position": [0, bob(1.4, 2.4), 0]},
        "right_arm": {"rotation": [breathe(6, 2.4), 0, breathe(4, 3.1)]},
        "left_arm": {"rotation": [breathe(6, 2.4, 180), 0, breathe(-4, 3.1)]},
        "body": {"rotation": [breathe(3, 2.4, 90), 0, 0]},
    })
    a.add("move", {"body": {"rotation": [f"12 * query.modified_move_speed", 0, 0]},
                   "right_arm": {"rotation": [f"25 * query.modified_move_speed", 0, 0]},
                   "left_arm": {"rotation": [f"25 * query.modified_move_speed", 0, 0]}})
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}})
    a.add("attack", {
        "right_arm": {"rotation": ["-variable.attack_time * 160", 0, 0]},
        "left_arm": {"rotation": ["-variable.attack_time * 140", 0, 0]},
    })
    c = ControllerSet(name)
    c.always("ambient", particles=[{"effect": "wisp", "locator": "chest"}])
    rp = client_entity(name, model, a, c,
                       ["idle", {"move": "query.modified_move_speed"}, "look_at_target",
                        {"attack": "variable.attack_time > 0"}, "ambient_controller"],
                       ("#0b0614", "#7ff6ff"),
                       render_controllers=[f"controller.render.{NS}.hollow_shade", f"controller.render.{NS}.hollow_shade_glow"],
                       textures={"crimson": f"{ENT_TEX}/{name}_crimson", "glow_crimson": f"{ENT_TEX}/{name}_crimson_glow"},
                       particles={"wisp": f"{NS}:soul_wisp"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("soul_essence"), count=(1, 2), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry("minecraft:bone", count=(0, 2))]},
    ])
    write_entity(name, bp, rp, a, c, "Hollow Shade", loot)
    REG.add_bp(f"loot_tables/entities/{NS}/{name}_crimson.json", loot_table([
        {"rolls": 1, "entries": [item_entry(ident("soul_essence"), count=(1, 2), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry(ident("blood_crystal"), count=(1, 2), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry("minecraft:bone", count=(0, 2))]},
    ]))
    REG.add_bp(f"spawn_rules/{NS}/{name}.json", {
        "format_version": SPAWN_FMT,
        "minecraft:spawn_rules": {
            "description": {"identifier": ident(name), "population_control": "monster"},
            "conditions": [{
                "minecraft:spawns_on_surface": {},
                "minecraft:brightness_filter": {"min": 0, "max": 6, "adjust_for_weather": True},
                "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
                "minecraft:weight": {"default": 8},
                "minecraft:herd": {"min_size": 1, "max_size": 2},
                "minecraft:biome_filter": {"all_of": [{"test": "has_biome_tag", "value": "monster"},
                                                      {"test": "has_biome_tag", "value": "overworld"}]},
            }],
        },
    })


def void_crawler():
    name = "void_crawler"
    model = register_model(name, DENS_MOB)
    comps = mob_components(name, 22, 0.32, 1.3, 0.9, ["arthropod", "void"], 5)
    comps.update({
        "minecraft:navigation.climb": {"can_path_over_water": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:behavior.leap_at_target": {"priority": 3, "yd": 0.45, "must_be_on_ground": True},
        "minecraft:behavior.melee_box_attack": {"priority": 4, "speed_multiplier": 1.2, "track_target": True},
        "minecraft:attack": {"damage": 5, "effect_name": "slowness", "effect_duration": 3},
    })
    bp = entity_doc(name, comps)
    a = AnimSet(name)
    legs = {}
    for i in range(4):
        for side, sgn in (("r", 1), ("l", -1)):
            ph = (i * 90 + (0 if side == "r" else 180)) % 360
            legs[f"leg_{side}{i}"] = {"rotation": [0, swing(18, ph, rate=60), f"math.abs({swing(14, ph, rate=60)}) * {sgn}"]}
    a.add("walk", legs)
    a.add("idle", {"abdomen": {"scale": "1 + math.sin(query.life_time * 200) * 0.04", "rotation": [breathe(3, 2.0), 0, 0]}})
    a.add("look_at_target", {"head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.7", 0]}})
    rp = client_entity(name, model, a, None, ["idle", {"walk": "query.modified_move_speed"}, "look_at_target"],
                       ("#07060c", "#b98cff"))
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("void_ichor"), count=(1, 2), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry("minecraft:string", count=(0, 2))]},
    ])
    write_entity(name, bp, rp, a, None, "Void Crawler", loot)


def astral_mite():
    name = "astral_mite"
    model = register_model(name, DENS_MOB)
    comps = mob_components(name, 10, 0.36, 0.6, 0.6, ["arthropod", "astral"], 3)
    comps.update({
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:behavior.leap_at_target": {"priority": 3, "yd": 0.4, "must_be_on_ground": True},
        "minecraft:behavior.melee_box_attack": {"priority": 4, "speed_multiplier": 1.3, "track_target": True},
        "minecraft:fire_immune": {},
        "minecraft:despawn": {"despawn_from_distance": {"min_distance": 24, "max_distance": 64}},
    })
    bp = entity_doc(name, comps)
    a = AnimSet(name)
    legs = {}
    for i in range(3):
        for side in ("r", "l"):
            ph = (i * 120 + (0 if side == "r" else 180)) % 360
            legs[f"leg_{side}{i}"] = {"rotation": [0, swing(25, ph, rate=90), 0]}
    a.add("walk", legs)
    a.add("idle", {"shell": {"rotation": [0, "query.life_time * 20", 0]}, "body": {"position": [0, bob(0.3, 1.0), 0]}})
    c = ControllerSet(name)
    c.always("ambient", particles=[{"effect": "spark"}])
    rp = client_entity(name, model, a, c, ["idle", {"walk": "query.modified_move_speed"}, "ambient_controller"],
                       ("#3a2608", "#ffe58a"), particles={"spark": f"{NS}:star_spark"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("stardust"), count=(1, 3), looting=True)]},
    ])
    write_entity(name, bp, rp, a, c, "Astral Mite", loot)


def thornling():
    name = "thornling"
    model = register_model(name, DENS_MOB)
    comps = mob_components(name, 16, 0.28, 0.7, 1.6, ["plant", "thornling"], 4)
    comps.update({
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True, "avoid_damage_blocks": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:behavior.melee_box_attack": {"priority": 3, "speed_multiplier": 1.15, "track_target": True},
        "minecraft:attack": {"damage": 4, "effect_name": "poison", "effect_duration": 3},
    })
    bp = entity_doc(name, comps)
    a = AnimSet(name)
    a.add("walk", {"right_leg": {"rotation": [swing(35), 0, 0]}, "left_leg": {"rotation": [swing(35, 180), 0, 0]},
                   "right_arm": {"rotation": [swing(25, 180), 0, 0]}, "left_arm": {"rotation": [swing(25), 0, 0]}})
    a.add("idle", {"head": {"rotation": [0, 0, breathe(4, 3.0)]}})
    a.add("attack", {"right_arm": {"rotation": ["-variable.attack_time * 150", 0, 0]},
                     "left_arm": {"rotation": ["-variable.attack_time * 150", 0, 0]}})
    rp = client_entity(name, model, a, None,
                       ["idle", {"walk": "query.modified_move_speed"}, {"attack": "variable.attack_time > 0"}],
                       ("#2e2013", "#9cff5a"))
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("living_bark"), count=(1, 2), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry("minecraft:stick", count=(0, 2))]},
    ])
    write_entity(name, bp, rp, a, None, "Thornling", loot)
    REG.add_bp(f"spawn_rules/{NS}/{name}.json", {
        "format_version": SPAWN_FMT,
        "minecraft:spawn_rules": {
            "description": {"identifier": ident(name), "population_control": "monster"},
            "conditions": [{
                "minecraft:spawns_on_surface": {},
                "minecraft:brightness_filter": {"min": 0, "max": 15, "adjust_for_weather": False},
                "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
                "minecraft:weight": {"default": 30},
                "minecraft:herd": {"min_size": 1, "max_size": 3},
                "minecraft:biome_filter": {"test": "has_biome_tag", "value": "apocalypse_blight"},
            }],
        },
    })


def rift_sentinel():
    name = "rift_sentinel"
    model = register_model(name, DENS_MOB)
    comps = mob_components(name, 40, 0.25, 1.0, 2.0, ["construct", "sentinel"], 6, despawn=False)
    comps.update({
        "minecraft:can_fly": {},
        "minecraft:flying_speed": {"value": 0.14},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:navigation.hover": {"can_path_over_water": True, "can_path_from_air": True, "can_sink": False,
                                        "avoid_damage_blocks": True},
        "minecraft:movement.hover": {},
        "minecraft:behavior.ranged_attack": {"priority": 3, "attack_interval": 2.6, "attack_radius": 20.0,
                                             "burst_shots": 2, "burst_interval": 0.4, "charge_shoot_trigger": 2.0},
        "minecraft:shooter": {"def": ident("star_bolt")},
        "minecraft:behavior.random_hover": {"priority": 7, "xz_dist": 8, "y_dist": 4, "interval": 80,
                                            "hover_height": {"min": 2, "max": 5}},
        "minecraft:damage_sensor": {"triggers": [{"cause": "fall", "deals_damage": "no"},
                                                 {"cause": "projectile", "deals_damage": "yes", "damage_multiplier": 0.5}]},
        "minecraft:fire_immune": {},
        "minecraft:despawn": {"despawn_from_distance": {"min_distance": 48, "max_distance": 128}},
    })
    del comps["minecraft:behavior.random_stroll"]
    del comps["minecraft:pushable_by_entity"]
    bp = entity_doc(name, comps)
    a = AnimSet(name)
    a.add("idle", {"body": {"position": [0, bob(1.5, 2.5), 0]},
                   "shards": {"rotation": [0, "query.life_time * 90", 0]},
                   "right_hand": {"position": [0, bob(0.8, 2.0, 90), 0]},
                   "left_hand": {"position": [0, bob(0.8, 2.0, 270), 0]}})
    a.add("charge", {"right_hand": {"position": [0, 0, -3]}, "left_hand": {"position": [0, 0, -3]},
                     "shards": {"rotation": [0, "query.life_time * 400", 0]}})
    c = ControllerSet(name)
    c.always("ambient", particles=[{"effect": "mote", "locator": "eye"}])
    rp = client_entity(name, model, a, c, ["idle", {"charge": "query.is_charging"}, "ambient_controller"],
                       ("#020205", "#3ff3ff"), particles={"mote": f"{NS}:null_mote"})
    loot = loot_table([
        {"rolls": 1, "entries": [item_entry(ident("null_fragment"), count=(1, 3), looting=True)],
         "conditions": [{"condition": "killed_by_player"}]},
        {"rolls": 1, "entries": [item_entry(ident("aether_crystal"), weight=1), {"type": "empty", "weight": 3}]},
    ])
    write_entity(name, bp, rp, a, c, "Rift Sentinel", loot)


# ================================================================================================
# projectiles, hazards, portals
# ================================================================================================

def star_bolt():
    name = "star_bolt"
    model = register_model(name, DENS_MOB)
    REG.add_texture(TexAsset(f"{ENT_TEX}/{name}_null", lambda d, m=model: _recolor(m.paint(d, seed=5), "null"),
                             DENS_MOB, pbr=True, glow=True))
    comps = {
        "minecraft:type_family": {"family": ["projectile", NS, "star_bolt"]},
        "minecraft:collision_box": {"width": 0.35, "height": 0.35},
        "minecraft:physics": {},
        "minecraft:pushable_by_block": {},
        "minecraft:conditional_bandwidth_optimization": {"default_values": {"max_optimized_distance": 80.0,
                                                                            "max_dropped_ticks": 7,
                                                                            "use_motion_prediction_hints": True}},
        "minecraft:projectile": {
            "anchor": "middle", "gravity": 0.0, "inertia": 1, "liquid_inertia": 1, "power": 1.4,
            "uncertainty_base": 4.0, "reflect_on_hurt": True, "offset": [0, 0.4, 0],
            "on_hit": {"impact_damage": {"damage": 6, "knockback": True, "apply_knockback_to_blocking_targets": True},
                       "remove_on_hit": {}},
        },
        "minecraft:timer": {"looping": False, "time": 8, "time_down_event": {"event": f"{NS}:expire"}},
    }
    groups = {f"{NS}:expire": {"minecraft:instant_despawn": {}}}
    events = {f"{NS}:expire": {"add": {"component_groups": [f"{NS}:expire"]}}}
    props = {f"{NS}:variant": {"type": "enum", "values": ["star", "null"], "default": "star", "client_sync": True}}
    bp = entity_doc(name, comps, groups, events, props, spawnable=False, category="misc")
    a = AnimSet(name)
    a.add("spin", {"bolt": {"rotation": [0, 0, "query.life_time * 720"]}})
    c = ControllerSet(name)
    c.always("trail", particles=[{"effect": "trail"}])
    rp = client_entity(name, model, a, c, ["spin", "trail_controller"], None,
                       render_controllers=[f"controller.render.{NS}.star_bolt", f"controller.render.{NS}.star_bolt_glow"],
                       textures={"null": f"{ENT_TEX}/{name}_null", "glow_null": f"{ENT_TEX}/{name}_null_glow"},
                       particles={"trail": f"{NS}:bolt_trail"})
    write_entity(name, bp, rp, a, c, "Star Bolt")


def meteor():
    name = "meteor"
    model = register_model(name, DENS_MOB)
    comps = {
        "minecraft:type_family": {"family": ["projectile", NS, "meteor"]},
        "minecraft:collision_box": {"width": 0.9, "height": 0.9},
        "minecraft:physics": {},
        "minecraft:fire_immune": {},
        "minecraft:conditional_bandwidth_optimization": {"default_values": {"max_optimized_distance": 160.0,
                                                                            "max_dropped_ticks": 5,
                                                                            "use_motion_prediction_hints": True}},
        "minecraft:projectile": {
            "anchor": "middle", "gravity": 0.04, "inertia": 1, "liquid_inertia": 0.8, "power": 1.0,
            "uncertainty_base": 0.0,
            "on_hit": {"impact_damage": {"damage": 10, "knockback": True, "catch_fire": True},
                       "remove_on_hit": {}},
        },
        "minecraft:timer": {"looping": False, "time": 20, "time_down_event": {"event": f"{NS}:expire"}},
    }
    groups = {f"{NS}:expire": {"minecraft:instant_despawn": {}}}
    events = {f"{NS}:expire": {"add": {"component_groups": [f"{NS}:expire"]}}}
    bp = entity_doc(name, comps, groups, events, spawnable=False, category="misc")
    a = AnimSet(name)
    a.add("tumble", {"rock": {"rotation": ["query.life_time * 200", "query.life_time * 90", 0]}})
    c = ControllerSet(name)
    c.always("trail", particles=[{"effect": "trail"}])
    rp = client_entity(name, model, a, c, ["tumble", "trail_controller"], None,
                       particles={"trail": f"{NS}:meteor_trail"})
    write_entity(name, bp, rp, a, c, "Meteor")


def void_rift():
    name = "void_rift"
    model = register_model(name, DENS_MOB)
    comps = {
        "minecraft:type_family": {"family": [NS, "hazard", "void_rift", "inanimate"]},
        "minecraft:health": {"value": 30, "max": 30},
        "minecraft:collision_box": {"width": 1.2, "height": 2.2},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:damage_sensor": {"triggers": [
            {"on_damage": {"filters": is_family("player")}, "deals_damage": "yes"},
            {"deals_damage": "no"},
        ]},
        "minecraft:loot": {"table": f"loot_tables/entities/{NS}/{name}.json"},
        "minecraft:experience_reward": {"on_death": "8"},
        "minecraft:timer": {"looping": False, "time": 90, "time_down_event": {"event": f"{NS}:expire"}},
    }
    groups = {f"{NS}:expire": {"minecraft:instant_despawn": {}}}
    events = {f"{NS}:expire": {"add": {"component_groups": [f"{NS}:expire"]}}}
    bp = entity_doc(name, comps, groups, events, category="misc")
    a = AnimSet(name)
    a.add("swirl", {"tear": {"rotation": [0, "query.life_time * 40", 0],
                             "scale": "1 + math.sin(query.life_time * 180) * 0.06"},
                    "core": {"rotation": ["query.life_time * 120", "query.life_time * 200", 0]}})
    c = ControllerSet(name)
    c.always("fx", particles=[{"effect": "swirl"}])
    rp = client_entity(name, model, a, c, ["swirl", "fx_controller"], ("#05030b", "#d8a8ff"),
                       materials={"default": "entity_alphatest"}, particles={"swirl": f"{NS}:void_swirl"})
    loot = loot_table([{"rolls": 1, "entries": [item_entry(ident("null_fragment"), count=(1, 3))]}])
    write_entity(name, bp, rp, a, c, "Void Rift", loot)


def rift_portal():
    name = "rift_portal"
    model = register_model(name, DENS_MOB)
    comps = {
        "minecraft:type_family": {"family": [NS, "portal", "inanimate"]},
        "minecraft:health": {"value": 100, "max": 100},
        "minecraft:collision_box": {"width": 0.5, "height": 0.5},
        "minecraft:physics": {"has_gravity": False, "has_collision": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:persistent": {},
        "minecraft:damage_sensor": {"triggers": [{"deals_damage": "no"}]},
    }
    groups = {f"{NS}:expire": {"minecraft:instant_despawn": {}}}
    events = {f"{NS}:expire": {"add": {"component_groups": [f"{NS}:expire"]}}}
    bp = entity_doc(name, comps, groups, events, spawnable=False, category="misc")
    a = AnimSet(name)
    a.add("spin", {"stones": {"rotation": [0, 0, "query.life_time * 25"]},
                   "gate": {"scale": "1 + math.sin(query.life_time * 120) * 0.03"}})
    c = ControllerSet(name)
    c.always("fx", particles=[{"effect": "glow"}])
    rp = client_entity(name, model, a, c, ["spin", "fx_controller"], None,
                       particles={"glow": f"{NS}:portal_glow"})
    write_entity(name, bp, rp, a, c, "Rift Portal")


# ------------------------------------------------------------------------------------------------
# texture variants
# ------------------------------------------------------------------------------------------------

def _recolor(cv, scheme: str):
    """Hue-shift a painted canvas for variants (crimson shade, null bolt)."""
    import numpy as np
    rgb = cv.rgba[..., :3]
    if scheme == "crimson":
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        cool = np.clip(b - r, 0, 1)
        new = np.stack([np.clip(lum * 1.1 + cool * 1.4, 0, 1), lum * 0.35, lum * 0.4], axis=-1)
        cv.rgba[..., :3] = new
    elif scheme == "null":
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        cv.rgba[..., :3] = np.stack([g * 0.7, r * 0.35, np.clip(r * 1.1 + 0.15, 0, 1)], axis=-1)
    return cv


def render_controllers() -> dict:
    boss_overlay = {"r": 1.0, "g": 0.08, "b": 0.12,
                    "a": f"query.property('{NS}:phase') == 3 ? 0.10 + math.abs(math.sin(query.life_time * 200)) * 0.12 : 0"}
    return {
        "format_version": "1.8.0",
        "render_controllers": {
            RC_DEFAULT: {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
                         "textures": ["Texture.default"]},
            RC_GLOW: {"geometry": "Geometry.default", "materials": [{"*": "Material.glow"}],
                      "textures": ["Texture.glow"]},
            f"controller.render.{NS}.boss": {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
                                              "textures": ["Texture.default"], "overlay_color": boss_overlay},
            f"controller.render.{NS}.hollow_shade": {
                "arrays": {"textures": {"Array.skins": ["Texture.default", "Texture.crimson"]}},
                "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
                "textures": [f"Array.skins[query.property('{NS}:variant') == 'crimson' ? 1 : 0]"]},
            f"controller.render.{NS}.hollow_shade_glow": {
                "arrays": {"textures": {"Array.glows": ["Texture.glow", "Texture.glow_crimson"]}},
                "geometry": "Geometry.default", "materials": [{"*": "Material.glow"}],
                "textures": [f"Array.glows[query.property('{NS}:variant') == 'crimson' ? 1 : 0]"]},
            f"controller.render.{NS}.star_bolt": {
                "arrays": {"textures": {"Array.skins": ["Texture.default", "Texture.null"]}},
                "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
                "textures": [f"Array.skins[query.property('{NS}:variant') == 'null' ? 1 : 0]"]},
            f"controller.render.{NS}.star_bolt_glow": {
                "arrays": {"textures": {"Array.glows": ["Texture.glow", "Texture.glow_null"]}},
                "geometry": "Geometry.default", "materials": [{"*": "Material.glow"}],
                "textures": [f"Array.glows[query.property('{NS}:variant') == 'null' ? 1 : 0]"]},
        },
    }


def build():
    for fn in (hollow_king, star_eater, root_titan, null_colossus, hollow_shade, void_crawler, astral_mite,
               thornling, rift_sentinel, star_bolt, meteor, void_rift, rift_portal):
        fn()
    REG.add_rp(f"render_controllers/{NS}.render_controllers.json", render_controllers())
    for boss, acts in ACTIONS.items():
        for aid, aname in acts.items():
            REG.ts(f"actions_{boss}", aname.upper(), str(aid))
