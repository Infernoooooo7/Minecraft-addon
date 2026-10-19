// THE SHATTERED EXPANSE — a real custom dimension (DimensionRegistry, void generator) whose terrain the
// scripts build: the Nexus hub, a bridge of stepping stones, the Colossus Arena and procedural floating
// islands generated around players in time-budgeted jobs. Travel uses Rift Portals opened by the Engine Key.
import {
  BlockVolume, Dimension, DimensionRegistry, Entity, Player, system, Vector3, world,
} from "@minecraft/server";
import { profile } from "../core/config.js";
import { actionbar, burst, playerSound, pushFog, removeFog, sound, title } from "../core/fx.js";
import { DIMENSION_EXPANSE, DP, FOG_ID, TAG, TICKING } from "../core/keys.js";
import { log } from "../core/log.js";
import { allPlayers, isTargetable } from "../core/players.js";
import { every, later } from "../core/scheduler.js";
import { readEntity, readWorld, writeEntity, writeWorld } from "../core/state.js";
import { BLOCKS, ENTITIES, FOGS, PARTICLES, SOUNDS, STRUCTURES } from "../generated/ids.js";
import {
  ARENA, bridgeIslands, cellKey, cellsNear, Column, columns, Island, islandForCell, NEXUS,
} from "../logic/islandGen.js";
import { discover, parseJournal } from "../logic/progression.js";
import { Rng } from "../logic/rng.js";

const OVERWORLD = "minecraft:overworld";
const PORTAL_LIFETIME = 1200; // absolute-time ticks an Engine Key rift stays open
export const NEXUS_ARRIVAL: Vector3 = { x: NEXUS.cx + 0.5, y: NEXUS.cy + 1, z: NEXUS.cz + 4.5 };
export const NEXUS_PORTAL_AT: Vector3 = { x: NEXUS.cx + 0.5, y: NEXUS.cy + 1.2, z: NEXUS.cz + 0.5 };
export const GATE_AT: Vector3 = { x: ARENA.cx, y: ARENA.cy + 2, z: ARENA.cz };
export const COLOSSUS_SPAWN: Vector3 = { x: ARENA.cx + 0.5, y: ARENA.cy + 1, z: ARENA.cz + 12.5 };

interface GenState {
  v: 1;
  nexus: boolean;
  arena: boolean;
  done: string[];
}

let gen: GenState = { v: 1, nexus: false, arena: false, done: [] };
const doneSet = new Set<string>();
const building = new Set<string>();
let coreBuilding: Promise<boolean> | undefined;

export function registerExpanseDimension(registry: DimensionRegistry): void {
  try {
    registry.registerCustomDimension(DIMENSION_EXPANSE);
  } catch (e) {
    // on /reload the dimension is already registered; anything else is reported
    log.warn(`custom dimension registration: ${e}`);
  }
}

export function expanse(): Dimension | undefined {
  try {
    return world.getDimension(DIMENSION_EXPANSE);
  } catch {
    return undefined;
  }
}

export function inExpanse(e: Entity): boolean {
  try {
    return e.dimension.id === DIMENSION_EXPANSE;
  } catch {
    return false;
  }
}

function loadGen(): void {
  try {
    const raw = readWorld(DP.EXPANSE_GEN);
    if (raw) {
      const d = JSON.parse(raw) as Partial<GenState>;
      gen = { v: 1, nexus: !!d.nexus, arena: !!d.arena, done: Array.isArray(d.done) ? d.done.slice(0, 1200) : [] };
    }
  } catch {
    gen = { v: 1, nexus: false, arena: false, done: [] };
  }
  doneSet.clear();
  for (const k of gen.done) doneSet.add(k);
}

function saveGen(): void {
  gen.done = [...doneSet];
  writeWorld(DP.EXPANSE_GEN, JSON.stringify(gen));
}

function worldSeed(): number {
  let h = 2166136261;
  for (const ch of world.seed ?? "apocalypse") h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
  return h;
}

// ------------------------------------------------------------------------------------------------
// terrain building (budgeted jobs)
// ------------------------------------------------------------------------------------------------

type Kind = "nexus" | "arena" | "bridge" | "wild";

