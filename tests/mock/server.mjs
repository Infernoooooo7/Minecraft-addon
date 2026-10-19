// A strict, deterministic stand-in for the parts of @minecraft/server 2.8.0 that APOCALYPSE ENGINE uses.
// It is NOT the game: physics, AI and rendering are absent. What it does enforce, like the engine:
//  * identifiers: entities, spawn events, entity properties (type/range/enum), items, blocks, effects,
//    sounds, particles, fogs and structures must exist in the built packs or in vanilla data;
//  * execution modes: world access before worldLoad (early execution) and the documented
//    "can't be called in restricted-execution mode" APIs inside before-events and command callbacks;
//  * custom components: every component used in item/block JSON must be registered and vice versa;
//  * after-events are deferred to the end of the tick, projectiles fly ballistically, timers expire.
// Every violation is recorded in `mock.problems`, even when the add-on catches the thrown error.
import {
  BLOCK_DEFS, EFFECTS, ENTITY_DEFS, FOG_IDS, ITEM_DEFS, PARTICLE_IDS, SOUND_IDS, STRUCTURE_IDS, VANILLA_BLOCKS,
  VANILLA_ENTITIES, VANILLA_FAMILIES, VANILLA_ITEMS, VANILLA_SOUNDS,
} from "./content.mjs";

// ------------------------------------------------------------------------------------------------
// enums
// ------------------------------------------------------------------------------------------------

export const EntityComponentTypes = {
  Health: "minecraft:health", Inventory: "minecraft:inventory", Equippable: "minecraft:equippable",
  Projectile: "minecraft:projectile", TypeFamily: "minecraft:type_family",
};
export const EquipmentSlot = { Chest: "Chest", Feet: "Feet", Head: "Head", Legs: "Legs", Mainhand: "Mainhand", Offhand: "Offhand" };
export const GameMode = { Adventure: "Adventure", Creative: "Creative", Spectator: "Spectator", Survival: "Survival" };
export const PlayerPermissionLevel = { Visitor: 0, Member: 1, Operator: 2, Custom: 3 };
export const CommandPermissionLevel = { Any: 0, GameDirectors: 1, Admin: 2, Host: 3, Owner: 4 };
export const CustomCommandParamType = {
  BlockType: "BlockType", Boolean: "Boolean", EntitySelector: "EntitySelector", EntityType: "EntityType", Enum: "Enum",
  Float: "Float", Integer: "Integer", ItemType: "ItemType", Location: "Location", PlayerSelector: "PlayerSelector", String: "String",
};
export const CustomCommandStatus = { Success: 0, Failure: 1 };
export const CustomCommandSource = { Block: "Block", Entity: "Entity", NPCDialogue: "NPCDialogue", Server: "Server" };
export const WeatherType = { Clear: "Clear", Rain: "Rain", Thunder: "Thunder" };
export const EntityDamageCause = Object.fromEntries([
  "anvil", "blockExplosion", "campfire", "charging", "contact", "drowning", "entityAttack", "entityExplosion", "fall",
  "fallingBlock", "fire", "fireTick", "fireworks", "flyIntoWall", "freezing", "lava", "lightning", "maceSmash", "magic",
  "magma", "none", "override", "piston", "projectile", "ramAttack", "selfDestruct", "sonicBoom", "soulCampfire",
  "stalactite", "stalagmite", "starve", "suffocation", "temperature", "thorns", "wither",
].map((c) => [c, c]));

// ------------------------------------------------------------------------------------------------
// runtime state
// ------------------------------------------------------------------------------------------------

export const mock = {
  tick: 0,
  timeBase: 1000,
  problems: [],
  uncaught: [],
  log: { particles: [], sounds: [], commands: [], explosions: [], weather: [], messages: [], structures: [], cooldowns: [] },
  worldDP: new Map(),
  entities: new Map(),
  dims: new Map(),
  customDims: new Set(),
  itemComponents: new Map(),
  blockComponents: new Map(),
  commands: new Map(),
  enums: new Map(),
  tickingAreas: new Map(),
  restricted: 0,
  worldLoaded: false,
  pending: [],
  timers: [],
  jobs: [],
  nextTimer: 1,
  nextEntity: 1,
};

export function problem(msg) {
  mock.problems.push(msg);
  return new Error(msg);
}

/** APIs documented as "can't be called in restricted-execution mode" (index.d.ts 2.8.0). */
function guard(name) {
  if (!mock.worldLoaded) throw problem(`early execution: ${name} called before worldLoad`);
  if (mock.restricted > 0) throw problem(`restricted execution: ${name} called inside a before-event or command callback`);
}

function early(name) {
  if (!mock.worldLoaded) throw problem(`early execution: ${name} called before worldLoad`);
}

function finite(v, what) {
  if (!v || !Number.isFinite(v.x) || !Number.isFinite(v.y) || !Number.isFinite(v.z)) throw problem(`${what}: non-finite vector ${JSON.stringify(v)}`);
}

function invoke(name, fn, restricted) {
  if (restricted) mock.restricted++;
  try {
    return fn();
  } catch (e) {
    mock.uncaught.push(`${name}: ${e?.stack ?? e}`);
    return undefined;
  } finally {
    if (restricted) mock.restricted--;
  }
}

// ------------------------------------------------------------------------------------------------
// events
// ------------------------------------------------------------------------------------------------

class Signal {
  constructor(name, { filter, restricted = false } = {}) {
    this.name = name;
    this.filter = filter;
    this.restricted = restricted;
    this.subs = [];
  }

  subscribe(cb, options) {
    if (typeof cb !== "function") throw problem(`${this.name}.subscribe: callback is not a function`);
    this.subs.push({ cb, options });
    return cb;
  }

  unsubscribe(cb) {
    this.subs = this.subs.filter((s) => s.cb !== cb);
  }

  fire(ev) {
    for (const s of [...this.subs]) {
      if (this.filter && !this.filter(ev, s.options)) continue;
      invoke(this.name, () => s.cb(ev), this.restricted);
    }
  }
}

function entityFilter(get) {
  return (ev, o) => {
    if (!o) return true;
    const e = get(ev);
    if (o.entityTypes && !o.entityTypes.includes(e.typeId)) return false;
    if (o.entities && !o.entities.some((x) => x.id === e.id)) return false;
    if (o.entityFilter && !e._matches(o.entityFilter)) return false;
    if (o.allowedDamageCauses && !o.allowedDamageCauses.includes(ev.damageSource?.cause)) return false;
    return true;
  };
}

function signals(defs, restricted) {
  const known = Object.fromEntries(Object.entries(defs).map(([k, f]) => [k, new Signal(k, { filter: f, restricted })]));
  return new Proxy(known, {
    get(t, k) {
      if (typeof k !== "string") return undefined;
      if (!t[k]) t[k] = new Signal(k, { restricted });
      return t[k];
    },
  });
}

const afterEvents = signals({
  entityHurt: entityFilter((e) => e.hurtEntity),
  entityDie: entityFilter((e) => e.deadEntity),
  entitySpawn: undefined,
  entityLoad: undefined,
  entityRemove: undefined,
}, false);
const beforeEvents = signals({ entityHurt: entityFilter((e) => e.hurtEntity) }, true);

function emit(name, ev) {
  mock.pending.push([name, ev]);
}

