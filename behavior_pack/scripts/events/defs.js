// The seven dynamic world events. Each one changes gameplay (spawns, effects, hazards, drops), stays inside
// the performance profile's caps, and cleans up after itself (event mobs, placed caches, weather).
import { EntityDamageCause, WeatherType, world } from "@minecraft/server";
import { config, intensityScale, profile } from "../core/config.js";
import { actionbar, burst, gravityPull, particle, ring, runeCircle, shake, sound } from "../core/fx.js";
import { DP, EVENT_TRIGGER, TAG } from "../core/keys.js";
import { isTargetable, playersNear } from "../core/players.js";
import { every, later } from "../core/scheduler.js";
import { readWorld, writeWorld } from "../core/state.js";
import { BLOCKS, ENTITIES, FOGS, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { wearsSet } from "../items/armor.js";
import { Rng } from "../logic/rng.js";
import { add } from "../logic/vec.js";
import { activeEvent, eventEntities, registerEvent, spawnEventMobAt, spawnForEvent } from "./runtime.js";
const MIN = 1200;
const DAY = 24000;
const fxRng = new Rng((Date.now() ^ 0x5eed) >>> 0);
/** Natural blocks a meteorite or cache may replace without terrain damage enabled. */
const SOFT_BLOCKS = new Set([
    "minecraft:air", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern",
    "minecraft:snow_layer", "minecraft:deadbush", "minecraft:poppy", "minecraft:dandelion",
]);
// ------------------------------------------------------------------------------------------------
// shared helpers
// ------------------------------------------------------------------------------------------------
const sec = (c) => Math.floor(c.elapsed / 20);
const brutal = () => config().eventIntensity === "brutal";
const roll = (c, p) => c.rng.chance(Math.min(1, p * intensityScale()));
function effect(e, id, seconds, amplifier = 0, particles = false) {
    try {
        e.addEffect(id, Math.max(1, Math.round(seconds * 20)), { amplifier, showParticles: particles });
    }
    catch {
        /* entity gone / immune */
    }
}
function mobsNear(p, radius, family, limit = 24) {
    try {
        return p.dimension.getEntities({
            location: p.location, maxDistance: radius, families: [family], excludeFamilies: ["apocalypse_boss"],
        }).slice(0, limit);
    }
    catch {
        return [];
    }
}
/** True when nothing but sky is above the player's head. */
function exposedToSky(p) {
    try {
        const top = p.dimension.getTopmostBlock({ x: p.location.x, z: p.location.z });
        return !top || top.location.y < p.location.y + 1.5;
    }
    catch {
        return false;
    }
}
/** Cheap ambient particles around each player, density by performance profile. */
function ambient(c, id, height = 6, spread = 10) {
    const interval = profile().ambientInterval;
    if (interval > 20 && sec(c) % Math.round(interval / 20) !== 0)
        return;
    const n = Math.max(1, Math.round(20 / interval));
    for (const p of c.players) {
        for (let i = 0; i < n; i++) {
            particle(p.dimension, id, {
                x: p.location.x + c.rng.range(-spread, spread),
                y: p.location.y + c.rng.range(1.5, height),
                z: p.location.z + c.rng.range(-spread, spread),
            });
        }
    }
}
/** Surface block (solid ground) on a ring around a player. */
function surfaceNear(p, rng, minDist, maxDist, maxDy = 12) {
    for (let attempt = 0; attempt < 5; attempt++) {
        const ang = rng.next() * Math.PI * 2;
        const d = rng.range(minDist, maxDist);
        const x = p.location.x + Math.cos(ang) * d;
        const z = p.location.z + Math.sin(ang) * d;
        try {
            const top = p.dimension.getTopmostBlock({ x, z }, Math.floor(p.location.y) + 24);
            if (!top || top.isLiquid || Math.abs(top.location.y - p.location.y) > maxDy)
                continue;
            if (SOFT_BLOCKS.has(top.typeId)) {
                const below = top.below();
                if (below && !below.isAir && !below.isLiquid && !SOFT_BLOCKS.has(below.typeId))
                    return below;
                continue;
            }
            return top;
        }
        catch {
            /* unloaded column */
        }
    }
    return undefined;
}
function compass(from, to) {
    const ang = ((Math.atan2(to.x - from.x, -(to.z - from.z)) * 180) / Math.PI + 360) % 360;
    return ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(ang / 45) % 8];
}
// ------------------------------------------------------------------------------------------------
// Blood Moon
// ------------------------------------------------------------------------------------------------
registerEvent({
    meta: {
        id: "blood_moon", name: "Blood Moon", window: "night", minTicks: 4 * MIN, maxTicks: 6 * MIN,
        cooldownTicks: 2 * DAY, weight: 3, minDay: 2,
    },
    summary: "Hostile mobs near players gain Strength and Speed; Crimson Shades hunt survivors and drop Blood Crystals.",
    color: "§4",
    fog: FOGS.FOG_BLOOD_MOON,
    startTitle: "BLOOD MOON",
    startSubtitle: "§cThe moon bleeds. The hunt begins.",
    startSound: SOUNDS.EVENT_BLOOD_MOON,
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.BLOOD_EMBER);
        if (s % 5 === 0) {
            for (const p of c.players) {
                for (const m of mobsNear(p, 32, "monster")) {
                    effect(m, "strength", 7, brutal() ? 1 : 0);
                    effect(m, "speed", 7, 0);
                }
            }
        }
        if (s % 4 === 1) {
            for (const p of c.players) {
                if (isTargetable(p) && roll(c, 0.6))
                    spawnForEvent(p, ENTITIES.HOLLOW_SHADE, 14, 28, EVENT_TRIGGER.BECOME_CRIMSON);
            }
        }
        if (s % 45 === 20)
            actionbar(c.players, "§4The Blood Moon empowers every creature of the night...");
    },
    killDrops: [{ item: ITEMS.BLOOD_CRYSTAL, chance: 0.12 }],
});
// ------------------------------------------------------------------------------------------------
// Void Storm
// ------------------------------------------------------------------------------------------------
function riftHazard(r, s) {
    try {
        const center = add(r.location, { x: 0, y: 1.1, z: 0 });
        for (const p of r.dimension.getPlayers({ location: center, maxDistance: 7 })) {
            if (!isTargetable(p) || wearsSet(p, "null_aegis"))
                continue; // full Null Aegis anchors its wearer
            const dx = center.x - p.location.x;
            const dz = center.z - p.location.z;
            const d = Math.hypot(dx, dz) || 1;
            if (d > 2.2) {
                p.applyKnockback({ x: (dx / d) * 0.32, z: (dz / d) * 0.32 }, 0);
            }
            else {
                p.applyDamage(2 * intensityScale(), { cause: EntityDamageCause.magic });
                effect(p, "wither", 2, 0, true);
            }
        }
        gravityPull(r.dimension, center, 5);
        if (s % 3 === 0)
            sound(r.dimension, SOUNDS.RIFT_HUM, center, 0.8);
    }
    catch {
        /* rift closed */
    }
}
function lightningNear(p, rng) {
    const ang = rng.next() * Math.PI * 2;
    const d = rng.range(12, 30);
    const x = p.location.x + Math.cos(ang) * d;
    const z = p.location.z + Math.sin(ang) * d;
    try {
        const top = p.dimension.getTopmostBlock({ x, z });
        if (top)
            p.dimension.spawnEntity("minecraft:lightning_bolt", { x, y: top.location.y + 1, z });
    }
    catch {
        /* unloaded */
    }
}
registerEvent({
    meta: {
        id: "void_storm", name: "Void Storm", window: "any", minTicks: 3 * MIN, maxTicks: 4.5 * MIN,
        cooldownTicks: 2 * DAY, weight: 2, minDay: 3,
    },
    summary: "A violet thunderstorm tears Void Rifts open near players: rifts drag you in and burn on contact. Destroy them for Null Fragments; Void Crawlers pour out.",
    color: "§5",
    fog: FOGS.FOG_VOID_STORM,
    startTitle: "VOID STORM",
    startSubtitle: "§dThe sky tears open. Close the rifts!",
    startSound: SOUNDS.EVENT_VOID_STORM,
    onStart(c) {
        try {
            c.overworld.setWeather(WeatherType.Thunder, 6 * MIN);
        }
        catch {
            /* ignore */
        }
    },
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.VOID_SWIRL, 8, 14);
        if (s % 8 === 2) {
            const rifts = eventEntities(ENTITIES.VOID_RIFT);
            for (const p of c.players) {
                if (!isTargetable(p))
                    continue;
                const near = rifts.filter((r) => {
                    try {
                        return Math.hypot(r.location.x - p.location.x, r.location.z - p.location.z) < 32;
                    }
                    catch {
                        return false;
                    }
                }).length;
                if (near < (brutal() ? 3 : 2) && roll(c, 0.7)) {
                    const r = spawnForEvent(p, ENTITIES.VOID_RIFT, 9, 20);
                    if (r) {
                        sound(r.dimension, SOUNDS.PORTAL_OPEN, r.location, 1, 0.7);
                        actionbar([p], `§dA Void Rift tears open to the ${compass(p.location, r.location)} — destroy it!`);
                    }
                }
            }
        }
        for (const r of eventEntities(ENTITIES.VOID_RIFT))
            riftHazard(r, s);
        if (s % 6 === 4) {
            for (const p of c.players)
                if (isTargetable(p) && roll(c, 0.5))
                    spawnForEvent(p, ENTITIES.VOID_CRAWLER, 10, 22);
        }
        if (config().lightning && s % 9 === 0) {
            const p = c.rng.pick(c.players);
            if (p)
                lightningNear(p, c.rng);
        }
    },
    onEnd(c) {
        try {
            c.overworld.setWeather(WeatherType.Clear, 2 * MIN);
        }
        catch {
            /* ignore */
        }
    },
    killDrops: [{ item: ITEMS.VOID_ICHOR, chance: 0.15 }],
});
// ------------------------------------------------------------------------------------------------
// Meteor Shower
// ------------------------------------------------------------------------------------------------
const METEOR_FLIGHT_TICKS = 30;
function launchMeteor(dim, impact, rng) {
    const ox = rng.range(-16, 16);
    const oz = rng.range(-16, 16);
    const start = { x: impact.x + ox, y: Math.min(dim.heightRange.max - 4, impact.y + 52), z: impact.z + oz };
    try {
        const m = dim.spawnEntity(ENTITIES.METEOR, start);
        m.addTag(TAG.HAZARD);
        const proj = m.getComponent("minecraft:projectile");
        const g = proj?.gravity ?? 0.04;
        const t = METEOR_FLIGHT_TICKS;
        // ballistic aim: horizontal speed covers the offset in t ticks, vertical accounts for gravity
        const vel = { x: -ox / t, y: -(start.y - impact.y - 0.5 * g * t * t) / t, z: -oz / t };
        if (proj)
            proj.shoot(vel, { uncertainty: 0 });
        else
            m.applyImpulse(vel);
        ring(dim, impact, 3.5, t / 20 + 0.4);
        sound(dim, SOUNDS.METEOR_WHISTLE, start, 1.3);
    }
    catch {
        /* unloaded */
    }
}
function meteorNear(p, rng) {
    try {
        if (!p.isValid || p.dimension.id !== "minecraft:overworld")
            return;
    }
    catch {
        return;
    }
    const ground = surfaceNear(p, rng, 16, 40, 24);
    if (ground)
        launchMeteor(p.dimension, { x: ground.location.x + 0.5, y: ground.location.y + 1, z: ground.location.z + 0.5 }, rng);
}
function placeMeteorite(dim, loc) {
    try {
        const hit = dim.getBlockFromRay({ x: loc.x, y: loc.y + 3, z: loc.z }, { x: 0, y: -1, z: 0 }, { maxDistance: 8, includeLiquidBlocks: true, includePassableBlocks: false });
        if (!hit || hit.block.isLiquid)
            return;
        const base = hit.block.above();
        if (!base || !SOFT_BLOCKS.has(base.typeId))
            return;
        base.setType(BLOCKS.METEORITE);
        const sides = [base.north(), base.south(), base.east(), base.west()];
        const extra = fxRng.int(0, 2);
        for (let i = 0; i < extra && sides.length; i++) {
            const b = sides.splice(fxRng.int(0, sides.length - 1), 1)[0];
            const below = b?.below();
            if (b && SOFT_BLOCKS.has(b.typeId) && below && !below.isAir && !below.isLiquid)
                b.setType(BLOCKS.METEORITE);
        }
        burst(dim, PARTICLES.CRYSTAL_GLINT, base.center(), 2, 0.6);
    }
    catch {
        /* unloaded */
    }
}
function meteorImpact(dim, loc) {
    sound(dim, SOUNDS.METEOR_IMPACT, loc, 1.5);
    burst(dim, PARTICLES.IMPACT_BURST, loc, 4, 1.5);
    burst(dim, PARTICLES.STAR_NOVA, add(loc, { x: 0, y: 0.5, z: 0 }), 1, 0.2);
    try {
        dim.createExplosion(loc, 2 + intensityScale(), { breaksBlocks: config().terrainDamage, causesFire: false });
    }
    catch {
        /* ignore */
    }
    for (const p of playersNear(dim, loc, 28))
        shake(p, 0.3, 0.6);
    later(2, () => placeMeteorite(dim, loc), "meteorite");
    if (activeEvent()?.meta.id === "meteor_shower" && fxRng.chance(0.6)) {
        const n = brutal() ? 2 : 1;
        for (let i = 0; i < n; i++) {
            spawnEventMobAt(dim, ENTITIES.ASTRAL_MITE, { x: loc.x + fxRng.range(-1.5, 1.5), y: loc.y + 1, z: loc.z + fxRng.range(-1.5, 1.5) });
        }
    }
}
registerEvent({
    meta: {
        id: "meteor_shower", name: "Meteor Shower", window: "night", minTicks: 3 * MIN, maxTicks: 5 * MIN,
        cooldownTicks: 1.5 * DAY, weight: 3, minDay: 1,
    },
    summary: "Meteors crash down near players (watch for the impact rings). Mine the Meteorite they leave for Star Metal; Astral Mites swarm the craters.",
    color: "§6",
    startTitle: "METEOR SHOWER",
    startSubtitle: "§eStars are falling — watch the sky!",
    startSound: SOUNDS.EVENT_METEOR_SHOWER,
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.STAR_SPARK, 14, 18);
        if (s % 6 !== 3)
            return;
        const per = Math.max(1, Math.round(profile().meteorsPerWave * intensityScale()));
        let budget = per * Math.min(4, Math.max(1, c.players.length));
        for (const p of c.players) {
            for (let i = 0; i < per && budget > 0; i++, budget--) {
                later(i * 12 + c.rng.int(0, 8), () => meteorNear(p, c.rng), "meteor");
            }
        }
    },
    killDrops: [{ item: ITEMS.STARDUST, chance: 0.2, min: 1, max: 2 }],
});
// ------------------------------------------------------------------------------------------------
// Reality Fracture
// ------------------------------------------------------------------------------------------------
function blinkMobs(p, rng) {
    for (const m of mobsNear(p, 16, "monster", 4)) {
        try {
            const from = m.location;
            const to = { x: from.x + rng.range(-6, 6), y: from.y + 0.5, z: from.z + rng.range(-6, 6) };
            burst(m.dimension, PARTICLES.FRACTURE_GLITCH, from, 1, 0.4);
            if (m.tryTeleport(to, { checkForBlocks: true }))
                burst(m.dimension, PARTICLES.FRACTURE_GLITCH, to, 1, 0.4);
        }
        catch {
            /* ignore */
        }
    }
}
const ANOMALIES = [
    {
        text: "§bLow gravity! You feel weightless.",
        run: (p) => {
            effect(p, "jump_boost", 8, 2, true);
            effect(p, "slow_falling", 9, 0, true);
        },
    },
    {
        text: "§3Heavy gravity drags at your limbs.",
        run: (p) => {
            effect(p, "slowness", 5, brutal() ? 2 : 1, true);
            effect(p, "mining_fatigue", 5, 0, true);
        },
    },
    {
        text: "§bA gravity surge lifts you off the ground!",
        run: (p) => {
            effect(p, "levitation", 1.5, 1, true);
            effect(p, "slow_falling", 6, 0, true);
        },
    },
    { text: "§3Reality skips — the monsters around you blink!", run: blinkMobs },
];
registerEvent({
    meta: {
        id: "reality_fracture", name: "Reality Fracture", window: "any", minTicks: 2.5 * MIN, maxTicks: 3.5 * MIN,
        cooldownTicks: 2 * DAY, weight: 2, minDay: 5,
    },
    summary: "Physics breaks down: gravity anomalies lift or anchor you, monsters blink around and Rift Sentinels leak in from the Expanse. Kills drop Fracture Shards.",
    color: "§3",
    fog: FOGS.FOG_FRACTURE,
    startTitle: "REALITY FRACTURE",
    startSubtitle: "§bThe world glitches. Trust nothing.",
    startSound: SOUNDS.EVENT_REALITY_FRACTURE,
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.FRACTURE_GLITCH, 5, 9);
        if (s % 5 === 0) {
            for (const p of c.players) {
                if (!isTargetable(p) || !roll(c, 0.55))
                    continue;
                const a = c.rng.pick(ANOMALIES);
                if (!a)
                    continue;
                a.run(p, c.rng);
                actionbar([p], a.text);
                burst(p.dimension, PARTICLES.FRACTURE_GLITCH, add(p.location, { x: 0, y: 1, z: 0 }), 2, 0.8);
            }
        }
        if (s % 7 === 3) {
            for (const p of c.players) {
                if (!isTargetable(p) || !roll(c, 0.45))
                    continue;
                const e = spawnForEvent(p, ENTITIES.RIFT_SENTINEL, 12, 24);
                if (e)
                    sound(e.dimension, SOUNDS.PORTAL_OPEN, e.location, 0.8, 1.4);
            }
        }
    },
    killDrops: [
        { item: ITEMS.FRACTURE_SHARD, chance: 0.3 },
        { item: ITEMS.FRACTURE_SHARD, chance: 1, min: 1, max: 2, types: [ENTITIES.RIFT_SENTINEL] },
    ],
});
// ------------------------------------------------------------------------------------------------
// Eclipse
// ------------------------------------------------------------------------------------------------
registerEvent({
    meta: {
        id: "eclipse", name: "Eclipse", window: "day", minTicks: 3 * MIN, maxTicks: 4.5 * MIN,
        cooldownTicks: 3 * DAY, weight: 2, minDay: 6,
    },
    summary: "The sun goes dark: Darkness pulses strike anyone under the open sky and the undead walk by day. Kills drop Eclipse Shards, and the Cursed Crown answers during an Eclipse.",
    color: "§8",
    fog: FOGS.FOG_ECLIPSE,
    startTitle: "ECLIPSE",
    startSubtitle: "§7The sun goes dark. The dead do not wait for night.",
    startSound: SOUNDS.EVENT_ECLIPSE,
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.ASH_FALL, 10, 12);
        if (s % 6 === 0) {
            for (const p of c.players)
                if (isTargetable(p) && exposedToSky(p))
                    effect(p, "darkness", 3 * intensityScale());
        }
        if (s % 5 === 2) {
            for (const p of c.players) {
                for (const m of mobsNear(p, 32, "undead"))
                    effect(m, "fire_resistance", 8);
                if (isTargetable(p) && roll(c, 0.6))
                    spawnForEvent(p, ENTITIES.HOLLOW_SHADE, 12, 26);
            }
        }
    },
    killDrops: [{ item: ITEMS.ECLIPSE_SHARD, chance: 0.25 }],
});
function loadCaches() {
    try {
        const v = JSON.parse(readWorld(DP.AWAKENING_CACHES) ?? "[]");
        return Array.isArray(v) ? v.filter((s) => typeof s?.x === "number") : [];
    }
    catch {
        return [];
    }
}
function saveCaches(list) {
    writeWorld(DP.AWAKENING_CACHES, JSON.stringify(list.slice(-32)));
}
/** Remove surfaced caches that were not opened. Unloaded spots are kept for a later sweep. */
function sinkCaches(dim) {
    const keep = [];
    for (const spot of loadCaches()) {
        try {
            const b = dim.getBlock(spot);
            if (!b) {
                keep.push(spot);
                continue;
            }
            if (b.typeId === BLOCKS.ENGINE_CACHE) {
                b.setType("minecraft:air");
                burst(dim, PARTICLES.SPECTRAL_BURST, b.center(), 1, 0.3);
                sound(dim, SOUNDS.RIFT_CLOSE, b.center(), 0.8);
            }
        }
        catch {
            keep.push(spot);
        }
    }
    saveCaches(keep);
}
registerEvent({
    meta: {
        id: "ancient_awakening", name: "Ancient Awakening", window: "any", minTicks: 3 * MIN, maxTicks: 4 * MIN,
        cooldownTicks: 2.5 * DAY, weight: 2, minDay: 3,
    },
    summary: "The buried Engine stirs: Sealed Engine Caches surface near players, guarded by Awakened Sentinels. Break them open before the event ends — unopened caches sink back into the earth.",
    color: "§e",
    fog: FOGS.FOG_AWAKENING,
    startTitle: "ANCIENT AWAKENING",
    startSubtitle: "§6Something old rises from the earth...",
    startSound: SOUNDS.EVENT_ANCIENT_AWAKENING,
    onStart(c) {
        const list = loadCaches();
        for (const p of c.players.slice(0, 8)) {
            if (!isTargetable(p))
                continue;
            const ground = surfaceNear(p, c.rng, 14, 26);
            const spot = ground?.above();
            if (!spot || !SOFT_BLOCKS.has(spot.typeId))
                continue;
            try {
                spot.setType(BLOCKS.ENGINE_CACHE);
            }
            catch {
                continue;
            }
            list.push({ x: spot.x, y: spot.y, z: spot.z });
            runeCircle(c.overworld, spot.bottomCenter(), 2.2, 3);
            actionbar([p], `§6A Sealed Engine Cache surfaced to the ${compass(p.location, spot.location)}!`);
        }
        saveCaches(list);
    },
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.CRYSTAL_GLINT, 4, 10);
        if (s % 3 !== 0)
            return;
        const list = loadCaches();
        const live = [];
        for (const spot of list) {
            let b;
            try {
                b = c.overworld.getBlock(spot);
            }
            catch {
                b = undefined;
            }
            if (b && b.typeId !== BLOCKS.ENGINE_CACHE)
                continue; // opened
            live.push(spot);
            if (!b)
                continue; // unloaded: keep tracking
            const center = b.bottomCenter();
            runeCircle(c.overworld, center, 2.2, 3.2);
            burst(c.overworld, PARTICLES.CRYSTAL_GLINT, add(center, { x: 0, y: 1.2, z: 0 }), 2, 0.5);
            const near = playersNear(c.overworld, center, 32).filter(isTargetable);
            for (const p of near) {
                if (Math.hypot(p.location.x - center.x, p.location.z - center.z) < 6)
                    effect(p, "haste", 4, 1);
            }
            if (s % 12 === 0 && near.length) {
                const guards = eventEntities(ENTITIES.RIFT_SENTINEL).filter((g) => {
                    try {
                        return Math.hypot(g.location.x - center.x, g.location.z - center.z) < 16;
                    }
                    catch {
                        return false;
                    }
                }).length;
                if (guards < (brutal() ? 3 : 2)) {
                    const g = spawnEventMobAt(c.overworld, ENTITIES.RIFT_SENTINEL, { x: center.x + c.rng.range(-4, 4), y: center.y + 1, z: center.z + c.rng.range(-4, 4) });
                    if (g)
                        burst(c.overworld, PARTICLES.SPECTRAL_BURST, g.location, 2, 0.6);
                }
            }
        }
        if (live.length !== list.length)
            saveCaches(live);
    },
    onEnd(c) {
        sinkCaches(c.overworld);
    },
    killDrops: [{ item: ITEMS.RIFT_SHARD, chance: 0.35, min: 1, max: 2 }],
});
// ------------------------------------------------------------------------------------------------
// Corruption Surge
// ------------------------------------------------------------------------------------------------
function spreadBlight(p, rng) {
    for (let i = 0; i < 3; i++) {
        const x = p.location.x + rng.range(-12, 12);
        const z = p.location.z + rng.range(-12, 12);
        try {
            const top = p.dimension.getTopmostBlock({ x, z }, Math.floor(p.location.y) + 8);
            if (!top || top.typeId !== "minecraft:grass_block")
                continue;
            top.setType(BLOCKS.BLIGHTED_GRASS);
            const above = top.above();
            if (above?.isAir && rng.chance(0.25))
                above.setType(BLOCKS.BLIGHT_SPROUT);
            burst(p.dimension, PARTICLES.SPORE_DRIFT, top.center(), 1, 0.4);
        }
        catch {
            /* unloaded */
        }
    }
}
registerEvent({
    meta: {
        id: "corruption_surge", name: "Corruption Surge", window: "any", minTicks: 2.5 * MIN, maxTicks: 4 * MIN,
        cooldownTicks: 2 * DAY, weight: 2, minDay: 4,
    },
    summary: "The Blight surges: Thornlings erupt from the soil, monsters regenerate and harden, and spore storms poison anyone in the open. With terrain damage enabled, grass turns to Blighted Grass.",
    color: "§2",
    fog: FOGS.FOG_BLIGHT,
    startTitle: "CORRUPTION SURGE",
    startSubtitle: "§aThe Blight spreads. Seek shelter from the spores.",
    startSound: SOUNDS.EVENT_CORRUPTION_SURGE,
    onPulse(c) {
        const s = sec(c);
        ambient(c, PARTICLES.SPORE_DRIFT, 4, 10);
        if (s % 4 === 1) {
            for (const p of c.players)
                if (isTargetable(p) && roll(c, 0.6))
                    spawnForEvent(p, ENTITIES.THORNLING, 8, 20);
        }
        if (s % 6 === 3) {
            for (const p of c.players) {
                for (const m of mobsNear(p, 28, "monster")) {
                    effect(m, "regeneration", 7, 0);
                    effect(m, "resistance", 7, 0);
                }
            }
        }
        if (s % 8 === 5) {
            for (const p of c.players) {
                if (!isTargetable(p) || !exposedToSky(p))
                    continue;
                effect(p, "poison", 3 * intensityScale(), 0, true);
                effect(p, "hunger", 6, 0, true);
                burst(p.dimension, PARTICLES.SPORE_DRIFT, add(p.location, { x: 0, y: 1.5, z: 0 }), 2, 1.2);
                actionbar([p], "§2Spores choke the open air — find shelter!");
            }
        }
        if (config().terrainDamage && s % 5 === 0)
            for (const p of c.players.slice(0, 8))
                spreadBlight(p, c.rng);
    },
    killDrops: [{ item: ITEMS.LIVING_BARK, chance: 0.25 }],
});
// ------------------------------------------------------------------------------------------------
// wiring (meteor impacts, stale cache sweep)
// ------------------------------------------------------------------------------------------------
export function initEventDefs() {
    world.afterEvents.projectileHitBlock.subscribe((ev) => {
        if (ev.projectile.typeId === ENTITIES.METEOR)
            meteorImpact(ev.dimension, ev.location);
    });
    world.afterEvents.projectileHitEntity.subscribe((ev) => {
        if (ev.projectile.typeId === ENTITIES.METEOR)
            meteorImpact(ev.dimension, ev.location);
    });
    // caches left in unloaded chunks when an Awakening ended are removed once those chunks load again
    every("awakening-sweep", 400, () => {
        if (activeEvent()?.meta.id === "ancient_awakening")
            return;
        if (loadCaches().length)
            sinkCaches(world.getDimension("minecraft:overworld"));
    }, 6);
}
