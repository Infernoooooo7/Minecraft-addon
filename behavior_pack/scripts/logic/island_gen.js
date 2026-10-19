// Deterministic floating-island layout for the Shattered Expanse custom dimension.
// Pure and unit tested: the same seed always produces the same islands.
import { hash2, Rng } from "./rng.js";
export const CELL = 64;
export const WORLD_RADIUS = 640;
export const NEXUS = { key: "nexus", cx: 0, cy: 96, cz: 0, r: 15, height: 2, depth: 14, seed: 11, flat: true };
export const ARENA = { key: "arena", cx: 0, cy: 92, cz: -120, r: 26, height: 1, depth: 18, seed: 23, flat: true };
/** Minimum radius factor of a flat island's wobbly edge (see `columns`). */
export const EDGE_MIN = 0.82;
export const BRIDGE_COUNT = 26;
export const BRIDGE_R = 3.5;
/**
 * A continuous, gently winding causeway of small overlapping islands from the Nexus to the Colossus
 * Arena: consecutive pieces always overlap, so the Arena is reachable on foot without building.
 */
export function bridgeIslands() {
    const out = [];
    for (let i = 1; i <= BRIDGE_COUNT; i++) {
        const t = i / (BRIDGE_COUNT + 1);
        const z = NEXUS.cz + (ARENA.cz - NEXUS.cz) * t;
        const x = Math.round(Math.sin(i * 0.35) * 3);
        const y = Math.round(NEXUS.cy + (ARENA.cy - NEXUS.cy) * t);
        out.push({ key: `bridge_${i}`, cx: x, cy: y, cz: Math.round(z), r: BRIDGE_R, height: 1, depth: 3, seed: 100 + i, flat: true });
    }
    return out;
}
export const cellKey = (cx, cz) => `${cx},${cz}`;
/** Islands in procedural cells avoid the reserved corridor between Nexus and Arena. */
export function islandForCell(cx, cz, worldSeed) {
    const h = hash2(cx, cz, worldSeed);
    const rng = new Rng(h);
    if (!rng.chance(0.72))
        return null;
    const x = cx * CELL + rng.int(10, CELL - 10);
    const z = cz * CELL + rng.int(10, CELL - 10);
    if (Math.hypot(x, z) > WORLD_RADIUS)
        return null;
    // keep the Nexus, Arena and bridge corridor clear
    if (Math.abs(x) < 40 && z < 40 && z > ARENA.cz - 50)
        return null;
    const r = rng.int(6, 17);
    return {
        key: cellKey(cx, cz), cx: x, cy: rng.int(72, 128), cz: z, r, height: rng.int(2, 6),
        depth: Math.round(r * rng.range(0.9, 1.6)), seed: h, flat: false,
    };
}
export function cellsNear(x, z, radius) {
    const out = [];
    const c0x = Math.floor((x - radius) / CELL);
    const c1x = Math.floor((x + radius) / CELL);
    const c0z = Math.floor((z - radius) / CELL);
    const c1z = Math.floor((z + radius) / CELL);
    for (let cx = c0x; cx <= c1x; cx++)
        for (let cz = c0z; cz <= c1z; cz++)
            out.push([cx, cz]);
    return out;
}
/** Smooth pseudo-noise in [0,1] from the island seed (cheap, deterministic). */
function wobble(seed, x, z) {
    const a = Math.sin((x * 0.31 + seed * 0.001) * 1.7) * Math.cos((z * 0.27 - seed * 0.002) * 1.3);
    const b = Math.sin((x * 0.11 + z * 0.13) + seed * 0.0007);
    return (a * 0.6 + b * 0.4) * 0.5 + 0.5;
}
/** Column spans (top/bottom Y) of an island, deterministic. */
export function columns(isl) {
    const out = [];
    const R = isl.r;
    const B = Math.ceil(R); // integer loop bound keeps columns on whole blocks for fractional radii
    const rng = new Rng(isl.seed ^ 0x5bd1e995);
    for (let dx = -B; dx <= B; dx++) {
        for (let dz = -B; dz <= B; dz++) {
            const d = Math.hypot(dx, dz);
            const edge = R * (EDGE_MIN + (1 - EDGE_MIN) * wobble(isl.seed, dx, dz));
            if (d > edge)
                continue;
            const t = d / edge;
            const w = wobble(isl.seed + 7, dx, dz);
            const top = isl.flat ? isl.cy : isl.cy + Math.round((1 - t * t) * isl.height * (0.6 + 0.4 * w));
            const under = Math.pow(1 - t, 0.75) * isl.depth * (0.55 + 0.45 * wobble(isl.seed + 13, dx, dz));
            const bottom = Math.min(top - 1, isl.cy - Math.max(1, Math.round(under)));
            let deco = "none";
            if (!isl.flat) {
                const roll = rng.next();
                if (roll < 0.025)
                    deco = "cluster";
                else if (roll < 0.032)
                    deco = "crystal";
            }
            out.push({ x: isl.cx + dx, z: isl.cz + dz, top, bottom, deco });
        }
    }
    return out;
}
