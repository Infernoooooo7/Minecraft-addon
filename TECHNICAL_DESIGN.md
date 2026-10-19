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
| Features / feature rules | `1.21.20` (structure template features `1.26.30`) | Scatter features use the `distribution` object layout |
| Biome (BP) / client biome | `1.26.0` / `1.21.120` | BP biome validated against the official 1.26.0 biome schema (`minecraft:replace_biomes`) |
| Client entity / attachables | `1.10.0` | Same as vanilla |
| Geometry | `1.12.0` | Widely supported Bedrock geometry schema |
| Animations / controllers / render controllers | `1.8.0` / `1.10.0` / `1.8.0` | Same as vanilla |
| Particles | `1.10.0` | Classic particle schema, still parsed |
| Texture sets (Vibrant Visuals) | `1.21.30` | Texture-set schema with MER/MERS layers |
| Fog | `1.21.90` | Distance fog for every renderer + volumetric media coefficients for Vibrant Visuals |
| Vibrant Visuals atmosphere / lighting / color grading | `1.21.40` / `1.21.70` / `1.21.90` | Biome-scoped (referenced by the Blighted Wilds client biome only) |

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
         boss_machine (phases, attack selection, cooldowns), event_scheduler, reward_ledger,
         progression, profiles, island_gen (dimension terrain), rng, vec
bosses/  runtime + hollow_king, star_eater, root_titan, null_colossus, kit
events/  runtime (rolls, persistence, fog, bounded spawns, kill drops) + defs (the 7 events)
items/   weapon abilities + on-hit effects, relics/Engine Key/Codex/elixir, armor set bonuses
world/   expanse (custom dimension: registration, island generation, portals, sentinels),
         blocks (ore drops with Silk Touch/Fortune, Engine Cache, Null Gate)
commands custom slash commands (/apocalypse:codex|event|profile|summon)
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
* **Vulnerability windows** (Null Colossus): armored stance takes only 35 % of incoming damage
  (`beforeEvents.entityHurt` damage scaling); core vents (after gravity slams, collapses, phase
  changes and every ~25 s) take 150 %. The Star Eater is exhausted for 4 s after a Supernova (150 %).
* **Leash**: bosses remember their arena center; straying 30–56 blocks (per boss) or falling 16
  blocks below it teleports them back.
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
* Each event implements `onStart / onPulse (every 20 ticks) / onEnd` with **real gameplay changes**,
  optional bonus drops on player kills of hostile mobs, and full cleanup at the end:

| Event | Window · from day · duration · cooldown | Gameplay |
|---|---|---|
| Blood Moon | night · 2 · 4–6 min · 2 days | crimson fog; hostile mobs near players gain Strength (II when brutal) and Speed; Crimson Shades hunt players (Blood Crystals); 12 % Blood Crystal kill drop |
| Void Storm | any · 3 · 3–4.5 min · 2 days | violet fog + thunderstorm; Void Rifts open near players (pull within 7 blocks, magic damage + Wither on contact, destroy for Null Fragments; full Null Aegis is immune); Void Crawlers; optional lightning 12–30 blocks away |
| Meteor Shower | night · 1 · 3–5 min · 1.5 days | telegraphed meteors strike 16–40 blocks from players (ballistic aim), explode (block damage only with terrain damage on) and leave Meteorite ore; Astral Mites swarm craters |
| Reality Fracture | any · 5 · 2.5–3.5 min · 2 days | teal fog; gravity anomalies (low gravity, heavy gravity, levitation surge) and monster blinks; Rift Sentinels leak in (Fracture Shards) |
| Eclipse | day · 6 · 3–4.5 min · 3 days | darkness fog; Darkness pulses under open sky; undead gain fire resistance; Hollow Shades walk by day; Eclipse Shards; the Cursed Crown works during an Eclipse |
| Ancient Awakening | any · 3 · 3–4 min · 2.5 days | golden haze; Sealed Engine Caches surface near players, guarded by Rift Sentinels; Haste near caches; unopened caches sink back at the end (persisted, swept even after reload) |
| Corruption Surge | any · 4 · 2.5–4 min · 2 days | blight fog; Thornlings erupt; monsters regenerate and harden; spores poison players in the open; with terrain damage on, grass turns to Blighted Grass |

* One event at a time; a 5-minute global quiet period follows any event; night events fade at dawn
  and day events at dusk. Event state (active id, end tick, cooldowns) is persisted and **rebased on
  load**, so a reload neither extends nor shortens an event.
