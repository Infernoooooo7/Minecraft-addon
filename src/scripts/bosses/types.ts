// Boss definition contracts shared by the runtime and the four boss modules.
import { Dimension, Entity, Player, Vector3 } from "@minecraft/server";
import type { AttackSpec, BossMachine, MachineConfig } from "../logic/bossMachine.js";
import type { Contributions } from "../logic/rewardLedger.js";

export interface Brain {
  id: string;
  def: BossDef;
  entity: Entity;
  machine: BossMachine;
  arena: Vector3;
  target?: Player;
  adds: Set<string>;
  contributions: Contributions;
  /** Scratch space for multi-step attacks (telegraphed positions, sweep angles...). */
  memory: Record<string, unknown>;
  /** Tick until which the boss takes bonus damage (vulnerability window). */
  vulnerableUntil: number;
  spawnedAt: number;
}

export interface Ctx {
  brain: Brain;
  boss: Entity;
  dim: Dimension;
  target?: Player;
  now: number;
  phase: number;
}

export interface BossAttack extends AttackSpec {
  /** Animation action id shown during the telegraph. */
  action: number;
  /** Animation action id at execution (defaults to `action`). */
  executeAction?: number;
  telegraph?(ctx: Ctx): void;
  execute(ctx: Ctx): void;
}

export interface BossDef {
  typeId: string;
  key: string;
  displayName: string;
  /** Section-sign colour code for titles. */
  color: string;
  machine: MachineConfig & { attacks: readonly BossAttack[] };
  roarAction: number;
  roarSound: string;
  leash: number;
  phaseTitles: Record<number, string>;
  onSpawn?(ctx: Ctx): void;
  onPhase?(ctx: Ctx, phase: number): void;
  onTick?(ctx: Ctx): void;
  /** Adjust incoming damage (armor, vulnerability windows). Runs in a before-event: no world writes. */
  modifyDamage?(brain: Brain, damage: number, now: number): number;
  firstKillReward?: Array<{ item: string; amount: number }>;
}
