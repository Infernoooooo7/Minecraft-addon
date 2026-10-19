// Dynamic world event runtime: rolls, start/stop, persistence across reloads, fog, bounded spawns.
import { Dimension, Entity, ItemStack, Player, system, Vector3, world } from "@minecraft/server";
import { config, profile } from "../core/config.js";
import { burst, playerSound, pushFog, removeFog, title } from "../core/fx.js";
import { DP, FOG_ID, TAG } from "../core/keys.js";
import { log } from "../core/log.js";
import { allPlayers, isTargetable } from "../core/players.js";
import { every, now } from "../core/scheduler.js";
import { readEntity, readWorld, readWorldNumber, writeEntity, writeWorld } from "../core/state.js";
import { PARTICLES, SOUNDS } from "../generated/ids.js";
import {
  end, EventMeta, eligible, EventState, parseState, pick, rebase, rollChance, ROLL_INTERVAL_TICKS, shouldEnd, start,
} from "../logic/event_scheduler.js";
import { parseJournal, recordEvent } from "../logic/progression.js";
import { Rng } from "../logic/rng.js";

export interface EventCtx {
  now: number;
  elapsed: number;
  overworld: Dimension;
  players: Player[];
  rng: Rng;
}

/** Bonus drop rolled when a player kills a hostile mob while the event is active. */
export interface KillDrop {
  item: string;
  chance: number;
  min?: number;
  max?: number;
  /** Restrict to these entity types (default: any monster). */
  types?: string[];
}

export interface WorldEvent {
  meta: EventMeta;
  /** One-line gameplay summary for the Engine Codex. */
  summary: string;
  color: string;
  fog?: string;
  startTitle: string;
  startSubtitle: string;
  startSound: string;
  onStart?(ctx: EventCtx): void;
  /** Called every second while active. */
  onPulse(ctx: EventCtx): void;
  onEnd?(ctx: EventCtx): void;
  killDrops?: KillDrop[];
}

const events = new Map<string, WorldEvent>();
let state: EventState = parseState(undefined);
const rng = new Rng(Date.now() & 0xffffffff);
const spawned = new Map<string, Entity>();

export function registerEvent(e: WorldEvent): void {
  events.set(e.meta.id, e);
}

export function allEvents(): WorldEvent[] {
  return [...events.values()];
}

export function activeEvent(): WorldEvent | undefined {
  return state.active ? events.get(state.active) : undefined;
}

export function eventState(): EventState {
  return state;
}

function persist(): void {
  writeWorld(DP.EVENT_STATE, JSON.stringify(state));
  writeWorld(DP.EVENT_SAVED_AT, now());
}

function overworld(): Dimension {
  return world.getDimension("minecraft:overworld");
}

function eventPlayers(): Player[] {
  return allPlayers().filter((p) => {
    try {
      return p.dimension.id === "minecraft:overworld";
    } catch {
      return false;
    }
  });
}

function ctx(): EventCtx {
  return { now: now(), elapsed: now() - state.startTick, overworld: overworld(), players: eventPlayers(), rng };
}

export function startEvent(id: string, forced = false): boolean {
  const ev = events.get(id);
  if (!ev) return false;
  if (state.active) stopEvent(false);
  if (!forced && !eligible([ev.meta], state, now(), world.getTimeOfDay(), world.getDay(), config().events).length) {
    return false;
  }
  state = start(state, ev.meta, now(), rng);
  persist();
  const c = ctx();
  for (const p of c.players) {
    if (ev.fog) pushFog(p, ev.fog, FOG_ID.EVENT);
    playerSound(p, ev.startSound, 1, 1);
  }
  title(c.players, `${ev.color}§l${ev.startTitle}`, ev.startSubtitle, 10, 70, 30);
  world.sendMessage(`${ev.color}§l[${ev.meta.name}]§r ${ev.startSubtitle}`);
  try {
    ev.onStart?.(c);
  } catch (e) {
    log.error(`event ${id} start`, e);
  }
  log.debug(`event ${id} started for ${state.endTick - state.startTick} ticks`);
  return true;
}

