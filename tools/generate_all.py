#!/usr/bin/env python3
"""Regenerate every generated asset of APOCALYPSE ENGINE deterministically.

Writes behavior_pack/ and resource_pack/ content (JSON, textures for all quality tiers, sounds,
structures) and src/scripts/generated/ids.ts. Compiled scripts in behavior_pack/scripts are left
untouched (they come from `tsc`).

Usage: python3 tools/generate_all.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.content import audio, blocks, entities, items, packs, particles, world  # noqa: E402
from tools.content.registry import REG  # noqa: E402
from tools.lib import jsonio, tex  # noqa: E402

BP = os.path.join(ROOT, "behavior_pack")
RP = os.path.join(ROOT, "resource_pack")
BP_KEEP = {"scripts"}


def clean():
    if os.path.isdir(BP):
        for name in os.listdir(BP):
            if name in BP_KEEP:
                continue
            p = os.path.join(BP, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    if os.path.isdir(RP):
        shutil.rmtree(RP)
    os.makedirs(BP, exist_ok=True)
    os.makedirs(RP, exist_ok=True)


def write_textures():
    count = 0
    for path, asset in sorted(REG.textures.items()):
        for tier in ("base", "balanced", "enhanced"):
            out = asset.render(tier)
            base_dir = RP if tier == "base" else os.path.join(RP, "subpacks", tier)
            name = os.path.basename(path)
            target = os.path.join(base_dir, path)
            tex.save_png(out["color"], target + ".png")
            count += 1
            if "glow" in out:
                tex.save_png(out["glow"], target + "_glow.png")
                count += 1
            if "mer" in out:
                tex.save_png(out["mer"], target + "_mer.png")
                count += 1
                layers = {"color": name, "metalness_emissive_roughness": name + "_mer"}
                if "normal" in out:
                    tex.save_png(out["normal"], target + "_normal.png")
                    layers["normal"] = name + "_normal"
                    count += 1
                jsonio.write(target + ".texture_set.json", {"format_version": "1.21.30", "minecraft:texture_set": layers})
            # glow overlays get their own colour-only texture sets so Vibrant Visuals treats them consistently
    return count


def main():
    t0 = time.time()
    clean()
    entities.build()
    items.build()
    blocks.build()
    world.build()
    particles.build()
    audio.build()
    packs.build()

    for path, obj in REG.bp.items():
        jsonio.write(os.path.join(BP, path), obj)
    for path, obj in REG.rp.items():
        jsonio.write(os.path.join(RP, path), obj)
    for path, data in REG.bp_bin.items():
        os.makedirs(os.path.dirname(os.path.join(BP, path)), exist_ok=True)
        with open(os.path.join(BP, path), "wb") as f:
            f.write(data)
    for path, data in REG.rp_bin.items():
        os.makedirs(os.path.dirname(os.path.join(RP, path)), exist_ok=True)
        with open(os.path.join(RP, path), "wb") as f:
            f.write(data)
    for tier, files in REG.subpack_json.items():
        for path, obj in files.items():
            jsonio.write(os.path.join(RP, "subpacks", tier, path), obj)
    for key, img in REG.images.items():
        where, rel = key.split(":", 1)
        tex.save_png(img, os.path.join(BP if where == "bp" else RP, rel))

    jsonio.write(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": "apocalypse", "texture_name": "atlas.items",
        "texture_data": {k: {"textures": v} for k, v in sorted(REG.item_textures.items())}})
    jsonio.write(os.path.join(RP, "textures", "terrain_texture.json"), {
        "resource_pack_name": "apocalypse", "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4,
        "texture_data": {k: {"textures": v} for k, v in sorted(REG.terrain_textures.items())}})
    jsonio.write(os.path.join(RP, "blocks.json"), {"format_version": [1, 1, 0], **dict(sorted(REG.blocks_json.items()))})
    jsonio.write(os.path.join(RP, "sounds", "sound_definitions.json"),
                 {"format_version": "1.20.20", "sound_definitions": dict(sorted(REG.sound_defs.items()))})
    jsonio.write(os.path.join(RP, "sounds.json"), {"entity_sounds": {"entities": dict(sorted(REG.entity_sounds.items()))}})
    jsonio.write_text(os.path.join(RP, "texts", "en_US.lang"), packs.lang_text(REG.lang))
    jsonio.write(os.path.join(RP, "texts", "languages.json"), ["en_US"])
    jsonio.write_text(os.path.join(ROOT, "src", "scripts", "generated", "ids.ts"), packs.ts_ids())

    n_tex = write_textures()
    print(f"generated: {len(REG.bp)} BP json, {len(REG.rp)} RP json, {len(REG.bp_bin)} structures, "
          f"{len(REG.rp_bin)} sounds, {n_tex} texture files, {len(REG.lang)} lang keys "
          f"in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
