#!/usr/bin/env python3
"""APOCALYPSE ENGINE static validator.

Checks both packs for JSON syntax, manifest correctness, UUID uniqueness, dependency links and
every cross-reference between files (entities <-> client entities <-> geometry bones/locators <->
animations <-> controllers <-> render controllers <-> textures <-> particles <-> sounds <-> loot
tables <-> recipes <-> features <-> structures <-> lang), plus image/texture-set sanity and script
import / identifier checks.

Optional, stronger checks when available:
  * Mojang's official JSON schemas (bedrock-samples/metadata/json_schemas) — pass --schemas PATH
    or set BEDROCK_SAMPLES. Adds schema validation, a per-format-version component whitelist and a
    comparison of field names against vanilla usage.
  * @minecraft/vanilla-data (node_modules) — validates every minecraft:* item/block/entity id.

Usage: python3 validate.py [--root DIR] [--schemas PATH] [--report FILE] [--json FILE]
Exit code 0 = no errors (warnings allowed).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import struct
import sys
from collections import defaultdict

ROOT_DEFAULT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DEFAULT)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
NS = "apocalypse"
VANILLA_RENDER_CONTROLLERS = {"controller.render.default", "controller.render.armor", "controller.render.armor.v2"}
VANILLA_MATERIALS = {"entity", "entity_alphatest", "entity_alphablend", "entity_emissive", "entity_emissive_alpha",
                     "entity_emissive_alpha_one_sided", "entity_nocull", "entity_change_color", "entity_glint",
                     "entity_alphatest_glint", "armor", "armor_enchanted"}
VANILLA_PARTICLE_MATERIALS = {"particles_base", "particles_opaque", "particles_alpha", "particles_blend", "particles_add"}
VANILLA_GEOMETRY_PREFIXES = ("geometry.humanoid.armor.", "geometry.player.armor.")
BLOCK_SOUNDS = {"stone", "wood", "gravel", "grass", "sand", "metal", "glass", "cloth", "snow", "ladder", "anvil",
                "slime", "honey_block", "deepslate", "amethyst_block", "amethyst_cluster", "moss_block", "netherrack",
                "nether_brick", "basalt", "bone_block", "calcite", "copper", "tuff", "mud", "packed_mud", "sculk",
                "lantern", "nylium", "fungus", "roots", "vines", "coral", "powder_snow", "dripstone_block",
                "chain", "candle", "azalea", "frog_spawn", "cherry_wood", "bamboo_wood", "decorated_pot",
                "trial_spawner", "vault", "heavy_core", "suspicious_sand", "suspicious_gravel"}
SCRIPT_MODULES = {"@minecraft/server", "@minecraft/server-ui"}


class Results:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: dict[str, int] = defaultdict(int)
        self.notes: list[str] = []

    def ok(self, check: str, n: int = 1):
        self.passes[check] += n

    def err(self, check: str, msg: str):
        self.errors.append(f"[{check}] {msg}")

    def warn(self, check: str, msg: str):
        self.warnings.append(f"[{check}] {msg}")


def load_json(path: str, R: Results, check="JSON"):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        if txt.startswith("﻿"):
            R.warn(check, f"{path}: UTF-8 BOM present")
            txt = txt[1:]
        data = json.loads(txt)
        R.ok(check)
        return data
    except Exception as e:  # noqa: BLE001
        R.err(check, f"{path}: invalid JSON: {e}")
        return None


def png_info(path: str):
    """Return (width, height, color_type) from a PNG header without decoding."""
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    color_type = head[25]
    return w, h, color_type


def is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


# ------------------------------------------------------------------------------------------------
# vanilla ids from @minecraft/vanilla-data
# ------------------------------------------------------------------------------------------------

def load_vanilla_ids(root: str):
    p = os.path.join(root, "node_modules", "@minecraft", "vanilla-data", "lib", "index.js")
    if not os.path.isfile(p):
        return None
    txt = open(p, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"var (Minecraft\w+Types)=\(\w+=>\{(.*?)\}\)\(", txt, re.S):
        out[m.group(1)] = set(re.findall(r'="(minecraft:[a-z0-9_.]+)"', m.group(2)))
    return out


# ------------------------------------------------------------------------------------------------
# main validator
# ------------------------------------------------------------------------------------------------

class Validator:
    def __init__(self, root: str, schema_root: str | None):
        self.root = root
        self.bp = os.path.join(root, "behavior_pack")
        self.rp = os.path.join(root, "resource_pack")
        self.R = Results()
        self.vanilla = load_vanilla_ids(root)
        self.schemas = None
        self.vanilla_fields = None
        if schema_root:
            try:
                from tools.schema_check import SchemaSet
                self.schemas = SchemaSet(schema_root)
                self.R.notes.append(f"Official Mojang JSON schemas loaded from {schema_root}")
                self.vanilla_fields = self._vanilla_field_usage(schema_root)
            except Exception as e:  # noqa: BLE001
                self.R.warn("SCHEMA", f"could not load schemas: {e}")
        else:
            self.R.notes.append("Official schema validation skipped (no bedrock-samples checkout provided)")
        if self.vanilla is None:
            self.R.notes.append("Vanilla id checks skipped (node_modules/@minecraft/vanilla-data not installed)")
        else:
            self.R.notes.append("Vanilla ids checked against @minecraft/vanilla-data "
                                + json.load(open(os.path.join(root, "node_modules", "@minecraft", "vanilla-data", "package.json")))["version"])

    # helpers -----------------------------------------------------------------------------------
    def rel(self, p):
        return os.path.relpath(p, self.root)

    def jsons(self, base, sub):
        return sorted(glob.glob(os.path.join(base, sub, "**", "*.json"), recursive=True))

    def vanilla_has(self, kind: str, ident: str) -> bool | None:
        if self.vanilla is None:
            return None
        table = {"item": ["MinecraftItemTypes", "MinecraftBlockTypes"], "block": ["MinecraftBlockTypes"],
                 "entity": ["MinecraftEntityTypes"], "effect": ["MinecraftEffectTypes"]}[kind]
        if kind == "effect":
            ident = ident if ident.startswith("minecraft:") else "minecraft:" + ident
        return any(ident in self.vanilla.get(t, set()) for t in table)

    def _vanilla_field_usage(self, schema_root):
        samples = os.path.abspath(os.path.join(schema_root, "..", "..", "behavior_pack", "entities"))
        if not os.path.isdir(samples):
            return None
        from tools.lib.jsonio import load_lenient
        usage = defaultdict(set)
        for f in glob.glob(os.path.join(samples, "*.json")):
            try:
                ent = load_lenient(f)["minecraft:entity"]
            except Exception:  # noqa: BLE001
                continue
            for g in [ent.get("components", {})] + list(ent.get("component_groups", {}).values()):
                for k, v in g.items():
                    if isinstance(v, dict):
                        usage[k].update(v.keys())
        return usage

    # ------------------------------------------------------------------------------------------
    def run(self):
        R = self.R
        for d in (self.bp, self.rp):
            if not os.path.isdir(d):
                R.err("STRUCTURE", f"missing pack folder {self.rel(d)}")
                return R
        self.all_json()
        self.manifests()
        self.lang = self.load_lang()
        self.geometry = self.load_geometry()
        self.textures = self.index_textures()
        self.particles = self.load_particles()
        self.sound_defs = self.load_sounds()
        self.items, self.blocks = self.check_items_blocks()
        self.entities = self.check_entities()
        self.check_client_entities()
        self.check_attachables()
        self.check_loot_tables()
        self.check_recipes()
        self.check_spawn_rules()
        self.check_world()
        self.check_texture_sets()
        self.check_images()
        self.check_scripts()
        self.check_empty_dirs()
        return R

    # ------------------------------------------------------------------------------------------
    def all_json(self):
        for base in (self.bp, self.rp):
            for p in sorted(glob.glob(os.path.join(base, "**", "*.json"), recursive=True)):
                load_json(p, self.R)

    def manifests(self):
        R = self.R
        uuids = []
        self.bp_manifest = load_json(os.path.join(self.bp, "manifest.json"), R, "MANIFEST")
        self.rp_manifest = load_json(os.path.join(self.rp, "manifest.json"), R, "MANIFEST")
        for name, man, base in (("BP", self.bp_manifest, self.bp), ("RP", self.rp_manifest, self.rp)):
            if not man:
                continue
            if man.get("format_version") != 2:
                R.err("MANIFEST", f"{name}: format_version must be 2")
            h = man.get("header", {})
            for key in ("name", "description", "uuid", "version", "min_engine_version"):
                if key not in h:
                    R.err("MANIFEST", f"{name}: header.{key} missing")
            for key in ("version", "min_engine_version"):
                v = h.get(key)
                if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) for x in v)):
                    R.err("MANIFEST", f"{name}: header.{key} must be [a,b,c]")
            uuids.append((f"{name} header", h.get("uuid")))
            for m in man.get("modules", []):
                uuids.append((f"{name} module {m.get('type')}", m.get("uuid")))
                if m.get("type") not in ("data", "resources", "script"):
                    R.err("MANIFEST", f"{name}: unknown module type {m.get('type')}")
                if m.get("type") == "script":
                    if m.get("language") != "javascript":
                        R.err("MANIFEST", f"{name}: script module language must be javascript")
                    entry = os.path.join(base, m.get("entry", ""))
                    if not os.path.isfile(entry):
                        R.err("MANIFEST", f"{name}: script entry {m.get('entry')} missing")
                    else:
                        R.ok("MANIFEST script entry")
            if not os.path.isfile(os.path.join(base, "pack_icon.png")):
                R.err("MANIFEST", f"{name}: pack_icon.png missing")
            else:
                info = png_info(os.path.join(base, "pack_icon.png"))
                if not info or info[0] != info[1] or not is_pow2(info[0]):
                    R.err("MANIFEST", f"{name}: pack_icon.png must be square power-of-two")
                else:
                    R.ok("MANIFEST pack icon")
        for label, u in uuids:
            if not isinstance(u, str) or not UUID_RE.match(u):
                R.err("UUID", f"{label}: invalid uuid {u}")
        vals = [u for _, u in uuids]
        if len(set(vals)) != len(vals):
            R.err("UUID", "duplicate UUIDs across packs/modules")
        else:
            R.ok("UUID unique", len(vals))
        if self.bp_manifest and self.rp_manifest:
            rp_uuid = self.rp_manifest["header"]["uuid"]
            rp_ver = self.rp_manifest["header"]["version"]
            deps = self.bp_manifest.get("dependencies", [])
            pack_deps = [d for d in deps if "uuid" in d]
            if not any(d["uuid"] == rp_uuid and d.get("version") == rp_ver for d in pack_deps):
                R.err("PACKDEP", "behavior pack does not depend on the resource pack header uuid+version")
            else:
                R.ok("PACKDEP BP->RP")
            if any(d.get("uuid") == self.bp_manifest["header"]["uuid"] for d in self.rp_manifest.get("dependencies", [])):
                R.err("PACKDEP", "resource pack depends back on behavior pack (circular)")
            mods = {d.get("module_name"): d.get("version") for d in deps if "module_name" in d}
            for mname in mods:
                if mname not in SCRIPT_MODULES:
                    R.err("PACKDEP", f"unexpected script module dependency {mname}")
            if "@minecraft/server" not in mods:
                R.err("PACKDEP", "missing @minecraft/server dependency")
            else:
                R.ok("PACKDEP script modules", len(mods))
            for sp in self.rp_manifest.get("subpacks", []):
                d = os.path.join(self.rp, "subpacks", sp.get("folder_name", ""))
                if not os.path.isdir(d) or not os.listdir(d):
                    R.err("SUBPACK", f"subpack folder {sp.get('folder_name')} missing or empty")
                elif not isinstance(sp.get("memory_tier"), int):
                    R.err("SUBPACK", f"subpack {sp.get('folder_name')} memory_tier must be an integer")
                else:
                    R.ok("SUBPACK")
            caps = self.rp_manifest.get("capabilities", [])
            for c in caps:
                if c not in ("pbr", "raytraced", "chemistry", "editorExtension", "experimental_custom_ui"):
                    R.err("MANIFEST", f"unknown capability {c}")
            if "pbr" in caps and self.rp_manifest["header"]["min_engine_version"] < [1, 21, 120]:
                R.err("MANIFEST", "pbr capability requires min_engine_version >= 1.21.120")

    # ------------------------------------------------------------------------------------------
    def load_lang(self):
        lang = {}
        p = os.path.join(self.rp, "texts", "en_US.lang")
        if not os.path.isfile(p):
            self.R.err("LANG", "resource_pack/texts/en_US.lang missing")
            return lang
        for line in open(p, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("##"):
                continue
            if "=" not in line:
                self.R.err("LANG", f"bad lang line: {line}")
                continue
            k, v = line.split("=", 1)
            if k in lang:
                self.R.err("LANG", f"duplicate lang key {k}")
            lang[k] = v.split("\t#")[0]
        if not os.path.isfile(os.path.join(self.rp, "texts", "languages.json")):
            self.R.err("LANG", "texts/languages.json missing")
        self.R.ok("LANG keys", len(lang))
        return lang

    def load_geometry(self):
        geo = {}
        for p in self.jsons(self.rp, "models"):
            d = load_json(p, Results())
            for g in (d or {}).get("minecraft:geometry", []):
                gid = g["description"]["identifier"]
                if gid in geo:
                    self.R.err("GEOMETRY", f"duplicate geometry {gid}")
                bones = {b["name"]: b for b in g.get("bones", [])}
                locators = set()
                for b in g.get("bones", []):
                    if b.get("parent") and b["parent"] not in bones:
                        self.R.err("GEOMETRY", f"{gid}: bone {b['name']} parent {b['parent']} missing")
                    locators.update((b.get("locators") or {}).keys())
                    for c in b.get("cubes", []):
                        u, v = c["uv"]
                        w, h, dd = c["size"]
                        if u + 2 * (w + dd) > g["description"]["texture_width"] or v + dd + h > g["description"]["texture_height"]:
                            self.R.err("GEOMETRY", f"{gid}: cube UV outside texture in bone {b['name']}")
                geo[gid] = {"bones": set(bones), "locators": locators, "tw": g["description"]["texture_width"],
                            "th": g["description"]["texture_height"]}
        self.R.ok("GEOMETRY models", len(geo))
        return geo

    def index_textures(self):
        """Map texture path (no extension) -> set of tiers it exists in."""
        idx = defaultdict(set)
        for f in glob.glob(os.path.join(self.rp, "**", "*.png"), recursive=True) + \
                glob.glob(os.path.join(self.rp, "**", "*.tga"), recursive=True):
            r = os.path.relpath(f, self.rp).replace(os.sep, "/")
            tier = "base"
            if r.startswith("subpacks/"):
                parts = r.split("/", 2)
                tier = parts[1]
                r = parts[2]
            idx[os.path.splitext(r)[0]].add(tier)
        return idx

    def tex_exists(self, path: str, check: str, ctx: str):
        if path.startswith("textures/misc/") or path.startswith("textures/entity/") and not path.startswith(f"textures/entity/{NS}"):
            return True  # vanilla texture
        if path not in self.textures:
            self.R.err(check, f"{ctx}: texture {path} not found")
            return False
        tiers = self.textures[path]
        if "base" not in tiers:
            self.R.err(check, f"{ctx}: texture {path} missing from base pack (needed when a subpack does not override it)")
            return False
        self.R.ok(check + " texture")
        return True

    def load_particles(self):
        out = {}
        for p in self.jsons(self.rp, "particles"):
            d = load_json(p, Results())
            if not d:
                continue
            pe = d["particle_effect"]
            pid = pe["description"]["identifier"]
            if pid in out:
                self.R.err("PARTICLE", f"duplicate particle {pid}")
            out[pid] = pe
            brp = pe["description"]["basic_render_parameters"]
            if brp.get("material") not in VANILLA_PARTICLE_MATERIALS:
                self.R.err("PARTICLE", f"{pid}: unknown material {brp.get('material')}")
            self.tex_exists(brp["texture"], "PARTICLE", pid)
        for tier in ("potato", "enhanced"):
            for p in glob.glob(os.path.join(self.rp, "subpacks", tier, "particles", "**", "*.json"), recursive=True):
                d = load_json(p, Results())
                pid = d["particle_effect"]["description"]["identifier"]
                if pid not in out:
                    self.R.err("SUBPACK", f"{tier} overrides unknown particle {pid}")
                else:
                    self.R.ok("SUBPACK particle override")
        self.R.ok("PARTICLE effects", len(out))
        return out

    def load_sounds(self):
        R = self.R
        sd = load_json(os.path.join(self.rp, "sounds", "sound_definitions.json"), R, "SOUND") or {}
        defs = sd.get("sound_definitions", {})
        for sid, d in defs.items():
            for s in d.get("sounds", []):
                name = s["name"] if isinstance(s, dict) else s
                if not (os.path.isfile(os.path.join(self.rp, name + ".ogg")) or os.path.isfile(os.path.join(self.rp, name + ".wav"))):
                    R.err("SOUND", f"{sid}: file {name}.ogg missing")
                else:
                    with open(os.path.join(self.rp, name + ".ogg"), "rb") as f:
                        if f.read(4) != b"OggS":
                            R.err("SOUND", f"{name}.ogg is not an Ogg stream")
                        else:
                            R.ok("SOUND files")
            if d.get("category") not in ("ambient", "block", "bottle", "bucket", "hostile", "music", "neutral",
                                         "player", "record", "ui", "weather"):
                R.err("SOUND", f"{sid}: unknown category {d.get('category')}")
        sj = load_json(os.path.join(self.rp, "sounds.json"), R, "SOUND") or {}
        for ent, cfg in sj.get("entity_sounds", {}).get("entities", {}).items():
            for ev, sid in cfg.get("events", {}).items():
                sid = sid if isinstance(sid, str) else sid.get("sound")
                if sid not in defs:
                    R.err("SOUND", f"sounds.json {ent}.{ev} -> undefined sound {sid}")
                else:
                    R.ok("SOUND entity events")
        return defs

    # ------------------------------------------------------------------------------------------
    def schema_check(self, area, docfile, comp_file, fmt, inst, path, kind):
        if not self.schemas:
            return
        R = self.R
        v, errs = self.schemas.validate(area, docfile, fmt, inst)
        for e in errs:
            R.err("SCHEMA", f"{self.rel(path)} ({kind} schema {v}): {e}")
        if not errs:
            R.ok(f"SCHEMA {kind}")
        names = self.schemas.component_names(area, fmt, comp_file)
        if names is None:
            return
        groups = [inst.get("components", {})]
        groups += list((inst.get("component_groups") or {}).values())
        groups += [p.get("components", {}) for p in inst.get("permutations", [])]
        for g in groups:
            for comp, val in g.items():
                if comp.startswith("minecraft:"):
                    if comp not in names:
                        R.err("COMPONENT", f"{self.rel(path)}: {comp} is not a valid {kind} component for format {fmt}")
                    else:
                        R.ok(f"COMPONENT {kind}")
                        if kind == "entity" and self.vanilla_fields and isinstance(val, dict) and comp in self.vanilla_fields \
                                and self.schemas.is_dynamic(area, fmt, comp_file, comp):
                            unknown = set(val) - self.vanilla_fields[comp]
                            if unknown:
                                R.warn("FIELDS", f"{self.rel(path)}: {comp} fields not used by any vanilla entity: {sorted(unknown)}")
                elif not comp.startswith(f"{NS}:"):
                    R.err("COMPONENT", f"{self.rel(path)}: foreign custom component {comp}")

    def check_items_blocks(self):
        R = self.R
        itex = load_json(os.path.join(self.rp, "textures", "item_texture.json"), R, "ITEM") or {}
        ttex = load_json(os.path.join(self.rp, "textures", "terrain_texture.json"), R, "BLOCK") or {}
        blocks_json = load_json(os.path.join(self.rp, "blocks.json"), R, "BLOCK") or {}
        items = {}
        for p in self.jsons(self.bp, "items"):
            d = load_json(p, Results())
            it = d["minecraft:item"]
            iid = it["description"]["identifier"]
            items[iid] = it
            self.schema_check("server/item", "ItemDocument.json", "Item Components.json", d["format_version"], it, p, "item")
            comps = it["components"]
            icon = comps.get("minecraft:icon")
            key = icon if isinstance(icon, str) else (icon or {}).get("textures", {}).get("default")
            if key not in itex.get("texture_data", {}):
                R.err("ITEM", f"{iid}: icon key {key} not in item_texture.json")
            else:
                self.tex_exists(itex["texture_data"][key]["textures"], "ITEM", iid)
            dn = comps.get("minecraft:display_name", {}).get("value")
            if dn and dn not in self.lang:
                R.err("LANG", f"{iid}: display name key {dn} missing in en_US.lang")
            elif dn:
                R.ok("LANG item names")
        blocks = {}
        for p in self.jsons(self.bp, "blocks"):
            d = load_json(p, Results())
            b = d["minecraft:block"]
            bid = b["description"]["identifier"]
            blocks[bid] = b
            self.schema_check("server/block", "Blocks.json", "Components.json", d["format_version"], b, p, "block")
            comps = b["components"]
            for face, mi in comps.get("minecraft:material_instances", {}).items():
                t = mi["texture"] if isinstance(mi, dict) else None
                if t and t not in ttex.get("texture_data", {}):
                    R.err("BLOCK", f"{bid}: material {face} texture key {t} not in terrain_texture.json")
                elif t:
                    self.tex_exists(ttex["texture_data"][t]["textures"], "BLOCK", bid)
            loot = comps.get("minecraft:loot")
            if loot and not os.path.isfile(os.path.join(self.bp, loot)):
                R.err("BLOCK", f"{bid}: loot table {loot} missing")
            if bid not in blocks_json:
                R.err("BLOCK", f"{bid}: no blocks.json entry (sound)")
            elif blocks_json[bid].get("sound") not in BLOCK_SOUNDS:
                R.err("BLOCK", f"{bid}: unknown block sound {blocks_json[bid].get('sound')}")
            else:
                R.ok("BLOCK sounds")
            if f"tile.{bid}.name" not in self.lang:
                R.err("LANG", f"{bid}: tile.{bid}.name missing")
            else:
                R.ok("LANG block names")
        # repair items
        for iid, it in items.items():
            for r in it["components"].get("minecraft:repairable", {}).get("repair_items", []):
                for ref in r.get("items", []):
                    self.item_ref(ref, f"{iid} repairable", items, blocks)
        return items, blocks

    def item_ref(self, ref: str, ctx: str, items=None, blocks=None, check="REF"):
        items = items if items is not None else self.items
        blocks = blocks if blocks is not None else self.blocks
        if ref.startswith(f"{NS}:"):
            if ref not in items and ref not in blocks:
                self.R.err(check, f"{ctx}: unknown item {ref}")
            else:
                self.R.ok(check)
        elif ref.startswith("minecraft:"):
            has = self.vanilla_has("item", ref)
            if has is False:
                self.R.err(check, f"{ctx}: unknown vanilla item {ref}")
            elif has:
                self.R.ok(check + " vanilla")
        else:
            self.R.err(check, f"{ctx}: unnamespaced item {ref}")

    # ------------------------------------------------------------------------------------------
    def check_entities(self):
        R = self.R
        ents = {}
        for p in self.jsons(self.bp, "entities"):
            d = load_json(p, Results())
            e = d["minecraft:entity"]
            eid = e["description"]["identifier"]
            if eid in ents:
                R.err("ENTITY", f"duplicate entity {eid}")
            ents[eid] = e
            self.schema_check("server/entity", "ActorDocument.json", "Entity component definitions.json",
                              d["format_version"], e, p, "entity")
            groups = e.get("component_groups", {})
            props = e["description"].get("properties", {})
            for pname, pdef in props.items():
                if pdef.get("type") not in ("int", "float", "bool", "enum"):
                    R.err("ENTITY", f"{eid}: property {pname} bad type")
                if pdef.get("type") == "int" and not (pdef["range"][0] <= pdef["default"] <= pdef["range"][1]):
                    R.err("ENTITY", f"{eid}: property {pname} default out of range")
                if pdef.get("type") == "enum" and pdef["default"] not in pdef["values"]:
                    R.err("ENTITY", f"{eid}: property {pname} default not in values")
            for ev, body in e.get("events", {}).items():
                seq = body.get("sequence", [body])
                for step in seq:
                    for op in ("add", "remove"):
                        for g in step.get(op, {}).get("component_groups", []):
                            if g not in groups:
                                R.err("ENTITY", f"{eid}: event {ev} references missing group {g}")
                            else:
                                R.ok("ENTITY event groups")
                    for prop in step.get("set_property", {}):
                        if prop not in props:
                            R.err("ENTITY", f"{eid}: event {ev} sets undeclared property {prop}")
            for g in [e.get("components", {})] + list(groups.values()):
                loot = g.get("minecraft:loot", {}).get("table")
                if loot and not os.path.isfile(os.path.join(self.bp, loot)):
                    R.err("ENTITY", f"{eid}: loot table {loot} missing")
                elif loot:
                    R.ok("ENTITY loot")
                sh = g.get("minecraft:shooter", {}).get("def")
                if sh and sh.startswith(f"{NS}:") and not os.path.isfile(os.path.join(self.bp, "entities", NS, sh.split(":")[1] + ".json")):
                    R.err("ENTITY", f"{eid}: shooter def {sh} missing")
                atk = g.get("minecraft:attack", {})
                if atk.get("effect_name") and self.vanilla_has("effect", atk["effect_name"]) is False:
                    R.err("ENTITY", f"{eid}: unknown effect {atk['effect_name']}")
                for eff in g.get("minecraft:mob_effect_immunity", {}).get("mob_effects", []):
                    if self.vanilla_has("effect", eff) is False:
                        R.err("ENTITY", f"{eid}: unknown immunity effect {eff}")
            if f"entity.{eid}.name" not in self.lang:
                R.err("LANG", f"entity.{eid}.name missing")
            else:
                R.ok("LANG entity names")
        return ents

    def check_client_entities(self):
        R = self.R
        rcs = {}
        for p in self.jsons(self.rp, "render_controllers"):
            d = load_json(p, Results())
            rcs.update(d.get("render_controllers", {}))
        anims = {}
        for p in self.jsons(self.rp, "animations"):
            d = load_json(p, Results())
            anims.update(d.get("animations", {}))
        ctrls = {}
        for p in self.jsons(self.rp, "animation_controllers"):
            d = load_json(p, Results())
            ctrls.update(d.get("animation_controllers", {}))
        clients = {}
        for p in self.jsons(self.rp, "entity"):
            d = load_json(p, Results())
            desc = d["minecraft:client_entity"]["description"]
            cid = desc["identifier"]
            clients[cid] = desc
            if cid not in self.entities:
                R.err("CLIENT", f"client entity {cid} has no behavior entity")
            for k, m in desc.get("materials", {}).items():
                if m not in VANILLA_MATERIALS:
                    R.err("CLIENT", f"{cid}: material {m} is not a documented vanilla material")
            for k, t in desc.get("textures", {}).items():
                self.tex_exists(t, "CLIENT", cid)
            gid = desc.get("geometry", {}).get("default")
            if gid not in self.geometry:
                R.err("CLIENT", f"{cid}: geometry {gid} not found")
                continue
            geo = self.geometry[gid]
            amap = desc.get("animations", {})
            for short, full in amap.items():
                if full.startswith("controller.animation."):
                    if full not in ctrls:
                        R.err("CLIENT", f"{cid}: controller {full} not found")
                        continue
                    for sname, st in ctrls[full]["states"].items():
                        for a in st.get("animations", []):
                            key = a if isinstance(a, str) else next(iter(a))
                            if key not in amap:
                                R.err("CLIENT", f"{cid}: controller {full} state {sname} uses unknown animation {key}")
                            else:
                                R.ok("CLIENT controller animations")
                        for pe in st.get("particle_effects", []):
                            if pe["effect"] not in desc.get("particle_effects", {}):
                                R.err("CLIENT", f"{cid}: controller particle key {pe['effect']} not in particle_effects")
                            if pe.get("locator") and pe["locator"] not in geo["locators"]:
                                R.err("CLIENT", f"{cid}: locator {pe['locator']} not in {gid}")
                            else:
                                R.ok("CLIENT locators")
                else:
                    if full not in anims:
                        R.err("CLIENT", f"{cid}: animation {full} not found")
                        continue
                    for bone in anims[full].get("bones", {}):
                        if bone not in geo["bones"]:
                            R.err("CLIENT", f"{cid}: animation {full} targets bone {bone} missing from {gid}")
                        else:
                            R.ok("CLIENT animation bones")
            for entry in desc.get("scripts", {}).get("animate", []):
                key = entry if isinstance(entry, str) else next(iter(entry))
                if key not in amap:
                    R.err("CLIENT", f"{cid}: scripts.animate references unknown {key}")
                else:
                    R.ok("CLIENT animate")
            for k, pid in desc.get("particle_effects", {}).items():
                if pid not in self.particles:
                    R.err("CLIENT", f"{cid}: particle {pid} not defined")
                else:
                    R.ok("CLIENT particles")
            for rc in desc.get("render_controllers", []):
                rcname = rc if isinstance(rc, str) else next(iter(rc))
                if rcname in VANILLA_RENDER_CONTROLLERS:
                    continue
                if rcname not in rcs:
                    R.err("CLIENT", f"{cid}: render controller {rcname} not found")
                    continue
                body = json.dumps(rcs[rcname])
                for ref in set(re.findall(r"Texture\.(\w+)", body)):
                    if ref not in desc.get("textures", {}):
                        R.err("CLIENT", f"{cid}: render controller {rcname} needs Texture.{ref}")
                for ref in set(re.findall(r"Material\.(\w+)", body)):
                    if ref not in desc.get("materials", {}):
                        R.err("CLIENT", f"{cid}: render controller {rcname} needs Material.{ref}")
                for ref in set(re.findall(r"query\.property\('([^']+)'\)", body)):
                    if ref not in self.entities.get(cid, {}).get("description", {}).get("properties", {}):
                        R.err("CLIENT", f"{cid}: render controller {rcname} reads undeclared property {ref}")
                R.ok("CLIENT render controllers")
            for ref in set(re.findall(r"query\.property\('([^']+)'\)", json.dumps(desc) + json.dumps(
                    [ctrls.get(f, {}) for f in amap.values()]))):
                if ref not in self.entities.get(cid, {}).get("description", {}).get("properties", {}):
                    R.err("CLIENT", f"{cid}: reads undeclared property {ref}")
        for eid in self.entities:
            if eid not in clients:
                R.err("CLIENT", f"behavior entity {eid} has no client entity (would be invisible)")
            else:
                R.ok("CLIENT pairs")

    def check_attachables(self):
        R = self.R
        for p in self.jsons(self.rp, "attachables"):
            d = load_json(p, Results())
            desc = d["minecraft:attachable"]["description"]
            aid = desc["identifier"].split(".")[0]
            if aid not in self.items:
                R.err("ATTACHABLE", f"attachable {aid} has no item")
            g = desc.get("geometry", {}).get("default", "")
            if not g.startswith(VANILLA_GEOMETRY_PREFIXES) and g not in self.geometry:
                R.err("ATTACHABLE", f"{aid}: geometry {g} unknown")
            for t in desc.get("textures", {}).values():
                self.tex_exists(t, "ATTACHABLE", aid)
            for m in desc.get("materials", {}).values():
                if m not in VANILLA_MATERIALS:
                    R.err("ATTACHABLE", f"{aid}: material {m} not vanilla")
            R.ok("ATTACHABLE")
        for iid, it in self.items.items():
            if "minecraft:wearable" in it["components"]:
                slot = it["components"]["minecraft:wearable"]["slot"]
                if slot.startswith("slot.armor") and not os.path.isfile(os.path.join(self.rp, "attachables", NS, iid.split(":")[1] + ".json")):
                    R.err("ATTACHABLE", f"wearable {iid} has no attachable (would be invisible when worn)")

    def check_loot_tables(self):
        for p in self.jsons(self.bp, "loot_tables"):
            d = load_json(p, Results())
            for pool in d.get("pools", []):
                for e in pool.get("entries", []):
                    if e.get("type") == "item":
                        self.item_ref(e["name"], self.rel(p), check="LOOT")

    def check_recipes(self):
        R = self.R
        ids = set()
        for p in self.jsons(self.bp, "recipes"):
            d = load_json(p, Results())
            key = next(k for k in d if k.startswith("minecraft:recipe"))
            r = d[key]
            rid = r["description"]["identifier"]
            if rid in ids:
                R.err("RECIPE", f"duplicate recipe id {rid}")
            ids.add(rid)
            refs = []
            if key == "minecraft:recipe_shaped":
                used = set("".join(r["pattern"])) - {" "}
                if used - set(r["key"]):
                    R.err("RECIPE", f"{rid}: pattern symbols without key {used - set(r['key'])}")
                if set(r["key"]) - used:
                    R.err("RECIPE", f"{rid}: unused key symbols {set(r['key']) - used}")
                widths = {len(row) for row in r["pattern"]}
                if len(widths) != 1 or max(widths) > 3 or len(r["pattern"]) > 3:
                    R.err("RECIPE", f"{rid}: pattern rows must be equal width <= 3")
                refs += [v["item"] for v in r["key"].values()]
                refs.append(r["result"]["item"])
            elif key == "minecraft:recipe_shapeless":
                refs += [i["item"] for i in r["ingredients"]]
                refs.append(r["result"]["item"])
            elif key == "minecraft:recipe_furnace":
                refs += [r["input"], r["output"]]
            for u in r.get("unlock", []):
                refs.append(u["item"])
            for ref in refs:
                self.item_ref(ref, rid, check="RECIPE")
            if "unlock" not in r and key != "minecraft:recipe_furnace":
                R.warn("RECIPE", f"{rid}: no unlock condition")
        R.ok("RECIPE count", len(ids))

    def check_spawn_rules(self):
        for p in self.jsons(self.bp, "spawn_rules"):
            d = load_json(p, Results())
            sid = d["minecraft:spawn_rules"]["description"]["identifier"]
            if sid not in self.entities:
                self.R.err("SPAWN", f"spawn rule for unknown entity {sid}")
            elif not self.entities[sid]["description"].get("is_spawnable"):
                self.R.warn("SPAWN", f"{sid} has a spawn rule but is_spawnable=false")
            else:
                self.R.ok("SPAWN")

    def check_world(self):
        R = self.R
        from tools.lib.mcstructure import read_structure
        features = {}
        for p in self.jsons(self.bp, "features"):
            d = load_json(p, Results())
            k = next(x for x in d if x.startswith("minecraft:"))
            fid = d[k]["description"]["identifier"]
            features[fid] = (k, d[k])
        for fid, (k, f) in features.items():
            if k == "minecraft:ore_feature":
                for rr in f["replace_rules"]:
                    self.block_ref(rr["places_block"], fid)
                    for mr in rr.get("may_replace", []):
                        self.block_ref(mr, fid)
            elif k == "minecraft:single_block_feature":
                self.block_ref(f["places_block"], fid)
            elif k == "minecraft:structure_template_feature":
                name = f["structure_name"]
                path = os.path.join(self.bp, "structures", *name.split(":")) + ".mcstructure"
                if not os.path.isfile(path):
                    R.err("WORLD", f"{fid}: structure {name} missing")
            R.ok("WORLD features")
        for p in self.jsons(self.bp, "feature_rules"):
            d = load_json(p, Results())
            fr = d["minecraft:feature_rules"]
            if fr["description"]["places_feature"] not in features:
                R.err("WORLD", f"{fr['description']['identifier']}: feature {fr['description']['places_feature']} missing")
            else:
                R.ok("WORLD feature rules")
        for p in sorted(glob.glob(os.path.join(self.bp, "structures", "**", "*.mcstructure"), recursive=True)):
            try:
                st = read_structure(open(p, "rb").read())
                size = st["size"]
                prim, sec = st["structure"]["block_indices"]
                n = size[0] * size[1] * size[2]
                pal = st["structure"]["palette"]["default"]["block_palette"]
                if len(prim) != n or len(sec) != n:
                    R.err("STRUCTURE", f"{self.rel(p)}: index count mismatch")
                if max(prim) >= len(pal):
                    R.err("STRUCTURE", f"{self.rel(p)}: palette index out of range")
                for b in pal:
                    self.block_ref(b["name"], self.rel(p))
                R.ok("STRUCTURE files")
            except Exception as e:  # noqa: BLE001
                R.err("STRUCTURE", f"{self.rel(p)}: unreadable NBT: {e}")
        fogs = set()
        for p in self.jsons(self.rp, "fogs"):
            d = load_json(p, Results())
            fogs.add(d["minecraft:fog_settings"]["description"]["identifier"])
        vv = set()
        for sub, key in (("atmospherics", "minecraft:atmosphere_settings"), ("color_grading", "minecraft:color_grading_settings"),
                         ("lighting", "minecraft:lighting_settings")):
            for p in self.jsons(self.rp, sub):
                d = load_json(p, Results())
                vv.add(d[key]["description"]["identifier"])
        for p in self.jsons(self.bp, "biomes"):
            d = load_json(p, Results())
            b = d["minecraft:biome"]
            bid = b["description"]["identifier"]
            sb = b["components"].get("minecraft:surface_builder", {}).get("builder", {})
            for k in ("top_material", "mid_material", "foundation_material", "sea_floor_material", "sea_material"):
                if k in sb:
                    self.block_ref(sb[k], bid)
            if self.schemas:
                v, errs = self.schemas.validate("server/biome", "Biome Document.json", d["format_version"], d)
                for e in errs:
                    R.err("SCHEMA", f"{self.rel(p)} (biome schema {v}): {e}")
                if not errs:
                    R.ok("SCHEMA biome")
            if not os.path.isfile(os.path.join(self.rp, "biomes", os.path.basename(p).replace(".biome.json", ".client_biome.json"))):
                R.err("WORLD", f"{bid}: client biome missing")
        for p in self.jsons(self.rp, "biomes"):
            d = load_json(p, Results())
            comps = d["minecraft:client_biome"]["components"]
            fog = comps.get("minecraft:fog_appearance", {}).get("fog_identifier")
            if fog and fog.startswith(f"{NS}:") and fog not in fogs:
                R.err("WORLD", f"client biome fog {fog} undefined")
            for key, field in (("minecraft:atmosphere_identifier", "atmosphere_identifier"),
                               ("minecraft:color_grading_identifier", "color_grading_identifier"),
                               ("minecraft:lighting_identifier", "lighting_identifier")):
                ref = comps.get(key, {}).get(field)
                if ref and ref.startswith(f"{NS}:") and ref not in vv:
                    R.err("WORLD", f"client biome {key} -> {ref} undefined")
                elif ref:
                    R.ok("WORLD vibrant visuals config")
        self.fogs = fogs

    def block_ref(self, ref: str, ctx: str):
        if ref.startswith(f"{NS}:"):
            if ref not in self.blocks:
                self.R.err("REF", f"{ctx}: unknown block {ref}")
            else:
                self.R.ok("REF blocks")
        elif ref.startswith("minecraft:"):
            has = self.vanilla_has("block", ref)
            if has is False:
                self.R.err("REF", f"{ctx}: unknown vanilla block {ref}")
            elif has:
                self.R.ok("REF vanilla blocks")

    def check_texture_sets(self):
        R = self.R
        for p in glob.glob(os.path.join(self.rp, "**", "*.texture_set.json"), recursive=True):
            d = load_json(p, Results())
            ts = d.get("minecraft:texture_set", {})
            if "color" not in ts:
                R.err("TEXTURESET", f"{self.rel(p)}: color layer required")
                continue
            if "normal" in ts and "heightmap" in ts:
                R.err("TEXTURESET", f"{self.rel(p)}: normal and heightmap both defined")
            folder = os.path.dirname(p)
            dims = set()
            for layer in ("color", "metalness_emissive_roughness", "normal", "heightmap"):
                ref = ts.get(layer)
                if not isinstance(ref, str) or ref.startswith("#"):
                    continue
                f = os.path.join(folder, ref + ".png")
                if not os.path.isfile(f):
                    R.err("TEXTURESET", f"{self.rel(p)}: layer {layer} image {ref}.png missing in same folder")
                    continue
                w, h, ct = png_info(f)
                dims.add((w, h))
                if layer == "metalness_emissive_roughness" and ct not in (2, 6):
                    R.err("TEXTURESET", f"{self.rel(p)}: MER must be RGB/RGBA")
            if len(dims) > 1:
                R.err("TEXTURESET", f"{self.rel(p)}: layers have different dimensions {dims}")
            else:
                R.ok("TEXTURESET")

    def check_images(self):
        R = self.R
        for f in glob.glob(os.path.join(self.rp, "**", "*.png"), recursive=True):
            info = png_info(f)
            if not info:
                R.err("IMAGE", f"{self.rel(f)}: not a PNG")
                continue
            w, h, ct = info
            if not (is_pow2(w) and is_pow2(h)):
                R.warn("IMAGE", f"{self.rel(f)}: non power-of-two {w}x{h}")
            if w > 1024 or h > 1024:
                R.err("IMAGE", f"{self.rel(f)}: {w}x{h} exceeds the 1024px mobile budget")
            R.ok("IMAGE png")

    def check_scripts(self):
        R = self.R
        sdir = os.path.join(self.bp, "scripts")
        files = sorted(glob.glob(os.path.join(sdir, "**", "*.js"), recursive=True))
        if not files:
            R.err("SCRIPT", "no compiled scripts found")
            return
        literals = set()
        for f in files:
            src = open(f, encoding="utf-8").read()
            for m in re.finditer(r"""(?:import|export)\s[^'"]*?from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]""", src):
                mod = m.group(1) or m.group(2)
                if mod.startswith("."):
                    target = os.path.normpath(os.path.join(os.path.dirname(f), mod))
                    if not os.path.isfile(target):
                        R.err("SCRIPT", f"{self.rel(f)}: import {mod} not found")
                    elif not mod.endswith(".js"):
                        R.err("SCRIPT", f"{self.rel(f)}: relative import {mod} must include .js")
                    else:
                        R.ok("SCRIPT imports")
                elif mod not in SCRIPT_MODULES:
                    R.err("SCRIPT", f"{self.rel(f)}: imports module {mod} not declared in manifest")
                else:
                    R.ok("SCRIPT module imports")
            literals.update(re.findall(r"""['"`](apocalypse:[a-z0-9_]+)['"`]""", src))
        known = set(self.entities) | set(self.items) | set(self.blocks) | set(self.particles) | self.fogs
        known |= {f"{NS}:shattered_expanse"}
        for e in self.entities.values():
            known |= set(e["description"].get("properties", {}))
            known |= set(e.get("events", {}))
            for fam in e.get("components", {}).get("minecraft:type_family", {}).get("family", []):
                known.add(f"{NS}:{fam}")
        for it in list(self.items.values()) + list(self.blocks.values()):
            for k in it.get("components", {}):
                if k.startswith(f"{NS}:"):
                    known.add(k)
            for t in it.get("components", {}).get("minecraft:tags", {}).get("tags", []) if isinstance(
                    it.get("components", {}).get("minecraft:tags"), dict) else []:
                known.add(t)
        for p in glob.glob(os.path.join(self.bp, "structures", NS, "*.mcstructure")):
            known.add(f"{NS}:" + os.path.basename(p).replace(".mcstructure", ""))
        unknown = sorted(l for l in literals if l not in known)
        # script-only identifiers (commands, dynamic properties, tags, ticking areas) are declared in scripts/core/keys
        keys_file = os.path.join(sdir, "core", "keys.js")
        declared = set(re.findall(r"""['"](apocalypse:[a-z0-9_]+)['"]""", open(keys_file).read())) if os.path.isfile(keys_file) else set()
        for l in unknown:
            if l not in declared:
                R.warn("SCRIPT", f"identifier {l} used by scripts is not defined by pack content")
        R.ok("SCRIPT identifiers", len(literals) - len(unknown))
        # custom components used in JSON must be registered in scripts
        registered = set()
        for f in files:
            registered |= set(re.findall(r"registerCustomComponent\(\s*['\"]([^'\"]+)['\"]", open(f, encoding="utf-8").read()))
            registered |= set(re.findall(r"registerCustomComponent\(\s*(\w+)\.(\w+)", open(f, encoding="utf-8").read()) and [])
        comps_used = set()
        for it in list(self.items.values()) + list(self.blocks.values()):
            for k in it["components"]:
                if k.startswith(f"{NS}:"):
                    comps_used.add(k)
        all_js = "\n".join(open(f, encoding="utf-8").read() for f in files)
        for c in sorted(comps_used):
            if c not in all_js:
                R.err("SCRIPT", f"custom component {c} is used in JSON but never registered by scripts")
            else:
                R.ok("SCRIPT custom components")
        # sounds referenced by scripts
        for sid in set(re.findall(r"""['"]((?:mob\.)?apocalypse\.[a-z0-9_.]+)['"]""", all_js)):
            if sid not in self.sound_defs:
                R.err("SCRIPT", f"script plays undefined sound {sid}")
            else:
                R.ok("SCRIPT sounds")

    def check_empty_dirs(self):
        for base in (self.bp, self.rp):
            for dirpath, dirnames, filenames in os.walk(base):
                if not dirnames and not filenames:
                    self.R.err("STRUCTURE", f"empty directory {self.rel(dirpath)}")


def format_report(R: Results) -> str:
    lines = ["APOCALYPSE ENGINE — static validation", "=" * 60]
    for n in R.notes:
        lines.append(f"note: {n}")
    lines.append("")
    lines.append(f"checks passed : {sum(R.passes.values())}")
    lines.append(f"errors        : {len(R.errors)}")
    lines.append(f"warnings      : {len(R.warnings)}")
    lines.append("")
    lines.append("passed checks by category:")
    for k in sorted(R.passes):
        lines.append(f"  {k:<40} {R.passes[k]}")
    if R.errors:
        lines.append("")
        lines.append("ERRORS:")
        lines += [f"  {e}" for e in R.errors]
    if R.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        lines += [f"  {w}" for w in R.warnings]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT_DEFAULT)
    ap.add_argument("--schemas", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    from tools.schema_check import find_schema_root
    schema_root = find_schema_root(args.schemas)
    v = Validator(os.path.abspath(args.root), schema_root)
    R = v.run()
    text = format_report(R)
    print(text)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"errors": R.errors, "warnings": R.warnings, "passes": R.passes, "notes": R.notes}, f, indent=2)
    sys.exit(1 if R.errors else 0)


if __name__ == "__main__":
    main()
