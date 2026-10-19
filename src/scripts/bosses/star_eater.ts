// THE STAR EATER — cosmic projectiles, gravity wells, comet dives and a line-of-sight Supernova.
import { Entity, Vector3 } from "@minecraft/server";
import { actionbar, burst, gravityPull, ring, shake, sound, title } from "../core/fx.js";
import { PROP } from "../core/keys.js";
import { playersNear, targetablePlayers } from "../core/players.js";
import { later } from "../core/scheduler.js";
import { ACTIONS_STAR_EATER as A, ENTITIES, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { add, dirTo, scale, V3 } from "../logic/vec.js";
import { groundAt, hasLineOfSight, hitRadius, strike, summonAdds } from "./kit.js";
import { forceAttack, registerBoss } from "./runtime.js";
import type { BossAttack, Ctx } from "./types.js";

const act = (k: keyof typeof A): number => Number(A[k]);
const maw = (c: Ctx): Vector3 => add(c.boss.location, add(scale(c.boss.getViewDirection(), 3), { x: 0, y: 2.2, z: 0 }));

/** Fire a star bolt projectile from `from` toward `to` (owner = shooter). */
export function fireBolt(shooter: Entity, from: V3, to: V3, speed = 1.3, variant: "star" | "null" = "star"): void {
  try {
    const bolt = shooter.dimension.spawnEntity(ENTITIES.STAR_BOLT, from);
    if (variant !== "star") bolt.setProperty(PROP.VARIANT, variant);
    const proj = bolt.getComponent("minecraft:projectile");
    if (proj) {
      proj.owner = shooter;
      proj.shoot(scale(dirTo(from, to), speed), { uncertainty: 0.6 });
    } else {
      bolt.applyImpulse(scale(dirTo(from, to), speed));
    }
  } catch {
    /* unloaded */
  }
}

const attacks: BossAttack[] = [
  {
    id: "star_volley", phases: [1, 2, 3], minRange: 4, maxRange: 40, cooldown: [6, 5, 4], windup: 0.8, recover: 0.6,
    weight: 4, action: act("BOLT_VOLLEY"),
    telegraph(c) {
      burst(c.dim, PARTICLES.STAR_SPARK, maw(c), 4, 0.6);
    },
    execute(c) {
      const t = c.target;
      if (!t) return;
      const n = [3, 5, 7][c.phase - 1];
      for (let i = 0; i < n; i++) {
        later(i * 3, () => {
          if (!c.boss.isValid || !t.isValid) return;
          const aim = add(t.location, { x: (Math.random() - 0.5) * 3, y: 1 + Math.random(), z: (Math.random() - 0.5) * 3 });
          fireBolt(c.boss, maw(c), aim, 1.3 + c.phase * 0.15);
          sound(c.dim, SOUNDS.STAR_EATER_BOLT, maw(c), 0.8, 1 + i * 0.05);
        }, "volley");
      }
    },
  },
  {
    id: "gravity_well", phases: [1, 2, 3], minRange: 0, maxRange: 28, cooldown: [16, 13, 10], windup: 1.0, recover: 1.0,
    weight: 2, action: act("GRAVITY_WELL"),
    telegraph(c) {
      if (!c.target) return;
      const center = groundAt(c.dim, c.target.location, 2);
      c.brain.memory.well = center;
      ring(c.dim, center, 8, 1.0, true);
      sound(c.dim, SOUNDS.STAR_EATER_GRAVITY, center);
    },
    execute(c) {
      const center = c.brain.memory.well as V3;
      if (!center) return;
      for (let i = 0; i < 8; i++) {
        later(i * 10, () => {
          if (!c.boss.isValid) return;
          gravityPull(c.dim, add(center, { x: 0, y: 1, z: 0 }), 6);
          for (const p of targetablePlayers(c.dim, center, 8)) {
            const d = dirTo(p.location, center, true);
            try {
              p.applyKnockback({ x: d.x * 0.45, z: d.z * 0.45 }, 0.05);
            } catch {
              /* ignore */
            }
          }
          hitRadius(c.boss, center, 1.8, 3, {});
        }, "gravity-well");
      }
      actionbar(playersNear(c.dim, center, 16), "§dA gravity well drags you in — run!");
    },
  },
  {
    id: "comet_dive", phases: [2, 3], minRange: 6, maxRange: 32, cooldown: [12, 10], windup: 1.2, recover: 1.2,
    weight: 3, action: act("DIVE"),
    telegraph(c) {
      if (!c.target) return;
      const spot = groundAt(c.dim, c.target.location, 2);
      c.brain.memory.dive = spot;
      ring(c.dim, spot, 4.5, 1.2);
      actionbar(playersNear(c.dim, spot, 20), "§6§lThe Star Eater dives — move!");
      sound(c.dim, SOUNDS.BOSS_WARN, spot);
    },
    execute(c) {
      const spot = c.brain.memory.dive as V3;
      if (!spot) return;
      try {
        c.boss.teleport(add(spot, { x: 0, y: 1.5, z: 0 }));
      } catch {
        return;
      }
      burst(c.dim, PARTICLES.STAR_NOVA, spot, 1, 0.5);
      burst(c.dim, PARTICLES.IMPACT_BURST, spot, 3, 1.5);
      sound(c.dim, SOUNDS.STAR_EATER_NOVA, spot, 0.8, 1.3);
      hitRadius(c.boss, spot, 4.5, 9, { knock: 1.5, up: 0.5 });
      for (const p of playersNear(c.dim, spot, 14)) shake(p, 0.4, 0.6);
      later(20, () => {
        try {
          if (c.boss.isValid) c.boss.applyImpulse({ x: 0, y: 1.2, z: 0 });
        } catch {
          /* ignore */
        }
      }, "rise");
    },
  },
  {
    id: "astral_brood", phases: [2, 3], minRange: 0, maxRange: 48, cooldown: [22, 16], windup: 1.0, recover: 0.8,
    weight: 2, needsTarget: false, action: act("BROOD"),
    execute(c) {
      const around = c.target ? c.target.location : c.boss.location;
      summonAdds(c.boss, c.brain.adds, ENTITIES.ASTRAL_MITE, c.phase === 3 ? 4 : 3, around, 6);
    },
  },
  {
    id: "supernova", phases: [3], minRange: 0, maxRange: 48, cooldown: 35, windup: 3.0, recover: 4.0, weight: 1,
    needsTarget: false, action: act("SUPERNOVA_CHARGE"), executeAction: act("SUPERNOVA_RELEASE"),
    telegraph(c) {
      ring(c.dim, groundAt(c.dim, c.boss.location, 2), 14, 3.0);
      title(playersNear(c.dim, c.boss.location, 48), "§6§lSUPERNOVA", "§eBreak line of sight — hide behind blocks!", 5, 50, 10);
      sound(c.dim, SOUNDS.STAR_EATER_CHARGE, c.boss.location, 1.3);
    },
    execute(c) {
      const core = add(c.boss.location, { x: 0, y: 2, z: 0 });
      burst(c.dim, PARTICLES.STAR_NOVA, core, 3, 2);
      sound(c.dim, SOUNDS.STAR_EATER_NOVA, core, 1.5);
      for (const p of targetablePlayers(c.dim, core, 16)) {
        const eye = add(p.location, { x: 0, y: 1.6, z: 0 });
        if (hasLineOfSight(c.dim, core, eye)) {
          strike(c.boss, p, 16, core, { knock: 2.0, up: 0.6, effects: [{ id: "blindness", seconds: 3 }] });
        } else {
          actionbar([p], "§aYou weathered the Supernova behind cover!");
        }
        shake(p, 0.8, 1.0);
      }
      // exhausted: a 4 second vulnerability window
      c.brain.vulnerableUntil = c.now + 80;
      actionbar(playersNear(c.dim, core, 48), "§b§lThe Star Eater is exhausted — strike now!");
    },
  },
];

registerBoss({
  typeId: ENTITIES.STAR_EATER,
  key: "star_eater",
  displayName: "The Star Eater",
  color: "§6",
  roarAction: act("ROAR"),
  roarSound: SOUNDS.STAR_EATER_ROAR,
  leash: 56,
  phaseTitles: {
    1: "§eDevourer of Constellations",
    2: "§ePhase II — The Hungry Sky",
    3: "§cPhase III — Collapsing Star",
  },
  machine: { phaseThresholds: [0.6, 0.25], globalCooldown: 1.0, transitionTime: 2.0, attacks },
  onPhase(c, phase) {
    if (phase === 3) later(50, () => forceAttack(c.brain, "supernova"), "supernova-opener");
  },
  onTick(c) {
    // altitude keeping: hover a few blocks above its target
    const t = c.target;
    if (!t) return;
    const dy = t.location.y + 5 - c.boss.location.y;
    try {
      if (Math.abs(dy) > 1.5 && c.brain.machine.state !== "recover") {
        c.boss.applyImpulse({ x: 0, y: Math.max(-0.25, Math.min(0.25, dy * 0.05)), z: 0 });
      }
    } catch {
      /* ignore */
    }
  },
  firstKillReward: [{ item: ITEMS.STAR_EATER_CORE, amount: 1 }, { item: ITEMS.STARDUST, amount: 12 }],
});
