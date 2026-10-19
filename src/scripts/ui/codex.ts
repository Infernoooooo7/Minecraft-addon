// The Engine Codex: per-player journal and guide, plus world settings and admin tools for operators.
import { Player, system } from "@minecraft/server";
import { ActionFormData, ActionFormResponse, FormCancelationReason, ModalFormData, ModalFormResponse } from "@minecraft/server-ui";
import { config, Difficulty, Intensity, saveConfig } from "../core/config.js";
import { playerSound } from "../core/fx.js";
import { DP } from "../core/keys.js";
import { isOperator } from "../core/players.js";
import { readEntity } from "../core/state.js";
import { BOSS_TYPES, bossCount, spawnBoss, worldProgress } from "../bosses/runtime.js";
import { activeEvent, allEvents, eventState, startEvent, stopEvent } from "../events/runtime.js";
import { SET_BONUS } from "../items/armor.js";
import { SOUNDS } from "../generated/ids.js";
import type { Frequency } from "../logic/eventScheduler.js";
import { PROFILES, ProfileId } from "../logic/profiles.js";
import { BOSS_ORDER, completion, nextObjective, parseJournal } from "../logic/progression.js";
import { expanseStatus, inExpanse, travelHome, travelToExpanse } from "../world/expanse.js";

const ICON = (name: string): string => `textures/items/apocalypse/${name}`;

const BOSS_INFO: Record<string, { name: string; icon: string; summon: string; tips: string }> = {
  hollow_king: {
    name: "The Hollow King", icon: "cursed_crown",
    summon: "Use a Cursed Crown in the Overworld at night (or during an Eclipse).",
    tips: "Phase II adds ground quakes (JUMP to dodge) and soul chains. Phase III opens with the Crown of Ruin: break away from the King when the violet ring appears.",
  },
  star_eater: {
    name: "The Star Eater", icon: "astral_lure",
    summon: "Use an Astral Lure at night under the open sky.",
    tips: "Dodge star volleys sideways and run from gravity wells. In Phase III it charges a Supernova: hide behind solid blocks, then strike while it is exhausted.",
  },
  root_titan: {
    name: "The Root Titan", icon: "heartseed",
    summon: "Plant a Heartseed by daylight while standing on grass, dirt, moss or blighted ground.",
    tips: "Move off the eruption rings, jump the earthsplitter shockwave and kill Thornlings quickly. Its sap shield fades after a few seconds.",
  },
  null_colossus: {
    name: "The Null Colossus", icon: "engine_key",
    summon: "In the Shattered Expanse, use the Engine Key on the Null Gate with 8 Null Fragments.",
    tips: "Its armor absorbs most damage. Attack when the core vents (cyan glow, 'CORE EXPOSED'): after gravity slams, collapses and every ~25 s. Full Null Aegis anchors you against the gravity lift.",
  },
};

const CRAFTING = [
  "§3Rift Shard§r — mine Rift Ore (Y -56 to 40, cyan veins).",
  "§bAether Crystal§r — 4 Rift Shards + 1 Amethyst Shard.",
  "§bRift Blade§r — Aether Crystal, Rift Shard, Stick (vertical).",
  "§3Riftwalker armor§r — Rift Shards in armor patterns.",
  "§6Star Metal Ingot§r — smelt Star Metal Chunks (from Meteorite blocks).",
  "§6Starforged armor§r — Star Metal Ingots in armor patterns.",
  "§6Starfall Scepter§r — Stardust, Star Metal Ingot, Sticks.",
  "§4Bloodfang Cleaver§r — Blood Crystals (Blood Moon), Iron Ingot, Stick.",
  "§5Cursed Crown§r — Soul Essence, Gold Ingot, Rift Shard (or 2 Eclipse Shards + 2 Soul Essence + Gold).",
  "§eAstral Lure§r — Stardust, Aether Crystal, Star Metal Ingot (or 2 Fracture Shards + 3 Stardust + Aether Crystal).",
  "§2Heartseed§r — Living Bark, Oak Saplings, Aether Crystal.",
  "§bAether Elixir§r — Glass Bottle, Aether Crystal, Glow Berries (or 2 bottles + Aether Crystal + Void Ichor for two).",
  "§5Soulreaver Scythe§r — Hollow Crown Shards, Soul Essence, Sticks.",
  "§dEvent Horizon§r — Stardust, Star Eater Core, Star Metal Ingots.",
  "§2Titan's Wrath§r — Living Bark, Titan Heartwood, Iron Block, Oak Log.",
  "§3Engine Key§r — Hollow Crown Shard, Star Eater Core, Titan Heartwood, 2 Aether Crystals.",
  "§3Null Edge§r — Null Fragments, Null Heart, Rift Blade.",
  "§3Null Aegis armor§r — each Starforged piece surrounded by 8 Null Fragments.",
];