* **Performance safeguards**: no world scans — only `getEntities` queries centred on players with
  `maxDistance` and type/family filters; per-player and global spawn caps from the performance
  profile; event mobs carry the `apocalypse:event_mob` tag and are despawned at event end; all
  hazards (rifts, meteors) self-expire via entity timers.

### 3.3 Progression loop

```
Rift Ore (worldgen) ─▶ Rift Shards ─▶ Riftwalker gear, Aether Crystals, Rift Blade
Events ─▶ Blood Crystals / Star Metal / Null Fragments / Fracture & Eclipse Shards
Hollow Shades / Void Crawlers / Astral Mites / Thornlings ─▶ Soul Essence / Void Ichor / Stardust / Living Bark
        └─▶ summoning relics: Cursed Crown, Astral Lure, Heartseed
Bosses ─▶ Hollow Crown Shard, Star Eater Core, Titan Heartwood ─▶ legendary weapons + Starforged gear
        └─▶ Engine Key (all three cores) ─▶ portal to the Shattered Expanse (custom dimension)
Shattered Expanse ─▶ Rift Sentinels (Null Fragments) ─▶ Null Gate (Engine Key + 8 fragments) ─▶ Null Colossus ─▶ Null Heart
        └─▶ Null Edge + Null Aegis armor (endgame)
```

Event materials also open alternative routes: 2 Eclipse Shards replace the Rift Shard/extra Soul
Essence of the Cursed Crown, Fracture Shards substitute in the Astral Lure, and Void Ichor brews two
Aether Elixirs at once.

The **Engine Codex** (given on first join) shows a per-player journal (discoveries, kills, events
survived, boss first-kills) and recipe hints, and exposes world settings to operators.

### 3.4 The Shattered Expanse — a real custom dimension

* Registered at startup with `StartupEvent.dimensionRegistry.registerCustomDimension(
  "apocalypse:shattered_expanse")` — stable since `@minecraft/server` 2.8.0. The engine creates it
  with the **void generator**; it is a genuine engine dimension, not an arena in the Overworld.
* Terrain is generated by script: a deterministic jittered grid of floating islands
  (`logic/island_gen`, unit tested) built column-by-column with `Dimension.fillBlocks`, budgeted per tick
  through `system.runJob`, only around players. Generated cells are persisted so they are built once.
* The Nexus island (arrival + permanent return portal) and the Colossus Arena are generated inside
  temporary ticking areas (`world.tickingAreaManager`, stable 2.6.0) exactly as the official
  custom-dimension tutorial recommends.
* Fog for the dimension is pushed per player with `/fog push` on arrival and removed on departure
  (re-synchronised on join). Falling below the islands returns the player to the Nexus with 3 hearts
  of damage instead of killing them in the void.

### 3.5 Weapons, armor and abilities

