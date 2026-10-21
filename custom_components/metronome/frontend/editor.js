/* Visual card editor. Built on HA's own ha-form with selectors (the frontend lazy-loads the
 * selector elements); a plain-control fallback is used only if ha-form never appears.
 * Contract: setConfig() + hass setter, and a bubbling, composed `config-changed` event with
 * the new config after every change. Only non-default options are written to YAML. */
import {DEFAULT_CONFIG, COLOR_KEYS, cleanConfig, validColor, escapeHTML as esc} from "./shared.js?v=0.1.0-beta.6";

const select = options => ({select: {mode: "dropdown", options: options.map(([value, label]) => ({value, label}))}});
const SCHEMA = [
  {name: "entity", required: true, selector: {entity: {filter: {integration: "metronome", domain: "media_player"}}}},
  {name: "name", selector: {text: {}}},
  {name: "layout", required: true, selector: select([["full", "Full"], ["compact", "Compact"]])},
  {type: "grid", name: "", schema: [
    {name: "show_title", selector: {boolean: {}}},
    {name: "show_tempo", selector: {boolean: {}}},
    {name: "show_signature", selector: {boolean: {}}},
    {name: "show_timer", selector: {boolean: {}}},
    {name: "show_advanced", selector: {boolean: {}}},
    {name: "show_step_buttons", selector: {boolean: {}}},
    {name: "show_timer_bar", selector: {boolean: {}}},
  ]},
  {name: "feedback", required: true, selector: select([["dots_glow", "Dots and subtle glow"], ["dots", "Dots"], ["off", "Off"]])},
  {name: "features_position", required: true, selector: select([["bottom", "Bottom"], ["inline", "Inline (next to the name)"]])},
  {name: "timer_display", required: true, selector: select([["remaining_finish", "Remaining time and finish time"], ["remaining", "Remaining time"]])},
  {name: "primary_color", selector: {text: {}}},
  {name: "secondary_color", selector: {text: {}}},
];
const LABELS = {
  entity: "Metronome entity", name: "Name (optional)", layout: "Layout",
  show_title: "Show title", show_tempo: "Show tempo marking", show_signature: "Show time signature",
  show_timer: "Show timer controls", show_advanced: "Show Advanced button", show_step_buttons: "Show −1/+1 buttons", show_timer_bar: "Compact: timer bar",
  feedback: "Beat feedback", features_position: "Compact: tempo controls position", timer_display: "Timer display",
  primary_color: "Primary colour", secondary_color: "Secondary colour",
};
const HELPERS = {
  name: "Default: the metronome's name",
  layout: "Compact opens the full card in a dialog",
  features_position: "Like the Tile card's features position; inline falls back to bottom on narrow cards",
  primary_color: "Default: theme media-player colour (arcs, handle, beat dots, toggles). Name, #hex, rgb(), hsl() or var(--…)",
  secondary_color: "Default: theme accent colour (count-in beats, selected timer field). Name, #hex, rgb(), hsl() or var(--…)",
};
const INVALID = "Not a CSS colour. Use a name (teal), hex (#16809e), rgb(…), hsl(…) or var(--…)";
const NOTE = "Tempo, timer duration and sound settings belong to the metronome entity, not to this card.";

// Some dashboards open the editor before HA has loaded ha-form; the built-in entities card
// editor pulls it in. Fall back to plain controls if it still is not there after 3 s.
async function haFormReady() {
  if (customElements.get("ha-form")) return true;
  try {
    const helpers = await window.loadCardHelpers?.();
    const card = await helpers?.createCardElement({type: "entities", entities: []});
    await card?.constructor?.getConfigElement?.();
  } catch (_) { /* fall back below */ }
  return Promise.race([customElements.whenDefined("ha-form").then(() => true),
    new Promise(resolve => setTimeout(() => resolve(false), 3000))]);
}

class MetronomeCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.ready = haFormReady().then(ok => { this.useForm = ok; this.render(); });
  }
  setConfig(config) {
    this.config = {...config};
    // Drop a pending invalid colour once the YAML changed that option some other way.
    for (const [key, entry] of Object.entries(this.invalid || {})) {
      if (config[key] !== entry.base) delete this.invalid[key];
    }
    this.render();
  }
  set hass(hass) {
    this._hass = hass;
    if (this.form) this.form.hass = hass;
    else this.render();
  }
  get hass() { return this._hass; }
  // What the form shows: defaults filled in so toggles and selects show the real state.
  // An invalid colour stays visible in its field with an error, but is never saved.
  formData() {
    const typed = Object.fromEntries(Object.entries(this.invalid || {}).map(([k, e]) => [k, e.text]));
    return {...DEFAULT_CONFIG, ...this.config, ...typed};
  }
  errors() {
    return Object.fromEntries(Object.keys(this.invalid || {}).map(key => [key, INVALID]));
  }
  // Valid colours (or blank = default) go to the config; invalid ones only into the form.
  sortColours(values) {
    this.invalid ||= {};
    const out = {...values};
    for (const key of COLOR_KEYS) {
      if (!(key in values)) continue;
      const text = values[key] ?? "";
      if (String(text).trim() === "" || validColor(String(text))) delete this.invalid[key];
      else {
        this.invalid[key] = {text, base: this.config[key]};
        out[key] = this.config[key];
      }
    }
    return out;
  }
  // Merge the form's values into the current config and tell HA.
  commit(values) {
    const next = cleanConfig({...this.config, ...values});
    if (JSON.stringify(next) === JSON.stringify(cleanConfig(this.config))) return;
    this.config = next;
    this.dispatchEvent(new CustomEvent("config-changed", {detail: {config: next}, bubbles: true, composed: true}));
  }
  render() {
    if (!this.config || !this._hass || this.useForm === undefined) return;
    if (this.useForm) return this.renderForm();
    this.renderFallback();
  }
  renderForm() {
    if (!this.form) {
      this.shadowRoot.innerHTML = `<style>:host{display:block}p{margin:16px 0 0;font-size:13px;line-height:1.5;color:var(--secondary-text-color)}</style><p>${esc(NOTE)}</p>`;
      const form = this.form = document.createElement("ha-form");
      form.computeLabel = schema => LABELS[schema.name] ?? schema.name;
      form.computeHelper = schema => HELPERS[schema.name];
      form.addEventListener("value-changed", event => {
        event.stopPropagation();
        this.commit(this.sortColours(event.detail.value));
        form.data = this.formData();
        form.error = this.errors();
      });
      this.shadowRoot.prepend(form);
    }
    this.form.hass = this._hass;
    this.form.schema = SCHEMA;
    this.form.data = this.formData();
    this.form.error = this.errors();
    this.form.computeError = error => error;
  }
  renderFallback() {
    const c = this.formData();
    const options = (items, value) => items.map(([v, label]) => `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(label)}</option>`).join("");
    const choice = (key, items) => `<label>${LABELS[key]}<select data-key="${key}">${options(items, c[key])}</select></label>`;
    const entities = Object.keys(this._hass.states).filter(id => id.startsWith("media_player.") && this._hass.states[id].attributes.output === "Current device");
    if (c.entity && !entities.includes(c.entity)) entities.unshift(c.entity);
    const flat = SCHEMA.flatMap(item => item.schema || [item]);
    const field = item => {
      if (item.name === "entity") return choice("entity", [["", "Choose an entity"], ...entities.map(id => [id, this._hass.states[id]?.attributes.friendly_name || id])]);
      if (item.selector.select) return choice(item.name, item.selector.select.options.map(o => [o.value, o.label]));
      if (item.selector.boolean) return `<label class="check"><input type="checkbox" data-key="${item.name}" ${c[item.name] ? "checked" : ""}>${LABELS[item.name]}</label>`;
      return `<label>${LABELS[item.name]}<input data-key="${item.name}" value="${esc(c[item.name] || "")}" placeholder="${esc(HELPERS[item.name]?.split(".")[0] || "")}"></label>`;
    };
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:var(--ha-font-family-body,inherit)}
      .form{display:grid;gap:16px}label{display:grid;gap:6px;font-size:14px}input,select{font:inherit;color:inherit;background:var(--input-fill-color,var(--secondary-background-color));border:1px solid var(--divider-color);border-radius:4px;padding:12px;min-height:48px;box-sizing:border-box;width:100%}input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.check{display:flex;align-items:center;gap:12px;min-height:40px}.check input{width:20px;min-height:20px;accent-color:var(--primary-color)}p{font-size:13px;color:var(--secondary-text-color);line-height:1.5;margin:0}
      </style><div class="form">${flat.map(field).join("")}<p>${esc(NOTE)}</p></div>`;
    // A ShadowRoot has no onchange handler property: listen with addEventListener.
    this.shadowRoot.querySelector(".form").addEventListener("change", event => {
      const target = event.target, key = target.dataset.key;
      if (!key) return;
      this.commit(this.sortColours({[key]: target.type === "checkbox" ? target.checked : target.value}));
      target.setCustomValidity?.(this.invalid?.[key] ? INVALID : "");
      target.reportValidity?.();
    });
  }
}
if (!customElements.get("metronome-card-editor")) customElements.define("metronome-card-editor", MetronomeCardEditor);
