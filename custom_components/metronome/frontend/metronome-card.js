import {getPlayer} from "./player.js?v=0.1.0-alpha.8";
import {styles} from "./styles.js?v=0.1.0-alpha.8";
import {DEFAULT_CONFIG, COLOR_KEYS, METERS, escapeHTML as esc, clamp, tempo, remaining, splitTime,
  timeText, arc, point, dialFraction, beatPosition, hapticMode, validColor} from "./shared.js?v=0.1.0-alpha.8";

const icon = name => `<ha-icon icon="mdi:${name}" aria-hidden="true"></ha-icon>`;
const button = (action, label, glyph, cls = "control") =>
  `<button type="button" class="${cls}" data-action="${action}" aria-label="${label}" title="${label}">${icon(glyph)}</button>`;
const svg = () => `<svg viewBox="0 0 320 320" aria-hidden="true"><path class="track"></path><path class="value"></path><circle class="knob" r="9"></circle><circle class="grab" r="24"></circle></svg>`;
const pickers = {
  signature: {label: "Time signature", icon: "music-note", options: Object.keys(METERS).map(v => [v,v])},
  count_in: {label: "Count-in", icon: "format-list-numbered", options: [[0,"Off"],[1,"1 bar"],[2,"2 bars"]]},
  pulse: {label: "Pulse length", icon: "sine-wave", options: [[20,"Short"],[40,"Medium"],[70,"Long"]]},
};
function picker(key) {
  const p = pickers[key];
  return `<div class="picker" data-picker="${key}"><button type="button" class="select-trigger" aria-label="${p.label}" aria-haspopup="menu" aria-expanded="false">${icon(p.icon)}<span class="select-content"><span class="select-label">${p.label}</span><span class="select-value"></span></span>${icon("menu-down")}</button><div class="menu" role="menu" aria-label="${p.label}" hidden>${p.options.map(([v,l]) => `<button type="button" role="menuitemradio" data-value="${v}" aria-checked="false">${l}</button>`).join("")}</div></div>`;
}
function tile(key, label, glyph) {
  return `<button type="button" class="tile" data-toggle="${key}" aria-pressed="false">${icon(glyph)}<span>${label}</span><small>Off</small></button>`;
}
// Full card: Advanced is the fifth square button. The compact card keeps four; its expand
// control opens the full view (with Advanced) instead of swapping the small card in place.
const transport = (advanced = false) => `<div class="transport" role="group" aria-label="Playback and timer">${button("start","Start","play")}${button("stop","Stop","stop")}${button("pause","Pause","pause")}${button("timer","Timer","timer-outline")}${advanced ? button("advanced","Advanced","tune") : ""}</div>`;

