// Minimal logger: warnings go to the content log; debug output is opt-in via the world config.
let debugEnabled = false;
export const log = {
    setDebug(on) {
        debugEnabled = on;
    },
    debug(msg) {
        if (debugEnabled)
            console.log(`[APOCALYPSE] ${msg}`);
    },
    warn(msg) {
        console.warn(`[APOCALYPSE] ${msg}`);
    },
    error(msg, e) {
        const detail = e instanceof Error ? `${e.message}\n${e.stack ?? ""}` : e !== undefined ? String(e) : "";
        console.error(`[APOCALYPSE] ${msg} ${detail}`);
    },
};
