# APOCALYPSE ENGINE 1.0.0 — Release Notes

**For:** Minecraft Bedrock Edition 1.26.30 or newer (built against 1.26.50), Android first; the packs
use only cross-platform features. **No experimental toggles.**

## Highlights
- **Four colossal bosses** — The Hollow King, The Star Eater, The Root Titan and The Null Colossus —
  each with telegraphed attacks, three phases and unique loot.
- **Seven world events** — Blood Moon, Void Storm, Meteor Shower, Reality Fracture, Eclipse, Ancient
  Awakening, Corruption Surge — that genuinely change how a night (or day) plays out.
- **The Shattered Expanse**, a custom dimension of floating islands reached through Engine Key rifts.
- **Gear with abilities**: Rift Dash, Soul Reap, Earthsplitter, Gravity Crush, Star Bolt, Gravity Well,
  three armor sets with set bonuses, and an elixir that cleanses event afflictions.
- **Mobile-first**: Potato / Balanced / Enhanced texture subpacks plus matching gameplay performance
  profiles; Vibrant Visuals PBR on Balanced and Enhanced.
- **Engine Codex**: your journal, next objective, recipes and (for operators) all world settings.

## Downloads
| File | Use |
|---|---|
| `APOCALYPSE_ENGINE.mcaddon` | recommended — imports both packs |
| `APOCALYPSE_ENGINE_BEHAVIOR.mcpack` / `APOCALYPSE_ENGINE_TEXTURES.mcpack` | the two packs separately |
| `APOCALYPSE_ENGINE_SOURCE.zip` | full source; rebuild with `python3 build.py` |
| `APOCALYPSE_ENGINE_VALIDATION.txt` | what was verified, and what was not |
| `APOCALYPSE_ENGINE_INSTALLATION.txt` | Android install, configuration, troubleshooting, uninstall |

## Testing status
- Static validation: 0 errors (official Mojang schemas, references, vanilla ids, scripts).
- Automated tests: all passing — logic unit tests, strict mock-runtime simulation of every event,
  boss fight, item, the dimension and the UI (re-run under extra random seeds), save/reload, tooling.
- **Not yet played in Minecraft.** Please report problems with your game version and device.

## Known issues
- Balance is untuned by real play.
- The Expanse is generated around players with a time budget, so islands appear a moment after
  arrival on slow phones.
- If other add-ons use up the world's ticking-area capacity, the first trip to the Expanse may ask
  you to retry.
- Vibrant Visuals effects need a device and settings that support Vibrant Visuals. No shaders.
