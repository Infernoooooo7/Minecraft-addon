# APOCALYPSE ENGINE — Gameplay Guide

All numbers below are taken from the shipped pack data and scripts (version 1.0.0). Balance has not
yet been tuned by real play.

## Progression at a glance

1. **Rift Ore** (cyan veins, Overworld Y −56…40; Deepslate variant deeper) → Rift Shards.
   Mine with a pickaxe; Silk Touch keeps the ore block, Fortune multiplies shards.
2. **Aether Crystal** (4 Rift Shards + Amethyst Shard) → Rift Blade, Riftwalker armor, Aether Elixir.
3. Survive **world events** for event materials (Blood Crystals, Stardust, Star Metal, Void Ichor,
   Fracture and Eclipse Shards).
4. Craft the **summoning relics** and defeat **the Hollow King**, **the Star Eater** and
   **the Root Titan**.
5. Forge the **Engine Key** (Hollow Crown Shard + Star Eater Core + Titan Heartwood + 2 Aether Crystals)
   and open a rift to **the Shattered Expanse**.
6. Collect **Null Fragments** from Rift Sentinels, cross the causeway to the **Colossus Arena** and
   wake **the Null Colossus** at the Null Gate (Engine Key in hand + 8 Null Fragments).
7. Endgame: Null Edge and the Null Aegis armor.

The **Engine Codex** (given on first join, craftable from Book + Rift Shard, or `/apocalypse:codex`)
always shows your next objective, your journal and all recipes.

## Bosses

Health tier = number of targetable players within 64 blocks at spawn, adjusted by the boss difficulty
setting (story −1, nightmare +1), clamped to 1–4. Tier multipliers: ×1, ×1.5, ×2, ×2.6. Scripted
attack damage is scaled by difficulty (story ×0.6, normal ×1, nightmare ×1.45). Each heavy attack is
telegraphed (ground rings, sounds, action-bar warnings, a wind-up animation). Crossing a phase
threshold triggers an invulnerable roar transition. At most two bosses can be summoned at once and
one of each kind.

### The Hollow King
* **Summon**: use a **Cursed Crown** in the Overworld at night, or during an Eclipse.
* **Health** 600 / 900 / 1200 / 1560 by tier; melee 11. Phases at 66 % and 33 %.
* **Phase I**: Spectral Summon (2 shades), Phantom Step (teleports behind you).
* **Phase II**: + Grave Quake (7-block shockwave — *jump* to dodge, grounded players only),
  Soul Chains (pull, Slowness, Wither), slash after Phantom Step.
* **Phase III** (opens with it): Crown of Ruin — 12-block nova, Weakness, two Crimson Shades, the King
  gains Strength and Speed; double quakes.
* **Loot**: 2–3 Hollow Crown Shards, 6–10 Soul Essence, 1/3 Soulreaver Scythe.
  **First kill** (per player): +1 Hollow Crown Shard, +8 Soul Essence, +5 levels.

### The Star Eater
* **Summon**: **Astral Lure** at night with open sky above you.
* **Health** 750 / 1125 / 1500 / 1950; melee 9; flies and hovers ~5 blocks above its target.
  Phases at 60 % and 25 %.
* **Phase I**: Star Volley (3/5/7 bolts by phase), Gravity Well (8-block pull).
* **Phase II**: + Comet Dive (telegraphed ring, then impact), Astral Brood (Astral Mites).
* **Phase III**: Supernova — 3 s charge, then 16 damage to every player *in line of sight*
  within 16 blocks. Hide behind solid blocks. Afterwards it is **exhausted for 4 s (×1.5 damage)**.
* **Loot**: Star Eater Core, 8–14 Stardust, 3–5 Star Metal Ingots, 1/3 Event Horizon.
  **First kill**: +Core, +12 Stardust, +5 levels.