export function flushEvents() {
  let guardN = 0;
  while (mock.pending.length && guardN++ < 10000) {
    const [name, ev] = mock.pending.shift();
    afterEvents[name].fire(ev);
  }
}

// ------------------------------------------------------------------------------------------------
// items
// ------------------------------------------------------------------------------------------------

function knownItem(id) {
  return ITEM_DEFS.has(id) || BLOCK_DEFS.has(id) || VANILLA_ITEMS.has(id);
}

export class ItemStack {
  constructor(type, amount = 1) {
    const id = typeof type === "string" ? type : type?.id;
    if (!knownItem(id)) throw problem(`ItemStack: unknown item type ${id}`);
    if (!Number.isInteger(amount) || amount < 1 || amount > 255) throw problem(`ItemStack: invalid amount ${amount} for ${id}`);
    this.typeId = id;
    this.amount = amount;
    this.enchantments = new Map();
    this.damage = 0;
    this.nameTag = undefined;
  }

  get maxAmount() {
    return ITEM_DEFS.get(this.typeId)?.["minecraft:max_stack_size"] ?? 64;
  }

  get isStackable() {
    return this.maxAmount > 1;
  }

  clone() {
    const c = new ItemStack(this.typeId, this.amount);
    c.enchantments = new Map(this.enchantments);
    c.damage = this.damage;
    c.nameTag = this.nameTag;
    return c;
  }

  hasTag(tag) {
    return this.getTags().includes(tag);
  }

  getTags() {
    const def = ITEM_DEFS.get(this.typeId);
    if (def) return def["minecraft:tags"]?.tags ?? [];
    const tags = [];
    for (const kind of ["pickaxe", "sword", "axe", "shovel", "hoe"]) if (this.typeId.endsWith(`_${kind}`)) tags.push(`minecraft:is_${kind}`);
    return tags;
  }

  getComponent(id) {
    const def = ITEM_DEFS.get(this.typeId) ?? {};
    const self = this;
    switch (id) {
      case "minecraft:cooldown": {
        const c = def["minecraft:cooldown"];
        if (!c) return undefined;
        return {
          cooldownCategory: c.category,
          cooldownTicks: Math.round(c.duration * 20),
          startCooldown(p) {
            p.startItemCooldown(c.category, Math.round(c.duration * 20));
          },
          getCooldownTicksRemaining(p) {
            return p.getItemCooldown(c.category);
          },
          isCooldownCategory: (cat) => cat === c.category,
        };
      }
      case "minecraft:durability": {
        const max = def["minecraft:durability"]?.max_durability ?? (this.getTags().length ? 250 : undefined);
        if (!max) return undefined;
        return {
          maxDurability: max,
          get damage() {
            return self.damage;
          },
          set damage(v) {
            if (!Number.isInteger(v) || v < 0 || v > max) throw problem(`durability.damage out of range: ${v}/${max}`);
            self.damage = v;
          },
        };
      }
      case "minecraft:enchantable":
        return {
          hasEnchantment: (t) => self.enchantments.has(typeof t === "string" ? t : t.id),
          getEnchantment: (t) => {
            const lvl = self.enchantments.get(typeof t === "string" ? t : t.id);
            return lvl ? { type: { id: t }, level: lvl } : undefined;
          },
          addEnchantment: (e) => self.enchantments.set(e.type.id ?? e.type, e.level),
          getEnchantments: () => [...self.enchantments].map(([k, v]) => ({ type: { id: k }, level: v })),
        };
      default:
        return undefined;
    }
  }
}

class Container {
  constructor(size) {
    this.size = size;
    this.slots = new Array(size).fill(undefined);
  }

  get emptySlotsCount() {
    return this.slots.filter((s) => !s).length;
  }

  getItem(i) {
    if (i < 0 || i >= this.size) throw problem(`container.getItem: slot ${i} out of range`);
    return this.slots[i]?.clone();
  }

  setItem(i, stack) {
    guard("Container.setItem");
    if (i < 0 || i >= this.size) throw problem(`container.setItem: slot ${i} out of range`);
    this.slots[i] = stack ? stack.clone() : undefined;
  }

  addItem(stack) {
    guard("Container.addItem");
    let left = stack.amount;
    for (let i = 0; i < this.size && left > 0; i++) {
      const s = this.slots[i];
      if (s && s.typeId === stack.typeId && s.amount < s.maxAmount) {
        const take = Math.min(left, s.maxAmount - s.amount);
        s.amount += take;
        left -= take;
      }
    }
    for (let i = 0; i < this.size && left > 0; i++) {
      if (!this.slots[i]) {
        const take = Math.min(left, stack.maxAmount);
        const c = stack.clone();
        c.amount = take;
        this.slots[i] = c;
        left -= take;
      }
    }
    if (left <= 0) return undefined;
    const rest = stack.clone();
    rest.amount = left;
    return rest;
  }

  count(typeId) {
    return this.slots.reduce((n, s) => n + (s?.typeId === typeId ? s.amount : 0), 0);
  }
}

// ------------------------------------------------------------------------------------------------
// entities
// ------------------------------------------------------------------------------------------------

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function matchesQuery(e, o = {}) {
  const fam = e._families;
  if (o.type && e.typeId !== o.type) return false;
  if (o.excludeTypes && o.excludeTypes.includes(e.typeId)) return false;
  if (o.families && !o.families.every((f) => fam.has(f))) return false;
  if (o.excludeFamilies && o.excludeFamilies.some((f) => fam.has(f))) return false;
  if (o.tags && !o.tags.every((t) => e._tags.has(t))) return false;
  if (o.excludeTags && o.excludeTags.some((t) => e._tags.has(t))) return false;
  if (o.name && e.nameTag !== o.name && e.name !== o.name) return false;
  if (o.location) {
    const d = dist(e._loc, o.location);
    if (o.maxDistance !== undefined && d > o.maxDistance) return false;
    if (o.minDistance !== undefined && d < o.minDistance) return false;
  }
  return true;
}

export class Entity {
  constructor(dim, typeId, loc) {
    this.id = String(-4294967296 * mock.nextEntity++ - 7);
    this.typeId = typeId;
    this._dim = dim;
    this._loc = { x: loc.x, y: loc.y, z: loc.z };
    this._valid = true;
    this._dead = false;
    this._tags = new Set();
    this._dp = new Map();
    this._effects = new Map();
    this._vel = { x: 0, y: 0, z: 0 };
    this._view = { x: 0, y: 0, z: 1 };
    this._nameTag = "";
    this._spawnTick = mock.tick;
    const def = ENTITY_DEFS.get(typeId);
    this._def = def;
    this._families = new Set(def ? def.families : VANILLA_FAMILIES[typeId] ?? []);
    this._props = new Map(Object.entries(def?.props ?? {}).map(([k, p]) => [k, p.default]));
    const h = def?.health ?? (VANILLA_FAMILIES[typeId] ? { value: 20, max: 20 } : null);
    this._maxHp = h ? h.max ?? h.value : 0;
    this._hp = h ? h.value : 0;
    this._groups = new Set();
    this._projectile = def?.projectile ? { owner: undefined, gravity: def.projectile.gravity ?? 0.05, flying: false } : null;
    this._knockback = [];
    mock.entities.set(this.id, this);
  }

  _check() {
    if (!this._valid) throw new Error("InvalidEntityError: entity is no longer valid");
  }

