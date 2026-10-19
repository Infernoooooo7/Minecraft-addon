import { actionbar, burst, line, ring, shake, shockwave, sound } from "../core/fx.js";
import { playersNear } from "../core/players.js";
import { ACTIONS_ROOT_TITAN as A, ENTITIES, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { add, ringPoint } from "../logic/vec.js";
import { groundAt, hitRadius, strike, summonAdds } from "./kit.js";
import { registerBoss } from "./runtime.js";
const act = (k) => Number(A[k]);
const feet = (c) => c.boss.location;
function eruptionSpots(c) {
    const t = c.target;
    if (!t)
        return [];
    const base = groundAt(c.dim, t.location, 2);
    const spots = [base];
    const extra = [0, 2, 4][c.phase - 1];
    for (let i = 0; i < extra; i++)
        spots.push(groundAt(c.dim, ringPoint(base, 3.5, (i * 360) / extra + Math.random() * 40), 3));
    return spots;
}
const attacks = [
    {
        id: "thorn_eruption", phases: [1, 2, 3], minRange: 3, maxRange: 30, cooldown: [8, 7, 5], windup: [1.1, 1.0, 0.8],
        recover: 0.8, weight: 4, action: act("ERUPTION"),
        telegraph(c) {
            const spots = eruptionSpots(c);
            c.brain.memory.eruption = spots;
            for (const s of spots)
                ring(c.dim, s, 2.2, [1.1, 1.0, 0.8][c.phase - 1]);
            sound(c.dim, SOUNDS.BOSS_WARN, spots[0] ?? feet(c), 0.8);
        },
        execute(c) {
            const spots = c.brain.memory.eruption ?? [];
            for (const s of spots) {
                burst(c.dim, PARTICLES.ROOT_ERUPTION, s, 2, 0.6);
                sound(c.dim, SOUNDS.ROOT_TITAN_ERUPTION, s, 0.9);
                hitRadius(c.boss, s, 2.2, 9, { up: 1.0, effects: [{ id: "slowness", seconds: 2, amp: 1 }] });
            }
        },
    },
    {
        id: "earthsplitter", phases: [1, 2, 3], minRange: 0, maxRange: 8, cooldown: [11, 9, 7], windup: 1.3, recover: 1.2,
        weight: 3, action: act("SLAM_WINDUP"), executeAction: act("SLAM"),
        telegraph(c) {
            ring(c.dim, feet(c), 6.5, 1.3);
            actionbar(playersNear(c.dim, feet(c), 24), "§2§lThe Titan raises its fists — JUMP or flee!");
            sound(c.dim, SOUNDS.BOSS_WARN, feet(c));
        },
        execute(c) {
            shockwave(c.dim, feet(c), 6.5);
            burst(c.dim, PARTICLES.ROOT_ERUPTION, feet(c), 4, 2.5);
            sound(c.dim, SOUNDS.ROOT_TITAN_SLAM, feet(c), 1.3);
            for (const p of playersNear(c.dim, feet(c), 18))
                shake(p, 0.6, 0.8);
            hitRadius(c.boss, feet(c), 6.5, 12, {
                knock: 1.4, up: 0.5, groundedOnly: true,
                effects: c.phase === 3 ? [{ id: "wither", seconds: 3, amp: 0 }] : [],
            });
        },
    },
    {
        id: "seed_brood", phases: [1, 2, 3], minRange: 0, maxRange: 48, cooldown: [20, 16, 12], windup: 1.5, recover: 1.0,
        weight: 2, needsTarget: false, action: act("BROOD"),
        execute(c) {
            const n = [2, 3, 4][c.phase - 1];
            const got = summonAdds(c.boss, c.brain.adds, ENTITIES.THORNLING, n, feet(c), 6);
            for (const e of got)
                burst(c.dim, PARTICLES.ROOT_ERUPTION, e.location, 1, 0.3);
        },
    },
    {
        id: "vine_lash", phases: [2, 3], minRange: 5, maxRange: 20, cooldown: [10, 8], windup: 0.7, recover: 0.6,
        weight: 3, action: act("VINE_PULL"),
        telegraph(c) {
            if (!c.target)
                return;
            line(c.dim, add(feet(c), { x: 0, y: 3, z: 0 }), add(c.target.location, { x: 0, y: 1, z: 0 }), PARTICLES.SPORE_DRIFT, 0.8);
        },
        execute(c) {
            const t = c.target;
            if (!t)
                return;
            line(c.dim, add(feet(c), { x: 0, y: 3, z: 0 }), add(t.location, { x: 0, y: 1, z: 0 }), PARTICLES.ROOT_ERUPTION, 1.2);
            strike(c.boss, t, 5, t.location, { effects: [{ id: "slowness", seconds: 1.5, amp: 3 }] });
            const d = { x: c.boss.location.x - t.location.x, z: c.boss.location.z - t.location.z };
            const l = Math.hypot(d.x, d.z) || 1;
            try {
                t.applyKnockback({ x: (d.x / l) * 2.0, z: (d.z / l) * 2.0 }, 0.35);
            }
            catch {
                /* ignore */
            }
        },
    },
    {
        id: "sap_shield", phases: [2, 3], minRange: 0, maxRange: 48, cooldown: [25, 18], windup: 1.0, recover: 1.0,
        weight: 1, needsTarget: false, action: act("SAP_SHIELD"),
        execute(c) {
            try {
                c.boss.addEffect("absorption", 200, { amplifier: 4, showParticles: true });
                c.boss.addEffect("resistance", 120, { amplifier: 0, showParticles: true });
            }
            catch {
                /* ignore */
            }
            burst(c.dim, PARTICLES.HEAL_MOTES, add(feet(c), { x: 0, y: 3, z: 0 }), 4, 2);
            actionbar(playersNear(c.dim, feet(c), 32), "§aThe Titan hardens its bark with living sap!");
        },
    },
];
registerBoss({
    typeId: ENTITIES.ROOT_TITAN,
    key: "root_titan",
    displayName: "The Root Titan",
    color: "§2",
    roarAction: act("ROAR"),
    roarSound: SOUNDS.ROOT_TITAN_ROAR,
    leash: 36,
    phaseTitles: {
        1: "§aWarden of the Blighted Wilds",
        2: "§aPhase II — The Forest Awakens",
        3: "§cPhase III — Overgrowth",
    },
    machine: { phaseThresholds: [0.66, 0.33], globalCooldown: 1.4, transitionTime: 2.2, attacks },
    onPhase(c, phase) {
        for (let i = 0; i < 6; i++)
            ring(c.dim, groundAt(c.dim, ringPoint(c.boss.location, 6, i * 60), 3), 2.0, 0.8);
        summonAdds(c.boss, c.brain.adds, ENTITIES.THORNLING, phase, c.boss.location, 6);
    },
    firstKillReward: [{ item: ITEMS.TITAN_HEARTWOOD, amount: 1 }, { item: ITEMS.LIVING_BARK, amount: 10 }],
});
