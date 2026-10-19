# Changelog

## [1.0.0] — 2026-10-19

First release.

### Added
- Four bosses with scripted multi-phase AI: The Hollow King, The Star Eater, The Root Titan and
  The Null Colossus (state machine with telegraphs, range checks, cooldowns, invulnerable phase
  transitions, multiplayer health tiers, leash, de-duplicated rewards and first-kill bonuses).
- Five creatures: Hollow Shade (with Crimson variant), Thornling, Void Crawler, Astral Mite,
  Rift Sentinel; hazards and projectiles: Void Rift, Meteor, Star Bolt, Rift Portal.
- Seven dynamic world events: Blood Moon, Void Storm, Meteor Shower, Reality Fracture, Eclipse,
  Ancient Awakening and Corruption Surge, with persistence, cooldowns, caps, cleanup and kill drops.
- The Shattered Expanse: a custom dimension (stable `DimensionRegistry`) with the Nexus, a causeway,
  the Colossus Arena and procedural floating islands, Engine Key rifts and void rescue.
- 41 items (7 weapons with abilities, 3 armor sets with set bonuses, summoning relics, Engine Key,
  Engine Codex, Aether Elixir, materials), 14 blocks, 30 recipes, Blighted Wilds biome, ruins.
- Engine Codex UI (journal, boss/event/crafting guides, operator settings, admin tools) and the
  commands `/apocalypse:codex`, `/apocalypse:event`, `/apocalypse:profile`, `/apocalypse:summon`.
- Original generated art and audio: HD textures, emissive layers, PBR texture sets for Vibrant
  Visuals, 29 particles, 7 fogs, biome atmosphere/lighting/color grading, synthesized sounds.
- Potato / Balanced / Enhanced resource subpacks and matching script performance profiles.
- `build.py` (one-command build and packaging with archive inspection), `validate.py` (static
  validation incl. official schemas and vanilla ids), unit tests, a strict mock-runtime simulation,
  save/reload tests and tooling tests.

### Fixed during development (found by the test suite)
- The Nexus→Arena stepping stones were ~7 blocks apart and could not be jumped; replaced with a
  continuous causeway (unit test + flood-fill walkability check).
- Null Colossus: the post-phase vent's bonus-damage window ended 52 ticks before its visual; an
  older vent's timer could hide a newer vent; a delayed vent could fire after the boss died.
- Event state was not rebased after a reload because the save timestamp was read as a string,
  which would have stretched an active event by the previous session's entire tick count.
- Ores dropped both the block and the shards with Silk Touch (Silk Touch/Fortune now handled by
  script).
- An invalid vanilla block id (`minecraft:dead_bush` → `minecraft:deadbush`) in the ruin features.
- Duplicate `undead` family on the Hollow Shade; Null Aegis rift immunity was described but not
  implemented.