  get isValid() {
    return this._valid;
  }

  get location() {
    this._check();
    return { ...this._loc };
  }

  get dimension() {
    this._check();
    return this._dim;
  }

  get nameTag() {
    return this._nameTag;
  }

  set nameTag(v) {
    guard("Entity.nameTag");
    this._nameTag = v;
  }

  get isOnGround() {
    this._check();
    return this._dim.typeAt(this._loc.x, this._loc.y - 0.1, this._loc.z) !== "minecraft:air";
  }

  get isSneaking() {
    return false;
  }

  get isInWater() {
    return false;
  }

  get isFalling() {
    return !this.isOnGround;
  }

  _matches(f) {
    return matchesQuery(this, f);
  }

  matches(o) {
    this._check();
    return matchesQuery(this, o);
  }

  getViewDirection() {
    this._check();
    return { ...this._view };
  }

  getHeadLocation() {
    this._check();
    return { x: this._loc.x, y: this._loc.y + 1.62, z: this._loc.z };
  }

  getRotation() {
    return { x: 0, y: 0 };
  }

  getVelocity() {
    return { ...this._vel };
  }

  getBlockFromViewDirection(opts) {
    this._check();
    return this._dim.getBlockFromRay(this.getHeadLocation(), this._view, opts);
  }

  lookAt() {}

  setRotation() {}

  // effects ---------------------------------------------------------------------------------------
  addEffect(id, duration, opts = {}) {
    guard("Entity.addEffect");
    this._check();
    const name = String(id).replace(/^minecraft:/, "");
    if (!EFFECTS.has(name)) throw problem(`addEffect: unknown effect ${id}`);
    if (!Number.isInteger(duration) || duration < 1 || duration > 20000000) throw problem(`addEffect(${id}): invalid duration ${duration}`);
    const amp = opts.amplifier ?? 0;
    if (!Number.isInteger(amp) || amp < 0 || amp > 255) throw problem(`addEffect(${id}): invalid amplifier ${amp}`);
    this._effects.set(name, { typeId: name, amplifier: amp, until: mock.tick + duration });
    return this.getEffect(name);
  }

  getEffect(id) {
    const name = String(id).replace(/^minecraft:/, "");
    const e = this._effects.get(name);
    if (!e || e.until <= mock.tick) return undefined;
    return { typeId: name, amplifier: e.amplifier, duration: e.until - mock.tick, displayName: name, isValid: true };
  }

  getEffects() {
    return [...this._effects.keys()].map((k) => this.getEffect(k)).filter(Boolean);
  }

  removeEffect(id) {
    guard("Entity.removeEffect");
    const name = String(id).replace(/^minecraft:/, "");
    if (!EFFECTS.has(name)) throw problem(`removeEffect: unknown effect ${id}`);
    return this._effects.delete(name);
  }

  // tags & dynamic properties ---------------------------------------------------------------------
  addTag(t) {
    guard("Entity.addTag");
    this._tags.add(t);
    return true;
  }

  removeTag(t) {
    guard("Entity.removeTag");
    return this._tags.delete(t);
  }

  hasTag(t) {
    return this._tags.has(t);
  }

  getTags() {
    return [...this._tags];
  }

  getDynamicProperty(k) {
    this._check();
    return this._dp.get(k);
  }

  setDynamicProperty(k, v) {
    this._check();
    checkDP(k, v);
    if (v === undefined) this._dp.delete(k);
    else this._dp.set(k, v);
  }

  getDynamicPropertyIds() {
    return [...this._dp.keys()];
  }

  // entity properties & events --------------------------------------------------------------------
  getProperty(id) {
    this._check();
    if (!this._props.has(id)) throw problem(`getProperty: ${this.typeId} does not declare ${id}`);
    return this._props.get(id);
  }

  setProperty(id, v) {
    guard("Entity.setProperty");
    this._check();
    const p = this._def?.props?.[id];
    if (!p) throw problem(`setProperty: ${this.typeId} does not declare ${id}`);
    if (p.type === "int" && (!Number.isInteger(v) || v < p.range[0] || v > p.range[1])) throw problem(`setProperty(${id}) int out of range: ${v}`);
    if (p.type === "float" && (typeof v !== "number" || v < p.range[0] || v > p.range[1])) throw problem(`setProperty(${id}) float out of range: ${v}`);
    if (p.type === "bool" && typeof v !== "boolean") throw problem(`setProperty(${id}) expects a boolean, got ${v}`);
    if (p.type === "enum" && !p.values.includes(v)) throw problem(`setProperty(${id}) invalid enum value ${v}`);
    this._props.set(id, v);
  }

  triggerEvent(name) {
    guard("Entity.triggerEvent");
    this._check();
    this._applyEvent(name);
  }

  _applyEvent(name) {
    const ev = this._def?.events?.[name];
    if (!ev) throw problem(`triggerEvent: ${this.typeId} has no event ${name}`);
    for (const g of ev.add?.component_groups ?? []) {
      const group = this._def.groups[g];
      if (!group) throw problem(`event ${name} adds missing component group ${g}`);
      this._groups.add(g);
      if (group["minecraft:health"]) {
        this._maxHp = group["minecraft:health"].max ?? group["minecraft:health"].value;
        this._hp = Math.min(this._hp, this._maxHp);
      }
      if (group["minecraft:instant_despawn"]) later(1, () => this._valid && this._despawn());
    }
    for (const [k, v] of Object.entries(ev.set_property ?? {})) {
      if (!this._def.props[k]) throw problem(`event ${name} sets undeclared property ${k}`);
      this._props.set(k, v);
    }
  }

  // components ------------------------------------------------------------------------------------
  getComponent(id) {
    this._check();
    const self = this;
    switch (id) {
      case "minecraft:health":
      case "health":
        if (!this._maxHp) return undefined;
        return {
          get currentValue() {
            return self._hp;
          },
          get effectiveMax() {
            return self._maxHp;
          },
          get defaultValue() {
            return self._maxHp;
          },
          effectiveMin: 0,
          setCurrentValue(v) {
            guard("EntityHealthComponent.setCurrentValue");
            self._hp = Math.max(0, Math.min(self._maxHp, v));
            return true;
          },
          resetToMaxValue() {
            guard("EntityHealthComponent.resetToMaxValue");
            self._hp = self._maxHp;
          },
        };
      case "minecraft:projectile":
      case "projectile":
        if (!this._projectile) return undefined;
        return {
          get owner() {
            return self._projectile.owner;
          },
          set owner(v) {
            self._projectile.owner = v;
          },
          get gravity() {
            return self._projectile.gravity;
          },
          set gravity(v) {
            self._projectile.gravity = v;
          },
          shoot(velocity, _opts) {
            guard("EntityProjectileComponent.shoot");
            finite(velocity, "shoot");
            self._vel = { ...velocity };
            self._projectile.flying = true;
          },
        };
      case "minecraft:type_family":
        return { getTypeFamilies: () => [...this._families], hasTypeFamily: (f) => this._families.has(f) };
      default:
        return undefined;
    }
  }

  hasComponent(id) {
    return !!this.getComponent(id);
  }

