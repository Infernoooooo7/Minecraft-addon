// Custom slash commands. Callbacks run in restricted execution, so all world changes go through system.run.
import { CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, Player, system, } from "@minecraft/server";
import { config, saveConfig } from "./core/config.js";
import { COMMAND } from "./core/keys.js";
import { BOSS_TYPES, spawnBoss } from "./bosses/runtime.js";
import { activeEvent, allEvents, eventState, startEvent, stopEvent } from "./events/runtime.js";
import { PROFILES } from "./logic/profiles.js";
import { openCodex } from "./ui/codex.js";
const EVENT_IDS = ["blood_moon", "void_storm", "meteor_shower", "reality_fracture", "eclipse", "ancient_awakening", "corruption_surge"];
const BOSS_IDS = BOSS_TYPES.map((t) => t.replace("apocalypse:", ""));
const ok = (message) => ({ status: CustomCommandStatus.Success, message });
const fail = (message) => ({ status: CustomCommandStatus.Failure, message });
function playerOf(origin) {
    const e = origin.initiator ?? origin.sourceEntity;
    return e instanceof Player ? e : undefined;
}
export function registerCommands(reg) {
    reg.registerEnum(COMMAND.EVENT_ENUM, EVENT_IDS);
    reg.registerEnum(COMMAND.ACTION_ENUM, ["start", "stop", "status"]);
    reg.registerEnum(COMMAND.PROFILE_ENUM, Object.keys(PROFILES));
    reg.registerEnum(COMMAND.BOSS_ENUM, BOSS_IDS);
    reg.registerCommand({
        name: COMMAND.CODEX,
        description: "Open the APOCALYPSE ENGINE codex (journal, guide, settings).",
        permissionLevel: CommandPermissionLevel.Any,
    }, (origin) => {
        const p = playerOf(origin);
        if (!p)
            return fail("Only players can open the codex.");
        system.run(() => void openCodex(p));
        return ok();
    });
    reg.registerCommand({
        name: COMMAND.EVENT,
        description: "Start, stop or inspect APOCALYPSE ENGINE world events.",
        permissionLevel: CommandPermissionLevel.GameDirectors,
        mandatoryParameters: [{ name: COMMAND.ACTION_ENUM, type: CustomCommandParamType.Enum }],
        optionalParameters: [{ name: COMMAND.EVENT_ENUM, type: CustomCommandParamType.Enum }],
    }, (_origin, action, eventId) => {
        if (action === "status") {
            const ev = activeEvent();
            const st = eventState();
            return ok(ev ? `${ev.meta.name} is active (${Math.max(0, Math.round((st.endTick - system.currentTick) / 20))}s left).`
                : `No event active. ${st.completed} events completed this world. Frequency: ${config().eventFrequency}.`);
        }
        if (action === "stop") {
            if (!activeEvent())
                return fail("No event is active.");
            system.run(() => stopEvent(true));
            return ok("Stopping the active event.");
        }
        const id = eventId ?? EVENT_IDS[0];
        if (!allEvents().some((e) => e.meta.id === id))
            return fail(`Unknown event ${id}.`);
        system.run(() => startEvent(id, true));
        return ok(`Starting ${id}.`);
    });
    reg.registerCommand({
        name: COMMAND.PROFILE,
        description: "Set the APOCALYPSE ENGINE performance profile (potato, balanced, enhanced).",
        permissionLevel: CommandPermissionLevel.GameDirectors,
        mandatoryParameters: [{ name: COMMAND.PROFILE_ENUM, type: CustomCommandParamType.Enum }],
    }, (_origin, id) => {
        if (!(id in PROFILES))
            return fail(`Unknown profile ${id}.`);
        system.run(() => saveConfig({ profile: id }));
        return ok(`Performance profile set to ${PROFILES[id].label}.`);
    });
    reg.registerCommand({
        name: COMMAND.SUMMON,
        description: "Summon an APOCALYPSE ENGINE boss in front of you.",
        permissionLevel: CommandPermissionLevel.GameDirectors,
        cheatsRequired: true,
        mandatoryParameters: [{ name: COMMAND.BOSS_ENUM, type: CustomCommandParamType.Enum }],
    }, (origin, boss) => {
        const p = playerOf(origin);
        if (!p)
            return fail("Run this as a player.");
        if (!BOSS_IDS.includes(boss))
            return fail(`Unknown boss ${boss}.`);
        system.run(() => {
            const d = p.getViewDirection();
            spawnBoss(`apocalypse:${boss}`, p.dimension.id, { x: p.location.x + d.x * 8, y: p.location.y + 1, z: p.location.z + d.z * 8 });
        });
        return ok(`Summoning ${boss}.`);
    });
}