function topBlock(kind: Kind, c: Column, isl: Island): string {
  const d = Math.hypot(c.x - isl.cx, c.z - isl.cz);
  switch (kind) {
    case "nexus":
      return d < 7.5 ? BLOCKS.RUNESTONE_BRICKS : BLOCKS.VOID_MOSS;
    case "arena":
      return d > isl.r - 6.5 && d < isl.r - 5 ? BLOCKS.CHISELED_RUNESTONE : d < isl.r - 6.5 ? BLOCKS.RUNESTONE_BRICKS : BLOCKS.VOID_MOSS;
    case "bridge":
      return BLOCKS.SHATTERED_STONE;
    default:
      return BLOCKS.VOID_MOSS;
  }
}

/** Builds one island; resolves to true when every column was written (chunks loaded). */
function buildIsland(dim: Dimension, isl: Island, kind: Kind): Promise<boolean> {
  return new Promise((resolve) => {
    const perTick = profile().genColumnsPerTick;
    const rng = new Rng(isl.seed ^ 0x2545f491);
    function* job(): Generator<void, void, void> {
      let failures = 0;
      let n = 0;
      for (const c of columns(isl)) {
        try {
          if (c.bottom <= c.top - 1) {
            dim.fillBlocks(new BlockVolume({ x: c.x, y: c.bottom, z: c.z }, { x: c.x, y: c.top - 1, z: c.z }),
              BLOCKS.SHATTERED_STONE);
          }
          dim.setBlockType({ x: c.x, y: c.top, z: c.z }, topBlock(kind, c, isl));
          if (kind === "wild") {
            if (rng.chance(0.06) && c.top - c.bottom > 3) {
              dim.setBlockType({ x: c.x, y: c.bottom + Math.floor((c.top - c.bottom) / 2), z: c.z }, BLOCKS.RIFT_ORE);
            }
            if (c.deco === "cluster") dim.setBlockType({ x: c.x, y: c.top + 1, z: c.z }, BLOCKS.AETHER_CLUSTER);
            if (c.deco === "crystal") {
              const h = rng.int(2, 4);
              dim.fillBlocks(new BlockVolume({ x: c.x, y: c.top + 1, z: c.z }, { x: c.x, y: c.top + h, z: c.z }),
                BLOCKS.AETHER_CRYSTAL_BLOCK);
            }
          }
        } catch {
          failures++;
        }
        if (++n % perTick === 0) yield;
      }
      resolve(failures === 0);
    }
    system.runJob(job());
  });
}

async function withTicking(id: string, dim: Dimension, from: Vector3, to: Vector3): Promise<boolean> {
  const mgr = world.tickingAreaManager;
  try {
    if (mgr.hasTickingArea(id)) return true;
    const options = { dimension: dim, from, to };
    if (!mgr.hasCapacity(options)) {
      log.warn(`no ticking-area capacity for ${id}`);
      return false;
    }
    await mgr.createTickingArea(id, options);
    return true;
  } catch (e) {
    log.warn(`ticking area ${id} failed: ${e}`);
    return false;
  }
}

function dropTicking(id: string): void {
  try {
    if (world.tickingAreaManager.hasTickingArea(id)) world.tickingAreaManager.removeTickingArea(id);
  } catch {
    /* ignore */
  }
}

function place(structure: string, dim: Dimension, at: Vector3): boolean {
  try {
    world.structureManager.place(structure, dim, at, { includeEntities: false });
    return true;
  } catch (e) {
    log.warn(`structure ${structure} failed: ${e}`);
    return false;
  }
}

function ensureNexusPortal(dim: Dimension): void {
  try {
    const existing = dim.getEntities({ type: ENTITIES.RIFT_PORTAL, location: NEXUS_PORTAL_AT, maxDistance: 3, tags: [TAG.NEXUS_PORTAL] });
    if (existing.length) return;
    const portal = dim.spawnEntity(ENTITIES.RIFT_PORTAL, NEXUS_PORTAL_AT);
    portal.addTag(TAG.NEXUS_PORTAL);
    writeEntity(portal, DP.PORTAL_DEST, "return");
    portal.nameTag = "§bRift Home";
  } catch {
    /* chunk not loaded yet */
  }
}