  // damage & movement -----------------------------------------------------------------------------
  applyDamage(amount, opts = {}) {
    guard("Entity.applyDamage");
    this._check();
    if (!Number.isFinite(amount) || amount < 0) throw problem(`applyDamage: invalid amount ${amount}`);
    if (opts.cause && !EntityDamageCause[opts.cause]) throw problem(`applyDamage: unknown cause ${opts.cause}`);
    return hurtEntity(this, amount, { cause: opts.cause ?? "none", damagingEntity: opts.damagingEntity });
  }

  applyKnockback(xz, vertical) {
    guard("Entity.applyKnockback");
    this._check();
    if (!Number.isFinite(xz?.x) || !Number.isFinite(xz?.z) || !Number.isFinite(vertical)) throw problem("applyKnockback: non-finite");
    this._knockback.push({ x: xz.x, z: xz.z, y: vertical });
  }

  applyImpulse(v) {
    guard("Entity.applyImpulse");
    this._check();
    finite(v, "applyImpulse");
    this._vel = { x: this._vel.x + v.x, y: this._vel.y + v.y, z: this._vel.z + v.z };
  }

  clearVelocity() {
    guard("Entity.clearVelocity");
    this._vel = { x: 0, y: 0, z: 0 };
  }

  teleport(loc, opts = {}) {
    guard("Entity.teleport");
    this._check();
    finite(loc, "teleport");
    const from = this._dim;
    const fromLoc = this._loc;
    if (opts.dimension && opts.dimension !== this._dim) this._dim = opts.dimension;
    this._loc = { x: loc.x, y: loc.y, z: loc.z };
    if (this instanceof Player && from !== this._dim) {
      emit("playerDimensionChange", { player: this, fromDimension: from, fromLocation: fromLoc, toDimension: this._dim, toLocation: { ...this._loc } });
    }
  }

  tryTeleport(loc, opts = {}) {
    guard("Entity.tryTeleport");
    finite(loc, "tryTeleport");
    if (opts.checkForBlocks && this._dim.typeAt(loc.x, loc.y, loc.z) !== "minecraft:air") return false;
    this.teleport(loc, opts);
    return true;
  }

  remove() {
    guard("Entity.remove");
    this._check();
    this._despawn();
  }

  _despawn() {
    if (!this._valid) return;
    this._valid = false;
    emit("entityRemove", { removedEntityId: this.id, typeId: this.typeId });
  }

  kill() {
    guard("Entity.kill");
    this._check();
    die(this, { cause: "override" });
    return true;
  }

  runCommand(cmd) {
    guard("Entity.runCommand");
    this._check();
    return runCommandText(cmd, this);
  }

  setOnFire() {
    guard("Entity.setOnFire");
    return true;
  }

  extinguishFire() {
    guard("Entity.extinguishFire");
    return true;
  }
}

function checkDP(k, v) {
  if (typeof k !== "string" || !k.includes(":")) throw problem(`dynamic property id should be namespaced: ${k}`);
  const ok = v === undefined || typeof v === "string" || typeof v === "number" || typeof v === "boolean" ||
    (typeof v === "object" && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z));
  if (!ok) throw problem(`dynamic property ${k}: unsupported value ${typeof v}`);
  if (typeof v === "string" && v.length > 32767) throw problem(`dynamic property ${k}: string too long (${v.length})`);
  if (typeof v === "number" && !Number.isFinite(v)) throw problem(`dynamic property ${k}: non-finite number`);
}

function hurtEntity(e, amount, source) {
  if (e._dead || !e._maxHp) return false;
  const before = { hurtEntity: e, damage: amount, damageSource: source, cancel: false };
  beforeEvents.entityHurt.fire(before);
  if (before.cancel) return false;
  const dmg = Math.max(0, before.damage);
  if (e instanceof Player && e._gameMode === GameMode.Creative) return false;
  e._hp = Math.max(0, e._hp - dmg);
  emit("entityHurt", { hurtEntity: e, damage: dmg, damageSource: source });
  if (e._hp <= 0) die(e, source);
  return true;
}

function die(e, source) {
  if (e._dead) return;
  e._dead = true;
  e._hp = 0;
  emit("entityDie", { deadEntity: e, damageSource: source });
  if (e instanceof Player) {
    later(40, () => {
      e._dead = false;
      e._hp = e._maxHp;
    });
  } else {
    later(20, () => e._despawn());
  }
}

export class Player extends Entity {
  constructor(dim, name, loc) {
    super(dim, "minecraft:player", loc);
    this.name = name;
    this._gameMode = GameMode.Survival;
    this.playerPermissionLevel = PlayerPermissionLevel.Operator;
    this.commandPermissionLevel = CommandPermissionLevel.GameDirectors;
    this.inventory = new Container(36);
    this.armor = {};
    this.selectedSlotIndex = 0;
    this.level = 0;
    this.xp = 0;
    this.messages = [];
    this.titles = [];
    this.actionbars = [];
    this.sounds = [];
    this.cooldowns = new Map();
    this.spawnPoint = undefined;
    const self = this;
    this.onScreenDisplay = {
      setTitle(t, o) {
        guard("ScreenDisplay.setTitle");
        self.titles.push({ title: t, subtitle: o?.subtitle });
      },
      setActionBar(t) {
        guard("ScreenDisplay.setActionBar");
        self.actionbars.push(t);
      },
    };
  }

  getGameMode() {
    return this._gameMode;
  }

  setGameMode(m) {
    guard("Player.setGameMode");
    this._gameMode = m;
  }

  getComponent(id) {
    if (id === "minecraft:inventory" || id === "inventory") return { container: this.inventory };
    if (id === "minecraft:equippable" || id === "equippable") {
      return {
        getEquipment: (slot) => (slot === EquipmentSlot.Mainhand ? this.inventory.getItem(this.selectedSlotIndex) : this.armor[slot]?.clone()),
        setEquipment: (slot, stack) => {
          guard("EntityEquippableComponent.setEquipment");
          if (slot === EquipmentSlot.Mainhand) this.inventory.setItem(this.selectedSlotIndex, stack);
          else this.armor[slot] = stack?.clone();
          return true;
        },
      };
    }
    return super.getComponent(id);
  }

  playSound(id, _opts) {
    guard("Player.playSound");
    checkSound(id);
    this.sounds.push(id);
  }

  sendMessage(m) {
    this.messages.push(typeof m === "string" ? m : JSON.stringify(m));
  }

  addLevels(n) {
    guard("Player.addLevels");
    this.level += n;
    return this.level;
  }

  addExperience(n) {
    guard("Player.addExperience");
    this.xp += n;
    return this.xp;
  }

  getSpawnPoint() {
    return this.spawnPoint;
  }

  startItemCooldown(cat, ticks) {
    guard("Player.startItemCooldown");
    if (!Number.isInteger(ticks) || ticks < 0) throw problem(`startItemCooldown: invalid ticks ${ticks}`);
    this.cooldowns.set(cat, mock.tick + ticks);
    mock.log.cooldowns.push({ player: this.name, cat, ticks });
  }

  getItemCooldown(cat) {
    return Math.max(0, (this.cooldowns.get(cat) ?? 0) - mock.tick);
  }

  spawnParticle(id, loc) {
    guard("Player.spawnParticle");
    checkParticle(id);
    finite(loc, "Player.spawnParticle");
  }
}

// ------------------------------------------------------------------------------------------------
// blocks & dimensions
// ------------------------------------------------------------------------------------------------

