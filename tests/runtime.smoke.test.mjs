// End-to-end runtime simulation of the compiled behavior-pack scripts on the strict mock runtime
// (tests/mock). This is not in-game testing: it exercises the real script code paths (startup, world
// load, every world event, every boss fight, abilities, relics, armor, ores, the Shattered Expanse,
// the Codex UI and commands) and fails on any API misuse the mock can detect. Run: node --test tests/
import { register } from "node:module";
register("./mock/hooks.mjs", import.meta.url);

import assert from "node:assert/strict";
import fs from "node:fs";
import { describe, it } from "node:test";

const M = await import("./mock/server.mjs");
const { ui } = await import("./mock/server-ui.mjs");
const {
  ARENA, NEXUS, bridgeIslands,
} = await import("../behavior_pack/scripts/logic/islandGen.js");

// determinism: seeded Math.random, and a fixed clock while the add-on seeds its own RNGs at import
let seed = 0x2f6b9a1d;
Math.random = () => {
  seed = (seed + 0x6d2b79f5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const realNow = Date.now;

const errors = [];
const warnings = [];
console.error = (...a) => errors.push(a.join(" "));
console.warn = (...a) => warnings.push(a.join(" "));
console.log = () => {};

const OW = "minecraft:overworld";
const EXPANSE = "apocalypse:shattered_expanse";
const P1 = M.addPlayer("Alex", { x: 0.5, y: 64, z: 0.5 });
const P2 = M.addPlayer("Sam", { x: 6.5, y: 64, z: 2.5 });
const stats = { ticks: 0, started: realNow() };

Date.now = () => 1767225600000;
await import("../behavior_pack/scripts/main.js");
Date.now = realNow;
M.boot();

async function run(n, watch) {
  for (let i = 0; i < n; i++) {
    await M.run(1);
    stats.ticks++;
    watch?.();
  }
}

function clean(label) {
  const report = { problems: M.mock.problems, uncaught: M.mock.uncaught, errors };
  assert.deepEqual(report, { problems: [], uncaught: [], errors: [] }, `${label}: ${JSON.stringify(report, null, 1)}`);
}

const wdp = (k) => JSON.parse(M.mock.worldDP.get(k) ?? "null");
const pdp = (p, k) => JSON.parse(p._dp.get(k) ?? "null");
const live = (typeId) => M.entitiesOf(typeId);
const eventMobs = () => [...M.mock.entities.values()].filter((e) => e._valid && e._tags.has("apocalypse:event_mob"));
const ow = () => M.mock.dims.get(OW);
const exp = () => M.mock.dims.get(EXPANSE);
const blocksOf = (dim, id) => [...dim.blocks].filter(([, v]) => v === id).map(([k]) => k.split(",").map(Number));
const heal = (...ps) => ps.forEach((p) => {
  p._hp = p._maxHp;
  p._dead = false;
  p._effects.clear();
});
const give = (p, id, n = 1) => p.inventory.addItem(new M.ItemStack(id, n));
const hold = (p, id) => {
  p.inventory.slots[p.selectedSlotIndex] = new M.ItemStack(id, 1);
};
const count = (p, id) => p.inventory.count(id);
const killAllBosses = async () => {
  for (const id of ["apocalypse:hollow_king", "apocalypse:star_eater", "apocalypse:root_titan", "apocalypse:null_colossus"]) {
    for (const b of live(id)) M.attack(P1, b, 1e9);
  }
  await run(25);
};

describe("APOCALYPSE ENGINE runtime simulation", { concurrency: false }, () => {
  it("boots: registrations, custom dimension, welcome kit", async () => {
    await run(60);
    clean("boot");
    assert.deepEqual([...M.mock.commands.keys()].sort(), ["apocalypse:codex", "apocalypse:event", "apocalypse:profile", "apocalypse:summon"]);
    assert.ok(M.mock.customDims.has(EXPANSE), "Shattered Expanse registered via DimensionRegistry");
    assert.equal(count(P1, "apocalypse:engine_codex"), 1);
    assert.equal(count(P2, "apocalypse:engine_codex"), 1);
    assert.equal(P1._dp.get("apocalypse:welcomed"), true);
    // a late joiner is welcomed once
    const P3 = M.addPlayer("Kai", { x: -4.5, y: 64, z: -3.5 });
    M.join(P3);
    await run(60);
    assert.equal(count(P3, "apocalypse:engine_codex"), 1);
    M.join(P3);
    await run(60);
    assert.equal(count(P3, "apocalypse:engine_codex"), 1, "no duplicate codex on re-spawn");
    P3._despawn();
    await run(2);
    clean("join");
  });

  // ------------------------------------------------------------------------------------------------
  // world events
  // ------------------------------------------------------------------------------------------------
  const EVENTS = {
    blood_moon: { time: 18000, fog: "apocalypse:fog_blood_moon" },
    void_storm: { time: 6000, fog: "apocalypse:fog_void_storm" },
    meteor_shower: { time: 18000, fog: null },
    reality_fracture: { time: 6000, fog: "apocalypse:fog_fracture" },
    eclipse: { time: 6000, fog: "apocalypse:fog_eclipse" },
    ancient_awakening: { time: 6000, fog: "apocalypse:fog_awakening" },
    corruption_surge: { time: 6000, fog: "apocalypse:fog_blight" },
  };

  for (const [id, spec] of Object.entries(EVENTS)) {
    it(`world event: ${id}`, async () => {
      M.setDay(10);
      M.setTime(spec.time);
      heal(P1, P2);
      const seen = { effects: new Set(), maxMobs: 0 };
      const res = M.command(P1, "apocalypse:event", "start", id);
      assert.equal(res.status, M.CustomCommandStatus.Success, JSON.stringify(res));
      await run(1200, () => {
        for (const p of [P1, P2]) for (const e of p.getEffects()) seen.effects.add(e.typeId);
        seen.maxMobs = Math.max(seen.maxMobs, eventMobs().length);
      });
      const st = wdp("apocalypse:event_state");
      assert.equal(st.active, id, "event active and persisted");
      if (spec.fog) assert.ok(P1._fogs?.some((f) => f.id === spec.fog && f.user === "apocalypse_event"), `fog ${spec.fog} pushed`);
      assert.ok(seen.maxMobs <= 18, `global event-mob cap respected (${seen.maxMobs})`);

      if (id === "blood_moon") {
        const shades = live("apocalypse:hollow_shade");
        assert.ok(shades.length > 0, "crimson shades hunt the players");
        assert.ok(shades.every((s) => s._props.get("apocalypse:variant") === "crimson"));
        assert.ok(shades.some((s) => s.getEffect("strength")), "monsters empowered");
      }
      if (id === "void_storm") {
        assert.ok(live("apocalypse:void_rift").length > 0, "void rifts opened");
        assert.equal(ow().weather, "Thunder");
        const rift = live("apocalypse:void_rift")[0];
        P1._loc = { x: rift._loc.x + 1, y: rift._loc.y, z: rift._loc.z };
        const hp = P1._hp;
        await run(40);
        assert.ok(P1._hp < hp || P1._knockback.length > 0, "rift drags/burns players in reach");
        P1._loc = { x: 0.5, y: 64, z: 0.5 };
      }
      if (id === "meteor_shower") {
        const booms = M.mock.log.explosions.filter((x) => x.dim === OW);
        assert.ok(booms.length >= 5, `meteors impacted (${booms.length})`);
        assert.ok(booms.every((b) => !b.breaksBlocks), "no terrain damage by default");
        const rings = M.mock.log.particles.filter((p) => p.id === "apocalypse:telegraph_ring");
        const miss = booms.map((b) => Math.min(...rings.map((r) => Math.hypot(r.loc.x - b.loc.x, r.loc.z - b.loc.z)))).sort((a, b) => a - b);
        assert.ok(miss[Math.floor(miss.length / 2)] < 2.5, `meteors land on their telegraph rings (median miss ${miss[Math.floor(miss.length / 2)].toFixed(2)})`);
        assert.ok(blocksOf(ow(), "apocalypse:meteorite").length > 0, "meteorite left in craters");
      }
      if (id === "reality_fracture") {
        const texts = [...P1.actionbars, ...P2.actionbars].join("\n");
        assert.match(texts, /gravity|blink|weightless/i, "anomalies hit the players");
      }
      if (id === "eclipse") {
        assert.ok(seen.effects.has("darkness"), "darkness pulses under the open sky");
        assert.ok(live("apocalypse:hollow_shade").length > 0, "shades walk by day");
      }
      if (id === "ancient_awakening") {
        assert.ok(blocksOf(ow(), "apocalypse:engine_cache").length > 0, "engine caches surfaced");
        assert.ok(wdp("apocalypse:awakening_caches").length > 0, "cache positions persisted");
      }
      if (id === "corruption_surge") {
        assert.ok(live("apocalypse:thornling").length > 0, "thornlings erupt");
        assert.ok(seen.effects.has("poison"), "spores poison exposed players");
      }

      // kill a few event mobs for kill drops
      for (const m of eventMobs().slice(0, 3)) if (m._maxHp) M.attack(P1, m, 1e6);
      await run(5);

      const stop = M.command(P1, "apocalypse:event", "stop");
      assert.equal(stop.status, M.CustomCommandStatus.Success);
      await run(30);
      assert.equal(wdp("apocalypse:event_state").active, null);
      assert.equal(eventMobs().length, 0, "event mobs cleaned up");
      assert.ok(!P1._fogs?.some((f) => f.user === "apocalypse_event"), "event fog removed");
      assert.equal(pdp(P1, "apocalypse:journal").events[id], 1, "journal records the survived event");
      if (id === "ancient_awakening") {
        assert.equal(blocksOf(ow(), "apocalypse:engine_cache").length, 0, "unopened caches sink back");
        assert.deepEqual(wdp("apocalypse:awakening_caches"), []);
      }
      if (id === "void_storm") assert.equal(ow().weather, "Clear");
      clean(id);
    });
  }

  // ------------------------------------------------------------------------------------------------
  // bosses
  // ------------------------------------------------------------------------------------------------
  const BOSSES = {
    hollow_king: { first: ["apocalypse:hollow_crown_shard", "apocalypse:soul_essence"], thresholds: [0.66, 0.33] },
    star_eater: { first: ["apocalypse:star_eater_core", "apocalypse:stardust"], thresholds: [0.6, 0.25] },
    root_titan: { first: ["apocalypse:titan_heartwood", "apocalypse:living_bark"], thresholds: [0.66, 0.33] },
    null_colossus: { first: ["apocalypse:null_heart", "apocalypse:null_fragment"], thresholds: [0.6, 0.25] },
  };

  for (const [key, spec] of Object.entries(BOSSES)) {
    it(`boss fight: ${key}`, async () => {
      M.setTime(18000);
      heal(P1, P2);
      P1._loc = { x: 0.5, y: 64, z: 0.5 };
      P2._loc = { x: 6.5, y: 64, z: 2.5 };
      const typeId = `apocalypse:${key}`;
      const before = { p1: spec.first.map((i) => count(P1, i)), p2: spec.first.map((i) => count(P2, i)) };
      assert.equal(M.command(P1, "apocalypse:summon", key).status, M.CustomCommandStatus.Success);
      await run(5);
      const boss = live(typeId)[0];
      assert.ok(boss, "boss spawned");
      assert.equal(boss._props.get("apocalypse:phase"), 1);
      assert.ok(boss._groups.has("apocalypse:tier_2"), "health tier scales with the two nearby players");
      assert.equal(boss._hp, boss._maxHp);
      const max = boss._maxHp;
      const actions = new Set();
      let hurt = 0;
      await run(600, () => {
        if (boss._valid) actions.add(boss._props.get("apocalypse:action"));
        for (const p of [P1, P2]) if (p._hp < p._maxHp) hurt++;
        heal(P1, P2);
      });
      assert.ok(actions.size >= 3, `boss runs its attack state machine (actions seen: ${[...actions]})`);
      const watch = () => {
        if (boss._valid) actions.add(boss._props.get("apocalypse:action"));
        for (const p of [P1, P2]) if (p._hp < p._maxHp) hurt++;
        heal(P1, P2);
      };

      // Null Colossus: armored outside vents
      if (key === "null_colossus") {
        await run(40);
        boss._props.set("apocalypse:vented", false);
        let vented = false;
        for (let i = 0; i < 900 && !vented; i++) {
          await run(1);
          vented = boss._props.get("apocalypse:vented") === true;
        }
        assert.ok(vented, "core vents open periodically");
        const hp0 = boss._hp;
        M.attack(P1, boss, 10);
        assert.ok(Math.abs(hp0 - boss._hp - 15) < 1e-6, `vented core takes x1.5 damage (${hp0 - boss._hp})`);
        await run(160);
        const hp1 = boss._hp;
        M.attack(P1, boss, 10);
        assert.ok(Math.abs(hp1 - boss._hp - 3.5) < 1e-6, `closed armor takes x0.35 damage (${hp1 - boss._hp})`);
      }

      // phase 2: chip damage until below the threshold (works whatever damage multiplier is active)
      const toFraction = (f) => {
        for (let i = 0; i < 2000 && boss._hp / max > f; i++) M.attack(P1, boss, max * 0.04);
      };
      toFraction(spec.thresholds[0] - 0.05);
      await run(12);
      assert.equal(boss._props.get("apocalypse:phase"), 2, "phase II at the first threshold");
      const hpT = boss._hp;
      M.attack(P2, boss, 50);
      assert.equal(boss._hp, hpT, "invulnerable during the phase transition");
      await run(80, watch);
      toFraction(spec.thresholds[1] - 0.05);
      await run(12);
      assert.equal(boss._props.get("apocalypse:phase"), 3, "phase III at the second threshold");
      await run(400, watch);
      assert.ok(hurt > 0, "boss attacks connect with players");

      // kill, rewards, dedup
      await run(20);
      M.attack(P1, boss, 1e9);
      M.attack(P2, boss, 1e9);
      await run(30);
      assert.equal(live(typeId).length, 0, "boss removed after death");
      const adds = [...M.mock.entities.values()].filter((e) => e._valid && e._tags.has("apocalypse:boss_add"));
      assert.equal(adds.length, 0, "adds are dismissed when the boss dies");
      const j = pdp(P1, "apocalypse:journal");
      assert.equal(j.kills[key], 1);
      spec.first.forEach((item, i) => {
        assert.ok(count(P1, item) > before.p1[i], `P1 first-kill reward ${item}`);
        assert.ok(count(P2, item) > before.p2[i], `P2 (contributor) first-kill reward ${item}`);
      });
      const after = spec.first.map((i) => count(P1, i));
      M.mock.pending.push(["entityDie", { deadEntity: boss, damageSource: { cause: "entityAttack", damagingEntity: P1 } }]);
      M.flushEvents();
      await run(5);
      assert.deepEqual(spec.first.map((i) => count(P1, i)), after, "duplicate death events never pay twice");
      assert.equal(wdp("apocalypse:world_progress")[key], 1);
      heal(P1, P2);
      clean(key);
    });
  }

  // ------------------------------------------------------------------------------------------------
  // items, relics, armor, blocks
  // ------------------------------------------------------------------------------------------------
  it("weapon abilities and on-hit effects", async () => {
    M.setTime(6000);
    heal(P1, P2);
    P1._loc = { x: 0.5, y: 64, z: 0.5 };
    P1._view = { x: 0, y: 0, z: 1 };
    const dim = ow();
    const foe = (z, x = 0.5) => dim.spawnEntity("minecraft:zombie", { x, y: 64, z });
    await run(2);

    let z = foe(3.5);
    hold(P1, "apocalypse:rift_blade");
    M.useItem(P1, "apocalypse:rift_blade");
    await run(3);
    assert.ok(P1._loc.z > 3, `rift dash moved the player forward (${P1._loc.z.toFixed(1)})`);
    assert.ok(z._hp < z._maxHp, "dash cuts enemies on the path");
    assert.ok(M.mock.log.cooldowns.some((c) => c.cat === "apocalypse_rift_blade"), "cooldown UI started");
    assert.equal(P1.inventory.getItem(0).damage, 2, "ability costs durability");
    const blinks = M.mock.log.cooldowns.length;
    M.useItem(P1, "apocalypse:rift_blade");
    await run(3);
    assert.equal(M.mock.log.cooldowns.length, blinks, "ability refuses to fire during its cooldown");

    P1._loc = { x: 0.5, y: 64, z: 0.5 };
    P1._hp = 8;
    z = foe(3.5);
    hold(P1, "apocalypse:soulreaver_scythe");
    M.useItem(P1, "apocalypse:soulreaver_scythe");
    await run(3);
    assert.ok(z._hp < z._maxHp && P1._hp > 8, "soul reap damages and heals");

    for (const id of ["apocalypse:titans_wrath", "apocalypse:null_edge", "apocalypse:event_horizon"]) {
      z = foe(4.5);
      hold(P1, id);
      if (id === "apocalypse:event_horizon") P1._view = { x: 0, y: -0.3, z: 0.954 };
      M.useItem(P1, id);
      await run(100);
      P1._view = { x: 0, y: 0, z: 1 };
      assert.ok(!z._valid || z._hp < z._maxHp, `${id} ability damages a nearby foe`);
    }

    for (const e of live("minecraft:zombie")) e._despawn();
    z = foe(10.5);
    hold(P1, "apocalypse:starfall_scepter");
    M.useItem(P1, "apocalypse:starfall_scepter");
    await run(40);
    assert.ok(z._hp < z._maxHp, "star bolt flies and hits");

    heal(P1);
    P1._hp = 10;
    z = foe(1.5);
    M.hitWithItem(P1, z, "apocalypse:bloodfang_cleaver");
    await run(3);
    assert.ok(P1._hp > 10, "lifesteal heals the wielder");
    assert.ok(z.getEffect("wither"), "bleed applied");
    z = dim.spawnEntity("apocalypse:rift_sentinel", { x: 0.5, y: 64, z: 1.5 });
    M.hitWithItem(P1, z, "apocalypse:null_edge");
    await run(2);
    const hpMarked = z._hp;
    M.hitWithItem(P1, z, "apocalypse:null_edge");
    await run(2);
    assert.ok(hpMarked - z._hp > 13, "second Null Edge hit detonates the mark");
    for (const e of [...live("minecraft:zombie"), ...live("apocalypse:rift_sentinel")]) M.attack(P1, e, 1e6);
    await run(25);
    heal(P1);
    clean("abilities");
  });

  it("summoning relics respect their rites", async () => {
    await killAllBosses();
    P1._loc = { x: 0.5, y: 64, z: 0.5 };
    M.setTime(6000);
    hold(P1, "apocalypse:cursed_crown");
    M.useItem(P1, "apocalypse:cursed_crown");
    await run(3);
    assert.match(P1.actionbars.at(-1), /daylight/);
    assert.equal(count(P1, "apocalypse:cursed_crown"), 1, "refused rite keeps the relic");
    M.setTime(18000);
    M.useItem(P1, "apocalypse:cursed_crown");
    await run(70);
    assert.equal(count(P1, "apocalypse:cursed_crown"), 0, "relic consumed");
    assert.equal(live("apocalypse:hollow_king").length, 1, "the Hollow King answers at night");
    hold(P1, "apocalypse:cursed_crown");
    M.useItem(P1, "apocalypse:cursed_crown");
    await run(3);
    assert.match(P1.actionbars.at(-1), /already walks/);
    await killAllBosses();

    hold(P1, "apocalypse:astral_lure");
    M.useItem(P1, "apocalypse:astral_lure");
    await run(70);
    assert.equal(live("apocalypse:star_eater").length, 1, "Astral Lure works under the open night sky");
    await killAllBosses();

    hold(P1, "apocalypse:heartseed");
    M.useItem(P1, "apocalypse:heartseed");
    await run(3);
    assert.match(P1.actionbars.at(-1), /night|daylight/i);
    M.setTime(6000);
    M.useItem(P1, "apocalypse:heartseed");
    await run(70);
    assert.equal(live("apocalypse:root_titan").length, 1, "Heartseed takes root on grass by day");
    await killAllBosses();
    heal(P1, P2);
    clean("relics");
  });

  it("Aether Elixir cleanses event afflictions", async () => {
    P1.addEffect("wither", 200);
    P1.addEffect("darkness", 200);
    M.consumeItem(P1, "apocalypse:aether_elixir");
    await run(3);
    assert.ok(!P1.getEffect("wither") && !P1.getEffect("darkness"));
    assert.ok(P1.getEffect("regeneration") && P1.getEffect("absorption"));
    clean("elixir");
  });

  it("armor set bonuses", async () => {
    const wear = (set) => {
      for (const [slot, piece] of [["Head", "helmet"], ["Chest", "chestplate"], ["Legs", "leggings"], ["Feet", "boots"]]) {
        P1.armor[slot] = new M.ItemStack(`apocalypse:${set}_${piece}`);
      }
    };
    P1._effects.clear();
    wear("riftwalker");
    await run(45);
    assert.ok(P1.getEffect("speed"), "riftwalker: speed");
    const hp = P1._hp;
    P1.applyDamage(6, { cause: "fall" });
    assert.equal(P1._hp, hp, "riftwalker: no fall damage");
    wear("starforged");
    await run(45);
    assert.ok(P1.getEffect("fire_resistance") && P1.getEffect("night_vision"), "starforged: fire resistance + night vision");
    wear("null_aegis");
    await run(45);
    assert.ok(P1.getEffect("resistance"), "null aegis: resistance");
    P1.armor = {};
    P1._effects.clear();
    clean("armor");
  });

  it("ores drop shards/XP (Fortune-aware) unless Silk Touch; caches open", async () => {
    const dim = ow();
    const at = { x: 20, y: 63, z: 20 };
    const dropsNear = (id) => [...M.mock.entities.values()].filter((e) => e._valid && e.typeId === "minecraft:item" && e.itemStack.typeId === id &&
      Math.hypot(e._loc.x - at.x - 0.5, e._loc.z - at.z - 0.5) < 1).reduce((n, e) => n + e.itemStack.amount, 0);
    const clear = () => [...M.mock.entities.values()].filter((e) => e.typeId === "minecraft:item" || e.typeId === "minecraft:xp_orb").forEach((e) => e._despawn());
    hold(P1, "minecraft:iron_pickaxe");
    M.breakBlock(P1, at, "apocalypse:rift_ore");
    await run(3);
    const plain = dropsNear("apocalypse:rift_shard");
    assert.ok(plain >= 1 && plain <= 3, `rift ore drops 1-3 shards (${plain})`);
    assert.ok(live("minecraft:xp_orb").length >= 2, "rift ore drops XP");
    assert.ok(pdp(P1, "apocalypse:journal").discovered.includes("apocalypse:rift_shard"), "discovery recorded");
    clear();
    const silk = P1.inventory.slots[0];
    silk.enchantments.set("silk_touch", 1);
    M.breakBlock(P1, at, "apocalypse:rift_ore");
    await run(3);
    assert.equal(dropsNear("apocalypse:rift_shard"), 0, "silk touch: the loot table drops the ore block instead");
    clear();
    silk.enchantments.delete("silk_touch");
    silk.enchantments.set("fortune", 3);
    let total = 0;
    for (let i = 0; i < 20; i++) {
      M.breakBlock(P1, at, "apocalypse:rift_ore");
      await run(2);
      total += dropsNear("apocalypse:rift_shard");
      clear();
    }
    assert.ok(total / 20 > 2.5, `fortune increases yields (avg ${(total / 20).toFixed(2)})`);
    hold(P1, "minecraft:wooden_shovel");
    M.breakBlock(P1, at, "apocalypse:meteorite");
    await run(3);
    assert.equal(dropsNear("apocalypse:star_metal_chunk"), 0, "meteorite needs a pickaxe");
    hold(P1, "minecraft:diamond_pickaxe");
    M.breakBlock(P1, at, "apocalypse:meteorite");
    await run(3);
    assert.ok(dropsNear("apocalypse:star_metal_chunk") >= 1 && dropsNear("apocalypse:stardust") >= 1, "meteorite: star metal + stardust");
    clear();
    M.breakBlock(P1, at, "apocalypse:engine_cache");
    await run(3);
    assert.ok(live("minecraft:xp_orb").length >= 5, "engine cache bursts with XP (loot comes from its loot table)");
    clear();
    void dim;
    clean("ores");
  });

  // ------------------------------------------------------------------------------------------------
  // the Shattered Expanse
  // ------------------------------------------------------------------------------------------------
  it("Engine Key opens a rift; the Expanse is generated and walkable to the Arena", async () => {
    heal(P1, P2);
    P1._loc = { x: 0.5, y: 64, z: 0.5 };
    P1._view = { x: 0, y: 0, z: 1 };
    hold(P1, "apocalypse:engine_key");
    M.useItem(P1, "apocalypse:engine_key");
    await run(3);
    const portal = live("apocalypse:rift_portal").find((e) => e._dim === ow());
    assert.ok(portal, "rift portal opened in the Overworld");
    assert.equal(portal._dp.get("apocalypse:dest"), "expanse");
    P1._loc = { x: portal._loc.x, y: portal._loc.y - 1, z: portal._loc.z };
    await run(400);
    assert.equal(P1._dim.id, EXPANSE, "player travelled to the custom dimension");
    assert.ok(M.mock.log.structures.some((s) => s.id === "apocalypse:nexus_shrine" && s.dim === EXPANSE), "nexus shrine placed");
    assert.equal(exp().typeAt(0, NEXUS.cy, 0), "apocalypse:runestone_bricks", "nexus island built");
    assert.ok(P1._fogs?.some((f) => f.id === "apocalypse:fog_expanse"), "expanse fog applied");
    assert.equal(pdp(P1, "apocalypse:journal").expanseVisits, 1);
    assert.ok(live("apocalypse:rift_portal").some((e) => e._dim === exp() && e._tags.has("apocalypse:nexus_portal")), "permanent return rift at the Nexus");
    await run(600);
    const gen = wdp("apocalypse:expanse_gen");
    assert.ok(gen.nexus && gen.arena, `nexus and arena generated (${JSON.stringify({ n: gen.nexus, a: gen.arena })})`);
    assert.ok(M.mock.log.structures.some((s) => s.id === "apocalypse:colossus_altar"), "colossus altar placed");
    assert.equal(M.mock.tickingAreas.size, 0, "temporary ticking areas released");
    assert.ok(gen.done.length > 5, `procedural cells generated around the player (${gen.done.length})`);

    // walkability: flood-fill over top surfaces (step height <= 1) from the Nexus to the Arena
    const d = exp();
    const solid = (x, y, z) => !["minecraft:air", "apocalypse:aether_cluster"].includes(d.typeAt(x, y, z));
    const standable = (x, y, z) => solid(x, y - 1, z) && !solid(x, y, z) && !solid(x, y + 1, z);
    const start = [0, NEXUS.cy + 1, 4];
    const goal = (x, z) => Math.hypot(x - ARENA.cx, z - ARENA.cz) < 6;
    const seen = new Set([start.join()]);
    const q = [start];
    let reached = false;
    while (q.length && !reached) {
      const [x, y, z] = q.shift();
      if (goal(x, z)) reached = true;
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        for (const dy of [0, 1, -1]) {
          const n = [x + dx, y + dy, z + dz];
          if (Math.abs(n[0]) > 40 || n[2] > 20 || n[2] < ARENA.cz - 30) continue;
          if (seen.has(n.join()) || !standable(...n)) continue;
          seen.add(n.join());
          q.push(n);
          break;
        }
      }
    }
    assert.ok(reached, "the Colossus Arena is reachable on foot from the Nexus");
    assert.equal(bridgeIslands().length > 0, true);
    clean("expanse travel");
  });

  it("Expanse life: sentinels, void rescue, Null Gate ritual, return home", async () => {
    const d = exp();
    P1._loc = { x: ARENA.cx + 0.5, y: ARENA.cy + 1, z: ARENA.cz + 0.5 };
    await run(800);
    assert.ok(live("apocalypse:rift_sentinel").some((e) => e._dim === d) || live("apocalypse:void_crawler").some((e) => e._dim === d),
      "Expanse guardians spawn away from the Nexus");
    heal(P1);
    P1._loc = { x: 0.5, y: NEXUS.cy - 80, z: 0.5 };
    await run(45);
    assert.ok(P1._loc.y > NEXUS.cy && P1._hp < P1._maxHp, "the void returns fallen players to the Nexus, hurt");
    heal(P1);

    P1._loc = { x: ARENA.cx + 0.5, y: ARENA.cy + 1, z: ARENA.cz + 3.5 };
    hold(P1, "apocalypse:engine_key");
    P1.inventory.slots = P1.inventory.slots.map((s) => (s?.typeId === "apocalypse:null_fragment" ? undefined : s));
    const gate = { x: ARENA.cx, y: ARENA.cy + 2, z: ARENA.cz };
    M.interactBlock(P1, gate, "apocalypse:null_gate");
    await run(3);
    assert.match(P1.actionbars.at(-1), /Null Fragments/);
    give(P1, "apocalypse:null_fragment", 10);
    M.interactBlock(P1, gate, "apocalypse:null_gate");
    await run(70);
    assert.equal(count(P1, "apocalypse:null_fragment"), 2, "gate consumes 8 fragments");
    const colossus = live("apocalypse:null_colossus");
    assert.equal(colossus.length, 1, "the Null Colossus rises in the arena");
    assert.equal(colossus[0]._dim, d);
    M.interactBlock(P1, gate, "apocalypse:null_gate");
    await run(3);
    assert.match(P1.actionbars.at(-1), /already stands/);
    M.attack(P1, colossus[0], 1e12);
    await run(30);

    P1._loc = { x: 30.5, y: NEXUS.cy + 1, z: 30.5 };
    M.useItem(P1, "apocalypse:engine_key");
    await run(3);
    const home = live("apocalypse:rift_portal").find((e) => e._dim === d && !e._tags.has("apocalypse:nexus_portal"));
    assert.ok(home && home._dp.get("apocalypse:dest") === "return", "a rift home opens inside the Expanse");
    P1._loc = { x: home._loc.x, y: home._loc.y - 1, z: home._loc.z };
    await run(20);
    assert.equal(P1._dim.id, OW, "back in the Overworld");
    assert.ok(Math.hypot(P1._loc.x - 0.5, P1._loc.z - 3) < 4, "returned to where the journey began");
    assert.ok(!P1._fogs?.some((f) => f.id === "apocalypse:fog_expanse"), "expanse fog removed");
    const t0 = stats.ticks;
    await run(1300);
    assert.ok(!live("apocalypse:rift_portal").some((e) => e._dim === ow()), `temporary rifts close after a minute (${stats.ticks - t0} ticks)`);
    clean("expanse life");
  });

  // ------------------------------------------------------------------------------------------------
  // codex & commands
  // ------------------------------------------------------------------------------------------------
  it("Engine Codex pages, operator settings and admin tools", async () => {
    ui.shown.length = 0;
    ui.responders.push(() => ({ canceled: false, selection: 0 }), () => ({ canceled: false, selection: 0 }));
    M.useItem(P1, "apocalypse:engine_codex");
    await run(10);
    assert.match(ui.shown[0].title, /ENGINE CODEX/);
    assert.equal(ui.shown[0].buttons.length, 7, "operators see settings + admin");
    assert.match(ui.shown[1].body, /Bosses defeated/);
    for (const page of [1, 2, 3, 4]) {
      ui.responders.push(() => ({ canceled: false, selection: page }));
      M.useItem(P1, "apocalypse:engine_codex");
      await run(10);
    }
    assert.ok(ui.shown.some((f) => /Summon:/.test(f.body ?? "")) || ui.shown.some((f) => f.title === "§lBosses"), "boss page");
    assert.ok(ui.shown.some((f) => /Blood Moon/.test(f.body ?? "") && /Corruption Surge/.test(f.body ?? "")), "all events listed");
    assert.ok(ui.shown.some((f) => /Engine Key/.test(f.body ?? "")), "crafting guide");

    ui.responders.push(() => ({ canceled: false, selection: 5 }), (form) => {
      assert.equal(form._elements.length, 8 + 7);
      return { canceled: false, formValues: [0, 3, 2, 2, true, false, true, false, true, true, true, true, true, true, true] };
    });
    M.useItem(P1, "apocalypse:engine_codex");
    await run(10);
    const cfg = wdp("apocalypse:config");
    assert.deepEqual([cfg.profile, cfg.eventFrequency, cfg.eventIntensity, cfg.bossDifficulty, cfg.terrainDamage, cfg.lightning],
      ["potato", "frequent", "brutal", "nightmare", true, false]);

    // terrain damage enabled: the Corruption Surge turns grass into Blighted Grass
    M.command(P1, "apocalypse:event", "start", "corruption_surge");
    await run(400);
    assert.ok(blocksOf(ow(), "apocalypse:blighted_grass").length > 0, "blight spreads when terrain damage is on");
    M.command(P1, "apocalypse:event", "stop");
    await run(5);
    heal(P1, P2);

    ui.responders.push(() => ({ canceled: false, selection: 6 }), () => ({ canceled: false, selection: 2 }));
    M.useItem(P1, "apocalypse:engine_codex");
    await run(10);
    assert.equal(wdp("apocalypse:event_state").active, "meteor_shower", "admin tools start events");
    M.command(P1, "apocalypse:event", "stop");
    await run(5);

    assert.equal(M.command(P1, "apocalypse:profile", "balanced").status, M.CustomCommandStatus.Success);
    await run(3);
    assert.equal(wdp("apocalypse:config").profile, "balanced");
    assert.match(M.command(P1, "apocalypse:event", "status").message, /No event active/);
    ui.shown.length = 0;
    ui.responders.push(() => ({ canceled: true, cancelationReason: "UserBusy" }), () => ({ canceled: false, selection: 0 }));
    M.command(P1, "apocalypse:codex");
    await run(30);
    assert.ok(ui.shown.filter((f) => /ENGINE CODEX/.test(f.title)).length >= 2, "codex retries while the chat screen is closing");
    P2.commandPermissionLevel = 0;
    assert.equal(M.command(P2, "apocalypse:summon", "hollow_king").status, M.CustomCommandStatus.Failure, "non-operators cannot summon");
    P2.commandPermissionLevel = 1;
    ui.responders.length = 0;
    clean("codex");
  });

  it("natural event scheduling over two in-game days", async () => {
    heal(P1, P2);
    const before = wdp("apocalypse:event_state").completed;
    const startedAt = realNow();
    await run(48000, () => {
      if (stats.ticks % 200 === 0) heal(P1, P2);
    });
    const st = wdp("apocalypse:event_state");
    assert.ok(st.completed > before, `events occur naturally (completed ${before} -> ${st.completed})`);
    stats.msPerTick = (realNow() - startedAt) / 48000;
    clean("scheduler");
  });

  it("summary", () => {
    stats.wallSeconds = (realNow() - stats.started) / 1000;
    stats.entitiesCreated = M.mock.nextEntity - 1;
    stats.particles = M.mock.log.particles.length;
    stats.sounds = M.mock.log.sounds.length;
    stats.explosions = M.mock.log.explosions.length;
    stats.problems = M.mock.problems.length;
    stats.warnings = warnings.length;
    stats.warningSamples = [...new Set(warnings)].slice(0, 10);
    stats.entitiesByType = {};
    for (const e of M.mock.entities.values()) stats.entitiesByType[e.typeId] = (stats.entitiesByType[e.typeId] ?? 0) + 1;
    stats.commandsRun = M.mock.log.commands.length;
    stats.structuresPlaced = M.mock.log.structures.map((s) => s.id);
    stats.expanseBlocks = M.mock.dims.get(EXPANSE).blocks.size;
    if (process.env.APOCALYPSE_SMOKE_SUMMARY) fs.writeFileSync(process.env.APOCALYPSE_SMOKE_SUMMARY, JSON.stringify(stats, null, 2));
    clean("final");
  });
});