/** Nexus first (blocking travel), then the bridge and the arena in the background. */
function ensureCore(): Promise<boolean> {
  if (coreBuilding) return coreBuilding;
  coreBuilding = (async () => {
    const dim = expanse();
    if (!dim) return false;
    if (!gen.nexus) {
      const ok = await withTicking(TICKING.NEXUS, dim, { x: NEXUS.cx - 24, y: 64, z: NEXUS.cz - 24 },
        { x: NEXUS.cx + 24, y: 128, z: NEXUS.cz + 24 });
      if (!ok) return false;
      if (!(await buildIsland(dim, NEXUS, "nexus"))) {
        dropTicking(TICKING.NEXUS);
        return false;
      }
      place(STRUCTURES.NEXUS_SHRINE, dim, { x: NEXUS.cx - 6, y: NEXUS.cy, z: NEXUS.cz - 6 });
      ensureNexusPortal(dim);
      gen.nexus = true;
      saveGen();
      dropTicking(TICKING.NEXUS);
    }
    if (!gen.arena) void buildArena(dim);
    return true;
  })();
  const p = coreBuilding;
  void p.finally(() => {
    coreBuilding = undefined;
  });
  return p;
}

async function buildArena(dim: Dimension): Promise<void> {
  if (building.has("arena")) return;
  building.add("arena");
  try {
    const ok = await withTicking(TICKING.ARENA, dim, { x: ARENA.cx - 32, y: 60, z: ARENA.cz - 32 },
      { x: ARENA.cx + 32, y: 120, z: NEXUS.cz });
    if (!ok) return;
    let all = await buildIsland(dim, ARENA, "arena");
    for (const b of bridgeIslands()) all = (await buildIsland(dim, b, "bridge")) && all;
    if (all && place(STRUCTURES.COLOSSUS_ALTAR, dim, { x: ARENA.cx - 4, y: ARENA.cy, z: ARENA.cz - 4 })) {
      gen.arena = true;
      saveGen();
    }
  } finally {
    dropTicking(TICKING.ARENA);
    building.delete("arena");
  }
}

/** Procedural islands in cells near Expanse players, built once each. */
function generateAround(p: Player): void {
  const dim = p.dimension;
  const seed = worldSeed();
  for (const [cx, cz] of cellsNear(p.location.x, p.location.z, 96)) {
    const key = cellKey(cx, cz);
    if (doneSet.has(key) || building.has(key) || building.size > 2) continue;
    const isl = islandForCell(cx, cz, seed);
    if (!isl) {
      doneSet.add(key);
      continue;
    }
    let loaded = false;
    try {
      loaded = dim.isChunkLoaded({ x: isl.cx - isl.r, y: isl.cy, z: isl.cz - isl.r }) &&
        dim.isChunkLoaded({ x: isl.cx + isl.r, y: isl.cy, z: isl.cz + isl.r });
    } catch {
      loaded = false;
    }
    if (!loaded) continue;
    building.add(key);
    void buildIsland(dim, isl, "wild").then((ok) => {
      building.delete(key);
      if (ok) {
        doneSet.add(key);
        saveGen();
      }
    });
  }
}

// ------------------------------------------------------------------------------------------------
// travel
// ------------------------------------------------------------------------------------------------

function saveReturnPoint(p: Player): void {
  if (inExpanse(p)) return;
  writeEntity(p, DP.RETURN_POINT, JSON.stringify({ d: p.dimension.id, x: p.location.x, y: p.location.y, z: p.location.z }));
}

function arriveFx(p: Player): void {
  burst(p.dimension, PARTICLES.PORTAL_GLOW, p.location, 3, 1);
  playerSound(p, SOUNDS.PORTAL_TRAVEL, 1, 1);
}