const WEAPONS = [
  "§bRift Blade§r — use: Rift Dash (blink 7 blocks, cutting through enemies). 5 s.",
  "§4Bloodfang Cleaver§r — hits heal you (25%) and make foes bleed.",
  "§5Soulreaver Scythe§r — use: Soul Reap (360° sweep, heals per soul). 10 s.",
  "§2Titan's Wrath§r — use: Earthsplitter (shockwave launches grounded foes). 10 s.",
  "§3Null Edge§r — hits mark foes; a second hit detonates the mark. Use: Gravity Crush. 14 s.",
  "§6Starfall Scepter§r — use: Star Bolt. 1.5 s.",
  "§dEvent Horizon§r — use: Gravity Well where you aim. 12 s.",
  "§bAether Elixir§r — cleanses event afflictions, grants Regeneration II and Absorption II.",
];

/** Show a form, retrying while the player is busy (e.g. the chat screen is still closing). */
async function show<T extends ActionFormResponse | ModalFormResponse>(p: Player, form: { show(p: Player): Promise<T> }): Promise<T | undefined> {
  for (let i = 0; i < 20; i++) {
    if (!p.isValid) return undefined;
    const r = await form.show(p);
    if (!r.canceled || r.cancelationReason !== FormCancelationReason.UserBusy) return r;
    await system.waitTicks(10);
  }
  return undefined;
}

export async function openCodex(p: Player): Promise<void> {
  playerSound(p, SOUNDS.CODEX_OPEN, 0.8, 1);
  const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
  const ev = activeEvent();
  const op = isOperator(p);
  const form = new ActionFormData()
    .title("§l§3ENGINE CODEX")
    .body([
      `§7Engine restored: §b${Math.round(completion(j) * 100)}%`,
      `§7Next: §f${nextObjective(j)}`,
      ev ? `§7Active event: ${ev.color}${ev.meta.name}` : "§7No world event is active.",
      `§7Performance profile: §f${PROFILES[config().profile].label}`,
    ].join("\n"))
    .button("Journal", ICON("engine_codex"))
    .button("Bosses", ICON("hollow_crown_shard"))
    .button("World Events", ICON("eclipse_shard"))
    .button("Crafting Guide", ICON("aether_crystal"))
    .button("Weapons & Armor", ICON("rift_blade"));
  if (op) form.button("§6World Settings", ICON("star_metal_ingot")).button("§cAdmin Tools", ICON("null_heart"));
  const r = await show(p, form);
  if (!r || r.canceled || r.selection === undefined) return;
  switch (r.selection) {
    case 0: return journal(p);
    case 1: return bosses(p);
    case 2: return events(p);
    case 3: return page(p, "Crafting Guide", CRAFTING.join("\n"));
    case 4: return page(p, "Weapons & Armor", [
      ...WEAPONS, "",
      `§3Riftwalker set§r — ${SET_BONUS.riftwalker}.`,
      `§6Starforged set§r — ${SET_BONUS.starforged}.`,
      `§3Null Aegis set§r — ${SET_BONUS.null_aegis}.`,
    ].join("\n"));
    case 5: return op ? settings(p) : undefined;
    case 6: return op ? admin(p) : undefined;
  }
}

async function page(p: Player, title: string, body: string): Promise<void> {
  const r = await show(p, new ActionFormData().title(`§l${title}`).body(body).button("Back"));
  if (r && !r.canceled) return openCodex(p);
}

async function journal(p: Player): Promise<void> {
  const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
  const lines = ["§lBosses defeated"];
  for (const b of BOSS_ORDER) {
    const k = j.kills[b] ?? 0;
    lines.push(`${k ? "§a✔" : "§8✖"} §f${BOSS_INFO[b].name}${k ? ` §7x${k} (first on day ${j.firstKillDay[b] ?? "?"})` : ""}`);
  }
  lines.push("", "§lEvents survived");
  for (const e of allEvents()) lines.push(`${e.color}${e.meta.name}§r: ${j.events[e.meta.id] ?? 0}`);
  lines.push("", `§lDiscoveries: §f${j.discovered.length}`, `§lExpanse visits: §f${j.expanseVisits}`);
  return page(p, "Journal", lines.join("\n"));
}

async function bosses(p: Player): Promise<void> {
  const j = parseJournal(readEntity(p, DP.JOURNAL) as string | undefined);
  const wp = worldProgress();
  const form = new ActionFormData().title("§lBosses").body("§7Choose a boss for its summoning rite and tactics.");
  for (const b of BOSS_ORDER) form.button(`${BOSS_INFO[b].name}\n§8${(j.kills[b] ?? 0) > 0 ? "defeated" : "undefeated"} · world kills ${wp[b] ?? 0}`, ICON(BOSS_INFO[b].icon));
  form.button("Back");
  const r = await show(p, form);
  if (!r || r.canceled || r.selection === undefined) return;
  const key = BOSS_ORDER[r.selection];
  if (!key) return openCodex(p);
  const info = BOSS_INFO[key];
  const r2 = await show(p, new ActionFormData().title(`§l${info.name}`)
    .body(`§eSummon:§r ${info.summon}\n\n§eTactics:§r ${info.tips}`).button("Back"));
  if (r2 && !r2.canceled) return bosses(p);
}

