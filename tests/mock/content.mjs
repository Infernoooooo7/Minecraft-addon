// Index of the built packs (entities, items, blocks, sounds, particles, fogs, structures) plus vanilla ids
// from @minecraft/vanilla-data. The mock runtime uses it to reject anything the real engine would not know.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  MinecraftBlockTypes, MinecraftEffectTypes, MinecraftEntityTypes, MinecraftItemTypes,
} from "@minecraft/vanilla-data";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const BP = path.join(ROOT, "behavior_pack");
const RP = path.join(ROOT, "resource_pack");

function walk(dir, suffix, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, suffix, out);
    else if (e.name.endsWith(suffix)) out.push(p);
  }
  return out;
}

const json = (p) => JSON.parse(fs.readFileSync(p, "utf8"));

/** id -> { families, health, events, groups, props, projectile, timer } */
export const ENTITY_DEFS = new Map();
for (const f of walk(path.join(BP, "entities"), ".json")) {
  const e = json(f)["minecraft:entity"];
  const c = e.components ?? {};
  ENTITY_DEFS.set(e.description.identifier, {
    families: new Set(c["minecraft:type_family"]?.family ?? []),
    health: c["minecraft:health"] ?? null,
    events: e.events ?? {},
    groups: e.component_groups ?? {},
    props: e.description.properties ?? {},
    projectile: c["minecraft:projectile"] ?? null,
    timer: c["minecraft:timer"] ?? null,
    components: c,
  });
}

/** id -> components */
export const ITEM_DEFS = new Map();
for (const f of walk(path.join(BP, "items"), ".json")) {
  const it = json(f)["minecraft:item"];
  ITEM_DEFS.set(it.description.identifier, it.components ?? {});
}

export const BLOCK_DEFS = new Map();
for (const f of walk(path.join(BP, "blocks"), ".json")) {
  const b = json(f)["minecraft:block"];
  BLOCK_DEFS.set(b.description.identifier, b.components ?? {});
}

export const SOUND_IDS = new Set(Object.keys(json(path.join(RP, "sounds", "sound_definitions.json")).sound_definitions));
export const PARTICLE_IDS = new Set(walk(path.join(RP, "particles"), ".json").map((f) => json(f).particle_effect.description.identifier));
export const FOG_IDS = new Set(walk(path.join(RP, "fogs"), ".json").map((f) => json(f)["minecraft:fog_settings"].description.identifier));
export const STRUCTURE_IDS = new Set(walk(path.join(BP, "structures"), ".mcstructure").map((f) => {
  const rel = path.relative(path.join(BP, "structures"), f).replace(/\\/g, "/").replace(/\.mcstructure$/, "");
  const [ns, ...rest] = rel.split("/");
  return `${ns}:${rest.join("/")}`;
}));

export const VANILLA_ITEMS = new Set(Object.values(MinecraftItemTypes));
export const VANILLA_ENTITIES = new Set([...Object.values(MinecraftEntityTypes), "minecraft:item"]);
export const VANILLA_BLOCKS = new Set(Object.values(MinecraftBlockTypes));
export const EFFECTS = new Set(Object.values(MinecraftEffectTypes).map((s) => s.replace("minecraft:", "")));
/** Vanilla sound events the scripts may play. */
export const VANILLA_SOUNDS = new Set(["random.break", "random.orb", "random.levelup"]);

export const VANILLA_FAMILIES = {
  "minecraft:player": ["player", "mob"],
  "minecraft:zombie": ["zombie", "undead", "monster", "mob"],
  "minecraft:skeleton": ["skeleton", "undead", "monster", "mob"],
  "minecraft:creeper": ["creeper", "monster", "mob"],
  "minecraft:pig": ["pig", "mob"],
};