export async function travelToExpanse(p: Player): Promise<void> {
  saveReturnPoint(p);
  actionbar([p], "§bThe rift pulls you through...");
  const ready = await ensureCore();
  const dim = expanse();
  if (!ready || !dim || !p.isValid) {
    actionbar([p], "§cThe rift collapsed — the Expanse could not be reached. Try again in a moment.");
    return;
  }
  try {
    p.teleport(NEXUS_ARRIVAL, { dimension: dim, facingLocation: { x: NEXUS.cx, y: NEXUS.cy + 1, z: NEXUS.cz - 10 } });
  } catch (e) {
    log.warn(`expanse teleport failed: ${e}`);
    return;
  }
  later(5, () => {
    if (!p.isValid) return;
    arriveFx(p);
    pushFog(p, FOGS.FOG_EXPANSE, FOG_ID.EXPANSE);
    const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
    j.expanseVisits++;
    discover(j, "expanse");
    writeEntity(p, DP.JOURNAL, JSON.stringify(j));
    title([p], "§3§lTHE SHATTERED EXPANSE", "§bThe Colossus Arena lies north across the stones.", 10, 70, 20);
    ensureNexusPortal(dim);
  });
}

export function travelHome(p: Player): void {
  let target: { d: string; x: number; y: number; z: number } | undefined;
  try {
    const raw = readEntity(p, DP.RETURN_POINT);
    if (typeof raw === "string") target = JSON.parse(raw);
  } catch {
    target = undefined;
  }
  let dim: Dimension;
  let loc: Vector3;
  if (target && target.d !== DIMENSION_EXPANSE) {
    dim = world.getDimension(target.d);
    loc = { x: target.x, y: target.y, z: target.z };
  } else {
    const sp = p.getSpawnPoint();
    if (sp) {
      dim = sp.dimension;
      loc = { x: sp.x + 0.5, y: sp.y, z: sp.z + 0.5 };
    } else {
      dim = world.getDimension(OVERWORLD);
      const d = world.getDefaultSpawnLocation();
      loc = { x: d.x + 0.5, y: d.y > 300 ? 120 : d.y, z: d.z + 0.5 };
      p.addEffect("slow_falling", 400, { amplifier: 0, showParticles: false });
    }
  }
  try {
    p.teleport(loc, { dimension: dim });
  } catch (e) {
    log.warn(`return teleport failed: ${e}`);
    return;
  }
  removeFog(p, FOG_ID.EXPANSE);
  later(5, () => {
    if (p.isValid) arriveFx(p);
  });
}

/** Engine Key use outside the Expanse opens a rift to it; inside, a rift home. */
export function openRiftPortal(p: Player): boolean {
  const dest = inExpanse(p) ? "return" : "expanse";
  const dir = p.getViewDirection();
  const at = { x: p.location.x + dir.x * 2.5, y: p.location.y + 1.2, z: p.location.z + dir.z * 2.5 };
  try {
    const portal = p.dimension.spawnEntity(ENTITIES.RIFT_PORTAL, at);
    writeEntity(portal, DP.PORTAL_DEST, dest);
    writeEntity(portal, DP.PORTAL_EXPIRES, world.getAbsoluteTime() + PORTAL_LIFETIME);
    portal.nameTag = dest === "expanse" ? "§3Rift to the Expanse" : "§bRift Home";
    sound(p.dimension, SOUNDS.PORTAL_OPEN, at, 1.2);
    burst(p.dimension, PARTICLES.PORTAL_GLOW, at, 4, 1);
    actionbar([p], dest === "expanse" ? "§3A rift to the Shattered Expanse opens. Step inside." : "§bA rift home opens. Step inside.");
    return true;
  } catch (e) {
    log.warn(`portal spawn failed: ${e}`);
    return false;
  }
}

const travelling = new Set<string>();

function tickPortals(): void {
  const t = world.getAbsoluteTime();
  for (const p of allPlayers()) {
    let portals: Entity[] = [];
    try {
      portals = p.dimension.getEntities({ type: ENTITIES.RIFT_PORTAL, location: p.location, maxDistance: 24 });
    } catch {
      continue;
    }
    for (const portal of portals) {
      const expires = Number(readEntity(portal, DP.PORTAL_EXPIRES) ?? 0);
      if (expires && t > expires && !portal.hasTag(TAG.NEXUS_PORTAL)) {
        burst(portal.dimension, PARTICLES.SPECTRAL_BURST, portal.location, 2, 0.6);
        sound(portal.dimension, SOUNDS.RIFT_CLOSE, portal.location);
        try {
          portal.remove();
        } catch {
          /* gone */
        }
        continue;
      }
      const d = Math.hypot(p.location.x - portal.location.x, p.location.y + 1 - portal.location.y, p.location.z - portal.location.z);
      if (d > 1.6 || travelling.has(p.id)) continue;
      travelling.add(p.id);
      later(40, () => travelling.delete(p.id), "travel-lock");
      const dest = readEntity(portal, DP.PORTAL_DEST);
      if (dest === "expanse") void travelToExpanse(p);
      else travelHome(p);
    }
  }
}

