// Save/reload simulation: the world is loaded with state persisted by a previous session (an active
// Blood Moon, a Hollow King in phase II, a returning player) and must resume it correctly.
import { register } from "node:module";
register("./mock/hooks.mjs", import.meta.url);

import assert from "node:assert/strict";
import { describe, it } from "node:test";

const M = await import("./mock/server.mjs");
const errors = [];
console.error = (...a) => errors.push(a.join(" "));
console.warn = () => {};
console.log = () => {};

const OW = "minecraft:overworld";
// --- state written by the "previous session" ------------------------------------------------------
M.mock.worldDP.set("apocalypse:event_state", JSON.stringify({
  active: "blood_moon", startTick: 1000, endTick: 5000, cooldownUntil: 0, lastEnd: { eclipse: 200 }, completed: 4,
}));
M.mock.worldDP.set("apocalypse:event_saved_at", 3000);
M.mock.worldDP.set("apocalypse:ledger", JSON.stringify(["-12884901895"]));
M.mock.worldDP.set("apocalypse:config", JSON.stringify({ profile: "potato", eventIntensity: "mild" }));
M.setDay(12);
M.setTime(15000);
const P = M.addPlayer("Alex", { x: 0.5, y: 64, z: 0.5 });
P._dp.set("apocalypse:welcomed", true);
P._dp.set("apocalypse:journal", JSON.stringify({ v: 1, kills: { hollow_king: 1 }, firstKillDay: { hollow_king: 3 }, events: {}, discovered: [], expanseVisits: 0 }));
P._fogs = [{ id: "apocalypse:fog_eclipse", user: "apocalypse_event" }]; // stale fog left on the client
const boss = new M.Entity(M.mock.dims.get(OW), "apocalypse:hollow_king", { x: 0.5, y: 64, z: 10.5 });
boss._dp.set("apocalypse:machine", JSON.stringify({ p: 2, r: { phantom_step: 999999 } }));
boss._dp.set("apocalypse:arena", JSON.stringify({ x: 0.5, y: 64, z: 10.5 }));
boss._hp = boss._maxHp * 0.5;

await import("../behavior_pack/scripts/main.js");
M.boot();

const run = async (n, f) => {
  for (let i = 0; i < n; i++) {
    await M.run(1);
    f?.();
  }
};
const wdp = (k) => JSON.parse(M.mock.worldDP.get(k) ?? "null");
const clean = () => assert.deepEqual({ p: M.mock.problems, u: M.mock.uncaught, e: errors }, { p: [], u: [], e: [] });

describe("save/reload persistence", { concurrency: false }, () => {
  it("resumes the active event with its remaining time and fixes stale fog", async () => {
    await run(40);
    const st = wdp("apocalypse:event_state");
    assert.equal(st.active, "blood_moon");
    const remaining = st.endTick - M.mock.tick;
    assert.ok(remaining > 1900 && remaining <= 2000, `remaining ${remaining} ticks`);
    assert.ok(st.lastEnd.eclipse < 0, "per-event cooldowns rebased onto the new clock");
    assert.deepEqual(P._fogs.map((f) => f.id), ["apocalypse:fog_blood_moon"], "stale fog replaced by the active event's fog");
    assert.equal(P.inventory.count("apocalypse:engine_codex"), 0, "returning players are not re-welcomed");
    assert.equal(wdp("apocalypse:config")?.profile ?? "potato", "potato");
    clean();
  });

  it("restores the boss brain mid-fight without replaying the intro", async () => {
    assert.equal(boss._props.get("apocalypse:phase"), 2, "phase II restored from the saved machine");
    assert.ok(!P.titles.some((t) => /HOLLOW KING/.test(t.title)), "no spawn intro on reload");
    let acted = false;
    await run(400, () => {
      acted ||= boss._props.get("apocalypse:action") > 0;
      P._hp = P._maxHp;
    });
    assert.ok(acted, "restored boss keeps fighting");
    clean();
  });

  it("ends the resumed event on schedule and records it", async () => {
    await run(1700, () => {
      P._hp = P._maxHp;
    });
    const st = wdp("apocalypse:event_state");
    assert.equal(st.active, null, "event ended after its remaining duration");
    assert.equal(st.completed, 5);
    assert.equal(JSON.parse(P._dp.get("apocalypse:journal")).events.blood_moon, 1);
    assert.deepEqual(P._fogs, [], "event fog cleared");
    clean();
  });

  it("pays a reloaded boss exactly once and keeps the ledger bounded", async () => {
    M.attack(P, boss, 1e9);
    await run(30);
    const j = JSON.parse(P._dp.get("apocalypse:journal"));
    assert.equal(j.kills.hollow_king, 2, "kill recorded (not a first kill: no duplicate first rewards)");
    assert.equal(P.inventory.count("apocalypse:hollow_crown_shard"), 0, "first-kill reward not paid twice");
    const ledger = wdp("apocalypse:ledger");
    assert.ok(ledger.includes(boss.id) && ledger.includes("-12884901895"));
    clean();
  });
});
