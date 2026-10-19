// Safe JSON persistence on top of dynamic properties.
import { Entity, world } from "@minecraft/server";
import { log } from "./log.js";

const MAX_STRING = 30000;

export function readWorld(key: string): string | undefined {
  try {
    const v = world.getDynamicProperty(key);
    return typeof v === "string" ? v : undefined;
  } catch (e) {
    log.warn(`read ${key} failed: ${e}`);
    return undefined;
  }
}

export function writeWorld(key: string, value: string | number | boolean | undefined): void {
  try {
    if (typeof value === "string" && value.length > MAX_STRING) {
      log.warn(`refusing to persist oversized ${key} (${value.length} chars)`);
      return;
    }
    world.setDynamicProperty(key, value);
  } catch (e) {
    log.warn(`write ${key} failed: ${e}`);
  }
}

export function readEntity(e: Entity, key: string): string | number | boolean | undefined {
  try {
    const v = e.getDynamicProperty(key);
    return typeof v === "object" ? undefined : v;
  } catch {
    return undefined;
  }
}

export function writeEntity(e: Entity, key: string, value: string | number | boolean | undefined): void {
  try {
    if (e.isValid) e.setDynamicProperty(key, value);
  } catch (err) {
    log.warn(`entity write ${key} failed: ${err}`);
  }
}