export function stopEvent(natural = true): void {
  const ev = activeEvent();
  if (!ev) return;
  const c = ctx();
  try {
    ev.onEnd?.(c);
  } catch (e) {
    log.error(`event ${ev.meta.id} end`, e);
  }
  for (const p of allPlayers()) removeFog(p, FOG_ID.EVENT);
  despawnEventEntities();
  if (natural) {
    for (const p of c.players) {
      if (!isTargetable(p)) continue;
      const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
      recordEvent(j, ev.meta.id);
      writeEntity(p, DP.JOURNAL, JSON.stringify(j));
      playerSound(p, SOUNDS.EVENT_END, 0.8, 1);
    }
    world.sendMessage(`${ev.color}[${ev.meta.name}]§r has ended. Survivors record it in their Engine Codex.`);
  }
  state = end(state, now());
  persist();
}

// ------------------------------------------------------------------------------------------------
// bounded event spawns
// ------------------------------------------------------------------------------------------------

function pruneSpawned(): void {
  for (const [id, e] of spawned) if (!e.isValid) spawned.delete(id);
}

export function eventMobCount(): number {
  pruneSpawned();
  return spawned.size;
}

export function nearbyEventMobs(p: Player, radius = 40): number {
  pruneSpawned();
  let n = 0;
  for (const e of spawned.values()) {
    try {
      const l = e.location;
      if (e.dimension.id === p.dimension.id && Math.hypot(l.x - p.location.x, l.z - p.location.z) < radius) n++;
    } catch {
      /* ignore */
    }
  }
  return n;
}

/** Spawn an event entity near a player if the per-player and global caps allow it. */
export function spawnForEvent(p: Player, typeId: string, minDist: number, maxDist: number, spawnEvent?: string,
  ignoreCap = false): Entity | undefined {
  const prof = profile();
  if (!ignoreCap && (eventMobCount() >= prof.eventMobsGlobal || nearbyEventMobs(p) >= prof.eventMobsPerPlayer)) return undefined;
  const dim = p.dimension;
  for (let attempt = 0; attempt < 4; attempt++) {
    const ang = rng.next() * Math.PI * 2;
    const d = rng.range(minDist, maxDist);
    const x = p.location.x + Math.cos(ang) * d;
    const z = p.location.z + Math.sin(ang) * d;
    try {
      const top = dim.getTopmostBlock({ x, z }, Math.min(dim.heightRange.max - 1, p.location.y + 24));
      if (!top || top.isLiquid || Math.abs(top.location.y - p.location.y) > 20) continue;
      const e = dim.spawnEntity(typeId, { x, y: top.location.y + 1, z }, spawnEvent ? { spawnEvent } : undefined);
      e.addTag(TAG.EVENT_MOB);
      writeEntity(e, DP.EVENT_TAG, state.active ?? "");
      spawned.set(e.id, e);
      burst(dim, PARTICLES.SPECTRAL_BURST, e.location, 1, 0.3);
      return e;
    } catch {
      /* unloaded / blocked: try another spot */
    }
  }
  return undefined;
}

/** Spawn an event entity at a location (meteor impacts, caches) under the global cap. */
export function spawnEventMobAt(dim: Dimension, typeId: string, loc: Vector3, spawnEvent?: string,
  ignoreCap = false): Entity | undefined {
  if (!ignoreCap && eventMobCount() >= profile().eventMobsGlobal) return undefined;
  try {
    const e = dim.spawnEntity(typeId, loc, spawnEvent ? { spawnEvent } : undefined);
    e.addTag(TAG.EVENT_MOB);
    writeEntity(e, DP.EVENT_TAG, state.active ?? "");
    spawned.set(e.id, e);
    return e;
  } catch {
    return undefined;
  }
}

