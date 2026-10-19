// THE HOLLOW KING — spectral summons, phantom teleports, telegraphed ground quakes, soul chains.
import { Player, Vector3 } from "@minecraft/server";
import { actionbar, burst, line, ring, runeCircle, shake, shockwave, sound } from "../core/fx.js";
import { PROP } from "../core/keys.js";
import { playersNear } from "../core/players.js";
import { later } from "../core/scheduler.js";
import { ACTIONS_HOLLOW_KING as A, ENTITIES, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { add, scale, V3 } from "../logic/vec.js";
import { groundAt, hitRadius, strike, summonAdds } from "./kit.js";
import { forceAttack, registerBoss } from "./runtime.js";
import type { BossAttack, Ctx } from "./types.js";

const act = (k: keyof typeof A): number => Number(A[k]);
const feet = (c: Ctx): Vector3 => c.boss.location;

function warn(c: Ctx, text: string, radius = 32): void {
  actionbar(playersNear(c.dim, c.boss.location, radius), text);
}

const attacks: BossAttack[] = [
  {
    id: "spectral_summon", phases: [1, 2, 3], minRange: 0, maxRange: 48, cooldown: [18, 14, 10], windup: 1.2,
    recover: 1.0, weight: 2, needsTarget: false, action: act("SUMMON"),
    telegraph(c) {
      for (let i = 0; i < 3; i++) {
        const a = (i / 3) * Math.PI * 2;
        runeCircle(c.dim, { x: feet(c).x + Math.cos(a) * 4, y: feet(c).y, z: feet(c).z + Math.sin(a) * 4 }, 1.6, 1.4);
      }
      sound(c.dim, SOUNDS.HOLLOW_KING_SUMMON, feet(c));
    },
    execute(c) {
      const n = [2, 3, 4][c.phase - 1];
      const spawned = summonAdds(c.boss, c.brain.adds, ENTITIES.HOLLOW_SHADE, n, feet(c), 5,
        c.phase === 3 ? "apocalypse:become_crimson" : undefined);
      warn(c, `§5The Hollow King calls ${spawned.length} shades from the grave!`);
    },
  },
  {
    id: "phantom_step", phases: [1, 2, 3], minRange: 6, maxRange: 40, cooldown: [10, 8, 6], windup: 0.5, recover: 0.6,
    weight: 3, action: act("PHANTOM_STEP"),
    telegraph(c) {
      burst(c.dim, PARTICLES.SPECTRAL_BURST, add(feet(c), { x: 0, y: 1.5, z: 0 }), 2, 0.8);
      sound(c.dim, SOUNDS.HOLLOW_KING_TELEPORT, feet(c));
    },
    execute(c) {
      const t = c.target;
      if (!t) return;
      const behind = add(t.location, scale(t.getViewDirection(), -2.6));
      const dest = groundAt(c.dim, { x: behind.x, y: t.location.y + 1, z: behind.z }, 3);
      try {
        c.boss.teleport(dest, { facingLocation: t.location });
      } catch {
        return;
      }
      burst(c.dim, PARTICLES.SPECTRAL_BURST, add(dest, { x: 0, y: 1.5, z: 0 }), 2, 0.8);
      sound(c.dim, SOUNDS.HOLLOW_KING_TELEPORT, dest, 1, 0.8);
      if (c.phase >= 2) {
        later(8, () => {
          if (!c.boss.isValid || !t.isValid) return;
          sound(c.dim, SOUNDS.HOLLOW_KING_SLASH, c.boss.location);
          if (Math.hypot(t.location.x - c.boss.location.x, t.location.z - c.boss.location.z) < 4) {
            strike(c.boss, t, 7, c.boss.location, { knock: 0.9, up: 0.3 });
          }
        }, "phantom-slash");
      }
    },
  },
  {
    id: "grave_quake", phases: [2, 3], minRange: 0, maxRange: 10, cooldown: [12, 9], windup: [1.4, 1.4, 1.0],
    recover: 1.2, weight: 3, action: act("QUAKE_WINDUP"), executeAction: act("QUAKE_SLAM"),
    telegraph(c) {
      const center = feet(c);
      c.brain.memory.quake = center;
      ring(c.dim, center, 7, c.phase === 3 ? 1.0 : 1.4);
      warn(c, "§c§lThe ground trembles — JUMP or get clear!");
      sound(c.dim, SOUNDS.BOSS_WARN, center);
    },
    execute(c) {
      const center = (c.brain.memory.quake as V3) ?? feet(c);
      quake(c, center, 7, 10);
      if (c.phase === 3) {
        ring(c.dim, center, 11, 0.6);
        later(12, () => quake(c, center, 11, 8), "second-quake");
      }
    },
  },
  {
    id: "soul_chains", phases: [2, 3], minRange: 3, maxRange: 18, cooldown: [16, 12], windup: 1.0, recover: 0.8,
    weight: 2, action: act("SOUL_CHAINS"),
    telegraph(c) {
      if (!c.target) return;
      c.brain.memory.chains = c.target.location;
      ring(c.dim, c.target.location, 2.6, 1.0, true);
      sound(c.dim, SOUNDS.HOLLOW_KING_CHAINS, c.target.location);
    },
    execute(c) {
      const spot = (c.brain.memory.chains as V3) ?? c.target?.location;
      if (!spot) return;
      line(c.dim, add(feet(c), { x: 0, y: 2.5, z: 0 }), add(spot, { x: 0, y: 1, z: 0 }), PARTICLES.SOUL_WISP, 0.7);
      const hit = hitRadius(c.boss, spot, 2.6, 4, {
        knock: -1.4, up: 0.2,
        effects: [{ id: "slowness", seconds: 3, amp: 2 }, { id: "wither", seconds: 4, amp: 0 }],
        groundedOnly: false,
      });
      if (hit.length) warn(c, "§5Soul chains bind you to the King!");
    },
  },
  {
    id: "crown_of_ruin", phases: [3], minRange: 0, maxRange: 48, cooldown: 30, windup: 2.0, recover: 1.5, weight: 2,
    needsTarget: false, action: act("CROWN_OF_RUIN"),
    telegraph(c) {
      ring(c.dim, feet(c), 12, 2.0, true);
      warn(c, "§4§lCROWN OF RUIN — break away from the King!", 40);
      sound(c.dim, SOUNDS.BOSS_WARN, feet(c), 1.2, 0.8);
    },
    execute(c) {
      burst(c.dim, PARTICLES.SPECTRAL_BURST, add(feet(c), { x: 0, y: 3, z: 0 }), 6, 3);
      hitRadius(c.boss, feet(c), 12, 6, { knock: 1.6, up: 0.4, effects: [{ id: "weakness", seconds: 6 }] });
      summonAdds(c.boss, c.brain.adds, ENTITIES.HOLLOW_SHADE, 2, feet(c), 6, "apocalypse:become_crimson");
      try {
        c.boss.addEffect("strength", 400, { amplifier: 1, showParticles: false });
        c.boss.addEffect("speed", 400, { amplifier: 0, showParticles: false });
      } catch {
        /* ignore */
      }
    },
  },
];

function quake(c: Ctx, center: V3, radius: number, damage: number): void {
  if (!c.boss.isValid) return;
  shockwave(c.dim, center, radius);
  burst(c.dim, PARTICLES.IMPACT_BURST, center, 3, 1.5);
  sound(c.dim, SOUNDS.HOLLOW_KING_QUAKE, center);
  for (const p of playersNear(c.dim, center, radius + 10)) shake(p, 0.5, 0.8);
  const hit = hitRadius(c.boss, center, radius, damage, { knock: 1.3, up: 0.55, groundedOnly: true });
  for (const p of hit) actionbar([p as Player], "§cThe quake throws you aside!");
}

registerBoss({
  typeId: ENTITIES.HOLLOW_KING,
  key: "hollow_king",
  displayName: "The Hollow King",
  color: "§5",
  roarAction: act("ROAR"),
  roarSound: SOUNDS.HOLLOW_KING_ROAR,
  leash: 40,
  phaseTitles: {
    1: "§dLord of the Hollow Court",
    2: "§dPhase II — The Crown Fractures",
    3: "§cPhase III — Crown of Ruin",
  },
  machine: { phaseThresholds: [0.66, 0.33], globalCooldown: 1.2, transitionTime: 2.0, attacks },
  onPhase(c, phase) {
    summonAdds(c.boss, c.brain.adds, ENTITIES.HOLLOW_SHADE, phase === 3 ? 3 : 2, c.boss.location, 5,
      phase === 3 ? "apocalypse:become_crimson" : undefined);
    if (phase === 3) {
      try {
        c.boss.setProperty(PROP.ACTION, act("ROAR"));
      } catch {
        /* ignore */
      }
      later(44, () => forceAttack(c.brain, "crown_of_ruin"), "crown-opener");
    }
  },
  firstKillReward: [{ item: ITEMS.HOLLOW_CROWN_SHARD, amount: 1 }, { item: ITEMS.SOUL_ESSENCE, amount: 8 }],
});
