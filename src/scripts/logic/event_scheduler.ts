// Dynamic world event scheduling. Pure and unit tested.

import { Rng, weightedPick } from "./rng.js";

export type TimeWindow = "night" | "day" | "any";
export type Frequency = "off" | "rare" | "normal" | "frequent";

export interface EventMeta {
  id: string;
  name: string;
  window: TimeWindow;
  /** Duration bounds in ticks. */
  minTicks: number;
  maxTicks: number;
  /** Per-event cooldown after it ends, ticks. */
  cooldownTicks: number;
  weight: number;
  /** Earliest in-game day (world.getDay()) the event can occur on. */
  minDay: number;
}

export interface EventState {
  active: string | null;
  startTick: number;
  endTick: number;
  /** Global quiet period after any event ends. */
  cooldownUntil: number;
  lastEnd: Record<string, number>;
  /** Count of events completed (for statistics / codex). */
  completed: number;
}

export const DAY_TICKS = 24000;
export const GLOBAL_COOLDOWN_TICKS = 6000;
export const ROLL_INTERVAL_TICKS = 100;

export function newState(): EventState {
  return { active: null, startTick: 0, endTick: 0, cooldownUntil: 0, lastEnd: {}, completed: 0 };
}

export function isNight(timeOfDay: number): boolean {
  const t = ((timeOfDay % DAY_TICKS) + DAY_TICKS) % DAY_TICKS;
  return t >= 13000 && t < 23000;
}

export function windowOk(w: TimeWindow, timeOfDay: number): boolean {
  if (w === "any") return true;
  return w === "night" ? isNight(timeOfDay) : !isNight(timeOfDay);
}

export function eventsPerDay(f: Frequency): number {
  return { off: 0, rare: 0.5, normal: 1, frequent: 2 }[f];
}

/** Probability that a single scheduler roll starts an event, so that ~eventsPerDay happen per day. */
export function rollChance(f: Frequency, intervalTicks = ROLL_INTERVAL_TICKS): number {
  return Math.min(1, (eventsPerDay(f) * intervalTicks) / DAY_TICKS * 1.6);
}

export function eligible(metas: readonly EventMeta[], s: EventState, now: number, timeOfDay: number, day: number,
  enabled: Record<string, boolean>): EventMeta[] {
  if (s.active) return [];
  if (now < s.cooldownUntil) return [];
  return metas.filter((m) =>
    enabled[m.id] !== false &&
    day >= m.minDay &&
    windowOk(m.window, timeOfDay) &&
    now >= (s.lastEnd[m.id] ?? -Infinity) + m.cooldownTicks);
}

export function pick(metas: readonly EventMeta[], rng: Rng): EventMeta | undefined {
  return weightedPick(metas, (m) => m.weight, rng.next());
}

export function start(s: EventState, m: EventMeta, now: number, rng: Rng): EventState {
  const dur = Math.round(rng.range(m.minTicks, m.maxTicks));
  return { ...s, active: m.id, startTick: now, endTick: now + dur };
}

export function shouldEnd(s: EventState, m: EventMeta | undefined, now: number, timeOfDay: number): boolean {
  if (!s.active) return false;
  if (!m) return true;
  if (now >= s.endTick) return true;
  // night events fade at dawn, day events at dusk (give a short grace period at the boundary)
  return m.window !== "any" && !windowOk(m.window, timeOfDay) && now - s.startTick > 200;
}

export function end(s: EventState, now: number): EventState {
  if (!s.active) return s;
  return {
    ...s,
    active: null,
    lastEnd: { ...s.lastEnd, [s.active]: now },
    cooldownUntil: now + GLOBAL_COOLDOWN_TICKS,
    completed: s.completed + 1,
  };
}

export function parseState(json: string | undefined): EventState {
  if (!json) return newState();
  try {
    const d = JSON.parse(json) as Partial<EventState>;
    return {
      active: typeof d.active === "string" ? d.active : null,
      startTick: Number(d.startTick) || 0,
      endTick: Number(d.endTick) || 0,
      cooldownUntil: Number(d.cooldownUntil) || 0,
      lastEnd: d.lastEnd && typeof d.lastEnd === "object" ? d.lastEnd : {},
      completed: Number(d.completed) || 0,
    };
  } catch {
    return newState();
  }
}

/**
 * Persisted ticks come from a previous session's system.currentTick, which restarts at 0 on load.
 * Rebase every stored tick so remaining durations/cooldowns carry over.
 */
export function rebase(s: EventState, savedAt: number, now: number): EventState {
  const shift = now - savedAt;
  const lastEnd: Record<string, number> = {};
  for (const [k, v] of Object.entries(s.lastEnd)) lastEnd[k] = v + shift;
  return {
    ...s,
    startTick: s.startTick + shift,
    endTick: s.endTick + shift,
    cooldownUntil: s.cooldownUntil + shift,
    lastEnd,
  };
}
