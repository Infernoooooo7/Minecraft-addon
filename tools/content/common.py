"""Shared constants and small JSON builders for APOCALYPSE ENGINE content."""
from __future__ import annotations

NS = "apocalypse"
ENTITY_FMT = "1.26.30"
ITEM_FMT = "1.26.30"
BLOCK_FMT = "1.26.30"
RECIPE_FMT = "1.20.10"
SPAWN_FMT = "1.8.0"
FEATURE_FMT = "1.21.20"

ENT_TEX = "textures/entity/apocalypse"
ITEM_TEX = "textures/items/apocalypse"
BLOCK_TEX = "textures/blocks/apocalypse"
ARMOR_TEX = "textures/models/armor/apocalypse"
PARTICLE_TEX = "textures/particle/apocalypse_particles"

# densities per tier (texels per model unit / per base 16px)
DENS_BOSS = {"base": 1, "balanced": 2, "enhanced": 2}
DENS_MOB = {"base": 1, "balanced": 2, "enhanced": 4}
DENS_ICON = {"base": 1, "balanced": 2, "enhanced": 4}     # icons painted at 16*density px
DENS_BLOCK = {"base": 1, "balanced": 2, "enhanced": 2}    # blocks painted at 16*density px
DENS_ARMOR = {"base": 1, "balanced": 2, "enhanced": 4}


def ident(name: str) -> str:
    return f"{NS}:{name}"


def is_family(value: str, subject: str = "other", operator: str | None = None) -> dict:
    f = {"test": "is_family", "subject": subject, "value": value}
    if operator:
        f["operator"] = operator
    return f


def player_targets(max_dist: float = 32, must_see: bool = False, extra: list | None = None) -> dict:
    types = [{"filters": is_family("player"), "max_dist": max_dist}]
    if extra:
        types.extend(extra)
    return types


def loot_table(pools: list) -> dict:
    return {"pools": pools}


def item_entry(item: str, weight: int = 1, count: tuple[int, int] | None = None, looting: bool = False,
               extra_functions: list | None = None) -> dict:
    e: dict = {"type": "item", "name": item, "weight": weight}
    fns = []
    if count:
        fns.append({"function": "set_count", "count": {"min": count[0], "max": count[1]}})
    if looting:
        fns.append({"function": "looting_enchant", "count": {"min": 0, "max": 1}})
    if extra_functions:
        fns.extend(extra_functions)
    if fns:
        e["functions"] = fns
    return e
