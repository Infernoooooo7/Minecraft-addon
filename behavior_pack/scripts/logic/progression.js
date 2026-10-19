// Per-player progression journal. Pure and unit tested.
export const BOSS_ORDER = ["hollow_king", "star_eater", "root_titan", "null_colossus"];
export function newJournal() {
    return { v: 1, kills: {}, firstKillDay: {}, events: {}, discovered: [], expanseVisits: 0 };
}
export function parseJournal(json) {
    if (!json)
        return newJournal();
    try {
        const d = JSON.parse(json);
        const j = newJournal();
        if (d.kills && typeof d.kills === "object")
            j.kills = { ...d.kills };
        if (d.firstKillDay && typeof d.firstKillDay === "object")
            j.firstKillDay = { ...d.firstKillDay };
        if (d.events && typeof d.events === "object")
            j.events = { ...d.events };
        if (Array.isArray(d.discovered))
            j.discovered = d.discovered.filter((x) => typeof x === "string").slice(0, 200);
        if (typeof d.expanseVisits === "number")
            j.expanseVisits = d.expanseVisits;
        return j;
    }
    catch {
        return newJournal();
    }
}
/** Records a boss kill; `first` is true only for this player's first kill of that boss. */
export function recordBossKill(j, boss, day) {
    const first = !j.kills[boss];
    j.kills[boss] = (j.kills[boss] ?? 0) + 1;
    if (first)
        j.firstKillDay[boss] = day;
    return { first };
}
export function recordEvent(j, eventId) {
    j.events[eventId] = (j.events[eventId] ?? 0) + 1;
}
export function discover(j, id) {
    if (j.discovered.includes(id))
        return false;
    j.discovered.push(id);
    return true;
}
export function bossesDefeated(j) {
    return BOSS_ORDER.filter((b) => (j.kills[b] ?? 0) > 0).length;
}
/** The Engine Key requires the three overworld boss cores; the Colossus requires the Engine Key. */
export function canForgeEngineKey(j) {
    return ["hollow_king", "star_eater", "root_titan"].every((b) => (j.kills[b] ?? 0) > 0);
}
export function completion(j) {
    const bossPart = bossesDefeated(j) / BOSS_ORDER.length;
    const eventPart = Math.min(1, Object.keys(j.events).length / 5);
    const discPart = Math.min(1, j.discovered.length / 20);
    return Math.round((bossPart * 0.6 + eventPart * 0.25 + discPart * 0.15) * 100) / 100;
}
export function nextObjective(j) {
    if (!j.discovered.includes("apocalypse:rift_shard"))
        return "Mine Rift Ore (glowing cyan veins, Y -56 to 40) to collect Rift Shards.";
    if (!(j.kills.hollow_king > 0))
        return "Craft a Cursed Crown from Soul Essence and use it at night to summon the Hollow King.";
    if (!(j.kills.star_eater > 0))
        return "Gather Stardust during a Meteor Shower, craft an Astral Lure and use it under the open night sky.";
    if (!(j.kills.root_titan > 0))
        return "Collect Living Bark from Thornlings in the Blighted Wilds, craft a Heartseed and plant it by day.";
    if (!(j.kills.null_colossus > 0)) {
        return j.expanseVisits > 0
            ? "Reach the Colossus Arena north of the Nexus and use the Engine Key on the Null Gate."
            : "Forge the Engine Key from the three boss cores and use it to open a rift to the Shattered Expanse.";
    }
    return "The Engine is restored. Hunt world events for rare drops and forge the full Null Aegis.";
}