const PASSABLE = new Set(["minecraft:air", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:poppy",
  "minecraft:dandelion", "minecraft:snow_layer", "apocalypse:blight_sprout", "apocalypse:aether_cluster"]);

function knownBlock(id) {
  return id === "minecraft:air" || BLOCK_DEFS.has(id) || VANILLA_BLOCKS.has(id);
}

export class BlockVolume {
  constructor(from, to) {
    this.from = { ...from };
    this.to = { ...to };
  }

  getCapacity() {
    return (Math.abs(this.to.x - this.from.x) + 1) * (Math.abs(this.to.y - this.from.y) + 1) * (Math.abs(this.to.z - this.from.z) + 1);
  }
}

class Block {
  constructor(dim, x, y, z) {
    this.dimension = dim;
    this.x = Math.floor(x);
    this.y = Math.floor(y);
    this.z = Math.floor(z);
    this.isValid = true;
  }

  get location() {
    return { x: this.x, y: this.y, z: this.z };
  }

  get typeId() {
    return this.dimension.typeAt(this.x, this.y, this.z);
  }

  get type() {
    return { id: this.typeId };
  }

  get permutation() {
    const id = this.typeId;
    return { type: { id }, matches: (n) => n === id, getAllStates: () => ({}) };
  }

  get isAir() {
    return this.typeId === "minecraft:air";
  }

  get isLiquid() {
    return this.typeId === "minecraft:water" || this.typeId === "minecraft:lava";
  }

  offset(v) {
    return new Block(this.dimension, this.x + v.x, this.y + v.y, this.z + v.z);
  }

  above(n = 1) {
    return this.offset({ x: 0, y: n, z: 0 });
  }

  below(n = 1) {
    return this.offset({ x: 0, y: -n, z: 0 });
  }

  north(n = 1) {
    return this.offset({ x: 0, y: 0, z: -n });
  }

  south(n = 1) {
    return this.offset({ x: 0, y: 0, z: n });
  }

  east(n = 1) {
    return this.offset({ x: n, y: 0, z: 0 });
  }

  west(n = 1) {
    return this.offset({ x: -n, y: 0, z: 0 });
  }

  center() {
    return { x: this.x + 0.5, y: this.y + 0.5, z: this.z + 0.5 };
  }

  bottomCenter() {
    return { x: this.x + 0.5, y: this.y, z: this.z + 0.5 };
  }

  setType(t) {
    guard("Block.setType");
    this.dimension._set(this.x, this.y, this.z, typeof t === "string" ? t : t.id);
  }

  hasTag() {
    return false;
  }

  getTags() {
    return [];
  }
}

const k3 = (x, y, z) => `${Math.floor(x)},${Math.floor(y)},${Math.floor(z)}`;

export class Dimension {
  constructor(id, terrain) {
    this.id = id;
    this.terrain = terrain;
    this.blocks = new Map();
    this.heightRange = { min: -64, max: 320 };
    this.weather = WeatherType.Clear;
    this.localizationKey = id;
  }

  typeAt(x, y, z) {
    const o = this.blocks.get(k3(x, y, z));
    return o ?? this.terrain(Math.floor(x), Math.floor(y), Math.floor(z));
  }

  _set(x, y, z, id) {
    if (!knownBlock(id)) throw problem(`unknown block type ${id}`);
    if (y < this.heightRange.min || y >= this.heightRange.max) throw problem(`block outside height range: ${y}`);
    this.blocks.set(k3(x, y, z), id);
  }

  getBlock(loc) {
    early("Dimension.getBlock");
    finite(loc, "getBlock");
    return new Block(this, loc.x, loc.y, loc.z);
  }

  getTopmostBlock(xz, minHeight) {
    early("Dimension.getTopmostBlock");
    if (!Number.isFinite(xz?.x) || !Number.isFinite(xz?.z)) throw problem("getTopmostBlock: non-finite xz");
    const start = Math.min(this.heightRange.max - 1, Math.floor(minHeight ?? this.heightRange.max - 1));
    for (let y = start; y >= this.heightRange.min; y--) {
      if (this.typeAt(xz.x, y, xz.z) !== "minecraft:air") return new Block(this, xz.x, y, xz.z);
    }
    return undefined;
  }

  getBlockFromRay(origin, dir, opts = {}) {
    early("Dimension.getBlockFromRay");
    finite(origin, "getBlockFromRay origin");
    finite(dir, "getBlockFromRay dir");
    const max = opts.maxDistance ?? 64;
    const l = Math.hypot(dir.x, dir.y, dir.z) || 1;
    for (let t = 0; t <= max; t += 0.1) {
      const p = { x: origin.x + (dir.x / l) * t, y: origin.y + (dir.y / l) * t, z: origin.z + (dir.z / l) * t };
      const id = this.typeAt(p.x, p.y, p.z);
      if (id === "minecraft:air") continue;
      if (!opts.includePassableBlocks && PASSABLE.has(id)) continue;
      if (!opts.includeLiquidBlocks && (id === "minecraft:water" || id === "minecraft:lava")) continue;
      return { block: new Block(this, p.x, p.y, p.z), face: "Up", faceLocation: { x: 0.5, y: 1, z: 0.5 } };
    }
    return undefined;
  }

  setBlockType(loc, type) {
    guard("Dimension.setBlockType");
    finite(loc, "setBlockType");
    this._set(loc.x, loc.y, loc.z, typeof type === "string" ? type : type.id);
  }