/** Live event entities, optionally of one type (used for hazard ticking). */
export function eventEntities(typeId?: string): Entity[] {
  pruneSpawned();
  const out: Entity[] = [];
  for (const e of spawned.values()) if (!typeId || e.typeId === typeId) out.push(e);
  return out;
}

export function isEventEntity(id: string): boolean {
  return spawned.has(id);
}

function rollKillDrops(dead: Entity, killer: Entity | undefined): void {
  const ev = activeEvent();
  if (!ev?.killDrops?.length || !killer || killer.typeId !== "minecraft:player") return;
  let loc: Vector3;
  let dim: Dimension;
  try {
    if (dead.dimension.id !== "minecraft:overworld") return;
    if (!dead.matches({ families: ["monster"] }) || dead.matches({ families: ["apocalypse_boss"] })) return;
    loc = dead.location;
    dim = dead.dimension;
  } catch {
    return;
  }
  for (const d of ev.killDrops) {
    if (d.types && !d.types.includes(dead.typeId)) continue;
    if (!rng.chance(d.chance)) continue;
    const n = Math.round(rng.range(d.min ?? 1, d.max ?? d.min ?? 1));
    try {
      dim.spawnItem(new ItemStack(d.item, Math.max(1, n)), loc);
    } catch {
      /* unloaded */
    }
  }
}

function despawnEventEntities(): void {
  for (const e of spawned.values()) {
    try {
      if (e.isValid) {
        burst(e.dimension, PARTICLES.SPECTRAL_BURST, e.location, 1, 0.3);
        e.remove();
      }
    } catch {
      /* gone */
    }
  }
  spawned.clear();
  // also clean tagged leftovers near players (e.g. after a reload, when references were lost)
  for (const p of allPlayers()) {
    try {
      for (const e of p.dimension.getEntities({ tags: [TAG.EVENT_MOB], location: p.location, maxDistance: 96 })) e.remove();
    } catch {
      /* ignore */
    }
  }
}

// ------------------------------------------------------------------------------------------------
// wiring
// ------------------------------------------------------------------------------------------------

export function syncPlayerFog(p: Player): void {
  removeFog(p, FOG_ID.EVENT);
  const ev = activeEvent();
  try {
    if (ev?.fog && p.dimension.id === "minecraft:overworld") pushFog(p, ev.fog, FOG_ID.EVENT);
  } catch {
    /* ignore */
  }
}

export function initEventRuntime(): void {
  const savedAt = readWorldNumber(DP.EVENT_SAVED_AT, 0);
  // tick counters restart with each session: rebase stored ticks onto the current clock
  state = rebase(parseState(readWorld(DP.EVENT_STATE)), savedAt, now());
  persist();

  every("event-scheduler", ROLL_INTERVAL_TICKS, () => {
    const ev = activeEvent();
    const tod = world.getTimeOfDay();
    if (state.active && shouldEnd(state, ev?.meta, now(), tod)) {
      stopEvent(true);
      return;
    }
    if (state.active) return;
    const cfg = config();
    if (cfg.eventFrequency === "off" || eventPlayers().length === 0) return;
    if (!rng.chance(rollChance(cfg.eventFrequency))) return;
    const options = eligible(allEvents().map((e) => e.meta), state, now(), tod, world.getDay(), cfg.events);
    const chosen = pick(options, rng);
    if (chosen) startEvent(chosen.id);
  }, 2);

  every("event-pulse", 20, () => {
    const ev = activeEvent();
    if (!ev) return;
    ev.onPulse(ctx());
  }, 5);

  every("event-persist", 600, () => persist(), 9);

  // dimension changes: event fog belongs to the Overworld only
  world.afterEvents.playerDimensionChange.subscribe((e) => {
    system.run(() => syncPlayerFog(e.player));
  });

  world.afterEvents.entityDie.subscribe((e) => {
    spawned.delete(e.deadEntity.id);
    rollKillDrops(e.deadEntity, e.damageSource.damagingEntity);
  });
}
