// Script-only identifiers (dynamic properties, tags, ticking areas, commands, the custom dimension).
// Content identifiers (entities, items, blocks, particles, sounds...) live in ../generated/ids.ts.

export const DIMENSION_EXPANSE = "apocalypse:shattered_expanse";

export const DP = {
  CONFIG: "apocalypse:config",
  EVENT_STATE: "apocalypse:event_state",
  EVENT_SAVED_AT: "apocalypse:event_saved_at",
  LEDGER: "apocalypse:ledger",
  WORLD_PROGRESS: "apocalypse:world_progress",
  EXPANSE_GEN: "apocalypse:expanse_gen",
  JOURNAL: "apocalypse:journal",
  WELCOMED: "apocalypse:welcomed",
  RETURN_POINT: "apocalypse:return_point",
  BOSS_ARENA: "apocalypse:arena",
  BOSS_MACHINE: "apocalypse:machine",
  OWNER: "apocalypse:owner",
  EVENT_TAG: "apocalypse:event",
  PORTAL_DEST: "apocalypse:dest",
  PORTAL_EXPIRES: "apocalypse:expires",
} as const;

export const TAG = {
  EVENT_MOB: "apocalypse:event_mob",
  BOSS_ADD: "apocalypse:boss_add",
  HAZARD: "apocalypse:hazard",
  NEXUS_PORTAL: "apocalypse:nexus_portal",
} as const;

export const FOG_ID = {
  EVENT: "apocalypse_event",
  EXPANSE: "apocalypse_expanse",
} as const;

export const TICKING = {
  NEXUS: "apocalypse:nexus_area",
  ARENA: "apocalypse:arena_area",
} as const;

export const COMMAND = {
  CODEX: "apocalypse:codex",
  EVENT: "apocalypse:event",
  PROFILE: "apocalypse:profile",
  SUMMON: "apocalypse:summon",
  EVENT_ENUM: "apocalypse:event_id",
  ACTION_ENUM: "apocalypse:event_action",
  PROFILE_ENUM: "apocalypse:profile_id",
  BOSS_ENUM: "apocalypse:boss_id",
} as const;

export const COMPONENT = {
  ABILITY: "apocalypse:ability",
  ON_HIT: "apocalypse:on_hit",
  RELIC: "apocalypse:relic",
  ENGINE_KEY: "apocalypse:engine_key",
  CODEX: "apocalypse:codex",
  ELIXIR: "apocalypse:elixir",
  ORE_XP: "apocalypse:ore_xp",
  CACHE: "apocalypse:cache",
  NULL_GATE: "apocalypse:null_gate",
} as const;

export const PROP = {
  ACTION: "apocalypse:action",
  PHASE: "apocalypse:phase",
  VARIANT: "apocalypse:variant",
  VENTED: "apocalypse:vented",
} as const;

export const EVENT_TRIGGER = {
  BECOME_CRIMSON: "apocalypse:become_crimson",
  EXPIRE: "apocalypse:expire",
  TIER: (n: number) => `apocalypse:tier_${n}`,
} as const;