// ------------------------------------------------------------------------------------------------
// Expanse life: fog, void rescue, sentinels, island generation
// ------------------------------------------------------------------------------------------------

function tickExpansePlayers(): void {
  const dim = expanse();
  if (!dim) return;
  let players: Player[] = [];
  try {
    players = dim.getPlayers();
  } catch {
    return;
  }
  for (const p of players) {
    if (p.location.y < NEXUS.cy - 70) {
      // fell off the islands: the Expanse spits you back out at the Nexus, hurt but alive
      try {
        p.teleport(NEXUS_ARRIVAL, { dimension: dim });
        p.addEffect("slow_falling", 100, { amplifier: 0, showParticles: false });
        if (isTargetable(p)) p.applyDamage(6);
        actionbar([p], "§3The void rejects you. You wake at the Nexus.");
      } catch {
        /* ignore */
      }
      continue;
    }
    generateAround(p);
  }
}

function spawnSentinels(): void {
  const dim = expanse();
  if (!dim) return;
  const rng = new Rng((system.currentTick * 2654435761) >>> 0);
  let players: Player[] = [];
  try {
    players = dim.getPlayers().filter(isTargetable);
  } catch {
    return;
  }
  for (const p of players) {
    try {
      const near = dim.getEntities({ type: ENTITIES.RIFT_SENTINEL, location: p.location, maxDistance: 48 }).length;
      if (near >= profile().sentinelsPerPlayer) continue;
      if (Math.hypot(p.location.x - NEXUS.cx, p.location.z - NEXUS.cz) < 24) continue; // the Nexus is a safe haven
      // islands are sparse: try a few spots and spawn on the first solid one
      for (let attempt = 0; attempt < 6; attempt++) {
        const ang = rng.next() * Math.PI * 2;
        const r = rng.range(14, 34);
        const x = p.location.x + Math.cos(ang) * r;
        const z = p.location.z + Math.sin(ang) * r;
        const top = dim.getTopmostBlock({ x, z });
        if (!top || Math.abs(top.location.y - p.location.y) > 24) continue;
        const typeId = rng.chance(0.25) ? ENTITIES.VOID_CRAWLER : ENTITIES.RIFT_SENTINEL;
        const e = dim.spawnEntity(typeId, { x, y: top.location.y + 1, z });
        burst(dim, PARTICLES.SPECTRAL_BURST, e.location, 2, 0.6);
        break;
      }
    } catch {
      /* unloaded */
    }
  }
}

export function initExpanse(): void {
  loadGen();
  every("portals", 10, tickPortals, 3);
  every("expanse-players", 40, tickExpansePlayers, 5);
  every("expanse-spawns", 160, spawnSentinels, 11);

  world.afterEvents.playerDimensionChange.subscribe((ev) => {
    const p = ev.player;
    system.run(() => {
      if (!p.isValid) return;
      if (ev.toDimension.id === DIMENSION_EXPANSE) pushFog(p, FOGS.FOG_EXPANSE, FOG_ID.EXPANSE);
      else removeFog(p, FOG_ID.EXPANSE);
    });
  });
}

/** Fog is session state on the client: re-apply it to players who log in inside the Expanse. */
export function syncExpanseFog(p: Player): void {
  if (inExpanse(p)) pushFog(p, FOGS.FOG_EXPANSE, FOG_ID.EXPANSE);
  else removeFog(p, FOG_ID.EXPANSE);
}

export function expanseStatus(): { nexus: boolean; arena: boolean; cells: number } {
  return { nexus: gen.nexus, arena: gen.arena, cells: doneSet.size };
}
