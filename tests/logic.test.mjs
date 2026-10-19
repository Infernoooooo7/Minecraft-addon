// Unit tests for the pure gameplay logic shipped in the behavior pack (compiled JS, no Minecraft runtime).
// Run: node --test tests/
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BossMachine, computePhase, perPhase } from "../behavior_pack/scripts/logic/boss_machine.js";
import {
  eligible, end, GLOBAL_COOLDOWN_TICKS, isNight, newState, parseState, pick, rebase, rollChance, shouldEnd, start,
  windowOk,
} from "../behavior_pack/scripts/logic/event_scheduler.js";
import { Contributions, RewardLedger } from "../behavior_pack/scripts/logic/reward_ledger.js";
import {
  bossesDefeated, canForgeEngineKey, completion, discover, newJournal, nextObjective, parseJournal, recordBossKill,
  recordEvent,
} from "../behavior_pack/scripts/logic/progression.js";
import { getProfile, PROFILES, scaledCount } from "../behavior_pack/scripts/logic/profiles.js";
import {
  ARENA, BRIDGE_COUNT, bridgeIslands, CELL, cellsNear, columns, EDGE_MIN, islandForCell, NEXUS, WORLD_RADIUS,
} from "../behavior_pack/scripts/logic/island_gen.js";
import { hash2, Rng, weightedPick } from "../behavior_pack/scripts/logic/rng.js";
import { dirTo, distToSegment, ringPoint, rotY } from "../behavior_pack/scripts/logic/vec.js";

const attack = (id, extra = {}) => ({
  id, phases: [1, 2, 3], minRange: 0, maxRange: 20, cooldown: 5, windup: 1, recover: 1, weight: 1, ...extra,
});
const cfg = (attacks, extra = {}) => ({ phaseThresholds: [0.66, 0.33], globalCooldown: 1, transitionTime: 2, attacks, ...extra });

/** Drive a machine tick by tick and collect events. */
function run(m, from, to, hp, dist, roll = () => 0) {
  const events = [];
  for (let t = from; t <= to; t++) for (const e of m.update(t, hp, dist, roll)) events.push({ t, ...e });
  return events;
}

