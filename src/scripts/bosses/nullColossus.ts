// THE NULL COLOSSUS — endgame construct of the Shattered Expanse.
// Armored stance (incoming damage x0.35) broken only by timed core vents (x1.5): a real
// vulnerability-window fight, plus gravity lift/slam, a sweeping null beam, collapse and orbitals.
import { EquipmentSlot, Player } from "@minecraft/server";
import { actionbar, burst, gravityPull, line, particle, ring, shake, sound, title } from "../core/fx.js";
import { PROP } from "../core/keys.js";
import { equipment, isTargetable, playersNear, targetablePlayers } from "../core/players.js";
import { later } from "../core/scheduler.js";
import { ACTIONS_NULL_COLOSSUS as A, ENTITIES, ITEMS, PARTICLES, SOUNDS } from "../generated/ids.js";
import { add, dirTo, ringPoint, rotY, scale, V3 } from "../logic/vec.js";
import { fireBolt } from "./starEater.js";
import { hitLine, hitRadius, strike, summonAdds } from "./kit.js";
import { registerBoss } from "./runtime.js";
import type { BossAttack, Brain, Ctx } from "./types.js";

const act = (k: keyof typeof A): number => Number(A[k]);
const VENT_TICKS = 120;

function wearsFullAegis(p: Player): boolean {
  return [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet]
    .every((s) => equipment(p, s)?.typeId?.startsWith("apocalypse:null_aegis_"));
}

function openVent(c: Ctx, ticks = VENT_TICKS): void {
  c.brain.vulnerableUntil = c.now + ticks;
  c.brain.memory.ventOpen = true;
  try {
    c.boss.setProperty(PROP.VENTED, true);
    c.boss.setProperty(PROP.ACTION, act("VENT"));
  } catch {
    /* ignore */
  }
  sound(c.dim, SOUNDS.NULL_COLOSSUS_VENT, c.boss.location, 1.2);
  title(playersNear(c.dim, c.boss.location, 48), "§b§lCORE EXPOSED", "§fStrike the Colossus now!", 2, 40, 10);
  later(ticks, () => {
    c.brain.memory.ventOpen = false;
    try {
      if (c.boss.isValid) {
        c.boss.setProperty(PROP.VENTED, false);
        c.boss.setProperty(PROP.ACTION, 0);
      }
    } catch {
      /* ignore */
    }
  }, "vent-close");
}

