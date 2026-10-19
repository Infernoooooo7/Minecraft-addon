// Mobile performance profiles. Pure data; unit tested for monotonicity.

export type ProfileId = "potato" | "balanced" | "enhanced";

export interface Profile {
  id: ProfileId;
  label: string;
  /** Multiplier for script-spawned particle counts. */
  particles: number;
  /** Max concurrently alive event mobs per player and in total. */
  eventMobsPerPlayer: number;
  eventMobsGlobal: number;
  /** Max boss adds alive per boss. */
  bossAdds: number;
  /** Meteors spawned per wave during a Meteor Shower. */
  meteorsPerWave: number;
  /** Interval (ticks) between ambient event particle pulses around each player. */
  ambientInterval: number;
  /** Shattered Expanse terrain columns generated per tick. */
  genColumnsPerTick: number;
  /** Max Rift Sentinels near each player in the Expanse. */
  sentinelsPerPlayer: number;
  /** Boss brain update interval in ticks. */
  bossTickInterval: number;
}

export const PROFILES: Record<ProfileId, Profile> = {
  potato: {
    id: "potato", label: "Potato", particles: 0.35, eventMobsPerPlayer: 2, eventMobsGlobal: 10, bossAdds: 3,
    meteorsPerWave: 1, ambientInterval: 40, genColumnsPerTick: 24, sentinelsPerPlayer: 1, bossTickInterval: 5,
  },
  balanced: {
    id: "balanced", label: "Balanced", particles: 1.0, eventMobsPerPlayer: 4, eventMobsGlobal: 18, bossAdds: 5,
    meteorsPerWave: 2, ambientInterval: 20, genColumnsPerTick: 48, sentinelsPerPlayer: 2, bossTickInterval: 4,
  },
  enhanced: {
    id: "enhanced", label: "Enhanced", particles: 1.6, eventMobsPerPlayer: 6, eventMobsGlobal: 28, bossAdds: 7,
    meteorsPerWave: 4, ambientInterval: 10, genColumnsPerTick: 96, sentinelsPerPlayer: 3, bossTickInterval: 4,
  },
};

export function getProfile(id: string | undefined): Profile {
  return id && id in PROFILES ? PROFILES[id as ProfileId] : PROFILES.balanced;
}

/** Scale an integer count by the particle multiplier, never below `min`. */
export function scaledCount(base: number, mult: number, min = 1): number {
  return Math.max(min, Math.round(base * mult));
}