### The Root Titan
* **Summon**: plant a **Heartseed** by day while standing on grass, dirt, moss or blighted ground.
* **Health** 900 / 1350 / 1800 / 2340; melee 15. Phases at 66 % and 33 %.
* **Phase I**: Thorn Eruption (rings under you — step out), Earthsplitter (6.5-block slam, jump to
  dodge), Seed Brood (Thornlings).
* **Phase II**: + Vine Lash (pulls you in, heavy Slowness), Sap Shield (Absorption + Resistance).
* **Phase III**: Earthsplitter adds Wither; more eruptions.
* **Loot**: 1–2 Titan Heartwood, 8–14 Living Bark, 1/3 Titan's Wrath.
  **First kill**: +Heartwood, +10 Living Bark, +5 levels.

### The Null Colossus
* **Summon**: in the Shattered Expanse, at the Colossus Arena, use the Null Gate while holding the
  **Engine Key** and carrying **8 Null Fragments** (consumed; refunded if the summon fails).
* **Health** 1200 / 1800 / 2400 / 3120; melee 18. Phases at 60 % and 25 %.
* **Armor**: takes **35 %** damage, except while its core **vents** (cyan glow, "CORE EXPOSED"):
  then **150 %**. Vents open after Gravity Slam, after Collapse, after each phase change and about
  every 25 s.
* **Attacks**: Gravity Lift → Slam (levitates you, then slams you down; full Null Aegis is immune),
  Null Beam (80° sweep — get out of its path), Collapse (pulls everyone to the centre, then
  explodes; phase II+), Orbital Barrage (phase II+). Phase III adds a damaging aura within 5 blocks.
* **Loot**: Null Heart, 10–16 Null Fragments, 1/3 Null Edge. **First kill**: +Null Heart,
  +16 Null Fragments, +5 levels.

Rewards go to every player who dealt at least 5 % of the damage (and the top damage dealer) plus any
targetable player within 48 blocks of the death. A death is paid out only once, even across reloads.

## World events

One event at a time; after any event there is a 5-minute quiet period. Frequency setting: off,
rare (~0.5/day), normal (~1/day), frequent (~2/day). Intensity (mild/normal/brutal) scales spawn
chances and some effects. Event mobs and hazards are capped by the performance profile and removed when
the event ends.

| Event | When | What happens | Rewards |
|---|---|---|---|
| **Blood Moon** | night, from day 2, 4–6 min | hostile mobs near players gain Strength + Speed; Crimson Shades hunt you | Blood Crystals (Crimson Shades; 12 % from any monster) |
| **Void Storm** | any time, from day 3, 3–4.5 min | thunderstorm; Void Rifts open near players — they pull you within 7 blocks and burn on contact (destroy them!); Void Crawlers; optional lightning | Null Fragments from rifts, Void Ichor |
| **Meteor Shower** | night, from day 1, 3–5 min | meteors strike 16–40 blocks from players (watch the impact rings), explode, leave Meteorite ore; Astral Mites swarm craters | Star Metal Chunks, Stardust |
| **Reality Fracture** | any time, from day 5, 2.5–3.5 min | low/heavy gravity, levitation surges, monsters blink around; Rift Sentinels leak in | Fracture Shards (30 %; Sentinels 1–2) |
| **Eclipse** | day, from day 6, 3–4.5 min | Darkness pulses under the open sky; undead stop burning; Hollow Shades walk by day; the Cursed Crown works | Eclipse Shards (25 %) |
| **Ancient Awakening** | any time, from day 3, 3–4 min | Sealed Engine Caches surface near players, guarded by Rift Sentinels; Haste near caches; unopened caches sink back at the end | cache loot (shards, crystals, ingots, relics), Rift Shards (35 %) |
| **Corruption Surge** | any time, from day 4, 2.5–4 min | Thornlings erupt; monsters regenerate and gain Resistance; spores poison players in the open (take shelter); with terrain damage on, grass turns to Blighted Grass | Living Bark (25 %) |

