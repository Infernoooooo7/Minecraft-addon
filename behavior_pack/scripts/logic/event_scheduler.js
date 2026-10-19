// Dynamic world event scheduling. Pure and unit tested.
import { weightedPick } from "./rng.js";
export const DAY_TICKS = 24000;
export const GLOBAL_COOLDOWN_TICKS = 6000;
export const ROLL_INTERVAL_TICKS = 100;
export function newState() {
    return { active: null, startTick: 0, endTick: 0, cooldownUntil: 0, lastEnd: {}, completed: 0 };
}
export function isNight(timeOfDay) {
    const t = ((timeOfDay % DAY_TICKS) + DAY_TICKS) % DAY_TICKS;
    return t >= 13000 && t < 23000;
}
export function windowOk(w, timeOfDay) {
    if (w === "any")
        return true;
    return w === "night" ? isNight(timeOfDay) : !isNight(timeOfDay);
}
export function eventsPerDay(f) {
    return { off: 0, rare: 0.5, normal: 1, frequent: 2 }[f];
}
/** Probability that a single scheduler roll starts an event, so that ~eventsPerDay happen per day. */
export function rollChance(f, intervalTicks = ROLL_INTERVAL_TICKS) {
    return Math.min(1, (eventsPerDay(f) * intervalTicks) / DAY_TICKS * 1.6);
}
export function eligible(metas, s, now, timeOfDay, day, enabled) {
    if (s.active)
        return [];
    if (now < s.cooldownUntil)
        return [];
    return metas.filter((m) => enabled[m.id] !== false &&
        day >= m.minDay &&
        windowOk(m.window, timeOfDay) &&
        now >= (s.lastEnd[m.id] ?? -Infinity) + m.cooldownTicks);
}
export function pick(metas, rng) {
    return weightedPick(metas, (m) => m.weight, rng.next());
}
export function start(s, m, now, rng) {
    const dur = Math.round(rng.range(m.minTicks, m.maxTicks));
    return { ...s, active: m.id, startTick: now, endTick: now + dur };
}
export function shouldEnd(s, m, now, timeOfDay) {
    if (!s.active)
        return false;
    if (!m)
        return true;
    if (now >= s.endTick)
        return true;
    // night events fade at dawn, day events at dusk (give a short grace period at the boundary)
    return m.window !== "any" && !windowOk(m.window, timeOfDay) && now - s.startTick > 200;
}
export function end(s, now) {
    if (!s.active)
        return s;
    return {
        ...s,
        active: null,
        lastEnd: { ...s.lastEnd, [s.active]: now },
        cooldownUntil: now + GLOBAL_COOLDOWN_TICKS,
        completed: s.completed + 1,
    };
}
export function parseState(json) {
    if (!json)
        return newState();
    try {
        const d = JSON.parse(json);
        return {
            active: typeof d.active === "string" ? d.active : null,
            startTick: Number(d.startTick) || 0,
            endTick: Number(d.endTick) || 0,
            cooldownUntil: Number(d.cooldownUntil) || 0,
            lastEnd: d.lastEnd && typeof d.lastEnd === "object" ? d.lastEnd : {},
            completed: Number(d.completed) || 0,
        };
    }
    catch {
        return newState();
    }
}
/**
 * Persisted ticks come from a previous session's system.currentTick, which restarts at 0 on load.
 * Rebase every stored tick so remaining durations/cooldowns carry over.
 */
export function rebase(s, savedAt, now) {
    const shift = now - savedAt;
    const lastEnd = {};
    for (const [k, v] of Object.entries(s.lastEnd))
        lastEnd[k] = v + shift;
    return {
        ...s,
        startTick: s.startTick + shift,
        endTick: s.endTick + shift,
        cooldownUntil: s.cooldownUntil + shift,
        lastEnd,
    };
}