describe("boss state machine", () => {
  it("computes phases from health thresholds", () => {
    assert.equal(computePhase(1, [0.66, 0.33]), 1);
    assert.equal(computePhase(0.66, [0.66, 0.33]), 2);
    assert.equal(computePhase(0.5, [0.66, 0.33]), 2);
    assert.equal(computePhase(0.2, [0.66, 0.33]), 3);
    assert.equal(computePhase(0, [0.66, 0.33]), 3);
  });

  it("perPhase indexes arrays and clamps", () => {
    assert.equal(perPhase(4, 3), 4);
    assert.equal(perPhase([3, 2, 1], 1), 3);
    assert.equal(perPhase([3, 2, 1], 3), 1);
    assert.equal(perPhase([3, 2], 3), 2);
  });

  it("waits for the intro delay, then telegraphs -> executes -> recovers", () => {
    const m = new BossMachine(cfg([attack("slam")]), 0, 2);
    const ev = run(m, 0, 200, 1, 5);
    const first = ev.find((e) => e.type === "telegraph");
    assert.ok(first, "an attack was telegraphed");
    assert.equal(first.t, 40, "intro delay of 2 s respected");
    const exec = ev.find((e) => e.type === "execute");
    assert.equal(exec.t, 60, "1 s windup");
    const rec = ev.find((e) => e.type === "recovered");
    assert.equal(rec.t, 80, "1 s recovery");
    // cooldown of 5 s from execution (t=60) -> next telegraph no earlier than 160
    const second = ev.filter((e) => e.type === "telegraph")[1];
    assert.ok(second.t >= 160, `cooldown respected (second at ${second.t})`);
  });

  it("respects range limits and target requirements", () => {
    const m = new BossMachine(cfg([attack("melee", { maxRange: 4 }), attack("summon", { needsTarget: false })]), 0, 0);
    assert.deepEqual(m.eligible(0, 10).map((a) => a.id), ["summon"]);
    assert.deepEqual(m.eligible(0, 2).map((a) => a.id).sort(), ["melee", "summon"]);
    assert.deepEqual(m.eligible(0, null).map((a) => a.id), ["summon"]);
  });

  it("gates attacks by phase", () => {
    const m = new BossMachine(cfg([attack("p1", { phases: [1] }), attack("p3", { phases: [3] })]), 0, 0);
    assert.deepEqual(m.eligible(0, 5).map((a) => a.id), ["p1"]);
    m.phase = 3;
    assert.deepEqual(m.eligible(0, 5).map((a) => a.id), ["p3"]);
  });

  it("enters an invulnerable transition when a threshold is crossed and never regresses", () => {
    const m = new BossMachine(cfg([attack("a")]), 0, 0);
    const ev = m.update(10, 0.5, 5, () => 0);
    assert.deepEqual(ev[0], { type: "phase", from: 1, to: 2 });
    assert.equal(m.invulnerable, true);
    assert.equal(m.update(20, 0.5, 5, () => 0).length, 0, "no attacks during transition");
    const endEv = run(m, 21, 60, 0.5, 5);
    assert.ok(endEv.some((e) => e.type === "transition_end"));
    assert.equal(m.invulnerable, false);
    // healing back above the threshold does not return to phase 1
    run(m, 61, 100, 0.9, 5);
    assert.equal(m.phase, 2);
  });

  it("interrupts a telegraphed attack on phase change", () => {
    const m = new BossMachine(cfg([attack("a", { windup: 3 })]), 0, 0);
    m.update(0, 1, 5, () => 0);
    assert.equal(m.state, "telegraph");
    m.update(5, 0.2, 5, () => 0);
    assert.equal(m.state, "transition");
    assert.equal(m.attack, null);
    assert.equal(m.phase, 3);
  });

  it("force() starts a scripted attack but never during a transition", () => {
    const m = new BossMachine(cfg([attack("nova", { phases: [3] })]), 0, 10);
    assert.equal(m.force("nova", 0)[0].type, "telegraph");
    const m2 = new BossMachine(cfg([attack("nova")]), 0, 0);
    m2.update(0, 0.5, 5, () => 0);
    assert.deepEqual(m2.force("nova", 1), []);
    assert.deepEqual(m2.force("missing", 1), []);
  });

  it("serializes phase and restores cooldowns relative to the new clock", () => {
    const m = new BossMachine(cfg([attack("a")]), 0, 0);
    m.phase = 2;
    m.readyAt.a = 99999;
    const m2 = new BossMachine(cfg([attack("a")]), 0, 0);
    m2.restore(m.serialize(), 500);
    assert.equal(m2.phase, 2);
    assert.equal(m2.readyAt.a, 540);
    m2.restore("{corrupt", 600);
    assert.equal(m2.phase, 2, "corrupt data ignored");
  });
});