Night events fade at dawn and day events at dusk. Each event also has its own multi-day cooldown.

## Creatures

| Creature | HP | Where | Drops |
|---|---|---|---|
| Hollow Shade | 24 (Crimson 30) | Overworld at night in dark places; Blood Moon, Eclipse, Hollow King | Soul Essence (+ Blood Crystals when Crimson) |
| Thornling | 16 | Blighted Wilds, Corruption Surge, Root Titan | Living Bark |
| Void Crawler | 22 | Void Storm, Shattered Expanse | Void Ichor |
| Astral Mite | 10 | meteor craters, Star Eater | Stardust |
| Rift Sentinel | 40 | Shattered Expanse, Reality Fracture, Ancient Awakening | Null Fragments |

## Weapons

| Weapon | Damage | Durability | Use ability (cooldown) / passive |
|---|---|---|---|
| Rift Blade | 8 | 900 | Rift Dash — blink up to 7 blocks, cutting foes on the path (5 s) |
| Bloodfang Cleaver | 9 | 1100 | lifesteal 25 % + bleed |
| Soulreaver Scythe | 10 | 1800 | Soul Reap — 360° sweep, each soul heals 1 heart (10 s); lifesteal 10 % |
| Titan's Wrath | 11 | 2000 | Earthsplitter — shockwave launches grounded foes (10 s) |
| Null Edge | 13 | 3000 | Gravity Crush (14 s); hits mark foes, the next hit detonates the mark |
| Starfall Scepter | 4 | 800 | Star Bolt (1.5 s) |
| Event Horizon | 5 | 1500 | Gravity Well where you aim (12 s) |

Abilities affect hostile mobs only (pets, villagers and other players are safe) and cost 2 durability.

## Armor sets (protection head/chest/legs/feet)

| Set | Protection | Full-set bonus |
|---|---|---|
| Riftwalker (Rift Shards) | 2/6/5/2 | Speed I, no fall damage |
| Starforged (Star Metal Ingots) | 3/8/6/3 | Fire Resistance, Night Vision |
| Null Aegis (Starforged piece + 8 Null Fragments) | 3/8/6/3, most durable | Resistance I, immune to the Colossus' gravity lift and Void Rift pull |

## Other items

* **Aether Elixir** — cleanses Wither, Poison, Darkness, Levitation, Slowness, Mining Fatigue,
  Blindness, Hunger and Weakness; grants Regeneration II (10 s) and Absorption II (2 min).
* **Engine Key** — opens a rift to the Expanse (or home, when used inside it); the rift stays open
  for one minute. Not consumed.
* Alternative recipes reward events: Eclipse Shards → Cursed Crown, Fracture Shards → Astral Lure,
  Void Ichor → two Aether Elixirs.

## The Shattered Expanse

* Arrive at the **Nexus** (safe from Sentinels); a permanent **Rift Home** stands at its centre.
* The **Colossus Arena** lies ~120 blocks north along a continuous causeway.
* Floating islands (Shattered Stone, Void Moss, Rift Ore, Aether crystals) generate around you.
* Falling into the void returns you to the Nexus with 3 hearts of damage.

## World generation (Overworld)

* **Rift Ore** veins (Y −56…40), **Deepslate Rift Ore**.
* **Blighted Wilds** biome: replaces part of forests, birch forests and dark forests; blighted grass and
  soil, blight sprouts, aether clusters, Thornlings, its own fog and (with Vibrant Visuals) its own
  atmosphere, lighting and color grading.
* **Ancient Ruins** (two designs, rare) in forests, plains, taiga, savanna, desert and the Blighted
  Wilds, each holding a Sealed Engine Cache.

## Settings (operators, Engine Codex → World Settings)

Performance profile · event frequency · event intensity · boss difficulty · terrain damage (off by
default) · Void Storm lightning · Codex for new players · debug logging · each event on/off.