const attacks: BossAttack[] = [
  {
    id: "gravity_lift", phases: [1, 2, 3], minRange: 0, maxRange: 20, cooldown: [14, 12, 9], windup: 1.5, recover: 2.5,
    weight: 3, action: act("GRAVITY_LIFT"), executeAction: act("GRAVITY_SLAM"),
    telegraph(c) {
      ring(c.dim, c.boss.location, 12, 1.5);
      sound(c.dim, SOUNDS.NULL_COLOSSUS_GRAVITY, c.boss.location);
      actionbar(playersNear(c.dim, c.boss.location, 32), "§3§lGravity inverts — prepare to fall!");
    },
    execute(c) {
      const lifted: Player[] = [];
      for (const p of targetablePlayers(c.dim, c.boss.location, 12)) {
        if (wearsFullAegis(p)) {
          actionbar([p], "§bYour Null Aegis anchors you against the lift.");
          continue;
        }
        try {
          p.addEffect("levitation", 30, { amplifier: 3, showParticles: true });
          lifted.push(p);
        } catch {
          /* ignore */
        }
      }
      gravityPull(c.dim, add(c.boss.location, { x: 0, y: 2, z: 0 }), 10);
      later(32, () => {
        if (!c.boss.isValid) return;
        burst(c.dim, PARTICLES.IMPACT_BURST, c.boss.location, 3, 3);
        for (const p of lifted) {
          if (!p.isValid || !isTargetable(p)) continue;
          try {
            p.removeEffect("levitation");
            p.applyKnockback({ x: 0, z: 0 }, -2.5);
          } catch {
            /* ignore */
          }
          strike(c.boss, p, 7, c.boss.location, {});
          shake(p, 0.7, 0.8);
        }
        // the effort of the slam exposes the core
        openVent({ ...c, now: c.now + 32 }, 100);
      }, "gravity-slam");
    },
  },
  {
    id: "null_beam", phases: [1, 2, 3], minRange: 5, maxRange: 32, cooldown: [12, 10, 8], windup: 2.0, recover: 1.0,
    weight: 3, action: act("BEAM_CHARGE"), executeAction: act("BEAM_FIRE"),
    telegraph(c) {
      if (!c.target) return;
      const eye = add(c.boss.location, { x: 0, y: 5.5, z: 0 });
      const dir = dirTo(eye, add(c.target.location, { x: 0, y: 1, z: 0 }));
      c.brain.memory.beamDir = dir;
      line(c.dim, eye, add(eye, scale(dir, 26)), PARTICLES.NULL_MOTE, 1.0);
      actionbar(playersNear(c.dim, c.boss.location, 40), "§b§lThe Null Beam charges — get out of its path!");
      sound(c.dim, SOUNDS.BOSS_WARN, c.boss.location);
    },
    execute(c) {
      const base = (c.brain.memory.beamDir as V3) ?? c.boss.getViewDirection();
      sound(c.dim, SOUNDS.NULL_COLOSSUS_BEAM, c.boss.location, 1.2);
      const steps = 10;
      for (let i = 0; i <= steps; i++) {
        later(i * 4, () => {
          if (!c.boss.isValid) return;
          const eye = add(c.boss.location, { x: 0, y: 5.5, z: 0 });
          const dir = rotY(base, -40 + (80 * i) / steps);
          const end = add(eye, scale(dir, 26));
          line(c.dim, eye, end, PARTICLES.NULL_BEAM, 1.4);
          hitLine(c.boss, eye, end, 1.3, 4, { knock: 0.4 });
        }, "beam-sweep");
      }
    },
  },
  {
    id: "collapse", phases: [2, 3], minRange: 0, maxRange: 48, cooldown: [22, 16], windup: 2.5, recover: 2.0, weight: 2,
    needsTarget: false, action: act("COLLAPSE"),
    telegraph(c) {
      ring(c.dim, c.boss.location, 6, 2.5);
      title(playersNear(c.dim, c.boss.location, 40), "§3§lCOLLAPSE", "§bResist the pull — escape the inner ring!", 2, 45, 10);
      for (let i = 0; i < 5; i++) {
        later(i * 10, () => {
          if (!c.boss.isValid) return;
          gravityPull(c.dim, add(c.boss.location, { x: 0, y: 2, z: 0 }), 14);
          for (const p of targetablePlayers(c.dim, c.boss.location, 18)) {
            const d = dirTo(p.location, c.boss.location, true);
            try {
              p.applyKnockback({ x: d.x * 0.5, z: d.z * 0.5 }, 0.02);
            } catch {
              /* ignore */
            }
          }
        }, "collapse-pull");
      }
    },
    execute(c) {
      const center = c.boss.location;
      try {
        c.dim.createExplosion(add(center, { x: 0, y: 1, z: 0 }), 3, { breaksBlocks: false, causesFire: false, source: c.boss });
      } catch {
        /* ignore */
      }
      burst(c.dim, PARTICLES.STAR_NOVA, add(center, { x: 0, y: 2, z: 0 }), 2, 1);
      hitRadius(c.boss, center, 6, 14, { knock: 2.0, up: 0.6 });
      openVent(c, 120);
    },
  },
  {
    id: "orbital_barrage", phases: [2, 3], minRange: 8, maxRange: 36, cooldown: [10, 8], windup: 1.0, recover: 0.6,
    weight: 3, action: act("GRAVITY_LIFT"),
    execute(c) {
      const t = c.target;
      if (!t) return;
      const n = c.phase === 3 ? 5 : 3;
      for (let i = 0; i < n; i++) {
        later(i * 5, () => {
          if (!c.boss.isValid || !t.isValid) return;
          const from = add(ringPoint(c.boss.location, 3.5, i * (360 / n)), { x: 0, y: 6, z: 0 });
          fireBolt(c.boss, from, add(t.location, { x: 0, y: 1, z: 0 }), 1.5, "null");
          particle(c.dim, PARTICLES.NULL_BEAM, from);
        }, "orbital");
      }
    },
  },
];

registerBoss({
  typeId: ENTITIES.NULL_COLOSSUS,
  key: "null_colossus",
  displayName: "The Null Colossus",
  color: "§3",
  roarAction: act("ROAR"),
  roarSound: SOUNDS.NULL_COLOSSUS_ROAR,
  leash: 30,
  phaseTitles: {
    1: "§bLast Warden of the Engine",
    2: "§bPhase II — Shatterpoint",
    3: "§cPhase III — Singularity",
  },
  machine: { phaseThresholds: [0.6, 0.25], globalCooldown: 1.2, transitionTime: 2.5, attacks },
  modifyDamage(brain: Brain, damage: number, tick: number): number {
    // before-event context: read-only logic only
    return tick < brain.vulnerableUntil ? damage * 1.5 : damage * 0.35;
  },
  onPhase(c, phase) {
    if (phase === 2) summonAdds(c.boss, c.brain.adds, ENTITIES.RIFT_SENTINEL, 2, c.boss.location, 8);
    if (phase === 3) summonAdds(c.boss, c.brain.adds, ENTITIES.RIFT_SENTINEL, 3, c.boss.location, 8);
    later(52, () => openVent(c, 140), "phase-vent");
  },
  onTick(c) {
    const ventEvery = 25 * 20;
    const last = (c.brain.memory.lastVent as number | undefined) ?? c.brain.spawnedAt;
    if (c.now - last > ventEvery && c.brain.machine.state === "idle" && c.now >= c.brain.vulnerableUntil) {
      c.brain.memory.lastVent = c.now;
      openVent(c);
    }
    if (c.phase === 3 && c.now % 20 < 5) {
      for (const p of targetablePlayers(c.dim, c.boss.location, 5)) strike(c.boss, p, 2, c.boss.location, {});
      particle(c.dim, PARTICLES.BOSS_AURA_CYAN, c.boss.location);
    }
  },
  firstKillReward: [{ item: ITEMS.NULL_HEART, amount: 1 }, { item: ITEMS.NULL_FRAGMENT, amount: 16 }],
});