describe("event scheduler", () => {
  const meta = (id, extra = {}) => ({
    id, name: id, window: "any", minTicks: 100, maxTicks: 200, cooldownTicks: 1000, weight: 1, minDay: 0, ...extra,
  });

  it("classifies night and windows", () => {
    assert.equal(isNight(13000), true);
    assert.equal(isNight(22999), true);
    assert.equal(isNight(23000), false);
    assert.equal(isNight(6000), false);
    assert.equal(isNight(-11000), true, "negative times wrap");
    assert.equal(windowOk("day", 6000), true);
    assert.equal(windowOk("night", 6000), false);
    assert.equal(windowOk("any", 18000), true);
  });

  it("roll chance scales with frequency and is 0 when off", () => {
    assert.equal(rollChance("off"), 0);
    assert.ok(rollChance("rare") < rollChance("normal"));
    assert.ok(rollChance("normal") < rollChance("frequent"));
    assert.ok(rollChance("frequent") <= 1);
  });

  it("filters by active event, cooldowns, minimum day, window and config", () => {
    const metas = [meta("a"), meta("b", { minDay: 5 }), meta("c", { window: "night" }), meta("d")];
    const s = newState();
    assert.deepEqual(eligible(metas, s, 0, 6000, 0, {}).map((m) => m.id), ["a", "d"]);
    assert.deepEqual(eligible(metas, s, 0, 18000, 9, { d: false }).map((m) => m.id), ["a", "b", "c"]);
    const active = { ...s, active: "a" };
    assert.deepEqual(eligible(metas, active, 0, 6000, 9, {}), []);
    const cooling = { ...s, cooldownUntil: 500 };
    assert.deepEqual(eligible(metas, cooling, 100, 6000, 9, {}), []);
    const perEvent = { ...s, lastEnd: { a: 0 } };
    assert.ok(!eligible(metas, perEvent, 500, 6000, 9, {}).some((m) => m.id === "a"));
    assert.ok(eligible(metas, perEvent, 1000, 6000, 9, {}).some((m) => m.id === "a"));
  });

  it("start/end lifecycle applies durations and the global cooldown", () => {
    const rng = new Rng(7);
    let s = start(newState(), meta("a"), 1000, rng);
    assert.equal(s.active, "a");
    assert.ok(s.endTick - s.startTick >= 100 && s.endTick - s.startTick <= 200);
    assert.equal(shouldEnd(s, meta("a"), 1050, 6000), false);
    assert.equal(shouldEnd(s, meta("a"), s.endTick, 6000), true);
    s = end(s, 1300);
    assert.equal(s.active, null);
    assert.equal(s.cooldownUntil, 1300 + GLOBAL_COOLDOWN_TICKS);
    assert.equal(s.lastEnd.a, 1300);
    assert.equal(s.completed, 1);
    assert.deepEqual(end(s, 2000), s, "ending twice is a no-op");
  });

  it("night events end at dawn after a grace period", () => {
    const night = meta("n", { window: "night", maxTicks: 100000, minTicks: 100000 });
    const s = start(newState(), night, 0, new Rng(1));
    assert.equal(shouldEnd(s, night, 100, 6000), false, "grace period");
    assert.equal(shouldEnd(s, night, 300, 6000), true, "daylight ends a night event");
    assert.equal(shouldEnd(s, night, 300, 18000), false);
    assert.equal(shouldEnd(s, undefined, 300, 18000), true, "unknown event ends");
  });

  it("parses persisted state defensively and rebases ticks across sessions", () => {
    assert.deepEqual(parseState(undefined), newState());
    assert.deepEqual(parseState("not json"), newState());
    const s = parseState(JSON.stringify({ active: "a", startTick: 900, endTick: 1500, cooldownUntil: 0, lastEnd: { b: 100 }, completed: 3 }));
    assert.equal(s.active, "a");
    const r = rebase(s, 1000, 20);
    assert.equal(r.endTick - 20, 1500 - 1000, "remaining duration kept");
    assert.equal(r.lastEnd.b, 100 - 980);
    assert.equal(r.completed, 3);
  });

  it("weighted pick honours weights", () => {
    const metas = [meta("rare", { weight: 1 }), meta("common", { weight: 9 })];
    const rng = new Rng(42);
    const counts = { rare: 0, common: 0 };
    for (let i = 0; i < 5000; i++) counts[pick(metas, rng).id]++;
    assert.ok(counts.common > counts.rare * 5, JSON.stringify(counts));
    assert.equal(pick([], rng), undefined);
  });
});

describe("reward ledger", () => {
  it("claims each id exactly once, across serialization", () => {
    const l = new RewardLedger();
    assert.equal(l.claim("boss1"), true);
    assert.equal(l.claim("boss1"), false);
    const l2 = RewardLedger.parse(l.serialize());
    assert.equal(l2.claim("boss1"), false, "duplicate after reload is rejected");
    assert.equal(l2.claim("boss2"), true);
    assert.equal(l2.claim(""), false);
  });

  it("is bounded", () => {
    const l = new RewardLedger([], 4);
    for (let i = 0; i < 10; i++) l.claim(`id${i}`);
    assert.equal(l.size, 4);
    assert.equal(l.has("id9"), true);
    assert.equal(l.has("id0"), false);
    assert.equal(RewardLedger.parse("garbage").size, 0);
    assert.equal(RewardLedger.parse(JSON.stringify([1, "x", null])).size, 1);
  });

  it("contributions include significant damage dealers and the top dealer", () => {
    const c = new Contributions();
    c.add("a", 900);
    c.add("b", 80);
    c.add("c", 20);
    c.add("d", -50);
    assert.deepEqual(c.eligible(0.05), ["a", "b"]);
    assert.equal(c.total(), 1000);
    const solo = new Contributions();
    solo.add("x", 1);
    assert.deepEqual(solo.eligible(0.5), ["x"]);
    assert.deepEqual(new Contributions().eligible(), []);
  });
});