  fillBlocks(volume, type, _opts) {
    guard("Dimension.fillBlocks");
    const id = typeof type === "string" ? type : type.id;
    if (!knownBlock(id)) throw problem(`fillBlocks: unknown block type ${id}`);
    const cap = volume.getCapacity();
    if (cap > 32768) throw problem(`fillBlocks: volume too large (${cap})`);
    const [x0, x1] = [Math.min(volume.from.x, volume.to.x), Math.max(volume.from.x, volume.to.x)];
    const [y0, y1] = [Math.min(volume.from.y, volume.to.y), Math.max(volume.from.y, volume.to.y)];
    const [z0, z1] = [Math.min(volume.from.z, volume.to.z), Math.max(volume.from.z, volume.to.z)];
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++) this._set(x, y, z, id);
    return { getCapacity: () => cap };
  }

  isChunkLoaded() {
    return true;
  }

  spawnEntity(type, loc, opts = {}) {
    guard("Dimension.spawnEntity");
    finite(loc, "spawnEntity");
    const id = typeof type === "string" ? type : type.id;
    if (!ENTITY_DEFS.has(id) && !VANILLA_ENTITIES.has(id)) throw problem(`spawnEntity: unknown entity type ${id}`);
    if (id === "minecraft:player") throw problem("spawnEntity: cannot spawn players");
    const e = new Entity(this, id, loc);
    if (opts.spawnEvent) {
      if (!ENTITY_DEFS.get(id)?.events?.[opts.spawnEvent]) throw problem(`spawnEntity(${id}): unknown spawn event ${opts.spawnEvent}`);
      e._applyEvent(opts.spawnEvent);
    }
    if (e._def?.timer) {
      const t = e._def.timer;
      later(Math.round(t.time * 20), () => {
        if (e._valid && !e._dead) e._applyEvent(t.time_down_event.event);
      });
    }
    emit("entitySpawn", { entity: e, cause: "Spawned" });
    return e;
  }

  spawnItem(stack, loc) {
    guard("Dimension.spawnItem");
    finite(loc, "spawnItem");
    if (!(stack instanceof ItemStack)) throw problem("spawnItem: not an ItemStack");
    const e = new Entity(this, "minecraft:item", loc);
    e.itemStack = stack.clone();
    return e;
  }

  spawnParticle(id, loc, vars) {
    guard("Dimension.spawnParticle");
    checkParticle(id);
    finite(loc, "spawnParticle");
    mock.log.particles.push({ id, loc: { ...loc }, vars: vars?.values ? { ...vars.values } : undefined, dim: this.id, tick: mock.tick });
  }

  playSound(id, loc, _opts) {
    guard("Dimension.playSound");
    checkSound(id);
    finite(loc, "playSound");
    mock.log.sounds.push({ id, loc: { ...loc }, tick: mock.tick });
  }

  getEntities(o = {}) {
    early("Dimension.getEntities");
    return [...mock.entities.values()].filter((e) => e._valid && e._dim === this && !(e instanceof Player) && matchesQuery(e, o))
      .concat(o.type === "minecraft:player" || !o.type ? this.getPlayers(o) : []);
  }

  getPlayers(o = {}) {
    early("Dimension.getPlayers");
    return [...mock.entities.values()].filter((e) => e instanceof Player && e._valid && e._dim === this && matchesQuery(e, o));
  }

  createExplosion(loc, radius, opts = {}) {
    guard("Dimension.createExplosion");
    finite(loc, "createExplosion");
    mock.log.explosions.push({ loc: { ...loc }, radius, breaksBlocks: !!opts.breaksBlocks, dim: this.id });
    return true;
  }

  setWeather(t, duration) {
    guard("Dimension.setWeather");
    if (!WeatherType[t]) throw problem(`setWeather: unknown weather ${t}`);
    this.weather = t;
    mock.log.weather.push({ t, duration, dim: this.id });
  }

  runCommand(cmd) {
    guard("Dimension.runCommand");
    return runCommandText(cmd, undefined);
  }
}

function checkParticle(id) {
  if (!PARTICLE_IDS.has(id) && !String(id).startsWith("minecraft:")) throw problem(`unknown particle ${id}`);
}

function checkSound(id) {
  if (!SOUND_IDS.has(id) && !VANILLA_SOUNDS.has(id)) throw problem(`unknown sound ${id}`);
}

function runCommandText(cmd, entity) {
  mock.log.commands.push({ cmd, entity: entity?.name ?? entity?.typeId });
  const parts = cmd.trim().split(/\s+/);
  if (parts[0] === "fog") {
    if (!["push", "pop", "remove"].includes(parts[2])) throw problem(`fog: bad mode in "${cmd}"`);
    if (parts[2] === "push" && !FOG_IDS.has(parts[3])) throw problem(`fog: unknown fog id ${parts[3]}`);
    if (parts[2] === "push" && entity instanceof Player) entity._fogs = [...(entity._fogs ?? []).filter((f) => f.user !== parts[4]), { id: parts[3], user: parts[4] }];
    if (parts[2] === "remove" && entity instanceof Player) entity._fogs = (entity._fogs ?? []).filter((f) => f.user !== parts[3]);
  } else if (parts[0] === "camerashake") {
    if (parts[1] !== "add" || !(Number(parts[3]) >= 0 && Number(parts[3]) <= 4) || !(Number(parts[4]) > 0)) throw problem(`camerashake: bad syntax "${cmd}"`);
  } else {
    throw problem(`unexpected command "${cmd}"`);
  }
  return { successCount: 1 };
}

export class MolangVariableMap {
  constructor() {
    this.values = {};
  }

  setFloat(name, v) {
    if (!/^variable\.[a-z_]+$/.test(name) || !Number.isFinite(v)) throw problem(`MolangVariableMap.setFloat(${name}, ${v})`);
    this.values[name] = v;
  }

  setColorRGB(name, c) {
    this.values[name] = c;
  }

  setColorRGBA(name, c) {
    this.values[name] = c;
  }

  setVector3(name, v) {
    this.values[name] = v;
  }
}

// ------------------------------------------------------------------------------------------------
// world & system
// ------------------------------------------------------------------------------------------------

const overworldTerrain = (_x, y) => (y < 63 ? "minecraft:dirt" : y === 63 ? "minecraft:grass_block" : "minecraft:air");
mock.dims.set("minecraft:overworld", new Dimension("minecraft:overworld", overworldTerrain));
mock.dims.set("minecraft:nether", new Dimension("minecraft:nether", (_x, y) => (y < 40 ? "minecraft:netherrack" : "minecraft:air")));
mock.dims.set("minecraft:the_end", new Dimension("minecraft:the_end", () => "minecraft:air"));

export const world = {
  afterEvents,
  beforeEvents,
  get seed() {
    return "4242";
  },
  getDimension(id) {
    early("World.getDimension");
    const d = mock.dims.get(id);
    if (!d) throw problem(`getDimension: unknown dimension ${id}`);
    return d;
  },
  getAllPlayers() {
    early("World.getAllPlayers");
    return [...mock.entities.values()].filter((e) => e instanceof Player && e._valid);
  },
  getPlayers(o) {
    return this.getAllPlayers().filter((p) => matchesQuery(p, o));
  },
  getEntity(id) {
    const e = mock.entities.get(id);
    return e?._valid ? e : undefined;
  },
  getAbsoluteTime() {
    early("World.getAbsoluteTime");
    return mock.timeBase + mock.tick;
  },
  getTimeOfDay() {
    early("World.getTimeOfDay");
    return (mock.timeBase + mock.tick) % 24000;
  },
  setTimeOfDay(t) {
    guard("World.setTimeOfDay");
    setTime(t);
  },
  getDay() {
    early("World.getDay");
    return Math.floor((mock.timeBase + mock.tick) / 24000);
  },
  getDynamicProperty(k) {
    early("World.getDynamicProperty");
    return mock.worldDP.get(k);
  },
  setDynamicProperty(k, v) {
    early("World.setDynamicProperty");
    checkDP(k, v);
    if (v === undefined) mock.worldDP.delete(k);
    else mock.worldDP.set(k, v);
  },
  getDynamicPropertyIds() {
    return [...mock.worldDP.keys()];
  },
  sendMessage(m) {
    mock.log.messages.push(typeof m === "string" ? m : JSON.stringify(m));
  },
  getDefaultSpawnLocation() {
    return { x: 0, y: 32767, z: 0 };
  },
  structureManager: {
    place(id, dim, loc, _opts) {
      guard("StructureManager.place");
      const sid = typeof id === "string" ? id : id.id;
      if (!STRUCTURE_IDS.has(sid)) throw problem(`structure ${sid} not found in the behavior pack`);
      finite(loc, "structure place");
      mock.log.structures.push({ id: sid, dim: dim.id, loc: { ...loc } });
    },
  },
  tickingAreaManager: {
    maxChunkCount: 400,
    get chunkCount() {
      return [...mock.tickingAreas.values()].reduce((n, a) => n + a.chunks, 0);
    },
    hasTickingArea(id) {
      guard("TickingAreaManager.hasTickingArea");
      return mock.tickingAreas.has(id);
    },
    hasCapacity(o) {
      guard("TickingAreaManager.hasCapacity");
      return this.chunkCount + chunksOf(o) <= this.maxChunkCount;
    },
    createTickingArea(id, o) {
      guard("TickingAreaManager.createTickingArea");
      if (mock.tickingAreas.has(id)) return Promise.reject(problem(`ticking area ${id} already exists`));
      finite(o.from, "ticking area from");
      finite(o.to, "ticking area to");
      mock.tickingAreas.set(id, { ...o, chunks: chunksOf(o) });
      return new Promise((resolve) => later(3, resolve));
    },
    removeTickingArea(id) {
      guard("TickingAreaManager.removeTickingArea");
      mock.tickingAreas.delete(typeof id === "string" ? id : id.identifier);
    },
    getAllTickingAreas() {
      return [...mock.tickingAreas.keys()];
    },
  },
};

