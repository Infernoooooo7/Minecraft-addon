// Boss combat state machine. Pure (no @minecraft imports) and unit tested.
//
//   IDLE --(attack chosen: phase + range + cooldown + weight)--> TELEGRAPH --(windup)--> EXECUTE
//   EXECUTE --> RECOVER --(recover time)--> IDLE (after a global cooldown)
//   any state --(health crosses a phase threshold)--> TRANSITION (invulnerable) --> IDLE
//
// Phases only ever increase, so healing cannot undo a transition.
import { weightedPick } from "./rng.js";
const TPS = 20;
export function perPhase(v, phase) {
    if (typeof v === "number")
        return v;
    return v[Math.min(v.length - 1, Math.max(0, phase - 1))];
}
export function computePhase(hpFraction, thresholds) {
    let phase = 1;
    for (const t of thresholds) {
        if (hpFraction <= t)
            phase++;
    }
    return phase;
}
export class BossMachine {
    constructor(cfg, now, introDelaySeconds = 2) {
        this.cfg = cfg;
        this.state = "idle";
        this.phase = 1;
        this.attack = null;
        this.stateEndsAt = 0;
        this.readyAt = {};
        this.globalReadyAt = now + Math.round(introDelaySeconds * TPS);
    }
    get invulnerable() {
        return this.state === "transition";
    }
    /** Attacks currently eligible for the given target distance (null = no target). */
    eligible(now, targetDist) {
        return this.cfg.attacks.filter((a) => {
            if (!a.phases.includes(this.phase))
                return false;
            if ((this.readyAt[a.id] ?? 0) > now)
                return false;
            const needsTarget = a.needsTarget !== false;
            if (targetDist === null)
                return !needsTarget;
            if (needsTarget && (targetDist < a.minRange || targetDist > a.maxRange))
                return false;
            return true;
        });
    }
    /** Force a specific attack into telegraph now (used for scripted phase openers). */
    force(attackId, now) {
        const a = this.cfg.attacks.find((x) => x.id === attackId);
        if (!a || this.state === "transition")
            return [];
        return this.beginTelegraph(a, now);
    }
    beginTelegraph(a, now) {
        this.attack = a;
        this.state = "telegraph";
        const windupTicks = Math.max(1, Math.round(perPhase(a.windup, this.phase) * TPS));
        this.stateEndsAt = now + windupTicks;
        return [{ type: "telegraph", attack: a, windupTicks }];
    }
    update(now, hpFraction, targetDist, roll) {
        const out = [];
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
                if (now < this.globalReadyAt)
                    break;
                const choice = weightedPick(this.eligible(now, targetDist), (a) => a.weight, roll());
                if (choice)
                    out.push(...this.beginTelegraph(choice, now));
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
    serialize() {
        return JSON.stringify({ p: this.phase, r: this.readyAt });
    }
    restore(json, now) {
        if (!json)
            return;
        try {
            const d = JSON.parse(json);
            if (typeof d.p === "number" && d.p >= 1 && d.p <= 3)
                this.phase = d.p;
            // cooldowns are relative to the old session's tick counter; reset them relative to now
            if (d.r)
                for (const k of Object.keys(d.r))
                    this.readyAt[k] = now + 40;
        }
        catch {
            /* corrupt data: keep defaults */
        }
    }
}