Abilities use **Custom Components V2** registered in `system.beforeEvents.startup` and referenced
directly in item JSON (e.g. `"apocalypse:ability": { "kind": "rift_dash", "cooldown": 5 }`).
Cooldowns: an in-script per-player cooldown plus `Player.startItemCooldown` for the native cooldown
UI (the item's `minecraft:cooldown` category); each use costs 2 durability.

| Item | Ability |
|---|---|
| Rift Blade | Rift Dash: blink up to 7 blocks (stops before walls), cutting enemies on the path |
| Soulreaver Scythe | Soul Reap: 360° sweep, each soul heals 1 heart (max 4) |
| Titan's Wrath | Earthsplitter: shockwave launches and slows grounded foes |
| Null Edge | hits mark foes, a second hit detonates the mark; Gravity Crush pulls foes together then crushes |
| Starfall Scepter | Star Bolt projectile (owner = wielder, so kills and boss contributions count) |
| Event Horizon | Gravity Well where you aim: 4 s of pull + grinding, then implosion |
| Bloodfang Cleaver | lifesteal (25 % of base damage) and bleed (Wither) |

Set bonuses (full set, refreshed every 2 s without flicker): **Riftwalker** Speed I + fall-damage
immunity (cancelled in `beforeEvents.entityHurt`), **Starforged** Fire Resistance + Night Vision,
**Null Aegis** Resistance I + immunity to the Colossus' gravity lift and Void Rift pull.

Ores (Rift Ore, Deepslate Rift Ore, Meteorite, Aether Cluster): the loot table only handles Silk
Touch (drops the block); the `apocalypse:ore_xp` component rolls the regular drops with a pickaxe,
applies Fortune and spawns XP — loot conditions cannot express "not Silk Touch", and two pools would
otherwise pay both.

---

## 4. Visual design

Art direction: *ancient machine-civilization meets cosmic decay*. Palette families: void violet
(#1a0f2e → #9b5cff), rift cyan (#3ff3ff), blood crimson (#ff2a4a), star gold (#ffd36a), blight green
(#8cff6a), bone/ivory and oxidised bronze for the Architect ruins.

* **Original assets only**: every texture, model, animation, particle sprite and sound is generated
  by our own tools (`tools/`) — noise fields, layered shading, panel lines, runic glyphs, emissive
  veins, FM/noise sound synthesis. No vanilla or third-party art is copied.
* Resolutions (mobile-conscious, measured from the built packs):
  | Tier | Bosses | Mobs | Items | Blocks | Armor | PBR |
  |---|---|---|---|---|---|---|
  | Potato (= base pack) | 256² | 64² | 16² | 16² | 64×32 | none |
  | Balanced subpack | 512² | 128² | 32² | 32² | 128×64 | 74 texture sets (MER; normals for blocks) |
  | Enhanced subpack | 512² | 256² | 64² | 32² | 256×128 | same 74 texture sets |
  The largest texture is 512² (the validator enforces a 1024 px mobile budget).
* **Vibrant Visuals (native PBR)**: resource pack declares the `pbr` capability; in the Balanced and
  Enhanced subpacks every custom block, entity and item has a `*.texture_set.json` with a MER layer
  (and normal maps for blocks), so
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
| Resource subpack | Potato: base textures, sparse particles | Balanced: 2× textures + PBR | Enhanced: up to 4× textures + PBR, dense particles |
| Boss brain update | every 5 ticks | every 4 ticks | every 4 ticks |

* Script work is tick-sliced through one scheduler; heavy work uses generators via `system.runJob`.
* Queries are always position-bounded; bosses only process when a player is within 64 blocks.
* All transient entities (rifts, portals, meteors, adds) have hard lifetimes and are cleaned on
  boss death / event end; `minecraft:despawn` covers chunk-unload cases.
* No FPS figure is promised — no physical Android device was available for profiling.

---

## 6. Build, validation and tests

* `python3 build.py` is the single regenerate command: generate assets → compile TypeScript → run
  all tests (plus the runtime simulation under extra random seeds) → static validation → optional
  official-schema and Creator Tools validation → package → reopen and inspect every archive → write
  the validation report and installation guide. It exits non-zero on any failure.
* `validate.py` checks: JSON syntax, manifests (format, UUID uniqueness, module types, dependency
  links, script entry, subpacks, capabilities), official JSON-schema validation of
  entities/items/blocks/biomes (when a `bedrock-samples` checkout is supplied), component whitelists
  per format version, cross references (client entities ↔ entities, geometry ids/bones/locators,
  textures, animations, controllers, render controllers, particles, sounds, loot tables, recipes,
  spawn rules, features, structures, item icons, terrain textures, attachables, lang keys), every
  bare `minecraft:<id>` value against `@minecraft/vanilla-data`, texture-set layer validity, image
  sizes, script imports/identifiers/custom-component coverage/sound ids.
* Tests:
  * `tests/logic.test.mjs` — pure logic: boss state machine, event scheduler, reward ledger,
    progression, profiles, island generation (incl. continuity of the Nexus→Arena causeway).
  * `tests/runtime.smoke.test.mjs` + `tests/mock/` — the compiled scripts run on a **strict mock of
    `@minecraft/server`** that rejects unknown identifiers, undeclared entity properties/events,
    out-of-range property values, unknown effects/sounds/particles/fogs/structures, world access in
    early execution and the documented restricted-execution APIs in before-events and command
    callbacks, and that requires every custom component in JSON to be registered. Scenarios cover
    every event, every boss fight, abilities, relics, armor, ores, the Expanse (including a
    flood-fill proving the Arena is reachable on foot), the Codex UI, commands and 6 in-game days of
    natural scheduling.
  * `tests/runtime.reload.test.mjs` — save/reload persistence (event rebase, boss brain restore,
    reward ledger).
  * `tests/test_tools.py` — `.mcstructure` codec, lenient JSON, validator clean run and
    **injected-defect detection** (the validator must catch six planted errors).
* These tests found and fixed real defects during development: unjumpable bridge gaps, a Null
  Colossus vent window shorter than its visual, overlapping vents closing early, a post-mortem vent
  callback, the event tick rebase silently skipped after reload, ore double drops with Silk Touch, and
  an invalid vanilla block id.
* None of this replaces playing the game: see the validation report for what remains untested.

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
* Manifests use `format_version` 2 (as Mojang's own samples do), so subpacks use `memory_tier`;
  pack settings (manifest v3) are not used — configuration lives in the Engine Codex instead.

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
