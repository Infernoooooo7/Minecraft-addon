// Armor set bonuses (full set of four pieces), refreshed on a slow tick to stay cheap on mobile.
import { EntityDamageCause, EquipmentSlot, Player, world } from "@minecraft/server";
import { allPlayers, equipment } from "../core/players.js";
import { every } from "../core/scheduler.js";
const SLOTS = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet];
export const SET_BONUS = {
    riftwalker: "Speed I and immunity to fall damage",
    starforged: "Fire Resistance and Night Vision",
    null_aegis: "Resistance I, anchored against gravity attacks and Void Rift pull",
};
export function wearsSet(p, set) {
    const prefix = `apocalypse:${set}_`;
    return SLOTS.every((s) => equipment(p, s)?.typeId?.startsWith(prefix) ?? false);
}
function refresh(p, id, seconds, amplifier = 0) {
    try {
        const cur = p.getEffect(id);
        // only top up when close to expiring so effects never flicker (night vision blinks below 10 s)
        if (!cur || cur.duration < 260)
            p.addEffect(id, seconds * 20, { amplifier, showParticles: false });
    }
    catch {
        /* ignore */
    }
}
export function initArmor() {
    every("armor-sets", 40, () => {
        for (const p of allPlayers()) {
            try {
                if (!p.isValid)
                    continue;
                if (wearsSet(p, "riftwalker"))
                    refresh(p, "speed", 16);
                if (wearsSet(p, "starforged")) {
                    refresh(p, "fire_resistance", 16);
                    refresh(p, "night_vision", 16);
                }
                if (wearsSet(p, "null_aegis"))
                    refresh(p, "resistance", 16);
            }
            catch {
                /* player left */
            }
        }
    }, 4);
    world.beforeEvents.entityHurt.subscribe((ev) => {
        const p = ev.hurtEntity;
        if (p instanceof Player && wearsSet(p, "riftwalker"))
            ev.cancel = true;
    }, { entityFilter: { type: "minecraft:player" }, allowedDamageCauses: [EntityDamageCause.fall] });
}
