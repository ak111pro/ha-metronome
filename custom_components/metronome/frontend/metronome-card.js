import {getPlayer} from "./player.js";
import {styles} from "./styles.js";
import {DEFAULT_CONFIG, METERS, escapeHTML as esc, clamp, tempo, remaining, splitTime,
  timeText, arc, point, dialFraction, beatPosition} from "./shared.js";

const icon = name => `<ha-icon icon="mdi:${name}" aria-hidden="true"></ha-icon>`;
const button = (action, label, glyph, cls = "control") =>
  `<button type="button" class="${cls}" data-action="${action}" aria-label="${label}" title="${label}">${icon(glyph)}</button>`;
const svg = () => `<svg viewBox="0 0 320 320" aria-hidden="true"><path class="track"></path><path class="value"></path><path class="hit"></path><circle class="knob" r="9"></circle></svg>`;
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
const transport = () => `<div class="transport" role="group" aria-label="Playback and timer">${button("start","Start","play")}${button("stop","Stop","stop")}${button("pause","Pause","pause")}${button("timer","Timer","timer-outline")}</div>`;

export class MetronomeCard extends HTMLElement {
  static async getConfigElement() {
    await import("./editor.js");
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
    this.onBeat = event => this.pulse(event.detail.beat);
  }
  setConfig(config) {
    if (!config.entity?.startsWith("media_player.")) throw new Error("Select a Metronome media_player entity");
    if (config.layout && !["full","compact"].includes(config.layout)) throw new Error("Layout must be full or compact");
    if (config.feedback && !["dots","dots_glow","off"].includes(config.feedback)) throw new Error("Feedback must be dots, dots_glow or off");
    if (config.timer_display && !["remaining","remaining_finish"].includes(config.timer_display)) throw new Error("Invalid timer_display");
    this.config = {...DEFAULT_CONFIG, ...config};
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
    this.shadowRoot.innerHTML = `<style>${styles}</style><ha-card class="idle">
      <section class="main" aria-label="Metronome">
      ${this.config.layout === "compact" ? `
        <div class="compact-head"><button type="button" class="compact-info" data-action="expand" aria-label="Open metronome controls"><div class="name"></div><div class="meta"></div></button>${button("expand","Open controls","arrow-expand")}</div>
        <div class="compact-adjust">${button("minus","Decrease by 1 BPM","minus","round")}<output class="compact-bpm"></output>${button("plus","Increase by 1 BPM","plus","round")}</div>
        ${transport()}<div class="compact-timer" hidden></div>` : `
        <header class="header"><div class="name"></div><div class="device"></div></header>
        <div class="dial bpm-dial"><div class="glow" aria-hidden="true"></div>${svg()}
          <input class="sr bpm-range" type="range" min="1" max="200" step="1" aria-label="Tempo dial">
          <div class="center"><div class="status" role="status">Idle</div><input class="bpm" type="number" min="1" max="200" step="1" inputmode="numeric" aria-label="Beats per minute"><div class="metadata"></div>
          <button type="button" class="tap" data-action="tap" aria-label="Tap tempo"><span class="tap-text">Tap</span><span class="dots" aria-hidden="true"></span></button></div>
          ${button("minus","Decrease by 1 BPM","minus","round minus")}${button("plus","Increase by 1 BPM","plus","round plus")}
        </div>${transport()}
        <div class="timer-panel" inert><div class="timer-inner"><div class="dial timer-dial">${svg()}
          <input class="sr timer-range" type="range" min="5" max="120" step="1" aria-label="Timer dial">
          <span class="sr progress" role="progressbar" aria-label="Time remaining" aria-valuemin="0" hidden></span>
          <div class="timer-adjust">${button("time-minus","Decrease seconds","minus","round")}${button("time-plus","Increase seconds","plus","round")}</div>
          <div class="timer-center"><div class="timer-label">Timer</div><div class="fields">${["Hours","Minutes","Seconds"].map((label,i) => `${i ? '<span class="colon" aria-hidden="true">:</span>' : ''}<label><input type="number" data-field="${i}" aria-label="${label}" min="0" max="${i ? 59 : 99}" inputmode="numeric"><span>${label}</span></label>`).join("")}</div><div class="timer-hint"></div></div>
        </div></div></div>
        <footer class="footer"><button type="button" class="select-trigger advanced" data-action="advanced">${icon("tune")}<span class="select-content"><span class="select-value">Advanced</span></span>${icon("chevron-right")}</button></footer>`}
      </section>
      <section class="advanced-view" aria-label="Advanced settings" hidden>
        <header class="subheader">${button("back","Back to metronome","chevron-left","back")}<div><div class="breadcrumb"></div><div class="name">Advanced</div></div></header>
        <div class="settings"><div class="settings-label">Rhythm</div><div class="grid">${picker("signature")}${picker("count_in")}</div><div class="note meter-note"></div>${tile("accent","Accent first beat","waveform")}
          <div class="settings-label">Sound</div><label class="volume-label" for="volume"><span>Volume</span><output></output></label><div class="volume-wrap"><div class="volume-fill" aria-hidden="true"><span class="volume-marker"></span></div><input id="volume" class="volume" type="range" min="0" max="100" step="1" aria-label="Volume"></div>${tile("muted","Mute","volume-off")}
          <div class="haptics"><div class="settings-label">Haptics</div><div class="grid">${tile("vibration","Vibration","vibrate")}${picker("pulse")}</div><div class="note">On compatible devices</div></div>
        </div>
      </section><div class="message" role="status" hidden></div>
      </ha-card>`;
    this.shadowRoot.addEventListener("click", this.clickHandler ||= event => this.handleClick(event));
    this.shadowRoot.addEventListener("change", this.changeHandler ||= event => this.handleChange(event));
    this.shadowRoot.addEventListener("input", this.inputHandler ||= event => {
      // Typing previews the value on the arc and tempo marking; Enter/blur commits it.
      if (event.target.classList.contains("bpm")) return this.update();
      if (event.target.classList.contains("volume")) {
        const v = Number(event.target.value);
        this.$(".volume-wrap").style.setProperty("--volume", `${v}%`);
        this.$(".volume-label output").textContent = `${v}%`;
        this.patch({volume: v / 100}, true);
      }
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
    if (input.matches(".volume")) this.patch({volume: Number(input.value)/100});
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
    // Only the arc's stroke hit area starts a drag. touch-action:none (path and its svg)
    // stops the browser from turning the gesture into a page scroll; a touch that starts
    // anywhere else in the dial still scrolls normally.
    const path = dial.querySelector(".hit");
    let dragging = null;
    const move = event => {
      if (dragging !== event.pointerId) return;
      event.preventDefault();
      const rect = dial.querySelector("svg").getBoundingClientRect();
      const fraction = dialFraction(event.clientX-rect.left-rect.width/2,event.clientY-rect.top-rect.height/2,inverted);
      const value = Math.round(inverted ? 5 + fraction*115 : 1 + fraction*199);
      this.draw(dial, fraction, inverted);
      if (!inverted) this.previewBpm(value);
      this.patch({[inverted ? "duration" : "bpm"]: value}, true);
    };
    const end = event => {
      if (dragging !== event.pointerId) return;
      if (event.type === "pointerup") move(event);
      dragging = null;
      this.dragBpm = null;
      dial.classList.remove("dragging");
      if (path.hasPointerCapture?.(event.pointerId)) path.releasePointerCapture(event.pointerId);
      this.flushPatch();
    };
    path.addEventListener("pointerdown", event => {
      const s = this.player?.state;
      if (!s || (inverted && (s.state !== "idle" || s.settings.duration < 5 || s.settings.duration > 120))) return;
      event.preventDefault();
      dragging = event.pointerId;
      dial.classList.add("dragging");
      try { path.setPointerCapture(event.pointerId); } catch (_) { /* pointer already gone */ }
      move(event);
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
  // Not "preview": HA sets a boolean `preview` property on every card element.
  previewBpm(bpm) {
    this.dragBpm = bpm;
    const input = this.$(".bpm");
    if (input && this.shadowRoot.activeElement !== input) input.value = bpm;
    if (this.player?.state) this.$(".metadata").textContent = this.meta(this.player.state.settings, bpm);
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
    dial.querySelector(".hit").setAttribute("d",arc(start,direction*270));
    const value = dial.querySelector(".value");
    value.setAttribute("d",arc(start, Math.abs(sweep) < .001 ? direction*.001 : sweep));
    value.style.opacity = fraction <= 0 ? "0" : "1";
    dial.querySelector(".knob").setAttribute("cx",p.x);
    dial.querySelector(".knob").setAttribute("cy",p.y);
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
    card.classList.toggle("active",active); card.classList.toggle("idle",!active);
    card.classList.toggle("feedback-off",this.config.feedback === "off");
    this.$(".main").hidden = this.advanced;
    this.$(".advanced-view").hidden = !this.advanced;
    this.all("button,input").forEach(el => { el.disabled = false; });
    const name = this.config.name || state.name;
    this.$(".main .name").textContent = name;
    this.$(".breadcrumb").textContent = name;
    const status = active ? "Active" : state.state === "paused" ? "Paused" : "Idle";
    const meta = this.meta(s);
    if (this.config.layout === "compact") {
      this.$(".meta").textContent = `${status} · ${meta}`;
      this.$(".compact-bpm").textContent = s.bpm;
    } else {
      this.$(".device").textContent = state.is_owner ? "This device" : state.output_ready ? "Another device selected" : "Current device";
      this.$(".status").textContent = status;
      const bpmInput = this.$(".bpm"), shown = this.shownBpm(s);
      bpmInput.defaultValue = s.bpm;
      if (this.shadowRoot.activeElement !== bpmInput && this.dragBpm == null) bpmInput.value = s.bpm;
      this.$(".bpm-range").value = s.bpm;
      this.$(".bpm-range").setAttribute("aria-valuetext",`${s.bpm} ${s.signature === "6/8" ? "dotted-quarter" : "quarter-note"} beats per minute`);
      this.$(".metadata").textContent = this.meta(s, shown);
      if (this.dragBpm == null) this.draw(this.$(".bpm-dial"),((shown ?? s.bpm)-1)/199);
      const dots = this.$(".dots");
      if (dots.children.length !== METERS[s.signature]) dots.innerHTML = "<span></span>".repeat(METERS[s.signature]);
      this.$(".footer").hidden = !this.config.show_advanced;
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
    this.$(".haptics").hidden = typeof navigator.vibrate !== "function";
    const volume = Math.round(s.volume*100);
    if (this.shadowRoot.activeElement !== this.$(".volume")) this.$(".volume").value = volume;
    this.$(".volume-wrap").style.setProperty("--volume", `${volume}%`);
    this.$(".volume-label output").textContent = `${volume}%`;
    this.updateClock();
  }

  finishLabel() {
    const at = this.player.state.ends_at;
    if (at == null || this.config.timer_display !== "remaining_finish") return "";
    const locale = this._hass.locale || {}, date = new Date(at*1000), now = new Date();
    const format = {hour:"2-digit",minute:"2-digit",second:"2-digit"};
    if (locale.time_format === "24") format.hour12 = false;
    if (locale.time_format === "12") format.hour12 = true;
    if (now.toDateString() !== date.toDateString()) Object.assign(format,{month:"short",day:"numeric"});
    return `Ends ${new Intl.DateTimeFormat(locale.language || undefined,format).format(date)}`;
  }
  updateClock() {
    const state = this.player?.state;
    if (!state || !this.isConnected) return;
    const s = state.settings, locked = state.state !== "idle", now = this.player.now();
    const countIn = state.state === "playing" && beatPosition(state,now) < 0;
    const rem = remaining(state,now);
    const finished = state.state === "idle" && state.completed;
    if (state.state === "playing" && !state.is_owner) {
      const beat = Math.floor(beatPosition(state,now));
      if (beat !== this.lastVisualBeat && now >= state.anchor_at) { this.lastVisualBeat = beat; this.pulse(((beat % METERS[s.signature])+METERS[s.signature])%METERS[s.signature]); }
    }
    if (this.config.layout === "compact") {
      const label = this.$(".compact-timer");
      label.hidden = !s.timer_enabled || !this.config.show_timer;
      label.textContent = `${timeText(locked ? rem : finished ? 0 : s.duration)}${this.finishLabel() ? " · " + this.finishLabel() : ""}`;
      return;
    }
    const dial = this.$(".timer-dial"), outside = !locked && (s.duration < 5 || s.duration > 120);
    dial.classList.toggle("outside",outside); dial.classList.toggle("locked",locked);
    if (!dial.classList.contains("dragging")) this.draw(dial,locked ? rem/s.duration : finished ? 0 : (s.duration-5)/115,true);
    const range = this.$(".timer-range");
    range.disabled = locked || outside; range.hidden = locked; range.value = clamp(s.duration,5,120);
    const progress = this.$(".progress");
    progress.hidden = !locked;
    progress.setAttribute("aria-valuemax",s.duration);
    progress.setAttribute("aria-valuenow",Math.ceil(rem));
    progress.setAttribute("aria-valuetext",`${timeText(rem)} remaining`);
    const fields = splitTime(locked ? rem : finished ? 0 : s.duration);
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
    this.$(".timer-hint").textContent = countIn ? "Starts after count-in" : state.state === "paused" ? "Paused · time saved" : state.state === "playing" ? this.finishLabel() : finished ? "Timer finished" : outside ? "Dial: 5–120 seconds. Use fields for other durations." : `${["Hours","Minutes","Seconds"][this.selectedField]} selected`;
  }

  pulse(beat) {
    if (this.advanced || this.config.feedback === "off" || !this.isConnected) return;
    const dots = this.all(".dots span");
    dots.forEach((el,i) => {
      el.getAnimations().forEach(animation => animation.cancel());
      el.style.opacity = this.motion.matches && i === beat ? "1" : ".28";
    });
    if (this.motion.matches) return;
    dots[beat]?.animate([{opacity:.28,transform:"scale(1)"},{opacity:1,transform:"scale(1.35)",offset:.15},{opacity:.28,transform:"scale(1)"}],{duration:Math.min(300,60000/this.player.state.settings.bpm*.8),easing:"ease-in-out"});
    if (this.config.feedback === "dots_glow") this.$(".glow")?.animate([{opacity:0},{opacity:.10,offset:.2},{opacity:0}],{duration:320,easing:"ease-in-out"});
  }

  openDialog() {
    let dialog = this.$("dialog");
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.setAttribute("aria-label",this.config.name || "Metronome controls");
      dialog.innerHTML = `<div class="close-row">${button("close","Close","close","close")}</div>`;
      const card = document.createElement("metronome-card");
      card.setConfig({...this.config,layout:"full"}); card.hass = this._hass;
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
