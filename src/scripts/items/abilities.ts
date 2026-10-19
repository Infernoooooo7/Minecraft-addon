// Weapon abilities (Custom Components V2). `apocalypse:ability` runs on use with a real cooldown;
// `apocalypse:on_hit` adds lifesteal / bleed / null marks to melee hits. Parameters come from item JSON.
import {
  CustomComponentParameters, Entity, EntityComponentTypes, EntityDamageCause, ItemComponentHitEntityEvent,
  ItemComponentUseEvent, ItemCustomComponent, Player, system, Vector3,
} from "@minecraft/server";
import { actionbar, burst, gravityPull, line, playerSound, ring, shake, shockwave, sound } from "../core/fx.js";
import { damageHeld } from "../core/players.js";
import { now } from "../core/scheduler.js";
import { PARTICLES, SOUNDS } from "../generated/ids.js";
import { fireBolt } from "../bosses/starEater.js";
import { add, dirTo, distToSegment, flat, norm, scale, V3 } from "../logic/vec.js";

interface AbilityParams {
  kind: string;
  cooldown?: number;
}

interface OnHitParams {
  kind: "lifesteal" | "null_mark";
  ratio?: number;
  bleed?: boolean;
  base?: number;
}

const cooldowns = new Map<string, number>();
const nullMarks = new Map<string, number>();

/** Hostile targets for player abilities: monsters only, so pets, villagers and other players are safe. */
function foesNear(p: Player, center: Vector3, radius: number): Entity[] {
  try {
    return p.dimension.getEntities({ location: center, maxDistance: radius, families: ["monster"] });
  } catch {
    return [];
  }
}

function hurt(p: Player, e: Entity, amount: number): boolean {
  try {
    return e.applyDamage(amount, { cause: EntityDamageCause.entityAttack, damagingEntity: p });
  } catch {
    return false;
  }
}

function heal(e: Entity, amount: number): void {
  try {
    const h = e.getComponent(EntityComponentTypes.Health);
    if (h) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + amount));
  } catch {
    /* ignore */
  }
}

function knock(from: Vector3, e: Entity, strength: number, up: number): void {
  try {
    const d = dirTo(from, e.location, true);
    e.applyKnockback({ x: d.x * strength, z: d.z * strength }, up);
  } catch {
    /* knockback-immune */
  }
}

const eye = (p: Player): V3 => p.getHeadLocation();

// ------------------------------------------------------------------------------------------------
// abilities
// ------------------------------------------------------------------------------------------------

type Ability = (p: Player) => boolean;

