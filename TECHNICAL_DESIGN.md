# APOCALYPSE ENGINE — Technical Design

Namespace: `apocalypse:` · Platform: Minecraft Bedrock Edition (Android first, works on all Bedrock platforms)

This document records the verified platform facts the add-on is built on, the architecture, and the
deliberate limits. Every API, component and file format used was checked against an authoritative
source (listed in §1) — nothing is taken from Java Edition or invented.

---

## 1. Target platform and evidence

| Item | Value | Evidence |
|---|---|---|
| Tested-against game version | **Bedrock 1.26.50** (current stable, hotfixes 1.26.51/1.26.52) | `Mojang/bedrock-samples/version.json` → `"latest": "1.26.50.4"` dated 15‑09‑2026; vanilla manifests use `min_engine_version [1,26,50]` |
| Minimum supported game version | **Bedrock 1.26.30** | Lowest version that ships every stable API we use (`DimensionRegistry`, `@minecraft/server` 2.8.0) |
| Manifest `min_engine_version` | `[1, 26, 30]` | Allows import on 1.26.30+ (a higher value hides the pack on older clients) |
| Script module | `@minecraft/server` **2.8.0** (stable) | npm publish 2026‑06‑16 together with 1.26.30; typings installed and used for compile-time checking |
| UI module | `@minecraft/server-ui` **2.0.0** (stable) | peer dependency `@minecraft/server ^2.0.0` |
| Experimental toggles required | **None** | Every feature below is in stable APIs/format versions (see §9) |

Authoritative sources consulted (all fetched during development, not recalled from memory):

* `Mojang/bedrock-samples` (main = 1.26.50.4): vanilla behavior/resource packs, **969 official JSON
  schemas** (`metadata/json_schemas`), script/engine metadata.
* `MicrosoftDocs/minecraft-creator` (source of learn.microsoft.com/minecraft/creator): update notes
  1.21.90 → 1.26.40, manifest reference, scripting v2 / custom components / custom dimensions,
  Vibrant Visuals + texture-set references, materials, subpacks, texture budgets, features,
  partial biome replacement, custom projectiles.
* npm: `@minecraft/server@2.8.0`, `@minecraft/server-ui@2.0.0`, `@minecraft/vanilla-data@1.26.52`
  official type definitions.