async function events(p: Player): Promise<void> {
  const st = eventState();
  const cfg = config();
  const lines: string[] = [`§7Frequency: §f${cfg.eventFrequency}§7 · intensity: §f${cfg.eventIntensity}`, ""];
  for (const e of allEvents()) {
    const status = st.active === e.meta.id ? "§a[ACTIVE]" : cfg.events[e.meta.id] === false ? "§8[disabled]" : "";
    const when = e.meta.window === "any" ? "any time" : e.meta.window === "night" ? "at night" : "by day";
    lines.push(`${e.color}§l${e.meta.name}§r ${status}`, `§7(${when}, from day ${e.meta.minDay})§r ${e.summary}`, "");
  }
  return page(p, "World Events", lines.join("\n"));
}

// ------------------------------------------------------------------------------------------------
// operator pages
// ------------------------------------------------------------------------------------------------

const PROFILE_IDS: ProfileId[] = ["potato", "balanced", "enhanced"];
const FREQS: Frequency[] = ["off", "rare", "normal", "frequent"];
const INTENSITIES: Intensity[] = ["mild", "normal", "brutal"];
const DIFFICULTIES: Difficulty[] = ["story", "normal", "nightmare"];

async function settings(p: Player): Promise<void> {
  const cfg = config();
  const evs = allEvents();
  const form = new ModalFormData()
    .title("§lWorld Settings")
    .dropdown("Performance profile", PROFILE_IDS.map((id) => PROFILES[id].label),
      { defaultValueIndex: PROFILE_IDS.indexOf(cfg.profile), tooltip: "Potato for low-end phones, Enhanced for flagships." })
    .dropdown("Event frequency", FREQS, { defaultValueIndex: FREQS.indexOf(cfg.eventFrequency) })
    .dropdown("Event intensity", INTENSITIES, { defaultValueIndex: INTENSITIES.indexOf(cfg.eventIntensity) })
    .dropdown("Boss difficulty", DIFFICULTIES, { defaultValueIndex: DIFFICULTIES.indexOf(cfg.bossDifficulty) })
    .toggle("Meteors and explosions break blocks", { defaultValue: cfg.terrainDamage })
    .toggle("Void Storm lightning", { defaultValue: cfg.lightning })
    .toggle("Give new players an Engine Codex", { defaultValue: cfg.giveCodex })
    .toggle("Debug logging", { defaultValue: cfg.debug });
  for (const e of evs) form.toggle(`Event: ${e.meta.name}`, { defaultValue: cfg.events[e.meta.id] !== false });
  form.submitButton("Save");
  const r = await show(p, form);
  if (!r || r.canceled || !r.formValues) return;
  const v = r.formValues;
  const enabled: Record<string, boolean> = {};
  evs.forEach((e, i) => {
    enabled[e.meta.id] = v[8 + i] !== false;
  });
  saveConfig({
    profile: PROFILE_IDS[Number(v[0])] ?? cfg.profile,
    eventFrequency: FREQS[Number(v[1])] ?? cfg.eventFrequency,
    eventIntensity: INTENSITIES[Number(v[2])] ?? cfg.eventIntensity,
    bossDifficulty: DIFFICULTIES[Number(v[3])] ?? cfg.bossDifficulty,
    terrainDamage: v[4] === true,
    lightning: v[5] === true,
    giveCodex: v[6] === true,
    debug: v[7] === true,
    events: enabled,
  });
  const ev = activeEvent();
  if (ev && enabled[ev.meta.id] === false) stopEvent(false);
  p.sendMessage("§a[Engine Codex] World settings saved. The performance profile applies immediately to new effects and spawns.");
}

async function admin(p: Player): Promise<void> {
  const evs = allEvents();
  const st = expanseStatus();
  const form = new ActionFormData().title("§l§cAdmin Tools")
    .body(`§7Bosses alive: ${bossCount()} · Expanse: nexus ${st.nexus ? "built" : "pending"}, arena ${st.arena ? "built" : "pending"}, cells ${st.cells}`);
  for (const e of evs) form.button(`Start: ${e.meta.name}`);
  form.button("Stop the active event");
  for (const t of BOSS_TYPES) form.button(`Summon ${t.replace("apocalypse:", "").replace(/_/g, " ")} here`);
  form.button(inExpanse(p) ? "Leave the Expanse" : "Travel to the Expanse");
  form.button("Back");
  const r = await show(p, form);
  if (!r || r.canceled || r.selection === undefined) return;
  let s = r.selection;
  if (s < evs.length) {
    const ok = startEvent(evs[s].meta.id, true);
    p.sendMessage(ok ? `§a${evs[s].meta.name} started.` : "§cCould not start that event.");
    return;
  }
  s -= evs.length;
  if (s === 0) {
    stopEvent(true);
    return;
  }
  s -= 1;
  if (s < BOSS_TYPES.length) {
    const dir = p.getViewDirection();
    spawnBoss(BOSS_TYPES[s], p.dimension.id, { x: p.location.x + dir.x * 8, y: p.location.y + 1, z: p.location.z + dir.z * 8 });
    return;
  }
  s -= BOSS_TYPES.length;
  if (s === 0) {
    if (inExpanse(p)) travelHome(p);
    else await travelToExpanse(p);
    return;
  }
  return openCodex(p);
}
