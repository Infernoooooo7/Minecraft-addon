// Block custom components: ore drops + XP (Silk Touch / Fortune aware), Engine Cache opening, Null Gate ritual.
import {
  BlockComponentPlayerBreakEvent, BlockComponentPlayerInteractEvent, BlockCustomComponent, CustomComponentParameters,
  Dimension, ItemStack, Player, system, Vector3,
} from "@minecraft/server";
import { actionbar, burst, ring, runeCircle, sound, title } from "../core/fx.js";
import { DP } from "../core/keys.js";
import { countItem, heldItem, isCreative, playersNear, removeItems } from "../core/players.js";
import { later } from "../core/scheduler.js";
import { readEntity, writeEntity } from "../core/state.js";
import { bossCount, spawnBoss } from "../bosses/runtime.js";
import { ENTITIES, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { discover, parseJournal } from "../logic/progression.js";
import { Rng } from "../logic/rng.js";
import { COLOSSUS_SPAWN, inExpanse } from "./expanse.js";

const rng = new Rng((Date.now() ^ 0xb10c) >>> 0);
const GATE_FRAGMENTS = 8;

interface OreParams {
  min: number;
  max: number;
  drops?: Array<{ item: string; min: number; max: number }>;
}

function spawnXp(dim: Dimension, at: Vector3, orbs: number): void {
  for (let i = 0; i < Math.min(orbs, 12); i++) {
    try {
      dim.spawnEntity("minecraft:xp_orb", at);
    } catch {
      return;
    }
  }
}

function journalDiscover(p: Player, id: string): void {
  const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
  if (discover(j, id)) writeEntity(p, DP.JOURNAL, JSON.stringify(j));
}

export const oreComponent: BlockCustomComponent = {
  onPlayerBreak(ev: BlockComponentPlayerBreakEvent, params: CustomComponentParameters) {
    const p = ev.player;
    if (!p || isCreative(p)) return;
    const cfg = params.params as OreParams;
    const tool = heldItem(p);
    const ench = tool?.getComponent("minecraft:enchantable");
    // Silk Touch: the loot table already drops the ore block itself
    if (ench?.hasEnchantment("silk_touch")) return;
    if (!tool?.hasTag("minecraft:is_pickaxe")) return;
    const fortune = ench?.getEnchantment("fortune")?.level ?? 0;
    const at = ev.block.center();
    const dim = ev.dimension;
    system.run(() => {
      for (const d of cfg.drops ?? []) {
        // vanilla-style Fortune: multiply by (1 + random 0..level), at most x(level + 1)
        const n = rng.int(d.min, d.max) * (fortune > 0 ? 1 + rng.int(0, fortune) : 1);
        try {
          dim.spawnItem(new ItemStack(d.item, Math.min(64, n)), at);
        } catch {
          /* unloaded */
        }
        journalDiscover(p, d.item);
      }
      spawnXp(dim, at, rng.int(cfg.min ?? 0, cfg.max ?? 0));
      burst(dim, PARTICLES.CRYSTAL_GLINT, at, 1, 0.3);
    });
  },
};

export const cacheComponent: BlockCustomComponent = {
  onPlayerBreak(ev: BlockComponentPlayerBreakEvent) {
    const p = ev.player;
    const at = ev.block.center();
    const dim = ev.dimension;
    system.run(() => {
      burst(dim, PARTICLES.SPECTRAL_BURST, at, 3, 0.8);
      burst(dim, PARTICLES.CRYSTAL_GLINT, at, 3, 0.8);
      sound(dim, SOUNDS.RELIC_USE, at, 1, 1.2);
      if (p && !isCreative(p)) {
        spawnXp(dim, at, rng.int(5, 9));
        journalDiscover(p, "apocalypse:engine_cache");
        actionbar([p], "§6The Engine Cache unseals with a hiss of ancient air.");
      }
    });
  },
};

export const nullGateComponent: BlockCustomComponent = {
  onPlayerInteract(ev: BlockComponentPlayerInteractEvent) {
    const p = ev.player;
    if (!p) return;
    const gate = ev.block.center();
    system.run(() => openGate(p, ev.dimension, gate));
  },
};

function openGate(p: Player, dim: Dimension, gate: Vector3): void {
  if (heldItem(p)?.typeId !== ITEMS.ENGINE_KEY) {
    actionbar([p], `§bThe Null Gate hungers: hold the Engine Key and carry ${GATE_FRAGMENTS} Null Fragments.`);
    return;
  }
  if (!inExpanse(p)) {
    actionbar([p], "§cThis gate is dead outside the Shattered Expanse.");
    return;
  }
  if (bossCount(ENTITIES.NULL_COLOSSUS) > 0) {
    actionbar([p], "§cThe Null Colossus already stands guard.");
    return;
  }
  if (!isCreative(p)) {
    if (countItem(p, ITEMS.NULL_FRAGMENT) < GATE_FRAGMENTS) {
      actionbar([p], `§cThe gate needs ${GATE_FRAGMENTS} Null Fragments (Rift Sentinels carry them).`);
      return;
    }
    removeItems(p, ITEMS.NULL_FRAGMENT, GATE_FRAGMENTS);
  }
  runeCircle(dim, { x: gate.x, y: gate.y - 1.4, z: gate.z }, 3, 3);
  ring(dim, COLOSSUS_SPAWN, 6, 3);
  sound(dim, SOUNDS.NULL_COLOSSUS_VENT, gate, 1.4, 0.6);
  title(playersNear(dim, gate, 64), "§3§lTHE NULL GATE OPENS", "§bThe last warden of the Engine awakens...", 10, 60, 20);
  later(60, () => {
    if (bossCount(ENTITIES.NULL_COLOSSUS) > 0) return;
    const boss = spawnBoss(ENTITIES.NULL_COLOSSUS, dim.id, COLOSSUS_SPAWN);
    if (!boss && !isCreative(p) && p.isValid) {
      // refund on failure so the offering is never lost
      try {
        p.dimension.spawnItem(new ItemStack(ITEMS.NULL_FRAGMENT, GATE_FRAGMENTS), p.location);
      } catch {
        /* ignore */
      }
    }
  }, "null-gate");
}