const ABILITIES: Record<string, Ability> = {
  /** Rift Blade: blink up to 7 blocks forward through enemies, cutting everything on the path. */
  rift_dash(p) {
    const dir = norm(flat(p.getViewDirection()));
    if (Math.abs(dir.x) + Math.abs(dir.z) < 0.01) return false;
    const start = p.location;
    let distance = 7;
    try {
      const hit = p.dimension.getBlockFromRay(add(start, { x: 0, y: 0.6, z: 0 }), dir,
        { maxDistance: 7, includePassableBlocks: false, includeLiquidBlocks: false });
      if (hit) distance = Math.max(0, Math.hypot(hit.block.x + 0.5 - start.x, hit.block.z + 0.5 - start.z) - 1.2);
    } catch {
      /* ignore */
    }
    if (distance < 1) {
      actionbar([p], "§cNo room to dash.");
      return false;
    }
    const dest = add(start, scale(dir, distance));
    let moved = false;
    for (const d of [distance, distance * 0.66, distance * 0.33]) {
      const to = add(start, scale(dir, d));
      if (p.tryTeleport(to, { checkForBlocks: true, keepVelocity: false })) {
        moved = true;
        break;
      }
    }
    if (!moved) return false;
    line(p.dimension, add(start, { x: 0, y: 1, z: 0 }), add(dest, { x: 0, y: 1, z: 0 }), PARTICLES.PORTAL_GLOW, 0.6);
    for (const e of foesNear(p, add(start, scale(dir, distance / 2)), distance / 2 + 2)) {
      const c = { x: e.location.x, y: e.location.y + 0.8, z: e.location.z };
      if (distToSegment(c, add(start, { x: 0, y: 0.8, z: 0 }), add(dest, { x: 0, y: 0.8, z: 0 })) <= 1.6) {
        hurt(p, e, 7);
        burst(p.dimension, PARTICLES.FRACTURE_GLITCH, c, 1, 0.3);
      }
    }
    sound(p.dimension, SOUNDS.ABILITY_DASH, p.location);
    return true;
  },

  /** Soulreaver Scythe: 360° reap; each soul taken heals the wielder. */
  soul_reap(p) {
    const center = p.location;
    ring(p.dimension, center, 5, 0.6, true);
    burst(p.dimension, PARTICLES.SOUL_WISP, add(center, { x: 0, y: 1, z: 0 }), 4, 2.5);
    let healed = 0;
    for (const e of foesNear(p, center, 5)) {
      if (hurt(p, e, 9)) {
        knock(center, e, 0.8, 0.25);
        if (healed < 8) {
          heal(p, 2);
          healed += 2;
        }
        burst(p.dimension, PARTICLES.SOUL_WISP, add(e.location, { x: 0, y: 1, z: 0 }), 1, 0.3);
      }
    }
    sound(p.dimension, SOUNDS.ABILITY_REAP, center);
    if (healed) actionbar([p], `§5Reaped souls restore ${healed / 2} heart${healed > 2 ? "s" : ""}.`);
    return true;
  },

  /** Titan's Wrath: ground slam shockwave; grounded enemies are launched and slowed. */
  earthsplitter(p) {
    const center = p.location;
    shockwave(p.dimension, center, 6);
    burst(p.dimension, PARTICLES.ROOT_ERUPTION, center, 4, 2.5);
    sound(p.dimension, SOUNDS.ABILITY_SLAM, center, 1.2);
    shake(p, 0.35, 0.5);
    for (const e of foesNear(p, center, 6)) {
      let grounded = true;
      try {
        grounded = e.isOnGround;
      } catch {
        /* ignore */
      }
      if (!grounded) continue;
      if (hurt(p, e, 11)) {
        knock(center, e, 1.1, 0.7);
        try {
          e.addEffect("slowness", 60, { amplifier: 1 });
        } catch {
          /* ignore */
        }
      }
    }
    return true;
  },

  /** Null Edge: drag every enemy around you into one point, then crush it. */
  gravity_crush(p) {
    const dim = p.dimension;
    const focus = add(p.location, add(scale(norm(flat(p.getViewDirection())), 4), { x: 0, y: 1, z: 0 }));
    const foes = foesNear(p, focus, 10).slice(0, 12);
    gravityPull(dim, focus, 8);
    sound(dim, SOUNDS.ABILITY_GRAVITY, focus);
    for (const e of foes) {
      try {
        const d = dirTo(e.location, focus, true);
        e.applyKnockback({ x: d.x * 1.4, z: d.z * 1.4 }, 0.25);
      } catch {
        /* ignore */
      }
    }
    system.runTimeout(() => {
      burst(dim, PARTICLES.NULL_BEAM, focus, 3, 1.2);
      burst(dim, PARTICLES.IMPACT_BURST, focus, 2, 1);
      sound(dim, SOUNDS.ABILITY_CRUSH, focus, 1.2);
      if (!p.isValid) return;
      for (const e of foesNear(p, focus, 4.5)) {
        if (hurt(p, e, 14)) {
          try {
            e.addEffect("slowness", 80, { amplifier: 2 });
          } catch {
            /* ignore */
          }
        }
      }
    }, 14);
    return true;
  },

  /** Starfall Scepter: a fast homing-free star bolt (owner = wielder, so kills count). */
  star_bolt(p) {
    const from = add(eye(p), scale(p.getViewDirection(), 1.2));
    fireBolt(p, from, add(from, scale(p.getViewDirection(), 30)), 2.0, "star");
    sound(p.dimension, SOUNDS.ABILITY_BOLT, from, 0.8, 1.1);
    return true;
  },

  /** Event Horizon: a gravity well where you aim; pulls and grinds enemies, then implodes. */
  gravity_well(p) {
    const dim = p.dimension;
    let center: V3 = add(eye(p), scale(p.getViewDirection(), 14));
    try {
      const hit = p.getBlockFromViewDirection({ maxDistance: 24, includePassableBlocks: false });
      if (hit) center = { x: hit.block.x + 0.5, y: hit.block.y + 1.5, z: hit.block.z + 0.5 };
    } catch {
      /* ignore */
    }
    ring(dim, add(center, { x: 0, y: -1, z: 0 }), 7, 4, true);
    sound(dim, SOUNDS.ABILITY_GRAVITY, center, 1.1);
    for (let i = 0; i < 8; i++) {
      system.runTimeout(() => {
        gravityPull(dim, center, 6);
        if (!p.isValid) return;
        for (const e of foesNear(p, center, 7)) {
          try {
            const d = dirTo(e.location, center, true);
            e.applyKnockback({ x: d.x * 0.55, z: d.z * 0.55 }, 0.08);
          } catch {
            /* ignore */
          }
          hurt(p, e, 2);
        }
        if (i === 7) {
          burst(dim, PARTICLES.STAR_NOVA, center, 1, 0.3);
          sound(dim, SOUNDS.ABILITY_CRUSH, center);
          for (const e of foesNear(p, center, 4)) hurt(p, e, 8);
        }
      }, 10 * (i + 1));
    }
    return true;
  },
};

