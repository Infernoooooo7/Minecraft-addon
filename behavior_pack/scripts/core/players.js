// Player queries and inventory helpers.
import { EntityComponentTypes, EquipmentSlot, GameMode, PlayerPermissionLevel, world, } from "@minecraft/server";
export function isTargetable(p) {
    try {
        if (!p.isValid)
            return false;
        const gm = p.getGameMode();
        return gm === GameMode.Survival || gm === GameMode.Adventure;
    }
    catch {
        return false;
    }
}
export function targetablePlayers(dim, center, radius) {
    try {
        return dim.getPlayers({ location: center, maxDistance: radius }).filter(isTargetable);
    }
    catch {
        return [];
    }
}
export function nearestTargetable(dim, center, radius) {
    return targetablePlayers(dim, center, radius).sort((a, b) => dist2(a.location, center) - dist2(b.location, center))[0];
}
export function playersNear(dim, center, radius) {
    try {
        return dim.getPlayers({ location: center, maxDistance: radius });
    }
    catch {
        return [];
    }
}
export function allPlayers() {
    try {
        return world.getAllPlayers();
    }
    catch {
        return [];
    }
}
export const dist2 = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2;
export function isOperator(p) {
    try {
        return p.playerPermissionLevel >= PlayerPermissionLevel.Operator;
    }
    catch {
        return false;
    }
}
export function equipment(p, slot) {
    try {
        return p.getComponent(EntityComponentTypes.Equippable)?.getEquipment(slot);
    }
    catch {
        return undefined;
    }
}
/** Give an item; whatever does not fit is dropped at the player's feet. */
export function giveItem(p, stack) {
    try {
        const inv = p.getComponent(EntityComponentTypes.Inventory)?.container;
        const rest = inv ? inv.addItem(stack) : stack;
        if (rest)
            p.dimension.spawnItem(rest, p.location);
    }
    catch {
        /* ignore */
    }
}
export function countItem(p, typeId) {
    let n = 0;
    try {
        const inv = p.getComponent(EntityComponentTypes.Inventory)?.container;
        if (!inv)
            return 0;
        for (let i = 0; i < inv.size; i++) {
            const it = inv.getItem(i);
            if (it?.typeId === typeId)
                n += it.amount;
        }
    }
    catch {
        /* ignore */
    }
    return n;
}
/** Remove one item of `typeId` from the main hand (used by consumable relics). */
export function consumeHeld(p, typeId) {
    try {
        const inv = p.getComponent(EntityComponentTypes.Inventory)?.container;
        if (!inv)
            return false;
        const slot = p.selectedSlotIndex;
        const it = inv.getItem(slot);
        if (!it || it.typeId !== typeId)
            return false;
        if (it.amount <= 1)
            inv.setItem(slot, undefined);
        else {
            it.amount -= 1;
            inv.setItem(slot, it);
        }
        return true;
    }
    catch {
        return false;
    }
}
/** Apply durability damage to the held item; breaks it (with sound) when exhausted. */
export function damageHeld(p, amount) {
    try {
        const inv = p.getComponent(EntityComponentTypes.Inventory)?.container;
        if (!inv)
            return;
        const slot = p.selectedSlotIndex;
        const it = inv.getItem(slot);
        const dur = it?.getComponent("minecraft:durability");
        if (!it || !dur)
            return;
        if (p.getGameMode() === GameMode.Creative)
            return;
        const next = dur.damage + amount;
        if (next >= dur.maxDurability) {
            inv.setItem(slot, undefined);
            p.playSound("random.break");
        }
        else {
            dur.damage = next;
            inv.setItem(slot, it);
        }
    }
    catch {
        /* ignore */
    }
}
/** Remove up to `amount` items of `typeId` from the inventory. Returns how many were removed. */
export function removeItems(p, typeId, amount) {
    let left = amount;
    try {
        const inv = p.getComponent(EntityComponentTypes.Inventory)?.container;
        if (!inv)
            return 0;
        for (let i = 0; i < inv.size && left > 0; i++) {
            const it = inv.getItem(i);
            if (it?.typeId !== typeId)
                continue;
            const take = Math.min(left, it.amount);
            left -= take;
            if (take >= it.amount)
                inv.setItem(i, undefined);
            else {
                it.amount -= take;
                inv.setItem(i, it);
            }
        }
    }
    catch {
        /* ignore */
    }
    return amount - left;
}
export function isCreative(p) {
    try {
        return p.getGameMode() === GameMode.Creative;
    }
    catch {
        return false;
    }
}
export function heldItem(p) {
    return equipment(p, EquipmentSlot.Mainhand);
}