describe("progression", () => {
  it("records first kills once and gates the Engine Key on the three overworld bosses", () => {
    const j = newJournal();
    assert.equal(recordBossKill(j, "hollow_king", 3).first, true);
    assert.equal(recordBossKill(j, "hollow_king", 4).first, false);
    assert.equal(j.kills.hollow_king, 2);
    assert.equal(j.firstKillDay.hollow_king, 3);
    assert.equal(canForgeEngineKey(j), false);
    recordBossKill(j, "star_eater", 5);
    recordBossKill(j, "root_titan", 6);
    assert.equal(canForgeEngineKey(j), true);
    assert.equal(bossesDefeated(j), 3);
  });

  it("guides the player through the progression in order", () => {
    const j = newJournal();
    assert.match(nextObjective(j), /Rift Ore/);
    discover(j, "apocalypse:rift_shard");
    assert.match(nextObjective(j), /Cursed Crown/);
    recordBossKill(j, "hollow_king", 1);
    assert.match(nextObjective(j), /Astral Lure/);
    recordBossKill(j, "star_eater", 1);
    assert.match(nextObjective(j), /Heartseed/);
    recordBossKill(j, "root_titan", 1);
    assert.match(nextObjective(j), /Engine Key/);
    j.expanseVisits = 1;
    assert.match(nextObjective(j), /Null Gate/);
    recordBossKill(j, "null_colossus", 1);
    assert.match(nextObjective(j), /restored/);
  });

  it("completion is bounded and monotonic", () => {
    const j = newJournal();
    const c0 = completion(j);
    recordEvent(j, "blood_moon");
    discover(j, "x");
    assert.ok(completion(j) > c0);
    for (const b of ["hollow_king", "star_eater", "root_titan", "null_colossus"]) recordBossKill(j, b, 1);
    for (let i = 0; i < 10; i++) recordEvent(j, `e${i}`);
    for (let i = 0; i < 40; i++) discover(j, `d${i}`);
    assert.equal(completion(j), 1);
    assert.equal(discover(j, "d1"), false, "discoveries are unique");
  });

  it("parses journals defensively", () => {
    assert.deepEqual(parseJournal(undefined), newJournal());
    assert.deepEqual(parseJournal("{oops"), newJournal());
    const j = parseJournal(JSON.stringify({ kills: { a: 1 }, discovered: ["x", 5, "y"], expanseVisits: 2 }));
    assert.deepEqual(j.discovered, ["x", "y"]);
    assert.equal(j.kills.a, 1);
    assert.equal(j.expanseVisits, 2);
  });
});

describe("performance profiles", () => {
  const order = ["potato", "balanced", "enhanced"];
  const keysUp = ["particles", "eventMobsPerPlayer", "eventMobsGlobal", "bossAdds", "meteorsPerWave", "genColumnsPerTick", "sentinelsPerPlayer"];

  it("are monotonic from potato to enhanced", () => {
    for (const k of keysUp) {
      for (let i = 1; i < order.length; i++) {
        assert.ok(PROFILES[order[i]][k] >= PROFILES[order[i - 1]][k], `${k} grows ${order[i - 1]} -> ${order[i]}`);
      }
    }
    for (let i = 1; i < order.length; i++) {
      assert.ok(PROFILES[order[i]].ambientInterval <= PROFILES[order[i - 1]].ambientInterval, "ambient interval shrinks");
      assert.ok(PROFILES[order[i]].bossTickInterval <= PROFILES[order[i - 1]].bossTickInterval);
    }
  });

  it("falls back to balanced and scales counts with a floor", () => {
    assert.equal(getProfile("nope").id, "balanced");
    assert.equal(getProfile(undefined).id, "balanced");
    assert.equal(scaledCount(4, 0.35), 1);
    assert.equal(scaledCount(4, 1.6), 6);
    assert.equal(scaledCount(1, 0.1, 0), 0);
  });
});

