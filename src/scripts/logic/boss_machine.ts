// Boss combat state machine. Pure (no @minecraft imports) and unit tested.
//
//   IDLE --(attack chosen: phase + range + cooldown + weight)--> TELEGRAPH --(windup)--> EXECUTE
//   EXECUTE --> RECOVER --(recover time)--> IDLE (after a global cooldown)
//   any state --(health crosses a phase threshold)--> TRANSITION (invulnerable) --> IDLE
//
// Phases only ever increase, so healing cannot undo a transition.

import { weightedPick } from "./rng.js";

export type BossState = "idle" | "telegraph" | "execute" | "recover" | "transition";

export interface AttackSpec {
  id: string;
  /** Phases (1-based) in which the attack can be chosen. */
  phases: readonly number[];
  minRange: number;
  maxRange: number;
  /** Cooldown in seconds; array indexed by phase-1, or a single value. */
  cooldown: number | readonly number[];
  /** Telegraph wind-up in seconds; array indexed by phase-1, or a single value. */
  windup: number | readonly number[];
  /** Recovery time after execution, seconds. */
  recover: number;
  weight: number;
  /** When false the attack may be used without a target (e.g. summons). Default true. */
  needsTarget?: boolean;
}

export interface MachineConfig {
  /** Health fractions at which phase 2, 3, ... begin (descending), e.g. [0.66, 0.33]. */
  phaseThresholds: readonly number[];
  /** Seconds between the end of one attack's recovery and choosing the next. */
  globalCooldown: number;
  /** Seconds of invulnerable phase transition. */
  transitionTime: number;
  attacks: readonly AttackSpec[];
}

export type MachineEvent =
  | { type: "phase"; from: number; to: number }
  | { type: "telegraph"; attack: AttackSpec; windupTicks: number }
  | { type: "execute"; attack: AttackSpec }
  | { type: "recovered"; attack: AttackSpec }
  | { type: "transition_end"; phase: number };

const TPS = 20;

export function perPhase(v: number | readonly number[], phase: number): number {
  if (typeof v === "number") return v;
  return v[Math.min(v.length - 1, Math.max(0, phase - 1))];
}

export function computePhase(hpFraction: number, thresholds: readonly number[]): number {
  let phase = 1;
  for (const t of thresholds) {
    if (hpFraction <= t) phase++;
  }
  return phase;
}

export class BossMachine {
  state: BossState = "idle";
  phase = 1;
  attack: AttackSpec | null = null;
  stateEndsAt = 0;
  globalReadyAt: number;
  readyAt: Record<string, number> = {};

  constructor(private readonly cfg: MachineConfig, now: number, introDelaySeconds = 2) {
    this.globalReadyAt = now + Math.round(introDelaySeconds * TPS);
  }

  get invulnerable(): boolean {
    return this.state === "transition";
  }

  /** Attacks currently eligible for the given target distance (null = no target). */
  eligible(now: number, targetDist: number | null): AttackSpec[] {
    return this.cfg.attacks.filter((a) => {
      if (!a.phases.includes(this.phase)) return false;
      if ((this.readyAt[a.id] ?? 0) > now) return false;
      const needsTarget = a.needsTarget !== false;
      if (targetDist === null) return !needsTarget;
      if (needsTarget && (targetDist < a.minRange || targetDist > a.maxRange)) return false;
      return true;
    });
  }

  /** Force a specific attack into telegraph now (used for scripted phase openers). */
  force(attackId: string, now: number): MachineEvent[] {
    const a = this.cfg.attacks.find((x) => x.id === attackId);
    if (!a || this.state === "transition") return [];
    return this.beginTelegraph(a, now);
  }

  private beginTelegraph(a: AttackSpec, now: number): MachineEvent[] {
    this.attack = a;
    this.state = "telegraph";
    const windupTicks = Math.max(1, Math.round(perPhase(a.windup, this.phase) * TPS));
    this.stateEndsAt = now + windupTicks;
    return [{ type: "telegraph", attack: a, windupTicks }];
  }

  update(now: number, hpFraction: number, targetDist: number | null, roll: () => number): MachineEvent[] {
    const out: MachineEvent[] = [];
    const p = computePhase(hpFraction, this.cfg.phaseThresholds);
    if (p > this.phase) {
      out.push({ type: "phase", from: this.phase, to: p });
      this.phase = p;
      this.attack = null;
      this.state = "transition";
      this.stateEndsAt = now + Math.round(this.cfg.transitionTime * TPS);
      return out;
    }
    switch (this.state) {
      case "transition":
        if (now >= this.stateEndsAt) {
          this.state = "idle";
          this.globalReadyAt = now + TPS;
          out.push({ type: "transition_end", phase: this.phase });
        }
        break;
      case "idle": {
        if (now < this.globalReadyAt) break;
        const choice = weightedPick(this.eligible(now, targetDist), (a) => a.weight, roll());
        if (choice) out.push(...this.beginTelegraph(choice, now));
        break;
      }
      case "telegraph":
        if (now >= this.stateEndsAt && this.attack) {
          const a = this.attack;
          out.push({ type: "execute", attack: a });
          this.readyAt[a.id] = now + Math.round(perPhase(a.cooldown, this.phase) * TPS);
          this.state = "recover";
          this.stateEndsAt = now + Math.round(a.recover * TPS);
        }
        break;
      case "recover":
        if (now >= this.stateEndsAt && this.attack) {
          out.push({ type: "recovered", attack: this.attack });
          this.attack = null;
          this.state = "idle";
          this.globalReadyAt = now + Math.round(this.cfg.globalCooldown * TPS);
        }
        break;
      case "execute":
        this.state = "recover";
        break;
    }
    return out;
  }

  serialize(): string {
    return JSON.stringify({ p: this.phase, r: this.readyAt });
  }

  restore(json: string | undefined, now: number): void {
    if (!json) return;
    try {
      const d = JSON.parse(json) as { p?: number; r?: Record<string, number> };
      if (typeof d.p === "number" && d.p >= 1 && d.p <= 3) this.phase = d.p;
      // cooldowns are relative to the old session's tick counter; reset them relative to now
      if (d.r) for (const k of Object.keys(d.r)) this.readyAt[k] = now + 40;
    } catch {
      /* corrupt data: keep defaults */
    }
  }
}
