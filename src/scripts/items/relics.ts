// Summoning relics, the Engine Key, the Engine Codex and the Aether Elixir (Custom Components V2).
import {
  CustomComponentParameters, Entity, ItemComponentConsumeEvent, ItemComponentUseEvent, ItemCustomComponent,
  ItemStack, Player, system, world,
} from "@minecraft/server";
import { actionbar, burst, playerSound, ring, runeCircle, sound, title } from "../core/fx.js";
import { consumeHeld, giveItem, isCreative, playersNear } from "../core/players.js";
import { later } from "../core/scheduler.js";
import { bossCount, spawnBoss } from "../bosses/runtime.js";
import { groundAt } from "../bosses/kit.js";
import { activeEvent } from "../events/runtime.js";
import { ENTITIES, PARTICLES, SOUNDS } from "../generated/ids.js";
import { isNight } from "../logic/eventScheduler.js";
import { add, flat, norm, scale } from "../logic/vec.js";
import { openCodex } from "../ui/codex.js";
import { GATE_AT, inExpanse, openRiftPortal } from "../world/expanse.js";

const OVERWORLD = "minecraft:overworld";
const MAX_BOSSES = 2;
const LIVING_SOIL = new Set([
  "minecraft:grass_block", "minecraft:dirt", "minecraft:podzol", "minecraft:coarse_dirt", "minecraft:moss_block",
  "minecraft:rooted_dirt", "apocalypse:blighted_grass", "apocalypse:blighted_soil",
]);

interface Ritual {
  typeId: string;
  name: string;
  color: string;
  /** Returns an explanation when the ritual cannot happen here and now. */
  check(p: Player): string | undefined;
}

function openSky(p: Player): boolean {
  try {
    const top = p.dimension.getTopmostBlock({ x: p.location.x, z: p.location.z });
    return !top || top.location.y < p.location.y + 1.5;
  } catch {
    return false;
  }
}

export const RITUALS: Record<string, Ritual> = {
  hollow_king: {
    typeId: ENTITIES.HOLLOW_KING, name: "The Hollow King", color: "§5",
    check(p) {
      if (p.dimension.id !== OVERWORLD) return "The Cursed Crown only answers in the Overworld.";
      if (!isNight(world.getTimeOfDay()) && activeEvent()?.meta.id !== "eclipse") {
        return "The Cursed Crown stays silent in daylight. Use it at night — or during an Eclipse.";
      }
      return undefined;
    },
  },
  star_eater: {
    typeId: ENTITIES.STAR_EATER, name: "The Star Eater", color: "§6",
    check(p) {
      if (p.dimension.id !== OVERWORLD) return "The Astral Lure needs the Overworld's stars.";
      if (!isNight(world.getTimeOfDay())) return "The Astral Lure only shines at night.";
      if (!openSky(p)) return "The Astral Lure needs the open night sky directly above you.";
      return undefined;
    },
  },
  root_titan: {
    typeId: ENTITIES.ROOT_TITAN, name: "The Root Titan", color: "§2",
    check(p) {
      if (p.dimension.id !== OVERWORLD) return "The Heartseed will only take root in the Overworld.";
      if (isNight(world.getTimeOfDay())) return "The Heartseed sleeps at night. Plant it by daylight.";
      let ground = "";
      try {
        ground = p.dimension.getBlock({ x: p.location.x, y: p.location.y - 0.5, z: p.location.z })?.typeId ?? "";
      } catch {
        ground = "";
      }
      if (!LIVING_SOIL.has(ground)) return "Stand on living soil (grass, dirt, moss or blighted ground) to plant the Heartseed.";
      return undefined;
    },
  },
};

function beginRitual(p: Player, bossKey: string, itemId: string): void {
  const r = RITUALS[bossKey];
  if (!r) return;
  const why = r.check(p);
  if (why) {
    actionbar([p], `§c${why}`);
    return;
  }
  if (bossCount(r.typeId) > 0) {
    actionbar([p], `§c${r.name} already walks this world.`);
    return;
  }
  if (bossCount() >= MAX_BOSSES) {
    actionbar([p], "§cThe world cannot bear another colossus right now. Defeat the one that lives.");
    return;
  }
  const creative = isCreative(p);
  if (!creative && !consumeHeld(p, itemId)) return;
  const dim = p.dimension;
  const ahead = norm(flat(p.getViewDirection()));
  const spot = groundAt(dim, add(p.location, scale(ahead, 8)), 4);
  runeCircle(dim, spot, 4, 3);
  ring(dim, spot, 6, 3);
  sound(dim, SOUNDS.RELIC_USE, p.location, 1.2);
  burst(dim, PARTICLES.SPECTRAL_BURST, add(spot, { x: 0, y: 1, z: 0 }), 4, 2);
  title(playersNear(dim, spot, 64), `${r.color}§lTHE RITUAL BEGINS`, `§7${r.name} answers the call...`, 10, 50, 20);
  later(60, () => {
    const boss = spawnBoss(r.typeId, dim.id, spot);
    if (!boss && !creative && p.isValid) giveItem(p, new ItemStack(itemId, 1));
  }, "ritual");
}

export const relicComponent: ItemCustomComponent = {
  onUse(ev: ItemComponentUseEvent, params: CustomComponentParameters) {
    const p = ev.source;
    const boss = (params.params as { boss?: string })?.boss;
    const itemId = ev.itemStack?.typeId;
    if (!boss || !itemId) return;
    system.run(() => {
      if (p.isValid) beginRitual(p, boss, itemId);
    });
  },
};

export const engineKeyComponent: ItemCustomComponent = {
  onUse(ev: ItemComponentUseEvent) {
    const p = ev.source;
    system.run(() => {
      if (!p.isValid) return;
      if (inExpanse(p) && Math.hypot(p.location.x - GATE_AT.x, p.location.z - GATE_AT.z) < 10) {
        actionbar([p], "§bUse the Engine Key on the Null Gate itself to wake the Colossus.");
        return;
      }
      if (openRiftPortal(p)) playerSound(p, SOUNDS.PORTAL_OPEN, 0.8, 1.2);
    });
  },
};

export const codexComponent: ItemCustomComponent = {
  onUse(ev: ItemComponentUseEvent) {
    const p = ev.source;
    system.run(() => {
      if (p.isValid) void openCodex(p);
    });
  },
};

const CLEANSED = ["wither", "poison", "darkness", "levitation", "slowness", "mining_fatigue", "blindness", "hunger", "weakness"];

export const elixirComponent: ItemCustomComponent = {
  onConsume(ev: ItemComponentConsumeEvent) {
    const e: Entity = ev.source;
    system.run(() => {
      if (!e.isValid) return;
      for (const id of CLEANSED) {
        try {
          e.removeEffect(id);
        } catch {
          /* not present */
        }
      }
      try {
        e.addEffect("regeneration", 200, { amplifier: 1, showParticles: true });
        e.addEffect("absorption", 2400, { amplifier: 1, showParticles: false });
      } catch {
        /* ignore */
      }
      burst(e.dimension, PARTICLES.HEAL_MOTES, add(e.location, { x: 0, y: 1, z: 0 }), 3, 0.6);
      if (e instanceof Player) {
        playerSound(e, SOUNDS.RELIC_USE, 0.6, 1.6);
        actionbar([e], "§bAether floods your veins: event afflictions cleansed.");
      }
    });
  },
};

