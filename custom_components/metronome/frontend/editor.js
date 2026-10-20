import {DEFAULT_CONFIG, escapeHTML as esc} from "./shared.js?v=0.1.0-alpha.2";

class MetronomeCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); }
  setConfig(config) { this.config = {...DEFAULT_CONFIG,...config}; this.render(); }
  set hass(hass) { this._hass = hass; if (!this.rendered) this.render(); }
  render() {
    if (!this.config || !this._hass) return;
    const c = this.config;
    const options = (items,value) => items.map(([v,label]) => `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(label)}</option>`).join("");
    const select = (key,label,items) => `<label>${label}<select data-key="${key}">${options(items,c[key])}</select></label>`;
    const entities = Object.keys(this._hass.states).filter(id => id.startsWith("media_player.") && this._hass.states[id].attributes.output === "Current device");
    if (c.entity && !entities.includes(c.entity)) entities.unshift(c.entity);
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:var(--ha-font-family-body,inherit)}
      .form{display:grid;gap:16px}label{display:grid;gap:6px;font-size:14px}input,select{font:inherit;color:inherit;background:var(--input-fill-color,var(--secondary-background-color));border:1px solid var(--divider-color);border-radius:4px;padding:12px;min-height:48px;box-sizing:border-box;width:100%}input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}.check{display:flex;align-items:center;gap:12px;min-height:40px}.check input{width:20px;min-height:20px;accent-color:var(--primary-color)}p{font-size:13px;color:var(--secondary-text-color);line-height:1.5;margin:0}
      </style><div class="form">
      ${select("entity","Metronome entity",[["","Choose an entity"],...entities.map(id => [id,this._hass.states[id]?.attributes.friendly_name || id])])}
      <label>Name (optional)<input data-key="name" value="${esc(c.name || "")}" placeholder="Entity name"></label>
      ${select("layout","Layout",[["full","Full"],["compact","Compact"]])}
      ${[ ["show_tempo","Show tempo marking"], ["show_signature","Show time signature"], ["show_timer","Show timer controls"], ["show_advanced","Show Advanced"] ].map(([key,label]) => `<label class="check"><input type="checkbox" data-key="${key}" ${c[key] ? "checked" : ""}>${label}</label>`).join("")}
      ${select("feedback","Beat feedback",[["dots_glow","Dots and subtle glow"],["dots","Dots"],["off","Off"]])}
      ${select("timer_display","Timer display",[["remaining_finish","Remaining time and finish time"],["remaining","Remaining time"]])}
      <p>Tempo, timer duration and sound settings belong to the metronome entity. Colours, typography and clock format follow Home Assistant. Compact controls open the full card in a dialog.</p></div>`;
    this.shadowRoot.onchange = event => {
      const target = event.target, key = target.dataset.key;
      if (!key) return;
      this.config = {...this.config,[key]:target.type === "checkbox" ? target.checked : target.value};
      if (!this.config.name) delete this.config.name;
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this.config},bubbles:true,composed:true}));
    };
    this.rendered = true;
  }
}
if (!customElements.get("metronome-card-editor")) customElements.define("metronome-card-editor",MetronomeCardEditor);