function chunksOf(o) {
  const cx = Math.floor(Math.max(o.from.x, o.to.x) / 16) - Math.floor(Math.min(o.from.x, o.to.x) / 16) + 1;
  const cz = Math.floor(Math.max(o.from.z, o.to.z) / 16) - Math.floor(Math.min(o.from.z, o.to.z) / 16) + 1;
  return cx * cz;
}

function later(ticks, cb) {
  const id = mock.nextTimer++;
  mock.timers.push({ id, at: mock.tick + Math.max(1, Math.round(ticks)), cb });
  return id;
}

const startupSignal = new Signal("system.beforeEvents.startup");

export const system = {
  get currentTick() {
    return mock.tick;
  },
  isEditorWorld: false,
  beforeEvents: { startup: startupSignal },
  afterEvents: signals({}, false),
  run(cb) {
    return later(1, cb);
  },
  runTimeout(cb, d = 1) {
    return later(d, cb);
  },
  runInterval(cb, i = 1) {
    const id = mock.nextTimer++;
    mock.timers.push({ id, at: mock.tick + Math.max(1, i), cb, interval: Math.max(1, i) });
    return id;
  },
  clearRun(id) {
    mock.timers = mock.timers.filter((t) => t.id !== id);
  },
  runJob(gen) {
    const id = mock.nextTimer++;
    mock.jobs.push({ id, gen });
    return id;
  },
  clearJob(id) {
    mock.jobs = mock.jobs.filter((j) => j.id !== id);
  },
  waitTicks(n) {
    return new Promise((resolve) => later(n, resolve));
  },
};

// ------------------------------------------------------------------------------------------------
// test driver
// ------------------------------------------------------------------------------------------------

export function setTime(timeOfDay) {
  const abs = mock.timeBase + mock.tick;
  const day = Math.floor(abs / 24000);
  mock.timeBase = day * 24000 + timeOfDay - mock.tick;
}

export function setDay(day) {
  const tod = (mock.timeBase + mock.tick) % 24000;
  mock.timeBase = day * 24000 + tod - mock.tick;
}

function stepProjectiles() {
  for (const e of [...mock.entities.values()]) {
    if (!e._valid || !e._projectile?.flying) continue;
    const p = e._projectile;
    const next = { x: e._loc.x + e._vel.x, y: e._loc.y + e._vel.y, z: e._loc.z + e._vel.z };
    e._vel.y -= p.gravity;
    const steps = Math.max(1, Math.ceil(Math.hypot(e._vel.x, e._vel.y, e._vel.z) / 0.25));
    let hit = null;
    for (let i = 1; i <= steps && !hit; i++) {
      const q = { x: e._loc.x + ((next.x - e._loc.x) * i) / steps, y: e._loc.y + ((next.y - e._loc.y) * i) / steps, z: e._loc.z + ((next.z - e._loc.z) * i) / steps };
      const victim = [...mock.entities.values()].find((o) => o._valid && o !== e && o !== p.owner && o._maxHp && !o._dead &&
        o._dim === e._dim && Math.hypot(o._loc.x - q.x, o._loc.y + 0.9 - q.y, o._loc.z - q.z) < 0.9);
      if (victim) hit = { kind: "entity", at: q, victim };
      else if (!PASSABLE.has(e._dim.typeAt(q.x, q.y, q.z))) hit = { kind: "block", at: q };
    }
    if (!hit) {
      e._loc = next;
      if (next.y < e._dim.heightRange.min) e._despawn();
      continue;
    }
    e._loc = hit.at;
    p.flying = false;
    const dim = e._dim;
    if (hit.kind === "entity") {
      const dmg = e._def?.projectile?.on_hit?.impact_damage?.damage ?? 0;
      if (dmg) hurtEntity(hit.victim, dmg, { cause: "projectile", damagingEntity: p.owner, damagingProjectile: e });
      emit("projectileHitEntity", { dimension: dim, location: { ...hit.at }, hitVector: { ...e._vel }, projectile: e, source: p.owner, getEntityHit: () => ({ entity: hit.victim }) });
    } else {
      const block = new Block(dim, hit.at.x, hit.at.y, hit.at.z);
      emit("projectileHitBlock", { dimension: dim, location: { ...hit.at }, hitVector: { ...e._vel }, projectile: e, source: p.owner, getBlockHit: () => ({ block, face: "Up", faceLocation: { x: 0.5, y: 1, z: 0.5 } }) });
    }
    if (e._def?.projectile?.on_hit?.remove_on_hit) later(1, () => e._despawn());
  }
}

/** Advance the simulation one tick: timers, jobs, projectiles, then deferred after-events. */
export function step() {
  mock.tick++;
  const due = mock.timers.filter((t) => t.at <= mock.tick).sort((a, b) => a.at - b.at || a.id - b.id);
  for (const t of due) {
    if (t.interval) t.at += t.interval;
    else mock.timers.splice(mock.timers.indexOf(t), 1);
    invoke(`timer#${t.id}`, t.cb, false);
  }
  for (const j of [...mock.jobs]) {
    for (let i = 0; i < 8; i++) {
      let r;
      try {
        r = j.gen.next();
      } catch (e) {
        mock.uncaught.push(`job: ${e.stack}`);
        r = { done: true };
      }
      if (r.done) {
        mock.jobs.splice(mock.jobs.indexOf(j), 1);
        break;
      }
    }
  }
  stepProjectiles();
  flushEvents();
}

export async function run(ticks) {
  for (let i = 0; i < ticks; i++) {
    step();
    await new Promise((r) => setImmediate(r));
  }
}

export function addPlayer(name, loc = { x: 0, y: 64, z: 0 }, dimId = "minecraft:overworld") {
  const p = new Player(mock.dims.get(dimId), name, loc);
  return p;
}

export function join(p) {
  emit("playerSpawn", { player: p, initialSpawn: true });
}

