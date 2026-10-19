// Shared combat helpers for scripted boss attacks.
import { EntityDamageCause } from "@minecraft/server";
import { bossDamageScale, profile } from "../core/config.js";
import { DP, TAG } from "../core/keys.js";
import { writeEntity } from "../core/state.js";
import { isTargetable, targetablePlayers } from "../core/players.js";
import { PARTICLES } from "../generated/ids.js";
import { burst } from "../core/fx.js";
import { dirTo, distToSegment } from "../logic/vec.js";
const addRefs = new Map();
/** Damage targetable players inside a sphere. Returns players hit. */
export function hitRadius(boss, center, radius, damage, opt = {}) {
    const hit = [];
    for (const p of targetablePlayers(boss.dimension, center, radius)) {
        if (opt.groundedOnly && !safeOnGround(p))
            continue;
        strike(boss, p, damage, center, opt);
        hit.push(p);
    }
    return hit;
}
/** Damage players within `width` of the segment a->b. */
export function hitLine(boss, a, b, width, damage, opt = {}) {
    const hit = [];
    const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
    const reach = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) / 2 + width + 1;
    for (const p of targetablePlayers(boss.dimension, mid, reach)) {
        const c = { x: p.location.x, y: p.location.y + 0.9, z: p.location.z };
        if (distToSegment(c, a, b) <= width) {
            strike(boss, p, damage, a, opt);
            hit.push(p);
        }
    }
    return hit;
}
export function strike(boss, p, damage, from, opt = {}) {
    try {
        if (!isTargetable(p))
            return;
        const dmg = Math.max(0, damage * bossDamageScale());
        if (dmg > 0)
            p.applyDamage(dmg, { cause: opt.cause ?? EntityDamageCause.entityAttack, damagingEntity: boss });
        if (opt.knock || opt.up) {
            const d = dirTo(from, p.location, true);
            const k = opt.knock ?? 0;
            p.applyKnockback({ x: d.x * k, z: d.z * k }, opt.up ?? 0);
        }
        for (const e of opt.effects ?? [])
            p.addEffect(e.id, Math.round(e.seconds * 20), { amplifier: e.amp ?? 0, showParticles: true });
    }
    catch {
        /* target may have died/left during the hit */
    }
}
export function safeOnGround(e) {
    try {
        return e.isOnGround;
    }
    catch {
        return true;
    }
}
/** Ground position under/near a location (top solid block + 1), or the location itself. */
export function groundAt(dim, loc, searchUp = 6) {
    try {
        const top = dim.getTopmostBlock({ x: loc.x, z: loc.z }, loc.y + searchUp);
        if (top)
            return { x: loc.x, y: top.location.y + 1, z: loc.z };
    }
    catch {
        /* unloaded */
    }
    return loc;
}
/** True when there is no solid block between two points (supernova cover check). */
export function hasLineOfSight(dim, from, to) {
    try {
        const d = { x: to.x - from.x, y: to.y - from.y, z: to.z - from.z };
        const l = Math.hypot(d.x, d.y, d.z);
        if (l < 0.5)
            return true;
        const hit = dim.getBlockFromRay(from, { x: d.x / l, y: d.y / l, z: d.z / l }, { maxDistance: l - 0.5, includeLiquidBlocks: false, includePassableBlocks: false });
        return !hit;
    }
    catch {
        return true;
    }
}
/** Summon boss adds respecting the profile cap. Returns spawned entities. */
export function summonAdds(boss, adds, typeId, count, around, radius, spawnEvent) {
    pruneAdds(boss.dimension, adds);
    const room = Math.max(0, profile().bossAdds - adds.size);
    const out = [];
    for (let i = 0; i < Math.min(room, count); i++) {
        const ang = Math.random() * Math.PI * 2;
        const r = radius * (0.5 + Math.random() * 0.5);
        const pos = groundAt(boss.dimension, { x: around.x + Math.cos(ang) * r, y: around.y + 2, z: around.z + Math.sin(ang) * r });
        try {
            const e = boss.dimension.spawnEntity(typeId, pos, spawnEvent ? { spawnEvent } : undefined);
            e.addTag(TAG.BOSS_ADD);
            writeEntity(e, DP.OWNER, boss.id);
            adds.add(e.id);
            addRefs.set(e.id, e);
            burst(boss.dimension, PARTICLES.SPECTRAL_BURST, pos, 1, 0.2);
            out.push(e);
        }
        catch {
            /* spawn blocked */
        }
    }
    return out;
}
export function pruneAdds(_dim, adds) {
    for (const id of [...adds]) {
        const e = addRefs.get(id);
        if (e && !e.isValid) {
            adds.delete(id);
            addRefs.delete(id);
        }
    }
}
export function despawnAdds(adds) {
    for (const id of adds) {
        const e = addRefs.get(id);
        try {
            if (e?.isValid) {
                burst(e.dimension, PARTICLES.SPECTRAL_BURST, e.location, 1, 0.2);
                e.remove();
            }
        }
        catch {
            /* already gone */
        }
        addRefs.delete(id);
    }
    adds.clear();
}