describe("island generation", () => {
  it("is deterministic per seed and cell", () => {
    const a = islandForCell(3, -2, 12345);
    const b = islandForCell(3, -2, 12345);
    assert.deepEqual(a, b);
    let differs = false;
    for (let i = 0; i < 20 && !differs; i++) differs = JSON.stringify(islandForCell(i, 1, 1)) !== JSON.stringify(islandForCell(i, 1, 2));
    assert.ok(differs, "seed changes the layout");
  });

  it("keeps islands inside the world radius and out of the Nexus-Arena corridor", () => {
    let n = 0;
    for (let cx = -12; cx <= 12; cx++) {
      for (let cz = -12; cz <= 12; cz++) {
        const isl = islandForCell(cx, cz, 999);
        if (!isl) continue;
        n++;
        assert.ok(Math.hypot(isl.cx, isl.cz) <= WORLD_RADIUS);
        assert.ok(!(Math.abs(isl.cx) < 40 && isl.cz < 40 && isl.cz > ARENA.cz - 50), `corridor clear: ${isl.cx},${isl.cz}`);
        assert.ok(isl.cx >= cx * CELL && isl.cx < (cx + 1) * CELL);
      }
    }
    assert.ok(n > 100, `plenty of islands (${n})`);
  });

  it("produces solid, bounded columns", () => {
    for (const isl of [NEXUS, ARENA, ...bridgeIslands(), islandForCell(5, 5, 7) ?? NEXUS]) {
      const cols = columns(isl);
      assert.ok(cols.length > 0, isl.key);
      const seen = new Set();
      for (const c of cols) {
        assert.ok(c.bottom < c.top, `${isl.key} column has thickness`);
        assert.ok(Math.hypot(c.x - isl.cx, c.z - isl.cz) <= isl.r + 0.01);
        const k = `${c.x},${c.z}`;
        assert.ok(!seen.has(k), "no duplicate columns");
        seen.add(k);
      }
      if (isl.flat) assert.ok(cols.every((c) => c.top === isl.cy), `${isl.key} is flat`);
    }
  });

  it("the causeway from the Nexus to the Arena is continuous (walkable without building)", () => {
    const b = bridgeIslands();
    assert.equal(b.length, BRIDGE_COUNT);
    const overlaps = (a, c) => Math.hypot(a.cx - c.cx, a.cz - c.cz) < EDGE_MIN * a.r + EDGE_MIN * c.r;
    assert.ok(overlaps(NEXUS, b[0]), "first piece touches the Nexus");
    assert.ok(overlaps(b[b.length - 1], ARENA), "last piece touches the Arena");
    for (let i = 1; i < b.length; i++) {
      assert.ok(b[i].cz < b[i - 1].cz, "heads north");
      assert.ok(overlaps(b[i - 1], b[i]), `pieces ${i} and ${i + 1} overlap`);
      assert.ok(Math.abs(b[i].cy - b[i - 1].cy) <= 1, "height steps are walkable");
    }
  });

  it("cellsNear covers the query square", () => {
    const cells = cellsNear(0, 0, 96);
    assert.equal(cells.length, 16);
    assert.ok(cells.some(([x, z]) => x === -2 && z === -2) && cells.some(([x, z]) => x === 1 && z === 1));
  });
});

describe("rng and vectors", () => {
  it("Rng is deterministic and in range", () => {
    const a = new Rng(5);
    const b = new Rng(5);
    for (let i = 0; i < 100; i++) {
      const x = a.next();
      assert.equal(x, b.next());
      assert.ok(x >= 0 && x < 1);
    }
    const r = new Rng(9);
    for (let i = 0; i < 500; i++) {
      const v = r.int(2, 4);
      assert.ok(v >= 2 && v <= 4 && Number.isInteger(v));
    }
    assert.equal(new Rng(1).pick([]), undefined);
  });

  it("weightedPick ignores non-positive weights", () => {
    const items = [{ w: 0 }, { w: -1 }, { w: 2 }];
    for (const roll of [0, 0.5, 0.999]) assert.equal(weightedPick(items, (i) => i.w, roll), items[2]);
    assert.equal(weightedPick([{ w: 0 }], (i) => i.w, 0.5), undefined);
  });

  it("hash2 is stable and spreads values", () => {
    assert.equal(hash2(1, 2, 3), hash2(1, 2, 3));
    assert.notEqual(hash2(1, 2, 3), hash2(2, 1, 3));
  });

  it("vector helpers", () => {
    const d = dirTo({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 0 });
    assert.ok(Math.abs(d.x - 0.6) < 1e-9 && Math.abs(d.y - 0.8) < 1e-9);
    const flat = dirTo({ x: 0, y: 0, z: 0 }, { x: 0, y: 5, z: 2 }, true);
    assert.equal(flat.y, 0);
    const r = rotY({ x: 1, y: 0, z: 0 }, 90);
    assert.ok(Math.abs(r.x) < 1e-9 && Math.abs(r.z - 1) < 1e-9);
    assert.equal(distToSegment({ x: 0, y: 1, z: 0 }, { x: -1, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }), 1);
    const p = ringPoint({ x: 0, y: 5, z: 0 }, 2, 0);
    assert.deepEqual(p, { x: 2, y: 5, z: 0 });
  });
});
