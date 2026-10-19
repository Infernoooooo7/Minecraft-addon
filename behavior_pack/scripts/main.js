// APOCALYPSE ENGINE — script entry point.
// Startup: custom components, commands and the custom dimension. World load: config, runtimes, scheduler.
import { ItemStack, system, world } from "@minecraft/server";
import "./bosses/hollowKing.js";
import "./bosses/starEater.js";
import "./bosses/rootTitan.js";
import "./bosses/nullColossus.js";
import "./events/defs.js";
import { initBossRuntime } from "./bosses/runtime.js";
import { registerCommands } from "./commands.js";
import { config, loadConfig } from "./core/config.js";
import { COMPONENT, DP } from "./core/keys.js";
import { log } from "./core/log.js";
import { giveItem } from "./core/players.js";
import { startScheduler } from "./core/scheduler.js";
import { readEntity, writeEntity } from "./core/state.js";
import { initEventDefs } from "./events/defs.js";
import { initEventRuntime, syncPlayerFog } from "./events/runtime.js";
import { ITEMS } from "./generated/ids.js";
import { abilityComponent, onHitComponent } from "./items/abilities.js";
import { initArmor } from "./items/armor.js";
import { codexComponent, elixirComponent, engineKeyComponent, relicComponent } from "./items/relics.js";
import { cacheComponent, nullGateComponent, oreComponent } from "./world/blocks.js";
import { initExpanse, registerExpanseDimension, syncExpanseFog } from "./world/expanse.js";
system.beforeEvents.startup.subscribe((ev) => {
    registerExpanseDimension(ev.dimensionRegistry);
    const items = ev.itemComponentRegistry;
    items.registerCustomComponent(COMPONENT.ABILITY, abilityComponent);
    items.registerCustomComponent(COMPONENT.ON_HIT, onHitComponent);
    items.registerCustomComponent(COMPONENT.RELIC, relicComponent);
    items.registerCustomComponent(COMPONENT.ENGINE_KEY, engineKeyComponent);
    items.registerCustomComponent(COMPONENT.CODEX, codexComponent);
    items.registerCustomComponent(COMPONENT.ELIXIR, elixirComponent);
    const blocks = ev.blockComponentRegistry;
    blocks.registerCustomComponent(COMPONENT.ORE_XP, oreComponent);
    blocks.registerCustomComponent(COMPONENT.CACHE, cacheComponent);
    blocks.registerCustomComponent(COMPONENT.NULL_GATE, nullGateComponent);
    registerCommands(ev.customCommandRegistry);
});
function welcome(p) {
    syncPlayerFog(p);
    syncExpanseFog(p);
    if (readEntity(p, DP.WELCOMED))
        return;
    writeEntity(p, DP.WELCOMED, true);
    p.sendMessage("§3§l[APOCALYPSE ENGINE]§r §7The Engine stirs beneath the world. Open the §bEngine Codex§7 (or type §f/apocalypse:codex§7) to begin.");
    if (config().giveCodex)
        giveItem(p, new ItemStack(ITEMS.ENGINE_CODEX, 1));
}
world.afterEvents.worldLoad.subscribe(() => {
    try {
        loadConfig();
        initBossRuntime();
        initEventRuntime();
        initEventDefs();
        initArmor();
        initExpanse();
        startScheduler();
        for (const p of world.getAllPlayers())
            welcome(p);
        log.debug("runtime initialised");
    }
    catch (e) {
        log.error("initialisation failed", e);
    }
});
world.afterEvents.playerSpawn.subscribe((ev) => {
    if (!ev.initialSpawn)
        return;
    const p = ev.player;
    system.runTimeout(() => {
        if (p.isValid)
            welcome(p);
    }, 40);
});
