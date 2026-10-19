// Minimal logger: warnings go to the content log; debug output is opt-in via the world config.
let debugEnabled = false;

export const log = {
  setDebug(on: boolean): void {
    debugEnabled = on;
  },
  debug(msg: string): void {
    if (debugEnabled) console.log(`[APOCALYPSE] ${msg}`);
  },
  warn(msg: string): void {
    console.warn(`[APOCALYPSE] ${msg}`);
  },
  error(msg: string, e?: unknown): void {
    const detail = e instanceof Error ? `${e.message}\n${e.stack ?? ""}` : e !== undefined ? String(e) : "";
    console.error(`[APOCALYPSE] ${msg} ${detail}`);
  },
};