/** Fire startup (registrations, custom dimensions), check component coverage, then worldLoad. */
export function boot() {
  const startup = {
    itemComponentRegistry: {
      registerCustomComponent(name, comp) {
        if (!/^[a-z0-9_]+:[a-z0-9_]+$/.test(name)) throw problem(`item component name ${name} is not namespaced`);
        if (mock.itemComponents.has(name)) throw problem(`item component ${name} registered twice`);
        mock.itemComponents.set(name, comp);
      },
    },
    blockComponentRegistry: {
      registerCustomComponent(name, comp) {
        if (!/^[a-z0-9_]+:[a-z0-9_]+$/.test(name)) throw problem(`block component name ${name} is not namespaced`);
        if (mock.blockComponents.has(name)) throw problem(`block component ${name} registered twice`);
        mock.blockComponents.set(name, comp);
      },
    },
    customCommandRegistry: {
      registerEnum(name, values) {
        if (!/^[a-z0-9_]+:[a-z0-9_]+$/.test(name)) throw problem(`command enum ${name} must be namespaced`);
        if (!Array.isArray(values) || !values.length || values.some((v) => typeof v !== "string" || !v)) throw problem(`enum ${name}: bad values`);
        mock.enums.set(name, values);
      },
      registerCommand(def, cb) {
        if (!/^[a-z0-9_]+:[a-z0-9_]+$/.test(def.name)) throw problem(`command name ${def.name} must be namespaced lowercase`);
        if (typeof def.description !== "string" || !def.description) throw problem(`command ${def.name}: missing description`);
        if (!Object.values(CommandPermissionLevel).includes(def.permissionLevel)) throw problem(`command ${def.name}: bad permission level`);
        for (const prm of [...(def.mandatoryParameters ?? []), ...(def.optionalParameters ?? [])]) {
          if (!Object.values(CustomCommandParamType).includes(prm.type)) throw problem(`command ${def.name}: bad parameter type ${prm.type}`);
          if (prm.type === CustomCommandParamType.Enum && !mock.enums.has(prm.name)) throw problem(`command ${def.name}: enum ${prm.name} not registered`);
        }
        if (mock.commands.has(def.name)) throw problem(`command ${def.name} registered twice`);
        mock.commands.set(def.name, { def, cb });
      },
    },
    dimensionRegistry: {
      registerCustomDimension(id) {
        if (!/^[a-z0-9_]+:[a-z0-9_]+$/.test(id) || id.startsWith("minecraft:")) throw problem(`custom dimension id ${id} invalid`);
        if (mock.customDims.has(id)) throw problem(`dimension ${id} registered twice`);
        mock.customDims.add(id);
        mock.dims.set(id, new Dimension(id, () => "minecraft:air"));
      },
    },
  };
  startupSignal.fire(startup);
  // custom component coverage: JSON <-> registrations
  const used = new Set();
  for (const [id, comps] of [...ITEM_DEFS, ...BLOCK_DEFS]) {
    const isItem = ITEM_DEFS.has(id);
    for (const k of Object.keys(comps)) {
      if (k.startsWith("minecraft:") || k.startsWith("tag:")) continue;
      used.add(k);
      const reg = isItem ? mock.itemComponents : mock.blockComponents;
      if (!reg.has(k)) mock.problems.push(`${id} uses custom component ${k} that is not registered as an ${isItem ? "item" : "block"} component`);
    }
  }
  for (const k of [...mock.itemComponents.keys(), ...mock.blockComponents.keys()]) {
    if (!used.has(k)) mock.problems.push(`custom component ${k} is registered but used by no item/block`);
  }
  mock.worldLoaded = true;
  emit("worldLoad", {});
  flushEvents();
}

function heldStack(p, typeId) {
  const s = new ItemStack(typeId, 1);
  p.inventory.slots[p.selectedSlotIndex] = s;
  return s.clone();
}

function componentsOf(typeId, defs) {
  const def = defs.get(typeId);
  if (!def) throw problem(`no definition for ${typeId}`);
  return Object.entries(def).filter(([k]) => !k.startsWith("minecraft:"));
}

/** Simulate a player using (right-click / tap) the held item. */
export function useItem(p, typeId) {
  const stack = heldStack(p, typeId);
  for (const [k, params] of componentsOf(typeId, ITEM_DEFS)) {
    const c = mock.itemComponents.get(k);
    if (c?.onUse) invoke(`${k}.onUse`, () => c.onUse({ source: p, itemStack: stack }, { params }), false);
  }
}

export function consumeItem(p, typeId) {
  const stack = heldStack(p, typeId);
  for (const [k, params] of componentsOf(typeId, ITEM_DEFS)) {
    const c = mock.itemComponents.get(k);
    if (c?.onConsume) invoke(`${k}.onConsume`, () => c.onConsume({ source: p, itemStack: stack }, { params }), false);
  }
}

export function hitWithItem(p, target, typeId) {
  const stack = heldStack(p, typeId);
  const dmg = ITEM_DEFS.get(typeId)?.["minecraft:damage"] ?? 1;
  hurtEntity(target, dmg, { cause: "entityAttack", damagingEntity: p });
  for (const [k, params] of componentsOf(typeId, ITEM_DEFS)) {
    const c = mock.itemComponents.get(k);
    if (c?.onHitEntity) invoke(`${k}.onHitEntity`, () => c.onHitEntity({ attackingEntity: p, hitEntity: target, hadEffect: true, itemStack: stack }, { params }), false);
  }
}

/** Simulate a player breaking a block of `typeId` at `loc` with the held tool. */
export function breakBlock(p, loc, typeId) {
  const dim = p._dim;
  dim._set(loc.x, loc.y, loc.z, "minecraft:air");
  const block = new Block(dim, loc.x, loc.y, loc.z);
  for (const [k, params] of componentsOf(typeId, BLOCK_DEFS)) {
    const c = mock.blockComponents.get(k);
    if (c?.onPlayerBreak) {
      invoke(`${k}.onPlayerBreak`, () => c.onPlayerBreak({ block, dimension: dim, player: p, brokenBlockPermutation: { type: { id: typeId } } }, { params }), false);
    }
  }
}

export function interactBlock(p, loc, typeId) {
  const dim = p._dim;
  dim._set(loc.x, loc.y, loc.z, typeId);
  const block = new Block(dim, loc.x, loc.y, loc.z);
  for (const [k, params] of componentsOf(typeId, BLOCK_DEFS)) {
    const c = mock.blockComponents.get(k);
    if (c?.onPlayerInteract) {
      invoke(`${k}.onPlayerInteract`, () => c.onPlayerInteract({ block, dimension: dim, player: p, face: "Up", faceLocation: { x: 0.5, y: 1, z: 0.5 } }, { params }), false);
    }
  }
}

/** Execute a custom slash command as a player (restricted execution, like the engine). */
export function command(p, name, ...args) {
  const c = mock.commands.get(name);
  if (!c) throw problem(`command ${name} is not registered`);
  if ((p.commandPermissionLevel ?? 0) < c.def.permissionLevel) return { status: CustomCommandStatus.Failure, message: "permission denied" };
  const params = [...(c.def.mandatoryParameters ?? []), ...(c.def.optionalParameters ?? [])];
  args.forEach((a, i) => {
    const prm = params[i];
    if (prm?.type === CustomCommandParamType.Enum && !mock.enums.get(prm.name).includes(a)) throw problem(`command ${name}: "${a}" is not in enum ${prm.name}`);
  });
  return invoke(`command ${name}`, () => c.cb({ sourceEntity: p, initiator: p, sourceType: CustomCommandSource.Entity }, ...args), true);
}

/** Player melee hit on an entity (no item components). */
export function attack(p, target, damage) {
  return hurtEntity(target, damage, { cause: "entityAttack", damagingEntity: p });
}

export function entitiesOf(typeId) {
  return [...mock.entities.values()].filter((e) => e._valid && e.typeId === typeId);
}
