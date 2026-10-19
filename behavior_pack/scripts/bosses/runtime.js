// Boss runtime: one "brain" per living boss, ticked by the scheduler. Handles target selection,
// the combat state machine, phase transitions (invulnerable), leashing, damage contributions,
// deduplicated rewards and cleanup.
import { EntityComponentTypes, EntityDamageCause, ItemStack, system, world, } from "@minecraft/server";
import { bossTierBonus, profile } from "../core/config.js";
import { actionbar, burst, playerSound, sound, title } from "../core/fx.js";
import { DIMENSION_EXPANSE, DP, EVENT_TRIGGER, PROP } from "../core/keys.js";
import { log } from "../core/log.js";
import { allPlayers, giveItem, isTargetable, nearestTargetable, playersNear } from "../core/players.js";
import { every, later, now } from "../core/scheduler.js";
import { readEntity, readWorld, writeEntity, writeWorld } from "../core/state.js";
import { ENTITIES, PARTICLES, SOUNDS } from "../generated/ids.js";
import { BossMachine } from "../logic/bossMachine.js";
import { parseJournal, recordBossKill } from "../logic/progression.js";
import { Contributions, RewardLedger } from "../logic/rewardLedger.js";
import { dist, distXZ } from "../logic/vec.js";
import { despawnAdds } from "./kit.js";
const defs = new Map();
const brains = new Map();
let ledger = new RewardLedger();
export function registerBoss(def) {
    defs.set(def.typeId, def);
}
export function activeBrains() {
    return [...brains.values()];
}
export function bossCount(typeId) {
    return [...brains.values()].filter((b) => b.entity.isValid && (!typeId || b.def.typeId === typeId)).length;
}
function ctxOf(b) {
    return { brain: b, boss: b.entity, dim: b.entity.dimension, target: b.target, now: now(), phase: b.machine.phase };
}
function setProp(e, id, v) {
    try {
        if (e.isValid)
            e.setProperty(id, v);
    }
    catch {
        /* property not declared on this entity */
    }
}
function hpFraction(e) {
    try {
        const h = e.getComponent(EntityComponentTypes.Health);
        return h ? h.currentValue / Math.max(1, h.effectiveMax) : 1;
    }
    catch {
        return 1;
    }
}
// ------------------------------------------------------------------------------------------------
// brain lifecycle
// ------------------------------------------------------------------------------------------------
function createBrain(e, fresh) {
    const def = defs.get(e.typeId);
    if (!def || brains.has(e.id))
        return brains.get(e.id);
    const arenaRaw = readEntity(e, DP.BOSS_ARENA);
    let arena = e.location;
    if (typeof arenaRaw === "string") {
        try {
            arena = JSON.parse(arenaRaw);
        }
        catch {
            /* keep current */
        }
    }
    else {
        writeEntity(e, DP.BOSS_ARENA, JSON.stringify(e.location));
    }
    const brain = {
        id: e.id, def, entity: e, machine: new BossMachine(def.machine, now(), fresh ? 3 : 1), arena,
        adds: new Set(), contributions: new Contributions(), memory: {}, vulnerableUntil: 0, spawnedAt: now(),
    };
    if (!fresh) {
        brain.machine.restore(readEntity(e, DP.BOSS_MACHINE), now());
    }
    setProp(e, PROP.PHASE, brain.machine.phase);
    setProp(e, PROP.ACTION, 0);
    brains.set(e.id, brain);
    return brain;
}
function onBossSpawned(e) {
    const brain = createBrain(e, true);
    if (!brain)
        return;
    const players = playersNear(e.dimension, e.location, 64).filter(isTargetable);
    const tier = Math.max(1, Math.min(4, players.length + bossTierBonus()));
    try {
        e.triggerEvent(EVENT_TRIGGER.TIER(tier));
    }
    catch (err) {
        log.warn(`tier event failed: ${err}`);
    }
    later(2, () => {
        try {
            e.getComponent(EntityComponentTypes.Health)?.resetToMaxValue();
        }
        catch {
            /* gone */
        }
    });
    const near = playersNear(e.dimension, e.location, 80);
    title(near, `${brain.def.color}§l${brain.def.displayName.toUpperCase()}`, brain.def.phaseTitles[1] ?? "", 10, 60, 20);
    sound(e.dimension, brain.def.roarSound, e.location, 1.2, 1);
    setProp(e, PROP.ACTION, brain.def.roarAction);
    later(30, () => setProp(e, PROP.ACTION, 0));
    brain.def.onSpawn?.(ctxOf(brain));
    log.debug(`${brain.def.key} spawned with health tier ${tier}`);
}
// ------------------------------------------------------------------------------------------------
// per-tick update
// ------------------------------------------------------------------------------------------------
function selectTarget(b) {
    const e = b.entity;
    const t = b.target;
    if (t && t.isValid && isTargetable(t) && t.dimension.id === e.dimension.id && dist(t.location, e.location) < 48)
        return;
    b.target = nearestTargetable(e.dimension, e.location, 40);
}
function runAttackPhase(b, kind, attack) {
    const ctx = ctxOf(b);
    try {
        if (kind === "telegraph") {
            setProp(b.entity, PROP.ACTION, attack.action);
            attack.telegraph?.(ctx);
        }
        else {
            setProp(b.entity, PROP.ACTION, attack.executeAction ?? attack.action);
            attack.execute(ctx);
        }
    }
    catch (err) {
        log.error(`${b.def.key}.${attack.id} ${kind} failed`, err);
    }
}
function tickBrain(b, tick) {
    const e = b.entity;
    if (!e.isValid) {
        brains.delete(b.id);
        return;
    }
    // dormant when nobody is around (saves CPU on mobile)
    const watchers = playersNear(e.dimension, e.location, 64);
    if (watchers.length === 0)
        return;
    selectTarget(b);
    const targetDist = b.target ? dist(b.target.location, e.location) : null;
    const events = b.machine.update(tick, hpFraction(e), targetDist, Math.random);
    for (const ev of events) {
        switch (ev.type) {
            case "phase": {
                setProp(e, PROP.PHASE, ev.to);
                setProp(e, PROP.ACTION, b.def.roarAction);
                sound(e.dimension, SOUNDS.BOSS_PHASE, e.location, 1.2, 1);
                sound(e.dimension, b.def.roarSound, e.location, 1.3, 0.9);
                burst(e.dimension, PARTICLES.SPECTRAL_BURST, { x: e.location.x, y: e.location.y + 2, z: e.location.z }, 4, 1.5);
                title(playersNear(e.dimension, e.location, 64), `${b.def.color}§l${b.def.displayName}`, b.def.phaseTitles[ev.to] ?? "", 5, 40, 15);
                b.def.onPhase?.(ctxOf(b), ev.to);
                writeEntity(e, DP.BOSS_MACHINE, b.machine.serialize());
                break;
            }
            case "transition_end":
                setProp(e, PROP.ACTION, 0);
                break;
            case "telegraph":
                runAttackPhase(b, "telegraph", ev.attack);
                break;
            case "execute":
                runAttackPhase(b, "execute", ev.attack);
                break;
            case "recovered":
                setProp(e, PROP.ACTION, 0);
                break;
        }
    }
    // leash: keep the fight near where it started (and pull back bosses that fell off an Expanse island)
    if (distXZ(e.location, b.arena) > b.def.leash || e.location.y < b.arena.y - 16) {
        try {
            burst(e.dimension, PARTICLES.SPECTRAL_BURST, e.location, 2, 1);
            e.teleport(b.arena);
            burst(e.dimension, PARTICLES.SPECTRAL_BURST, b.arena, 2, 1);
        }
        catch {
            /* unloaded arena */
        }
    }
    b.def.onTick?.(ctxOf(b));
}
/** Start a specific attack now (scripted phase openers) through the normal telegraph path. */
export function forceAttack(b, attackId) {
    if (!b.entity.isValid)
        return;
    for (const ev of b.machine.force(attackId, now())) {
        if (ev.type === "telegraph")
            runAttackPhase(b, "telegraph", ev.attack);
    }
}
// ------------------------------------------------------------------------------------------------
// death & rewards
// ------------------------------------------------------------------------------------------------
function persistLedger() {
    writeWorld(DP.LEDGER, ledger.serialize());
}
function rewardPlayer(p, def) {
    const journal = parseJournal(readEntity(p, DP.JOURNAL));
    const { first } = recordBossKill(journal, def.key, world.getDay());
    writeEntity(p, DP.JOURNAL, JSON.stringify(journal));
    if (first) {
        for (const r of def.firstKillReward ?? []) {
            try {
                giveItem(p, new ItemStack(r.item, r.amount));
            }
            catch {
                /* unknown item */
            }
        }
        try {
            p.addLevels(5);
        }
        catch {
            /* ignore */
        }
        title([p], `§6§lFIRST VICTORY`, `${def.color}${def.displayName}§r has fallen`, 10, 70, 20);
    }
    else {
        actionbar([p], `${def.color}${def.displayName}§r defeated again`);
    }
    playerSound(p, SOUNDS.BOSS_DEFEAT, 1, 1);
}
function onBossDied(dead, killer) {
    const id = dead.id;
    const def = defs.get(dead.typeId);
    if (!def)
        return;
    const brain = brains.get(id);
    brains.delete(id);
    if (!ledger.claim(id)) {
        log.debug(`duplicate death for ${id} ignored`);
        return;
    }
    persistLedger();
    const loc = dead.location;
    const dim = dead.dimension;
    if (brain)
        despawnAdds(brain.adds);
    burst(dim, PARTICLES.STAR_NOVA, { x: loc.x, y: loc.y + 2, z: loc.z }, 2, 1);
    const contributorIds = new Set(brain ? brain.contributions.eligible(0.05) : []);
    if (killer && killer.typeId === "minecraft:player")
        contributorIds.add(killer.id);
    const contributors = allPlayers().filter((p) => contributorIds.has(p.id));
    // anyone who fought nearby but dealt no damage still gets the journal entry if within range
    for (const p of playersNear(dim, loc, 48))
        if (!contributorIds.has(p.id) && isTargetable(p))
            contributors.push(p);
    for (const p of contributors)
        rewardPlayer(p, def);
    const names = contributors.map((p) => p.name).join(", ") || "the world";
    world.sendMessage(`${def.color}§l${def.displayName}§r has been defeated by §e${names}§r.`);
    const wp = readWorld(DP.WORLD_PROGRESS);
    let progress = {};
    try {
        progress = wp ? JSON.parse(wp) : {};
    }
    catch {
        progress = {};
    }
    progress[def.key] = (progress[def.key] ?? 0) + 1;
    writeWorld(DP.WORLD_PROGRESS, JSON.stringify(progress));
}
export function worldProgress() {
    try {
        return JSON.parse(readWorld(DP.WORLD_PROGRESS) ?? "{}");
    }
    catch {
        return {};
    }
}
// ------------------------------------------------------------------------------------------------
// wiring
// ------------------------------------------------------------------------------------------------
export function initBossRuntime() {
    ledger = RewardLedger.parse(readWorld(DP.LEDGER));
    const types = [...defs.keys()];
    world.afterEvents.entitySpawn.subscribe((ev) => {
        if (defs.has(ev.entity.typeId))
            onBossSpawned(ev.entity);
    });
    world.afterEvents.entityLoad.subscribe((ev) => {
        if (defs.has(ev.entity.typeId))
            createBrain(ev.entity, false);
    });
    // pick up bosses that were already loaded when the script started (/reload or world load)
    later(20, () => {
        for (const dimId of ["minecraft:overworld", "minecraft:nether", "minecraft:the_end", DIMENSION_EXPANSE]) {
            try {
                for (const t of types)
                    for (const e of world.getDimension(dimId).getEntities({ type: t }))
                        createBrain(e, false);
            }
            catch {
                /* dimension not loaded */
            }
        }
    });
    world.beforeEvents.entityHurt.subscribe((ev) => {
        const b = brains.get(ev.hurtEntity.id);
        if (!b)
            return;
        if (b.machine.invulnerable) {
            ev.cancel = true;
            return;
        }
        if (ev.damageSource.cause === EntityDamageCause.fall || ev.damageSource.cause === EntityDamageCause.suffocation) {
            ev.cancel = true;
            return;
        }
        if (b.def.modifyDamage)
            ev.damage = b.def.modifyDamage(b, ev.damage, system.currentTick);
        else if (system.currentTick < b.vulnerableUntil)
            ev.damage = ev.damage * 1.5;
    }, { entityFilter: { families: ["apocalypse_boss"] } });
    world.afterEvents.entityHurt.subscribe((ev) => {
        const b = brains.get(ev.hurtEntity.id);
        const src = ev.damageSource.damagingEntity;
        if (b && src && src.typeId === "minecraft:player")
            b.contributions.add(src.id, ev.damage);
    }, { entityTypes: types });
    world.afterEvents.entityDie.subscribe((ev) => {
        onBossDied(ev.deadEntity, ev.damageSource.damagingEntity);
    }, { entityTypes: types });
    world.afterEvents.entityRemove.subscribe((ev) => {
        const b = brains.get(ev.removedEntityId);
        if (b)
            brains.delete(ev.removedEntityId);
    });
    every("boss-brains", profile().bossTickInterval, (tick) => {
        for (const b of [...brains.values()])
            tickBrain(b, tick);
    }, 1);
    every("boss-persist", 200, () => {
        for (const b of brains.values())
            if (b.entity.isValid)
                writeEntity(b.entity, DP.BOSS_MACHINE, b.machine.serialize());
    }, 3);
}
/** Spawn a boss (used by relics, the Null Gate and admin tools). */
export function spawnBoss(typeId, dimId, loc) {
    try {
        return world.getDimension(dimId).spawnEntity(typeId, loc);
    }
    catch (e) {
        log.error(`spawnBoss ${typeId} failed`, e);
        return undefined;
    }
}
export const BOSS_TYPES = [ENTITIES.HOLLOW_KING, ENTITIES.STAR_EATER, ENTITIES.ROOT_TITAN, ENTITIES.NULL_COLOSSUS];