* `@minecraft/creator-tools@0.20.0` (Mojang's official validator / renderer / structure builder).

### Format versions used

| File type | `format_version` | Why |
|---|---|---|
| BP entities | `1.26.30` | Matches minimum game version; validated against official 1.26.30 entity schema (400 components). Uses `pushable_by_block`/`pushable_by_entity` (legacy `minecraft:pushable` is no longer parsed since 1.26.10) |
| BP items | `1.26.30` | Custom Components V2 (component id directly in `components`), `minecraft:wearable.protection` |
| BP blocks | `1.26.30` | Parsed with the 1.26.20 block parser: `minecraft:tags` is an array, strict light/material validation |
| Recipes | `1.20.10` | Same as current vanilla recipes |
| Spawn rules | `1.8.0` | Same as vanilla |
| Features / feature rules | `1.21.20` | Scatter features use the `distribution` object layout |
| Biome (BP) / client biome | `1.21.120` | Same as vanilla biome files |
| Client entity / attachables | `1.10.0` | Same as vanilla |
| Geometry | `1.12.0` | Widely supported Bedrock geometry schema |
| Animations / controllers / render controllers | `1.8.0` / `1.10.0` / `1.8.0` | Same as vanilla |
| Particles | `1.10.0` | Classic particle schema, still parsed |
| Texture sets (Vibrant Visuals) | `1.21.30` | Texture-set schema with MER/MERS layers |
| Fog | `1.16.100` | Vanilla fog schema |

---

## 2. Pack architecture

```
APOCALYPSE_ENGINE/
├── behavior_pack/            # "APOCALYPSE ENGINE [BP]" — data + script modules
│   ├── manifest.json         # depends on RP uuid + @minecraft/server 2.8.0 + server-ui 2.0.0
│   ├── entities/ items/ blocks/ recipes/ loot_tables/ spawn_rules/
│   ├── features/ feature_rules/ biomes/ structures/apocalypse/
│   ├── scripts/              # compiled JavaScript (from src/scripts TypeScript)
│   └── texts/
├── resource_pack/            # "APOCALYPSE ENGINE [RP]" — visuals and audio
│   ├── manifest.json         # capabilities: ["pbr"], 3 subpacks
│   ├── entity/ models/ animations/ animation_controllers/ render_controllers/ attachables/
│   ├── particles/ fogs/ biomes/ sounds/ textures/ texts/
│   └── subpacks/potato | balanced | enhanced
├── src/scripts/              # TypeScript sources (type-checked against official typings)
├── tools/                    # deterministic generators: textures, geometry, animations, sounds,
│                             # structures, all pack JSON
├── tests/                    # node:test unit tests for pure logic + Python validator tests
├── docs/                     # gameplay guide, lore, model previews
├── build.py  validate.py
└── release/                  # generated deliverables
```

* The **behavior pack depends on the resource pack** (header uuid + version). The resource pack does
  **not** depend back — circular pack dependencies can stop both packs from loading.
* All UUIDs are generated once and stored in `tools/pack_ids.json` so upgrades keep the same pack
  identity (re-importing a higher `header.version` replaces the old copy).
* Everything in the packs is generated deterministically by `tools/generate_all.py` (fixed seeds), so
  the source project rebuilds byte-identical assets. Generated files are committed so the packs are
  complete without running the generators.

---

## 3. Gameplay architecture (Script API)

Scripts are written in TypeScript (`src/scripts`), compiled by `tsc` with `strict` mode against the
**2.8.0** typings, so any API that does not exist in the stable 2.8.0 surface fails the build.

```
main.ts                 startup registration (custom components, commands, custom dimension)
core/    config, scheduler (tick-sliced tasks), persistent state (dynamic properties), fx helpers
logic/   PURE modules with no @minecraft imports — unit tested in Node:
         bossMachine (phases, attack selection, cooldowns), eventScheduler, rewardLedger,
         progression, profiles, islandGen (dimension terrain), rng, vec
bosses/  bossRuntime + hollowKing, starEater, rootTitan, nullColossus
events/  eventRuntime + bloodMoon, voidStorm, meteorShower, realityFracture, eclipse
items/   weapon abilities (custom components), relics (boss summons), armor set bonuses
world/   expanse (custom dimension: registration, island generation, portals, sentinels), ores
ui/      Engine Codex (journal, settings, admin)
```

### 3.1 Boss state machine (all four bosses)

Each boss is a JSON entity (movement, targeting, melee, boss bar via `minecraft:boss`, health tiers)
plus a scripted **brain** ticked every 4 game ticks (5 Hz):

```
          ┌──────────── phase threshold crossed ─────────────┐
          ▼                                                  │
 IDLE ──select attack──▶ TELEGRAPH ──windup──▶ EXECUTE ──▶ RECOVER ──▶ IDLE
   ▲  (range + cooldown +           (warning particles,        (damage,     (vulnerability
   │   phase filtered, weighted)     sound, title, anim)        summons)     window)
   └────────────── TRANSITION (invulnerable roar, adds, new attack pool) ◀──┘
```

* **Target selection**: nearest valid player (survival/adventure, same dimension, ≤ 40 blocks);
  keeps the current target while valid; re-evaluates every second.
* **Range checks**: every attack declares `[minRange, maxRange]`; only attacks whose range contains
  the current target distance are eligible.
* **Telegraphs**: every heavy attack has a wind-up (0.8–3 s) with ground-ring/line particles, a sound
  cue, an action-bar warning to nearby players and a client animation (synced entity property
  `apocalypse:action`).
* **Phases**: thresholds per boss (e.g. 66 % / 33 %). Crossing one triggers an invulnerable
  transition (damage cancelled via `world.beforeEvents.entityHurt`), a roar, add summons and a new
  attack pool. Phase is synced to clients (`apocalypse:phase`) for enrage visuals.
* **Vulnerability windows** (Null Colossus): armored stance reduces incoming damage by 75 %
  (`beforeEvents.entityHurt` damage scaling); periodic core vents take 150 % damage.
* **Leash**: bosses remember their arena center; straying > 48 blocks teleports them back.
* **Multiplayer**: health tier chosen at spawn from nearby player count × difficulty setting
  (component-group events); AoE hits all players in range; rewards go to every contributor.
* **Death & rewards**: base drops come from JSON loot tables. Script rewards are keyed by the boss
  entity id in a persisted **reward ledger** so a kill can only pay out once; first-kill bonuses are
  per-player flags. Adds are despawned when the boss dies.

### 3.2 Dynamic world events

`eventRuntime` owns a single persisted state (`apocalypse:event_state`): active event id, start/end
tick, per-event cooldowns, last roll day. A scheduler task runs every 100 ticks (5 s):

* Rolls only when no event is active, the global cooldown has elapsed and the event's time window
  matches (night / day / any). Weighted pick; frequency is a world setting (off/rare/normal/frequent).
* Each event implements `onStart / onPulse (every 20 ticks) / onEnd` with **real gameplay changes**:

| Event | Window | Gameplay |
|---|---|---|
| Blood Moon | night | crimson fog; hostile mobs near players gain Strength/Speed; Crimson Shades hunt players; Blood Crystal drops |
| Void Storm | any (thunder) | violet fog, thunderstorm; Void Rifts open near players (pull + damage hazard, destroyable for Null Fragments); Void Crawlers |
| Meteor Shower | night | meteors strike near (not on) players, explode (block damage optional) and leave Meteorite ore; Astral Mites; Star Metal economy |
| Reality Fracture | any | gravity anomalies (levitation / slow-fall pulses), unstable blink of mobs, Rift Sentinels leak from the Expanse, Fracture Shards |
| Eclipse | day | darkness fog, Darkness pulses, Hollow Shades walk in daylight, Eclipse Shards; boosts Hollow King summon |

* **Performance safeguards**: no world scans — only `getEntities` queries centred on players with
  `maxDistance` and type/family filters; per-player and global spawn caps from the performance
  profile; event mobs carry the `apocalypse:event_mob` tag and are despawned at event end if no
  player is near; all hazards self-expire.

### 3.3 Progression loop

```
Rift Ore (worldgen) ─▶ Rift Shards ─▶ Riftwalker gear, Aether Crystals, Rift Blade
Events ─▶ Blood Crystals / Star Metal / Null Fragments / Fracture & Eclipse Shards
Hollow Shades / Void Crawlers / Astral Mites / Thornlings ─▶ Soul Essence / Void Ichor / Stardust / Living Bark
        └─▶ summoning relics: Cursed Crown, Astral Lure, Heartseed
Bosses ─▶ Hollow Crown Shard, Star Eater Core, Titan Heartwood ─▶ legendary weapons + Starforged gear
        └─▶ Engine Key (all three cores) ─▶ portal to the Shattered Expanse (custom dimension)
Shattered Expanse ─▶ Rift Sentinels (Null Fragments) ─▶ Null Gate ─▶ Null Colossus ─▶ Null Heart
        └─▶ Null Edge + Null Aegis armor (endgame)
```

The **Engine Codex** (given on first join) shows a per-player journal (discoveries, kills, events
survived, boss first-kills) and recipe hints, and exposes world settings to operators.

### 3.4 The Shattered Expanse — a real custom dimension

* Registered at startup with `StartupEvent.dimensionRegistry.registerCustomDimension(
  "apocalypse:shattered_expanse")` — stable since `@minecraft/server` 2.8.0. The engine creates it
  with the **void generator**; it is a genuine engine dimension, not an arena in the Overworld.
* Terrain is generated by script: a deterministic jittered grid of floating islands
  (`logic/islandGen`, unit tested) built column-by-column with `Dimension.fillBlocks`, budgeted per tick
  through `system.runJob`, only around players. Generated cells are persisted so they are built once.
* The Nexus island (arrival + permanent return portal) and the Colossus Arena are generated inside
  temporary ticking areas (`world.tickingAreaManager`, stable 2.6.0) exactly as the official
  custom-dimension tutorial recommends.
* Fog for the dimension is pushed per player with `/fog push` on arrival and popped on departure.

### 3.5 Weapons, armor and abilities

Abilities use **Custom Components V2** registered in `system.beforeEvents.startup` and referenced
directly in item JSON (e.g. `"apocalypse:ability": { "kind": "rift_dash" }`). Cooldowns use
`minecraft:cooldown` (native cooldown UI) + `ItemCooldownComponent.startCooldown`. Set bonuses are
checked every 2 s from the equippable component.

---

## 4. Visual design

Art direction: *ancient machine-civilization meets cosmic decay*. Palette families: void violet
(#1a0f2e → #9b5cff), rift cyan (#3ff3ff), blood crimson (#ff2a4a), star gold (#ffd36a), blight green
(#8cff6a), bone/ivory and oxidised bronze for the Architect ruins.

* **Original assets only**: every texture, model, animation, particle sprite and sound is generated
  by our own tools (`tools/`) — noise fields, layered shading, panel lines, runic glyphs, emissive
  veins, FM/noise sound synthesis. No vanilla or third-party art is copied.
* Resolutions (mobile-conscious): bosses 256×256 (enhanced) / 128×128 (balanced) / 64×64 (potato);
  mobs 128/64; items 32×32 (2× vanilla); blocks 32×32 (16×16 in potato); armor 128×64.
* **Vibrant Visuals (native PBR)**: resource pack declares the `pbr` capability; every custom block,
  entity and item ships a `*.texture_set.json` with a MER layer (and normal maps for blocks), so
  crystals, runes, eyes and meteorite veins are **truly emissive** under Vibrant Visuals on supported
  devices. In the classic renderer, glowing parts use the documented `entity_emissive_alpha`
  material overlay plus bright baked colors.
* **Particles**: custom Snowstorm-format effects (telegraph rings sized by Molang variables, shockwaves,
  meteor trails, rifts, boss auras, beams).
* **Fog**: custom fog definitions per event and for the Expanse (`/fog push|pop`).
* **Sound**: synthesized OGG Vorbis effects registered in `sound_definitions.json`.

### What we do NOT do (and why)

* **No custom shaders.** Since the RenderDragon renderer, resource packs cannot ship their own
  shader programs, and Microsoft's materials documentation warns that even custom material files are
  unstable and may be removed. We ship zero GLSL/HLSL, no custom `.material` files, and make no shader
  claims. Only documented vanilla materials (`entity_alphatest`, `entity_emissive_alpha`,
  `particles_alpha`, `particles_add`, `armor`, …) are referenced. All "next-gen" lighting comes from
  native Vibrant Visuals + PBR texture sets, which only render on devices/settings where the player
  has Vibrant Visuals enabled.
* We do not modify global Vibrant Visuals lighting/atmosphere files, so the player's world keeps
  Mojang's look outside our content.

---

## 5. Mobile performance

| Setting | POTATO | BALANCED (default) | ENHANCED |
|---|---|---|---|
| Script particle multiplier | 0.35 | 1.0 | 1.6 |
| Max event mobs per player / global | 2 / 10 | 4 / 18 | 6 / 28 |
| Max boss adds alive | 3 | 5 | 7 |
| Meteors per wave | 1 | 2 | 4 |
| Ambient FX interval | 40 t | 20 t | 10 t |
| Expanse generation budget | 24 columns / tick | 48 | 96 |
| Resource subpack | Potato (16× blocks, 64× mobs, sparse particles) | Balanced | Enhanced (256× bosses, dense particles) |

* Script work is tick-sliced through one scheduler; heavy work uses generators via `system.runJob`.
* Queries are always position-bounded; bosses only process when a player is within 64 blocks.
* All transient entities (rifts, portals, meteors, adds) have hard lifetimes and are cleaned on
  boss death / event end; `minecraft:despawn` covers chunk-unload cases.
* No FPS figure is promised — no physical Android device was available for profiling.

---

## 6. Build, validation and tests

* `python3 build.py` → regenerates assets (optional `--no-generate`), compiles TypeScript (when `tsc`
  is available, otherwise uses committed JS), runs unit tests, runs `validate.py`, optionally runs
  Mojang's Creator Tools validator, packages and re-inspects the archives, writes the report.
* `validate.py` checks: JSON syntax, manifests (format, UUID uniqueness, module types, dependency
  links, script entry), official JSON-schema validation of entities/items/blocks, cross references
  (client entities ↔ entities, geometry ids, textures, animations, controllers, render controllers,
  particles, sounds, loot tables, recipes, spawn rules, features, structures, item icons, terrain
  textures, attachables, lang keys), texture-set layer validity, image sizes/alpha, script imports.
* Unit tests (Node `node:test`): boss phase transitions, attack selection with range/cooldowns,
  telegraph timing, event scheduling/cooldowns/time windows, reward de-duplication, progression
  gating, profile values, island generation determinism.

---

## 7. Deliverables

`release/APOCALYPSE_ENGINE.mcaddon` (both packs) · `release/APOCALYPSE_ENGINE_BEHAVIOR.mcpack` ·
`release/APOCALYPSE_ENGINE_TEXTURES.mcpack` · `release/APOCALYPSE_ENGINE_SOURCE.zip` ·
`release/APOCALYPSE_ENGINE_VALIDATION.txt` · `release/APOCALYPSE_ENGINE_INSTALLATION.txt`

---

## 8. Known limitations (by design)

* In-game runtime testing requires Minecraft; the official Bedrock Dedicated Server route requires the
  user to accept the Minecraft EULA themselves, so it was not run on the user's behalf.
* Custom dimensions use the engine's void generator; terrain inside is script-built.
* Vibrant Visuals rendering depends on device support and the player's video settings.
* Boss bars come from the vanilla `minecraft:boss` component (one style).

## 9. Experimental-feature audit

| Feature | Status | Source |
|---|---|---|
| Custom dimensions (`DimensionRegistry`) | Stable in `@minecraft/server` 2.8.0 | 1.26.30 notes; 2.8.0 typings |
| Ticking areas API | Stable 2.6.0 | 1.26.10 notes |
| `world.beforeEvents.entityHurt` | Stable 2.6.0 | 1.26.10 notes |
| Custom Components V2 | Stable since 2.0.0 / item format 1.21.90+ | scripting v2 docs |
| Custom commands | Stable 2.x | 2.8.0 typings |
| Partial biome replacement | Stable since 1.21.110 | 1.21.110 notes |
| Data-driven projectiles (`minecraft:projectile`) | Stable (Custom Projectiles released 1.26.30) | 1.26.30 notes |
| PBR texture sets / `pbr` capability | Stable (min_engine ≥ 1.21.120) | Vibrant Visuals docs |
