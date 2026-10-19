// One tick loop dispatching all periodic work, with per-task error isolation and phase offsets so
// heavy tasks don't land on the same tick (mobile frame-time friendly).
import { system } from "@minecraft/server";
import { log } from "./log.js";

interface Task {
  name: string;
  interval: number;
  offset: number;
  fn: (tick: number) => void;
  failures: number;
}

const tasks: Task[] = [];
let started = false;

export function every(name: string, interval: number, fn: (tick: number) => void, offset = tasks.length % 7): void {
  tasks.push({ name, interval: Math.max(1, Math.floor(interval)), offset, fn, failures: 0 });
}

export function startScheduler(): void {
  if (started) return;
  started = true;
  system.runInterval(() => {
    const tick = system.currentTick;
    for (const t of tasks) {
      if ((tick + t.offset) % t.interval !== 0) continue;
      try {
        t.fn(tick);
      } catch (e) {
        t.failures++;
        if (t.failures <= 3 || t.failures % 100 === 0) log.error(`task ${t.name} failed (${t.failures}x)`, e);
      }
    }
  }, 1);
}

/** Run `fn` after `ticks` ticks, swallowing errors into the log. */
export function later(ticks: number, fn: () => void, name = "later"): number {
  return system.runTimeout(() => {
    try {
      fn();
    } catch (e) {
      log.error(`${name} failed`, e);
    }
  }, Math.max(1, Math.round(ticks)));
}

export const now = (): number => system.currentTick;