export const abilityComponent: ItemCustomComponent = {
  onUse(ev: ItemComponentUseEvent, params: CustomComponentParameters) {
    const p = ev.source;
    const cfg = params.params as AbilityParams;
    const ability = ABILITIES[cfg?.kind];
    if (!ability || !ev.itemStack) return;
    const key = `${p.id}:${cfg.kind}`;
    const t = now();
    const ready = cooldowns.get(key) ?? 0;
    if (t < ready) {
      actionbar([p], `§7${((ready - t) / 20).toFixed(1)}s until ready`);
      return;
    }
    const cdTicks = Math.round((cfg.cooldown ?? 5) * 20);
    const category = ev.itemStack.getComponent("minecraft:cooldown")?.cooldownCategory;
    system.run(() => {
      if (!p.isValid) return;
      let ok = false;
      try {
        ok = ability(p);
      } catch {
        ok = false;
      }
      if (!ok) return;
      cooldowns.set(key, t + cdTicks);
      if (category) {
        try {
          p.startItemCooldown(category, cdTicks);
        } catch {
          /* ignore */
        }
      }
      damageHeld(p, 2);
    });
  },
};

// ------------------------------------------------------------------------------------------------
// on-hit effects
// ------------------------------------------------------------------------------------------------

export const onHitComponent: ItemCustomComponent = {
  onHitEntity(ev: ItemComponentHitEntityEvent, params: CustomComponentParameters) {
    const cfg = params.params as OnHitParams;
    const attacker = ev.attackingEntity;
    const target = ev.hitEntity;
    if (!cfg || !ev.hadEffect) return;
    system.run(() => {
      if (!attacker.isValid || !target.isValid) return;
      if (cfg.kind === "lifesteal") {
        heal(attacker, (cfg.base ?? 8) * (cfg.ratio ?? 0.2));
        if (cfg.bleed) {
          try {
            target.addEffect("wither", 50, { amplifier: 0 });
          } catch {
            /* ignore */
          }
          burst(target.dimension, PARTICLES.BLOOD_BURST, add(target.location, { x: 0, y: 1, z: 0 }), 1, 0.3);
        }
        if (attacker instanceof Player) playerSound(attacker, SOUNDS.ABILITY_LIFESTEAL, 0.5, 1.2);
      } else if (cfg.kind === "null_mark") {
        const t = now();
        const marked = (nullMarks.get(target.id) ?? 0) > t;
        if (marked) {
          nullMarks.delete(target.id);
          try {
            target.applyDamage(7, { cause: EntityDamageCause.magic, damagingEntity: attacker });
          } catch {
            /* ignore */
          }
          burst(target.dimension, PARTICLES.NULL_BEAM, add(target.location, { x: 0, y: 1, z: 0 }), 2, 0.6);
          sound(target.dimension, SOUNDS.ABILITY_CRUSH, target.location, 0.7, 1.3);
        } else {
          nullMarks.set(target.id, t + 100);
          burst(target.dimension, PARTICLES.NULL_MOTE, add(target.location, { x: 0, y: 1.2, z: 0 }), 2, 0.4);
        }
        if (nullMarks.size > 256) for (const [id, exp] of nullMarks) if (exp <= t) nullMarks.delete(id);
      }
    });
  },
};
