// Visual / audio helpers. Every particle call is scaled by the performance profile and guarded
// against unloaded chunks so effects can never crash gameplay code.
import { Dimension, MolangVariableMap, Player, Vector3 } from "@minecraft/server";
import { PARTICLES } from "../generated/ids.js";
import { add, scale, sub, len, V3 } from "../logic/vec.js";
import { scaledCount } from "../logic/profiles.js";
import { profile } from "./config.js";

export function particle(dim: Dimension, id: string, loc: Vector3, vars?: MolangVariableMap): void {
  try {
    dim.spawnParticle(id, loc, vars);
  } catch {
    /* unloaded chunk / invalid dimension: effects are cosmetic */
  }
}

/** Spawn an effect `count` times (scaled by profile) with a small random offset. */
export function burst(dim: Dimension, id: string, loc: Vector3, count = 1, spread = 0.4): void {
  const n = scaledCount(count, profile().particles);
  for (let i = 0; i < n; i++) {
    particle(dim, id, {
      x: loc.x + (Math.random() - 0.5) * spread * 2,
      y: loc.y + (Math.random() - 0.5) * spread,
      z: loc.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

/** Ground ring telegraph. Uses Molang variables read by the particle (variable.radius/variable.life). */
export function ring(dim: Dimension, center: Vector3, radius: number, lifeSeconds: number, violet = false): void {
  const vars = new MolangVariableMap();
  vars.setFloat("variable.radius", radius);
  vars.setFloat("variable.life", lifeSeconds);
  particle(dim, violet ? PARTICLES.TELEGRAPH_RING_VIOLET : PARTICLES.TELEGRAPH_RING, center, vars);
}

export function shockwave(dim: Dimension, center: Vector3, radius: number): void {
  const vars = new MolangVariableMap();
  vars.setFloat("variable.radius", radius);
  vars.setFloat("variable.life", 0.6);
  particle(dim, PARTICLES.SHOCKWAVE, center, vars);
}

export function runeCircle(dim: Dimension, center: Vector3, radius: number, life = 1.5): void {
  const vars = new MolangVariableMap();
  vars.setFloat("variable.radius", radius);
  vars.setFloat("variable.life", life);
  particle(dim, PARTICLES.RUNE_CIRCLE, center, vars);
}

export function gravityPull(dim: Dimension, center: Vector3, radius: number): void {
  const vars = new MolangVariableMap();
  vars.setFloat("variable.radius", radius);
  particle(dim, PARTICLES.GRAVITY_PULL, center, vars);
}

/** Particles along a segment; spacing grows on low profiles. */
export function line(dim: Dimension, from: V3, to: V3, id: string, spacing = 0.8): void {
  const d = sub(to, from);
  const l = len(d);
  const step = spacing / Math.max(0.2, profile().particles);
  const n = Math.min(64, Math.floor(l / step));
  for (let i = 0; i <= n; i++) particle(dim, id, add(from, scale(d, n ? i / n : 0)));
}

export function sound(dim: Dimension, id: string, loc: Vector3, volume = 1, pitch = 1): void {
  try {
    dim.playSound(id, loc, { volume, pitch });
  } catch {
    /* ignore */
  }
}

export function playerSound(p: Player, id: string, volume = 1, pitch = 1): void {
  try {
    p.playSound(id, { volume, pitch });
  } catch {
    /* ignore */
  }
}

export function title(players: Player[], main: string, sub?: string, fadeIn = 10, stay = 50, fadeOut = 20): void {
  for (const p of players) {
    try {
      p.onScreenDisplay.setTitle(main, { fadeInDuration: fadeIn, stayDuration: stay, fadeOutDuration: fadeOut, subtitle: sub });
    } catch {
      /* ignore */
    }
  }
}

export function actionbar(players: Player[], text: string): void {
  for (const p of players) {
    try {
      p.onScreenDisplay.setActionBar(text);
    } catch {
      /* ignore */
    }
  }
}

export function shake(p: Player, intensity: number, seconds: number): void {
  try {
    p.runCommand(`camerashake add @s ${intensity.toFixed(2)} ${seconds.toFixed(2)} positional`);
  } catch {
    /* ignore */
  }
}

export function pushFog(p: Player, fogId: string, userId: string): void {
  try {
    p.runCommand(`fog @s remove ${userId}`);
    p.runCommand(`fog @s push ${fogId} ${userId}`);
  } catch {
    /* ignore */
  }
}

export function removeFog(p: Player, userId: string): void {
  try {
    p.runCommand(`fog @s remove ${userId}`);
  } catch {
    /* ignore */
  }
}
