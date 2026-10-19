// Minimal @minecraft/server-ui 2.0.0 stand-in: forms record what they show and answer from a scripted queue.
import { mock, problem } from "./server.mjs";

export const FormCancelationReason = { UserBusy: "UserBusy", UserClosed: "UserClosed" };

/** Queue of responders: (form) => response. Empty queue = the player closes the form. */
export const ui = { responders: [], shown: [] };

function answer(form, player) {
  if (!player?.isValid) return Promise.reject(problem("form.show: invalid player"));
  ui.shown.push({ kind: form.kind, title: form._title, body: form._body, buttons: form._buttons, elements: form._elements, player: player.name });
  const r = ui.responders.shift();
  return Promise.resolve(r ? r(form) : { canceled: true, cancelationReason: FormCancelationReason.UserClosed });
}

export class ActionFormData {
  constructor() {
    this.kind = "action";
    this._buttons = [];
    this._elements = [];
  }
  title(t) { this._title = t; return this; }
  body(t) { this._body = t; return this; }
  button(text, icon) {
    if (icon !== undefined && !/^textures\//.test(icon)) throw problem(`button icon path should start with textures/: ${icon}`);
    this._buttons.push(text);
    return this;
  }
  header(t) { this._elements.push({ type: "header", t }); return this; }
  label(t) { this._elements.push({ type: "label", t }); return this; }
  divider() { this._elements.push({ type: "divider" }); return this; }
  show(p) { return answer(this, p); }
}

export class ModalFormData {
  constructor() {
    this.kind = "modal";
    this._elements = [];
    this._buttons = [];
  }
  title(t) { this._title = t; return this; }
  dropdown(label, items, o = {}) {
    if (!items.length) throw problem(`dropdown ${label}: no items`);
    const d = o.defaultValueIndex ?? 0;
    if (!Number.isInteger(d) || d < 0 || d >= items.length) throw problem(`dropdown ${label}: default index ${d} out of range`);
    this._elements.push({ type: "dropdown", label, items, default: d });
    return this;
  }
  toggle(label, o = {}) { this._elements.push({ type: "toggle", label, default: !!o.defaultValue }); return this; }
  slider(label, min, max, o = {}) { this._elements.push({ type: "slider", label, min, max, default: o.defaultValue ?? min }); return this; }
  textField(label, placeholder, o = {}) { this._elements.push({ type: "textField", label, default: o.defaultValue ?? "" }); return this; }
  submitButton(t) { this._submit = t; return this; }
  header(t) { this._elements.push({ type: "header", t }); return this; }
  label(t) { this._elements.push({ type: "label", t }); return this; }
  divider() { this._elements.push({ type: "divider" }); return this; }
  show(p) { return answer(this, p); }
}

export class MessageFormData {
  constructor() { this.kind = "message"; this._buttons = []; this._elements = []; }
  title(t) { this._title = t; return this; }
  body(t) { this._body = t; return this; }
  button1(t) { this._buttons[0] = t; return this; }
  button2(t) { this._buttons[1] = t; return this; }
  show(p) { return answer(this, p); }
}

void mock;
