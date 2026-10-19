// Reward de-duplication: a boss kill (keyed by entity id) can pay out exactly once, even if the
// death event is observed twice or the world reloads in between. Pure and unit tested.
export class RewardLedger {
    constructor(ids = [], capacity = 64) {
        this.capacity = capacity;
        this.ids = ids.slice(-capacity);
    }
    has(id) {
        return this.ids.includes(id);
    }
    /** Returns true only the first time an id is claimed. */
    claim(id) {
        if (!id || this.has(id))
            return false;
        this.ids.push(id);
        if (this.ids.length > this.capacity)
            this.ids.splice(0, this.ids.length - this.capacity);
        return true;
    }
    get size() {
        return this.ids.length;
    }
    serialize() {
        return JSON.stringify(this.ids);
    }
    static parse(json, capacity = 64) {
        if (!json)
            return new RewardLedger([], capacity);
        try {
            const d = JSON.parse(json);
            return new RewardLedger(Array.isArray(d) ? d.filter((x) => typeof x === "string") : [], capacity);
        }
        catch {
            return new RewardLedger([], capacity);
        }
    }
}
/** Damage contribution tracking for fair multiplayer rewards. */
export class Contributions {
    constructor() {
        this.dmg = new Map();
    }
    add(playerId, amount) {
        if (amount > 0)
            this.dmg.set(playerId, (this.dmg.get(playerId) ?? 0) + amount);
    }
    /** Players who dealt at least `minShare` of the total damage (always includes the top dealer). */
    eligible(minShare = 0.05) {
        const total = [...this.dmg.values()].reduce((a, b) => a + b, 0);
        if (total <= 0)
            return [];
        const sorted = [...this.dmg.entries()].sort((a, b) => b[1] - a[1]);
        return sorted.filter(([, v], i) => i === 0 || v / total >= minShare).map(([k]) => k);
    }
    total() {
        return [...this.dmg.values()].reduce((a, b) => a + b, 0);
    }
}
