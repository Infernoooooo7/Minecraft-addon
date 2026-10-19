// Pure vector math (no @minecraft imports so it can be unit tested in Node).
export const v3 = (x, y, z) => ({ x, y, z });
export const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export const scale = (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s });
export const len = (a) => Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
export const dist = (a, b) => len(sub(a, b));
export const distXZ = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
export const flat = (a) => ({ x: a.x, y: 0, z: a.z });
export function norm(a) {
    const l = len(a);
    return l < 1e-6 ? { x: 0, y: 0, z: 0 } : scale(a, 1 / l);
}
export function dirTo(from, to, flatten = false) {
    const d = sub(to, from);
    return norm(flatten ? flat(d) : d);
}
export const lerp = (a, b, t) => add(a, scale(sub(b, a), t));
/** Rotate a vector around the Y axis by `deg` degrees. */
export function rotY(a, deg) {
    const r = (deg * Math.PI) / 180;
    const c = Math.cos(r);
    const s = Math.sin(r);
    return { x: a.x * c - a.z * s, y: a.y, z: a.x * s + a.z * c };
}
/** Shortest distance from point p to segment ab. */
export function distToSegment(p, a, b) {
    const ab = sub(b, a);
    const l2 = ab.x * ab.x + ab.y * ab.y + ab.z * ab.z;
    if (l2 < 1e-9)
        return dist(p, a);
    let t = ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y + (p.z - a.z) * ab.z) / l2;
    t = Math.max(0, Math.min(1, t));
    return dist(p, add(a, scale(ab, t)));
}
/** Point on a horizontal ring around `c` at angle `deg` and radius `r`. */
export function ringPoint(c, r, deg) {
    const a = (deg * Math.PI) / 180;
    return { x: c.x + Math.cos(a) * r, y: c.y, z: c.z + Math.sin(a) * r };
}
export const fmt = (a) => `${a.x.toFixed(1)}, ${a.y.toFixed(1)}, ${a.z.toFixed(1)}`;