export class MetronomeCard extends HTMLElement {
  static async getConfigElement() {
    await import("./editor.js?v=0.1.0-alpha.8");
    return document.createElement("metronome-card-editor");
  }
  static getStubConfig(hass) {
    return {type: "custom:metronome-card", entity: Object.keys(hass?.states || {}).find(id =>
      id.startsWith("media_player.") && hass.states[id].attributes.output === "Current device") || ""};
  }
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.selectedField = 2;
    this.taps = [];
    this.motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    this.onChange = () => this.update();
    this.onBeat = event => this.pulse(event.detail.beat, event.detail.countIn);
  }
  setConfig(config) {
    if (!config.entity?.startsWith("media_player.")) throw new Error("Select a Metronome media_player entity");
    if (config.layout && !["full","compact"].includes(config.layout)) throw new Error("Layout must be full or compact");
    if (config.feedback && !["dots","dots_glow","off"].includes(config.feedback)) throw new Error("Feedback must be dots, dots_glow or off");
    if (config.timer_display && !["remaining","remaining_finish"].includes(config.timer_display)) throw new Error("Invalid timer_display");
    if (config.features_position && !["bottom","inline"].includes(config.features_position)) throw new Error("features_position must be bottom or inline");
    for (const key of COLOR_KEYS) {
      if (config[key] != null && config[key] !== "" && !validColor(String(config[key]))) throw new Error(`${key}: "${config[key]}" is not a CSS colour`);
    }
    this.config = {...DEFAULT_CONFIG, ...config};
    // primary_color / secondary_color override the theme through these two properties.
    for (const key of COLOR_KEYS) {
      const property = `--metronome-${key.replace("_","-")}`;
      if (this.config[key]) this.style.setProperty(property, String(this.config[key]).trim());
      else this.style.removeProperty(property);
    }
    this.build();
    this.connect();
  }
  set hass(hass) {
    this._hass = hass;
    this.connect();
    const dialogCard = this.shadowRoot.querySelector("dialog metronome-card");
    if (dialogCard) dialogCard.hass = hass;
  }
  get hass() { return this._hass; }
  getCardSize() { return this.config?.layout === "compact" ? 3 : this.player?.state?.settings.timer_enabled ? 12 : 7; }
  // Sections: the full card needs the whole section width (both dials, 228 px transport
  // row plus insets); the compact card fits from three quarters of a section.
  getGridOptions() {
    return this.config?.layout === "compact"
      ? {columns: 12, rows: "auto", min_columns: 9}
      : {columns: 12, rows: "auto", min_columns: 12};
  }
  connectedCallback() {
    this.connect();
    clearInterval(this.tick);
    this.tick = setInterval(() => this.updateClock(), 100);
  }
  disconnectedCallback() {
    clearInterval(this.tick);
    cancelAnimationFrame(this.countdownRaf); this.countdownRaf = null;
    clearTimeout(this.patchTimeout);
    this.flushPatch();
    this.unlisten();
  }
  unlisten() {
    if (this.player) {
      this.player.removeEventListener("change", this.onChange);
      this.player.removeEventListener("beat", this.onBeat);
    }
  }
  connect() {
    if (!this.isConnected || !this.config || !this._hass) return;
    const player = getPlayer(this._hass, this.config.entity);
    if (player !== this.player) { this.unlisten(); this.player = player; }
    this.player.addEventListener("change", this.onChange);
    this.player.addEventListener("beat", this.onBeat);
    this.update();
  }
  $(selector) { return this.shadowRoot.querySelector(selector); }
  all(selector) { return [...this.shadowRoot.querySelectorAll(selector)]; }

  build() {
    this.advanced = false;
    this.shadowRoot.innerHTML = `<style>${styles}</style><ha-card class="idle${this.config.layout === "compact" ? " compact" : ""}">
      <section class="main" aria-label="Metronome">
      ${this.config.layout === "compact" ? `
        <div class="compact-grid${this.config.features_position === "inline" ? " inline" : ""}">
          <button type="button" class="compact-info" data-action="expand" aria-label="Open metronome controls"><span class="tile-icon">${icon("metronome")}</span><span class="tile-text"><span class="name"${this.config.show_title ? "" : " hidden"}></span><span class="meta"></span></span></button>
          <div class="compact-adjust" role="group" aria-label="Tempo">${button("minus","Decrease by 1 BPM","minus","feature")}<output class="compact-bpm" aria-label="Beats per minute"></output>${button("plus","Increase by 1 BPM","plus","feature")}</div>
          ${transport()}<div class="compact-timer" hidden></div></div>` : `
        <header class="header"${this.config.show_title ? "" : " hidden"}><div class="name"></div></header>
        <div class="dial bpm-dial"><div class="glow" aria-hidden="true"></div>${svg()}
          <input class="sr bpm-range" type="range" min="1" max="200" step="1" aria-label="Tempo dial">
          <div class="center"><div class="status" role="status">Idle</div><input class="bpm" type="number" min="1" max="200" step="1" inputmode="numeric" aria-label="Beats per minute"><div class="metadata"></div>
          <button type="button" class="tap" data-action="tap" aria-label="Tap tempo"><span class="tap-text">Tap</span><span class="dots" aria-hidden="true"></span></button></div>
          ${button("minus","Decrease by 1 BPM","minus","round minus")}${button("plus","Increase by 1 BPM","plus","round plus")}
        </div>${transport(true)}
        <div class="timer-panel" inert><div class="timer-inner"><div class="dial timer-dial">${svg()}
          <input class="sr timer-range" type="range" min="5" max="120" step="1" aria-label="Timer dial">
          <span class="sr progress" role="progressbar" aria-label="Time remaining" aria-valuemin="0" hidden></span>
          <div class="timer-adjust">${button("time-minus","Decrease seconds","minus","round")}${button("time-plus","Increase seconds","plus","round")}</div>
          <div class="timer-center"><div class="timer-label">Timer</div><div class="fields">${["Hours","Minutes","Seconds"].map((label,i) => `${i ? '<span class="colon" aria-hidden="true">:</span>' : ''}<label><input type="number" data-field="${i}" aria-label="${label}" min="0" max="${i ? 59 : 99}" inputmode="numeric"><span>${label}</span></label>`).join("")}</div><div class="timer-hint"></div></div>
        </div></div></div>`}
      </section>
      <section class="advanced-view" aria-label="Advanced settings" hidden>
        <header class="subheader">${button("back","Back to metronome","chevron-left","back")}<div><div class="breadcrumb"></div><div class="name">Advanced</div></div></header>
        <div class="settings"><div class="settings-label">Rhythm</div><div class="grid">${picker("signature")}${picker("count_in")}</div><div class="note meter-note"></div>${tile("accent","Accent first beat","waveform")}
          <div class="settings-label">Sound</div><div class="volume-label"><span id="volume-label">Volume</span><output></output></div><div class="volume-wrap" role="slider" tabindex="0" aria-labelledby="volume-label" aria-valuemin="0" aria-valuemax="100"><div class="volume-fill" aria-hidden="true"><span class="volume-marker"></span></div></div>${tile("muted","Mute","volume-off")}
          <div class="settings-label">Output</div><div class="output"><div class="output-status" role="status">${icon("volume-high")}<span class="output-device"></span></div><button type="button" class="tile output-claim" data-action="claim">${icon("cellphone-arrow-down")}<span>Play on this device</span></button><div class="note output-note"></div></div>
          <div class="haptics"><div class="settings-label">Haptics</div><div class="grid">${tile("vibration","Vibration","vibrate")}${picker("pulse")}</div><div class="note haptics-note"></div><button type="button" class="tile haptic-test" data-action="test-haptic">${icon("vibrate")}<span>Test vibration</span></button></div>
          <div class="diagnostics"><div class="settings-label">Diagnostics</div><dl class="diag"></dl></div>
        </div>
      </section><div class="message" role="status" hidden></div>
      </ha-card>`;
    this.shadowRoot.addEventListener("click", this.clickHandler ||= event => this.handleClick(event));
    this.shadowRoot.addEventListener("change", this.changeHandler ||= event => this.handleChange(event));
    this.shadowRoot.addEventListener("input", this.inputHandler ||= event => {
      // Typing previews the value on the arc and tempo marking; Enter/blur commits it.
      if (event.target.classList.contains("bpm")) return this.update();
    });
    this.shadowRoot.addEventListener("focusout", this.blurHandler ||= event => {
      if (event.target.classList.contains("bpm")) queueMicrotask(() => this.update());
    });
    this.shadowRoot.addEventListener("focusin", this.focusHandler ||= event => {
      if (event.target.dataset.field != null) { this.selectedField = Number(event.target.dataset.field); this.updateClock(); }
    });
    this.shadowRoot.addEventListener("keydown", this.keyHandler ||= event => {
      const target = event.target;
      if ((target.classList.contains("bpm") || target.dataset.field != null) && (event.key === "Enter" || event.key === "Escape")) {
        event.preventDefault();
        // Escape restores the committed value; blur commits through the change event.
        if (event.key === "Escape") { target.value = target.defaultValue; }
        target.blur();
        return;
      }
      this.menuKey(event);
    });
    this.bindVolume();
    this.bindDial(".bpm-dial", false);
    this.bindDial(".timer-dial", true);
  }

  async run(operation) {
    try { await operation(); this.localError = ""; }
    catch (error) { this.localError = error?.message || String(error); }
    this.update();
  }
  patch(changes, delayed = false) {
    this.pendingPatch = {...this.pendingPatch, ...changes};
    if (!delayed) return this.flushPatch();
    clearTimeout(this.patchTimeout);
    this.patchTimeout = setTimeout(() => this.flushPatch(), 80);
  }
  flushPatch() {
    if (!this.pendingPatch || !this.player) return;
    const changes = this.pendingPatch;
    this.pendingPatch = null;
    return this.run(() => this.player.action("configure", changes));
  }
  handleClick(event) {
    const target = event.target.closest("button");
    if (!target || target.disabled) return;
    const pickerEl = target.closest(".picker");
    if (pickerEl) {
      const key = pickerEl.dataset.picker;
      if (target.dataset.value != null) {
        const value = key === "signature" ? target.dataset.value : Number(target.dataset.value);
        if (key === "pulse") this.player.pulse = value;
        else this.patch({[key]: value});
        this.closeMenus(); pickerEl.querySelector(".select-trigger").focus(); this.update();
      } else {
        const menu = pickerEl.querySelector(".menu"), open = menu.hidden;
        this.closeMenus();
        menu.hidden = !open;
        target.setAttribute("aria-expanded", String(open));
        if (open) menu.querySelector('[aria-checked="true"]')?.focus();
      }
      return;
    }
    this.closeMenus();
    const state = this.player?.state;
    if (target.dataset.toggle && state) {
      const key = target.dataset.toggle;
      if (key === "vibration") { this.player.vibration = !this.player.vibration; this.update(); }
      else this.patch({[key]: !state.settings[key]});
      return;
    }
    const action = target.dataset.action;
    if (action === "expand") return this.openDialog();
    if (action === "advanced" || action === "back") {
      this.advanced = action === "advanced";
      this.update();
      this.$(this.advanced ? '[data-action="back"]' : '[data-action="advanced"]')?.focus();
      return;
    }
    if (!state) return;
    if (action === "start") return this.run(() => this.player.start());
    if (action === "claim") return this.run(() => this.player.claim());
    if (action === "test-haptic") { this.player.testHaptic(); this.updateDiagnostics(true); return; }
    if (action === "stop" || action === "pause") return this.run(() => this.player.action(action));
    if (action === "timer") return this.patch({timer_enabled: !state.settings.timer_enabled});
    if (action === "minus" || action === "plus") return this.patch({bpm: clamp(state.settings.bpm + (action === "plus" ? 1 : -1),1,200)});
    if (action === "time-minus" || action === "time-plus") {
      const delta = [3600,60,1][this.selectedField] * (action === "time-plus" ? 1 : -1);
      return this.patch({duration: clamp(state.settings.duration + delta,1,359999)});
    }
    if (action === "tap") {
      const now = performance.now();
      if (this.taps.length && now - this.taps.at(-1) > 60000) this.taps = [];
      this.taps.push(now); this.taps = this.taps.slice(-6);
      if (this.taps.length > 1) {
        const intervals = this.taps.slice(1).map((v,i) => v - this.taps[i]).sort((a,b) => a-b);
        const mid = intervals.length >> 1;
        const interval = intervals.length % 2 ? intervals[mid] : (intervals[mid-1] + intervals[mid])/2;
        this.patch({bpm: clamp(Math.round(60000 / interval),1,200)});
      }
    }
  }

  handleChange(event) {
    const input = event.target;
    if (input.matches(".bpm,.bpm-range")) this.patch({bpm: clamp(Math.round(Number(input.value)),1,200)});
    if (input.matches(".timer-range")) this.patch({duration: clamp(Math.round(Number(input.value)),5,120)});
    if (input.dataset.field != null) {
      const values = this.all("[data-field]").map((el,i) => clamp(Math.round(Number(el.value)),0,i ? 59 : 99));
      this.patch({duration: Math.max(1, values[0]*3600 + values[1]*60 + values[2])});
    }
  }
  closeMenus() {
    this.all(".menu").forEach(el => { el.hidden = true; });
    this.all(".picker>.select-trigger").forEach(el => el.setAttribute("aria-expanded","false"));
  }
  menuKey(event) {
    const pickerEl = event.target.closest(".picker");
    if (!pickerEl) return;
    const menu = pickerEl.querySelector(".menu"), options = [...menu.querySelectorAll("button")];
    if (event.key === "Escape" || event.key === "Tab") {
      this.closeMenus();
      if (event.key === "Escape") { event.preventDefault(); pickerEl.querySelector(".select-trigger").focus(); }
    } else if (["ArrowDown","ArrowUp","Home","End"].includes(event.key)) {
      event.preventDefault(); menu.hidden = false;
      pickerEl.querySelector(".select-trigger").setAttribute("aria-expanded","true");
      const index = options.indexOf(this.shadowRoot.activeElement);
      options[event.key === "Home" ? 0 : event.key === "End" ? options.length-1 : (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length].focus();
    }
  }

  bindDial(selector, inverted) {
    const dial = this.$(selector);
    if (!dial) return;
    // Only the handle starts a drag (a 48 px circle around the knob): a tap or swipe on
    // the arc track never changes the value, and the page scrolls normally there. The
    // handle has touch-action:none, so dragging it never scrolls the page.
    const path = dial.querySelector(".grab");
    let dragging = null, moved = false;
    new ResizeObserver(() => this.sizeGrab(dial)).observe(dial);
    const move = event => {
      if (dragging !== event.pointerId) return;
      event.preventDefault();
      moved = true;
      const rect = dial.querySelector("svg").getBoundingClientRect();
      const fraction = dialFraction(event.clientX-rect.left-rect.width/2,event.clientY-rect.top-rect.height/2,inverted);
      const value = Math.round(inverted ? 5 + fraction*115 : 1 + fraction*199);
      this.draw(dial, fraction, inverted);
      // Live preview of the number (BPM) or the h/m/s fields (timer) while dragging; the
      // value is sent coalesced (80 ms) and committed on release.
      if (inverted) this.previewDuration(value); else this.previewBpm(value);
      this.patch({[inverted ? "duration" : "bpm"]: value}, true);
    };
    const end = event => {
      if (dragging !== event.pointerId) return;
      if (event.type === "pointerup" && moved) move(event);
      dragging = null;
      dial.classList.remove("dragging");
      if (path.hasPointerCapture?.(event.pointerId)) path.releasePointerCapture(event.pointerId);
      // Keep showing the dragged value until HA confirmed it, so it never jumps back.
      const drag = this.dragToken;
      Promise.resolve(this.flushPatch()).finally(() => {
        if (drag !== this.dragToken) return;
        this.dragBpm = null; this.dragDuration = null; this.update();
      });
    };
    path.addEventListener("pointerdown", event => {
      const s = this.player?.state;
      if (!s || (inverted && (s.state !== "idle" || s.settings.duration < 5 || s.settings.duration > 120))) return;
      event.preventDefault();
      dragging = event.pointerId;
      this.dragToken = (this.dragToken || 0) + 1;
      moved = false;
      dial.classList.add("dragging");
      try { path.setPointerCapture(event.pointerId); } catch (_) { /* pointer already gone */ }
      // No value change on press: a tap on the handle changes nothing; moving does.
    });
    path.addEventListener("pointermove", move);
    path.addEventListener("pointerup", end);
    path.addEventListener("pointercancel", end);
    path.addEventListener("lostpointercapture", end);
    // Older WebKit ignores touch-action on SVG shapes: cancel the touch scroll explicitly.
    const stopTouch = event => { if (event.cancelable) event.preventDefault(); };
    path.addEventListener("touchstart", stopTouch, {passive: false});
    path.addEventListener("touchmove", stopTouch, {passive: false});
  }
  /* Volume: a pointer-events slider over the whole 48 px track (no native range input:
   * WebKit's thumb could not be dragged on the iPad and showed through as a second handle on
   * the iPhone). Drag or tap anywhere; keyboard: arrows +-1, PageUp/PageDown +-10, Home/End.
   * The value is sent coalesced while dragging and committed on release. */
  showVolume(value) {
    const wrap = this.$(".volume-wrap");
    if (!wrap) return;
    wrap.style.setProperty("--volume", `${value}%`);
    wrap.setAttribute("aria-valuenow", value);
    wrap.setAttribute("aria-valuetext", `${value}%`);
    this.$(".volume-label output").textContent = `${value}%`;
  }
  setVolume(value, commit) {
    const v = clamp(Math.round(value), 0, 100);
    this.dragVolume = commit ? null : v;
    this.showVolume(v);
    this.patch({volume: v / 100}, !commit);
  }
  bindVolume() {
    const wrap = this.$(".volume-wrap");
    if (!wrap) return;
    let dragging = null;
    const valueAt = event => { const r = wrap.getBoundingClientRect(); return (event.clientX - r.left) / r.width * 100; };
    wrap.addEventListener("pointerdown", event => {
      if (!this.player?.state || event.button > 0) return;
      dragging = event.pointerId;
      try { wrap.setPointerCapture(event.pointerId); } catch (_) { /* pointer gone */ }
      this.setVolume(valueAt(event), false);
    });
    wrap.addEventListener("pointermove", event => { if (dragging === event.pointerId) this.setVolume(valueAt(event), false); });
    const end = event => {
      if (dragging !== event.pointerId) return;
      dragging = null;
      this.setVolume(this.dragVolume ?? valueAt(event), true);
    };
    wrap.addEventListener("pointerup", end);
    wrap.addEventListener("pointercancel", end);
    wrap.addEventListener("keydown", event => {
      const now = Math.round((this.player?.state?.settings.volume ?? 0) * 100);
      const step = {ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10}[event.key];
      const next = step != null ? now + step : event.key === "Home" ? 0 : event.key === "End" ? 100 : null;
      if (next == null) return;
      event.preventDefault();
      this.setVolume(next, true);
    });
  }
  // Advanced → Diagnostics (collapsed): what the next phone test needs to see.
  // Always visible (a <details> with a flex <summary> did not open on iOS WebKit); refreshed
  // about once a second while Advanced is shown.
  updateDiagnostics(force = false) {
    if (!this.$(".diagnostics") || !this.player) return;
    const t = performance.now();
    if (!force && t - (this.diagAt || 0) < 900) return;
    this.diagAt = t;
    const d = this.player.diagnostics();
    const rows = [["Audio", `${d.audio}${d.sample_rate ? ` · ${d.sample_rate} Hz` : ""}`], ["Audio session", d.audio_session],
      ["This page is the output", d.owner ? "yes" : "no"], ["Haptics path", `${d.haptics}${d.vibration_on ? " · on" : " · off"}`],
      ["App", `${d.app}${d.external_bus ? " · HA external bus" : ""}${d.vibrate_api ? " · navigator.vibrate" : ""}`], ["Last haptic", d.last_haptic || "–"], ["Audio contexts", String(d.contexts)], ["Last audio event", d.last_error || "–"]];
    const html = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
    if (this.$(".diag").innerHTML !== html) this.$(".diag").innerHTML = html;
  }
  // Not "preview": HA sets a boolean `preview` property on every card element.
  previewBpm(bpm) {
    this.dragBpm = bpm;
    const input = this.$(".bpm");
    if (input && this.shadowRoot.activeElement !== input) input.value = bpm;
    if (this.player?.state) this.$(".metadata").textContent = this.meta(this.player.state.settings, bpm);
  }
  previewDuration(seconds) {
    this.dragDuration = seconds;
    this.updateClock();
  }
  // The BPM the dial shows: dragged, typed (null while the typed text is not 1-200),
  // otherwise the committed value.
  shownBpm(s) {
    if (this.dragBpm != null) return this.dragBpm;
    const input = this.$(".bpm");
    if (!input || this.shadowRoot.activeElement !== input) return s.bpm;
    const typed = Number(input.value);
    return input.value !== "" && Number.isInteger(typed) && typed >= 1 && typed <= 200 ? typed : null;
  }
  meta(s, bpm = s.bpm) {
    return ["BPM", ...(this.config.show_signature ? [s.signature] : []),
      ...(this.config.show_tempo && bpm != null ? [tempo(bpm)] : [])].join(" · ");
  }
  draw(dial, fraction, inverted = false) {
    const start = inverted ? 225 : 135, direction = inverted ? -1 : 1;
    const sweep = direction * 270 * clamp(fraction,0,1), p = point(start + sweep);
    dial.querySelector(".track").setAttribute("d",arc(start,direction*270));

    const value = dial.querySelector(".value");
    value.setAttribute("d",arc(start, Math.abs(sweep) < .001 ? direction*.001 : sweep));
    value.style.opacity = fraction <= 0 ? "0" : "1";
    dial.querySelector(".knob").setAttribute("cx",p.x);
    dial.querySelector(".knob").setAttribute("cy",p.y);
    const grab = dial.querySelector(".grab");
    grab.setAttribute("cx",p.x); grab.setAttribute("cy",p.y);
    this.sizeGrab(dial);
  }
  // The grab circle is 48 CSS px wide whatever the dial's size (viewBox is 320 units).
  sizeGrab(dial) {
    const width = dial.querySelector("svg").getBoundingClientRect().width;
    if (width > 0) dial.querySelector(".grab").setAttribute("r", 24 * 320 / width);
  }

  update() {
    if (!this.config || !this.$("ha-card")) return;
    const state = this.player?.state;
    const message = this.$(".message");
    const error = this.localError || this.player?.error || (!state ? "Connecting to metronome…" : "");
    message.textContent = error; message.hidden = !error;
    if (!state) { this.all("button,input").forEach(el => { el.disabled = true; }); return; }
    const s = state.settings, active = state.state === "playing", locked = state.state !== "idle";
    const card = this.$("ha-card");
    card.classList.toggle("active",active); card.classList.toggle("idle",!active); card.classList.toggle("paused",state.state === "paused");
    if (!active) card.classList.remove("count-in");
    card.classList.toggle("feedback-off",this.config.feedback === "off");
    this.$(".main").hidden = this.advanced;
    this.$(".advanced-view").hidden = !this.advanced;
    this.all("button,input").forEach(el => { el.disabled = false; });
    const name = this.config.name || state.name;
    this.$(".main .name").textContent = name;
    this.$(".breadcrumb").textContent = name;
    this.renderStatus(state, this.player.now());
    if (this.config.layout === "compact") {
      this.$(".compact-bpm").textContent = s.bpm;
      this.$(".compact-info").setAttribute("aria-label", `Open ${name} controls`);
    } else {
      const bpmInput = this.$(".bpm"), shown = this.shownBpm(s);
      bpmInput.defaultValue = s.bpm;
      if (this.shadowRoot.activeElement !== bpmInput && this.dragBpm == null) bpmInput.value = s.bpm;
      this.$(".bpm-range").value = s.bpm;
      this.$(".bpm-range").setAttribute("aria-valuetext",`${s.bpm} ${s.signature === "6/8" ? "dotted-quarter" : "quarter-note"} beats per minute`);
      this.$(".metadata").textContent = this.meta(s, shown);
      if (this.dragBpm == null) this.draw(this.$(".bpm-dial"),((shown ?? s.bpm)-1)/199);
      const dots = this.$(".dots");
      if (dots.children.length !== METERS[s.signature]) dots.innerHTML = "<span></span>".repeat(METERS[s.signature]);
      this.$('[data-action="advanced"]').hidden = !this.config.show_advanced;
      const panel = this.$(".timer-panel"), open = s.timer_enabled && this.config.show_timer;
      panel.classList.toggle("open",open); panel.inert = !open;
    }
    this.$('[data-action="start"]').disabled = active;
    this.$('[data-action="start"]').setAttribute("aria-label",state.state === "paused" ? "Resume" : "Start");
    this.$('[data-action="start"]').title = state.state === "paused" ? "Resume" : "Start";
    this.$('[data-action="stop"]').disabled = !locked;
    this.$('[data-action="pause"]').disabled = !active || !s.timer_enabled;
    this.$('[data-action="pause"]').title = s.timer_enabled ? "Pause" : "Pause is available with a timer";
    const timer = this.$('[data-action="timer"]');
    timer.disabled = locked; timer.hidden = !this.config.show_timer;
    timer.setAttribute("aria-pressed",String(s.timer_enabled));
    timer.setAttribute("aria-expanded",String(s.timer_enabled && this.config.layout === "full"));
    this.$('[data-action="minus"]').disabled = s.bpm <= 1;
    this.$('[data-action="plus"]').disabled = s.bpm >= 200;
    this.all("[data-picker]").forEach(el => {
      const key = el.dataset.picker, value = key === "pulse" ? this.player.pulse : s[key];
      el.querySelector(".select-value").textContent = pickers[key].options.find(([v]) => v === value)[1];
      el.querySelector(".select-trigger").disabled = key === "pulse" ? !this.player.vibration : locked;
      el.querySelectorAll("[data-value]").forEach(option => option.setAttribute("aria-checked",String(option.dataset.value === String(value))));
    });
    this.$(".meter-note").textContent = `${METERS[s.signature]} beats per bar · ${s.signature === "6/8" ? "Dotted-quarter" : "Quarter-note"} beat`;
    this.all("[data-toggle]").forEach(el => {
      const key = el.dataset.toggle, value = key === "vibration" ? this.player.vibration : s[key];
      el.setAttribute("aria-pressed",String(value)); el.querySelector("small").textContent = value ? "On" : "Off";
    });
    // Output: which page plays; "Play on this device" selects this page (only while idle,
    // like Start). There is no speaker picker: output is always a page's own audio.
    this.$(".output-device").textContent = state.is_owner ? "This device"
      : state.output_ready ? `Another device${state.output_user ? ` (${state.output_user})` : ""}` : "No device selected";
    const claim = this.$(".output-claim");
    claim.hidden = state.is_owner;
    claim.disabled = locked;
    this.$(".output-note").textContent = state.is_owner ? "Sound comes from this phone or browser while the page stays open."
      : locked ? "Stop the session to move playback to this device."
      : "Tap to enable sound here. Start does the same.";
    const haptics = hapticMode();
    this.$(".haptics").hidden = !haptics;
    this.$(".haptics-note").textContent = haptics === "companion"
      ? "Uses the app's light, medium or heavy haptic. Silent or mute mode can turn it off."
      : "Silent or mute mode on the phone can turn vibration off.";
    if (this.dragVolume == null) this.showVolume(Math.round(s.volume*100));
    this.updateClock();
  }

  finishLabel() {
    const at = this.player.state.ends_at;
    if (at == null || this.config.timer_display !== "remaining_finish") return "";
    const locale = this._hass.locale || {}, date = new Date(at*1000), now = new Date();
    // 24-hour clock unless the HA profile explicitly asks for 12-hour (owner's choice: the
    // "language" default would give AM/PM for English).
    const format = {hour:"2-digit",minute:"2-digit",second:"2-digit"};
    if (locale.time_format === "12") format.hour12 = true; else format.hourCycle = "h23";
    if (now.toDateString() !== date.toDateString()) Object.assign(format,{month:"short",day:"numeric"});
    return `Ends ${new Intl.DateTimeFormat(locale.language || undefined,format).format(date)}`;
  }
  // "Count-in" from Start until the first exercise beat, then "Active" (HA's media_player
  // phase attribute flips at the same moment). Re-rendered every clock tick.
  renderStatus(state, now) {
    const status = state.state === "paused" ? "Paused" : state.state !== "playing" ? "Idle"
      : beatPosition(state, now) < 0 ? "Count-in" : "Active";
    if (this.config.layout === "compact") {
      // The full card's Advanced view names the output; here only when it plays elsewhere.
      const elsewhere = state.state !== "idle" && state.output_ready && !state.is_owner;
      const text = `${status}${elsewhere ? " on another device" : ""} · ${this.meta(state.settings)}`;
      const meta = this.$(".meta");
      if (meta.textContent !== text) meta.textContent = text;
    } else {
      const el = this.$(".status");
      if (el.textContent !== status) el.textContent = status;
    }
  }
  updateClock() {
    const state = this.player?.state;
    if (!state || !this.isConnected) return;
    const s = state.settings, locked = state.state !== "idle", now = this.player.now();
    const countIn = state.state === "playing" && beatPosition(state,now) < 0;
    const rem = remaining(state,now);
    this.renderStatus(state, now);
    if (this.advanced) this.updateDiagnostics();
    const finished = state.state === "idle" && state.completed;
    if (state.state === "playing" && !state.is_owner) {
      const beat = Math.floor(beatPosition(state,now));
      if (beat !== this.lastVisualBeat && now >= state.anchor_at) { this.lastVisualBeat = beat; this.pulse(((beat % METERS[s.signature])+METERS[s.signature])%METERS[s.signature], beat < 0); }
    }
    if (this.config.layout === "compact") {
      const label = this.$(".compact-timer");
      label.hidden = !s.timer_enabled || !this.config.show_timer;
      label.textContent = `${timeText(locked ? rem : finished ? 0 : s.duration)}${this.finishLabel() ? " · " + this.finishLabel() : ""}`;
      return;
    }
    // While the timer handle is dragged, the fields follow it (s.duration lags behind).
    const duration = !locked && this.dragDuration != null ? this.dragDuration : s.duration;
    const dial = this.$(".timer-dial"), outside = !locked && (duration < 5 || duration > 120);
    dial.classList.toggle("outside",outside); dial.classList.toggle("locked",locked);
    // Running countdown: drawn every animation frame (smooth, see countdownFrame); 1 s steps
    // with reduced motion; the clock tick draws everything else.
    const animate = locked && state.state === "playing" && !this.motion.matches;
    if (animate && !this.countdownRaf) this.countdownRaf = requestAnimationFrame(() => this.countdownFrame());
    if (!dial.classList.contains("dragging") && !animate) {
      const shown = locked && this.motion.matches ? Math.ceil(rem) : rem;
      this.draw(dial,locked ? shown/s.duration : finished ? 0 : (duration-5)/115,true);
    }
    const range = this.$(".timer-range");
    range.disabled = locked || outside; range.hidden = locked; range.value = clamp(duration,5,120);
    const progress = this.$(".progress");
    progress.hidden = !locked;
    progress.setAttribute("aria-valuemax",s.duration);
    progress.setAttribute("aria-valuenow",Math.ceil(rem));
    progress.setAttribute("aria-valuetext",`${timeText(rem)} remaining`);
    const fields = splitTime(locked ? rem : finished && this.dragDuration == null ? 0 : duration);
    this.all("[data-field]").forEach((input,i) => {
      input.disabled = locked; input.classList.toggle("selected",i === this.selectedField && !locked);
      const text = String(fields[i]).padStart(2,"0");
      input.defaultValue = text;
      if (this.shadowRoot.activeElement !== input || locked) input.value = text;
    });
    ["time-minus","time-plus"].forEach((key,i) => {
      const b = this.$(`[data-action="${key}"]`);
      b.disabled = locked || (i ? s.duration >= 359999 : s.duration <= 1);
      b.setAttribute("aria-label",`${i ? "Increase" : "Decrease"} ${["hours","minutes","seconds"][this.selectedField]}`);
    });
    this.$(".timer-label").textContent = locked ? "Remaining" : "Timer";
    this.$(".timer-hint").textContent = countIn ? "Starts after count-in" : state.state === "paused" ? "Paused · time saved" : state.state === "playing" ? this.finishLabel() : finished ? "Timer finished" : outside ? "Dial: 5 s – 2 min" : `${["Hours","Minutes","Seconds"][this.selectedField]} selected`;
  }

  countdownFrame() {
    this.countdownRaf = null;
    const state = this.player?.state;
    if (!state || !this.isConnected || state.state !== "playing" || this.motion.matches || this.config.layout === "compact") return;
    const dial = this.$(".timer-dial");
    if (!dial || !this.$(".timer-panel.open")) return;
    this.draw(dial, remaining(state, this.player.now()) / state.settings.duration, true);
    // requestAnimationFrame does not run while the page is hidden: no load in the background.
    this.countdownRaf = requestAnimationFrame(() => this.countdownFrame());
  }

  pulse(beat, countIn = false) {
    if (this.advanced || this.config.feedback === "off" || !this.isConnected) return;
    // Count-in beats use HA's accent colour (dots and glow); exercise beats the active colour.
    this.$("ha-card").classList.toggle("count-in", countIn);
    if (this.config.layout === "compact") return this.pulseNumber(beat, countIn);
    const dots = this.all(".dots span");
    dots.forEach((el,i) => {
      el.getAnimations().forEach(animation => animation.cancel());
      el.style.opacity = this.motion.matches && i === beat ? "1" : ".28";
    });
    if (this.motion.matches) return;
    dots[beat]?.animate([{opacity:.28,transform:"scale(1)"},{opacity:1,transform:"scale(1.35)",offset:.15},{opacity:.28,transform:"scale(1)"}],{duration:Math.min(300,60000/this.player.state.settings.bpm*.8),easing:"ease-in-out"});
    if (this.config.feedback === "dots_glow") this.$(".glow")?.animate([{opacity:0},{opacity:.10,offset:.2},{opacity:0}],{duration:320,easing:"ease-in-out"});
  }

  /* Compact only: the BPM number pulses on each beat (the full card keeps a stable number).
   * Primary colour for beats, a stronger pulse on the accented first beat, secondary colour
   * for count-in. dots = pulse only, dots_glow = pulse + glow; reduced motion: no scale. */
  pulseNumber(beat, countIn) {
    const el = this.$(".compact-bpm"), s = this.player?.state?.settings;
    if (!el || !s) return;
    el.getAnimations().forEach(animation => animation.cancel());
    const css = getComputedStyle(this.$("ha-card"));
    const color = css.getPropertyValue(countIn ? "--highlight" : "--accent").trim();
    const strong = !countIn && beat === 0 && s.accent;
    const peak = {color, offset: .15};
    if (!this.motion.matches) peak.transform = `scale(${strong ? 1.2 : 1.1})`;
    if (this.config.feedback === "dots_glow") peak.textShadow = `0 0 ${strong ? 16 : 10}px ${color}`;
    const rest = {transform: "scale(1)", textShadow: "0 0 0 transparent"};
    el.animate([rest, peak, rest], {duration: Math.min(320, 60000 / s.bpm * .8), easing: "ease-in-out"});
  }

  openDialog() {
    let dialog = this.$("dialog");
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.setAttribute("aria-label",this.config.name || "Metronome controls");
      // Close sits on the title row (top right); the inner card's header is tightened.
      dialog.innerHTML = button("close","Close","close","dialog-close");
      const card = document.createElement("metronome-card");
      card.setAttribute("in-dialog","");
      card.setConfig({...this.config,layout:"full",show_title:true}); card.hass = this._hass;
      dialog.append(card); this.shadowRoot.append(dialog);
      dialog.querySelector("button").addEventListener("click",() => dialog.close());
      dialog.addEventListener("click",event => { if (event.target === dialog) dialog.close(); });
      dialog.addEventListener("close",() => { dialog.remove(); this.$('[data-action="expand"]')?.focus(); });
    }
    dialog.showModal();
  }
}

if (!customElements.get("metronome-card")) customElements.define("metronome-card",MetronomeCard);
window.customCards ||= [];
if (!window.customCards.some(card => card.type === "metronome-card")) window.customCards.push({
  type: "metronome-card", name: "Metronome", description: "Current-device metronome with an optional timer", preview: false,
});
