// World configuration (operators edit it from the Engine Codex or /apocalypse:profile).
import type { Frequency } from "../logic/event_scheduler.js";
import { getProfile, Profile, ProfileId } from "../logic/profiles.js";
import { DP } from "./keys.js";
import { log } from "./log.js";
import { readWorld, writeWorld } from "./state.js";

export type Intensity = "mild" | "normal" | "brutal";
export type Difficulty = "story" | "normal" | "nightmare";

export interface WorldConfig {
  profile: ProfileId;
  eventFrequency: Frequency;
  eventIntensity: Intensity;
  bossDifficulty: Difficulty;
  /** Meteors and boss explosions may break blocks. */
  terrainDamage: boolean;
  /** Void Storm lightning strikes. */
  lightning: boolean;
  /** Give new players an Engine Codex. */
  giveCodex: boolean;
  events: Record<string, boolean>;
  debug: boolean;
}

const DEFAULTS: WorldConfig = {
  profile: "balanced",
  eventFrequency: "normal",
  eventIntensity: "normal",
  bossDifficulty: "normal",
  terrainDamage: false,
  lightning: true,
  giveCodex: true,
  events: {},
  debug: false,
};

let current: WorldConfig = { ...DEFAULTS };

export function loadConfig(): WorldConfig {
  const raw = readWorld(DP.CONFIG);
  if (raw) {
    try {
      current = { ...DEFAULTS, ...(JSON.parse(raw) as Partial<WorldConfig>) };
    } catch {
      current = { ...DEFAULTS };
    }
  }
  log.setDebug(current.debug);
  return current;
}

export function config(): WorldConfig {
  return current;
}

export function profile(): Profile {
  return getProfile(current.profile);
}

export function saveConfig(patch: Partial<WorldConfig>): WorldConfig {
  current = { ...current, ...patch };
  writeWorld(DP.CONFIG, JSON.stringify(current));
  log.setDebug(current.debug);
  return current;
}

export function intensityScale(): number {
  return { mild: 0.6, normal: 1, brutal: 1.5 }[current.eventIntensity];
}

/** Damage multiplier for scripted boss attacks. */
export function bossDamageScale(): number {
  return { story: 0.6, normal: 1, nightmare: 1.45 }[current.bossDifficulty];
}

/** Health tier offset for bosses (story = fewer tiers). */
export function bossTierBonus(): number {
  return { story: -1, normal: 0, nightmare: 1 }[current.bossDifficulty];
}
