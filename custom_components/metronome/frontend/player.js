/* A single engine per HA connection/entity, independent of card attachment.
 * No audio is generated on the HA host. WS sends session changes, never beats.
 */
import {METERS, HAPTIC_TYPES, TONES, TONE_TAIL, masterGain, beatPosition, hapticMode} from "./shared.js?v=0.1.0-beta.1";

const REGISTRY = Symbol.for("metronome.players.v1");
globalThis[REGISTRY] ||= new WeakMap();

/* One AudioContext per page, shared by all instances. The card module is a global
 * dashboard resource, so this also runs on pages without a metronome card: every user
 * gesture (capture phase, before e.g. the Tile's own click handler) resumes the context
 * and tells HA "this page was just tapped" (metronome/arm). A native play from the same
 * user within 3 s then selects this page as output (see coordinator.armed_client). The
 * context is suspended again 5 s after the last gesture unless a page is a ready output. */
const SHARED = Symbol.for("metronome.audio.v1");
const shared = globalThis[SHARED] ||= {ctx: null, gestureAt: -Infinity, armAt: -Infinity, timer: null, players: new Set(), installed: false};
export const GESTURE_MS = 5000;
shared.contexts ||= 0;
export function audioContext() {
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (!Audio) return null;
  if (!shared.ctx || shared.ctx.state === "closed") {
    shared.ctx = new Audio({latencyHint: "interactive"});
    shared.contexts++;
  }
  return shared.ctx;
}
/* Inside a tap: a context that another app's audio left "interrupted" (or closed) does not
 * come back with resume() on iOS (seen after YouTube took the audio session: Start stopped
 * YouTube but stayed silent until YouTube was killed). Replace it with a fresh context in the
 * same gesture and re-apply the playback session. A merely suspended context (our own
 * battery suspend) is resumed as before. Players rebind their gain to the new context. */
export function freshAudioInGesture(reason) {
  const old = shared.ctx;
  if (old && !["interrupted", "closed"].includes(old.state)) return audioContext();
  if (old) {
    noteError(`context ${old.state} after ${reason}: replaced`);
    try { old.close().catch(() => {}); } catch (_) { /* already closed */ }
    shared.ctx = null;
  }
  playbackSession(false);
  const ctx = audioContext();
  for (const player of shared.players) if (player.audio && player.audio !== ctx) player.attachAudio();
  return ctx;
}
export const recentGesture = () => performance.now() - shared.gestureAt < GESTURE_MS;
// resume() can hang on WebKit (e.g. while a call holds the audio session): never wait forever.
export const withTimeout = (promise, ms) => Promise.race([promise.catch(() => {}), new Promise(resolve => setTimeout(resolve, ms))]);
shared.lastError ||= "";
export const lastAudioError = () => shared.lastError;
function noteError(text) { shared.lastError = `${new Date().toLocaleTimeString()} ${text}`; }

/* iOS: Web Audio in the Companion app's WKWebView uses the "ambient" audio session by default,
 * which the ring/silent switch mutes (the iPad has no switch). The page that becomes the output
 * switches to "playback" (WebKit Audio Session API, iOS 17+), like a music app: the silent
 * switch no longer mutes it, and other apps' audio pauses while it plays. Without that API
 * (older iOS), a looping silent <audio> element started in the tap does the same. Back to
 * "auto" when the page stops being the output. Other browsers have neither: no change there. */
const IOS = typeof navigator !== "undefined" && (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
const SILENT_WAV = "data:audio/wav;base64,UklGRkQDAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YSADAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA==";
export const audioSessionType = () => (typeof navigator !== "undefined" && navigator.audioSession?.type) || null;
export function playbackSession(on) {
  try {
    if (navigator.audioSession) {
      const type = on ? "playback" : "auto";
      if (navigator.audioSession.type !== type) navigator.audioSession.type = type;
    } else if (IOS) {
      if (!shared.unlock) {
        shared.unlock = new Audio(SILENT_WAV);
        shared.unlock.loop = true;
        shared.unlock.setAttribute("playsinline", "");
      }
      if (on) shared.unlock.play().catch(() => {}); else shared.unlock.pause();
    }
  } catch (error) { noteError(`audio session: ${error?.message || error}`); }
}
function scheduleSuspend() {
  clearTimeout(shared.timer);
  shared.timer = setTimeout(() => {
    if ([...shared.players].some(p => p.readyForAudio) || recentGesture()) return scheduleSuspend();
    if (shared.ctx?.state === "running") shared.ctx.suspend().catch(() => {});
    playbackSession(false);
  }, GESTURE_MS);
}
// Metronome media players known to this page: each gets a (standby) subscription, so HA
// can hand output to this page even when no metronome card is on it (Tile, more-info).
export function standby(hass = document.querySelector("home-assistant")?.hass) {
  if (!hass?.connection || !hass.states) return [];
  return Object.keys(hass.states)
    .filter(id => id.startsWith("media_player.") && hass.states[id].attributes?.output === "Current device")
    .map(id => getPlayer(hass, id));
}
function onGesture(event) {
  if (!event.isTrusted) return;
  const hass = document.querySelector("home-assistant")?.hass;
  if (!standby(hass).length) return;
  shared.gestureAt = performance.now();
  const ctx = freshAudioInGesture("a tap");
  if (ctx && ctx.state !== "running") {
    // The output page re-applies "playback" in the tap (a new context needs it again).
    if ([...shared.players].some(p => p.readyForAudio)) playbackSession(true);
    ctx.resume().catch(() => {});
  }
  scheduleSuspend();
  // One arm per tap (pointerup, touchend and click all fire); it precedes the service call.
  if (shared.gestureAt - shared.armAt > 250) {
    shared.armAt = shared.gestureAt;
    hass.connection.sendMessagePromise({type: "metronome/arm"}).catch(() => {});
  }
}
if (!shared.installed && typeof window !== "undefined") {
  shared.installed = true;
  for (const type of ["pointerup", "touchend", "click", "keydown"]) window.addEventListener(type, onGesture, {capture: true, passive: true});
  // Standby subscriptions as soon as HA's frontend has its state (no card needed).
  let tries = 0;
  const boot = setInterval(() => { if (standby().length || ++tries > 60) clearInterval(boot); }, 1000);
}
export function getPlayer(hass, entity) {
  let map = globalThis[REGISTRY].get(hass.connection);
  if (!map) globalThis[REGISTRY].set(hass.connection, map = new Map());
  if (!map.has(entity)) map.set(entity, new Player(hass.connection, entity));
  return map.get(entity);
}

class Player extends EventTarget {
  constructor(connection, entity) {
    super();
    this.connection = connection;
    this.entity = entity;
    this.state = null;
    this.nodes = new Set();
    this.visuals = new Set();
    this.serverOffset = Date.now() / 1000 - performance.now() / 1000;
    this.readyForAudio = false;
    // True once Start was tapped in this page load (audio unlocked by a user gesture).
    // An armed page re-selects itself after it was hidden or reconnected, as long as no
    // other device took over; a page that never tapped Start is never selected.
    this.armed = false;
    this.pulse = 20;
    this.vibration = false;
    this.showDiagnostics = false;  // Advanced → Show diagnostics, local to this page
    this.lastFinished = null;
    this.error = "";
    shared.players.add(this);
    this.ready = new Promise((resolve, reject) => {
      this.resolveReady = resolve;
      connection.subscribeMessage(state => this.receive(state), {
        type: "metronome/subscribe", entity_id: entity,
      }).then(unsub => { this.unsubscribe = unsub; }).catch(error => {
        this.fail(error); reject(error);
      });
    });
    // An unselected browser can render state without becoming an audio output.
    this.ready.catch(() => {});
    this.heartbeat = setInterval(() => {
      if (this.subscription != null && this.readyForAudio && !document.hidden) {
        this.send("heartbeat").catch(error => this.interrupt(error));
      }
    }, 3000);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) this.interrupt();
      else this.rearm();
    });
    window.addEventListener("pagehide", () => this.interrupt());
    connection.addEventListener("disconnected", () => this.interrupt("Connection lost. Tap Start to reconnect audio."));
  }

  now() { return performance.now() / 1000 + this.serverOffset; }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, {detail})); }
  fail(error) {
    this.error = typeof error === "string" ? error : error?.message || "Metronome connection failed";
    this.emit("change", this.state);
  }

  async send(action, settings) {
    const sent = performance.now() / 1000;
    const state = await this.connection.sendMessagePromise({
      type: "metronome/control", entity_id: this.entity, action,
      ...(this.subscription != null ? {subscription: this.subscription} : {}),
      ...(settings ? {settings} : {}),
    });
    const received = performance.now() / 1000;
    // Midpoint estimate; audio remains on its own stable clock between changes.
    if (received - sent < 1) this.serverOffset = state.server_time - (sent + received) / 2;
    this.receive(state);
    return state;
  }

  receive(state) {
    let resubscribed = false;
    if (state.subscription != null) {
      resubscribed = this.subscription != null && this.subscription !== state.subscription;
      this.subscription = state.subscription;
      this.serverOffset = state.server_time - performance.now() / 1000;
      this.resolveReady();
    }
    if (this.state && state.instance_id === this.state.instance_id && state.sequence < this.state.sequence) return;
    const previous = this.state;
    this.state = state;
    // HA selected this page after a native play right after a tap here (metronome/arm):
    // the gesture already unlocked the shared AudioContext, so take the output.
    if (state.is_owner && !this.readyForAudio && !this.rearming && recentGesture() && this.attachAudio()) {
      this.readyForAudio = true;
      this.armed = true;
      this.error = "";
      playbackSession(true);
      // The scheduler runs on a silent clock until the context runs (statechange reschedules).
      if (this.audio.state !== "running") withTimeout(this.audio.resume(), 1500).then(() => this.checkAudio());
      this.report();
    }
    this.updateGain();
    const timeline = `${state.session_id}/${state.anchor_at}/${state.settings.bpm}/${state.state}/${state.is_owner}`;
    if (timeline !== this.timeline) {
      this.timeline = timeline;
      const preserveChime = state.is_owner && state.state === "idle" && state.last_event === "finished" && this.lastFinished === state.session_id;
      this.silence(!preserveChime);
      if (state.state === "playing" && state.is_owner && this.readyForAudio && !document.hidden) this.schedule();
    }
    if (previous?.state === "playing" && state.state === "idle" && state.last_event === "finished" && state.is_owner) this.finished();
    if (state.is_owner && !this.readyForAudio && !this.rearming) {
      this.send("release").catch(() => {});
    }
    this.emit("change", state);
    // After a websocket reconnect the server has a new subscription and no owner.
    if (resubscribed || (!this.readyForAudio && !state.output_ready)) this.rearm();
  }

  /* Re-select this page as output without a new tap, only if it was unlocked by Start
   * earlier, is visible, and no other device is selected. Browsers keep the user
   * activation for the page, so resume() normally succeeds; if it does not, the page
   * simply stays unselected and asks for Start again. */
  async rearm() {
    if (!this.armed || this.readyForAudio || this.rearming || document.hidden) return;
    if (!this.state || this.subscription == null || this.state.state !== "idle") return;
    if (this.state.output_ready && !this.state.is_owner) return;
    if (!this.audio || this.audio.state === "closed") return;
    // At most one automatic attempt every 2 s, so a flapping audio device cannot loop.
    if (performance.now() - (this.lastRearm || -Infinity) < 2000) return;
    this.lastRearm = performance.now();
    this.rearming = true;
    try {
      if (this.audio.state !== "running") await withTimeout(this.audio.resume(), 1500);
      if (this.audio.state !== "running" || document.hidden) return;
      this.readyForAudio = true;
      await this.send("claim");
      this.error = "";
      this.emit("change", this.state);
    } catch (_) {
      this.readyForAudio = !!this.state?.is_owner;
    } finally {
      this.rearming = false;
    }
  }

  /* Select this page as the output without starting: Start does the same first. Both run
   * inside the tap (user gesture), which is what lets the browser enable audio. */
  async claim() {
    // resume() is invoked directly during the click gesture, before network waits.
    freshAudioInGesture("Start");
    if (!this.attachAudio()) throw new Error("Audio is unavailable in this browser");
    playbackSession(true);
    await withTimeout(this.audio.resume(), 1500);
    // Still not running after the timeout (a dead context that kept reporting "suspended"):
    // one fresh context, still close enough to the tap for WebKit's user activation.
    if (this.audio.state !== "running") {
      noteError(`context ${this.audio.state} after resume at Start: replaced`);
      const old = shared.ctx; shared.ctx = null;
      try { old?.close().catch(() => {}); } catch (_) { /* closed */ }
      playbackSession(false);
      this.attachAudio();
      playbackSession(true);
      await withTimeout(this.audio.resume(), 1500);
    }
    await this.ready;
    this.readyForAudio = true;
    this.armed = true;
    this.error = "";
    try {
      await this.send("claim");
    } catch (error) {
      if (!this.state?.is_owner) this.readyForAudio = false;
      throw error;
    }
    // Without a running context the session still runs: beat dots and haptics continue,
    // sound comes back when the system lets the context run (next tap).
    this.checkAudio();
    this.report();
  }

  /* Sound blocked or paused by the system (WebKit "interrupted": calls, Siri, other apps;
   * or "suspended"): keep the output and the beat (dots, haptics), say why, retry on the
   * next tap (the gesture listener resumes the context). */
  checkAudio() {
    if (!this.readyForAudio || !this.audio) return;
    if (this.audio.state === "running") {
      if (this.error.startsWith("No sound")) { this.error = ""; this.emit("change", this.state); }
      return;
    }
    noteError(`AudioContext ${this.audio.state}`);
    this.error = `No sound: the system paused audio on this device (${this.audio.state}). Beat dots and haptics continue; tap anywhere to resume sound.`;
    this.emit("change", this.state);
  }

  diagnostics() {
    const ctx = shared.ctx;
    return {
      audio: ctx ? ctx.state : "none", sample_rate: ctx ? ctx.sampleRate : null, contexts: shared.contexts,
      audio_session: audioSessionType() || (IOS ? "n/a (silent-audio fallback)" : "n/a"),
      owner: !!this.state?.is_owner, ready: this.readyForAudio,
      haptics: hapticMode() || "none", vibration_on: this.vibration,
      last_haptic: this.lastHaptic || "", last_error: shared.lastError || "",
      app: window.webkit?.messageHandlers?.externalBus ? "ios-companion" : window.externalApp ? "android-companion" : "browser",
      external_bus: !!document.querySelector("home-assistant")?.hass?.auth?.external,
      vibrate_api: typeof navigator.vibrate === "function",
    };
  }

  // Once per take-over, for the HA log (logger custom_components.metronome, debug level).
  report() {
    clearTimeout(this.reportTimer);
    this.reportTimer = setTimeout(() => {
      this.connection.sendMessagePromise({type: "metronome/diagnostics", entity_id: this.entity, diagnostics: this.diagnostics()}).catch(() => {});
    }, 1500);
  }

  // Use the page's shared AudioContext (own gain node per instance).
  attachAudio() {
    const ctx = audioContext();
    if (!ctx) return null;
    if (this.audio !== ctx) {
      this.audio = ctx;
      this.lastToneEnd = 0;  // times of the previous context mean nothing here
      this.master = ctx.createGain();
      this.master.connect(ctx.destination);
      ctx.addEventListener("statechange", () => {
        if (this.audio !== ctx) return;
        if (this.readyForAudio) {
          // Switch the scheduler between the audio clock and the silent clock.
          if (this.state?.state === "playing" && this.state.is_owner && !document.hidden) this.schedule();
          this.checkAudio();
        } else if (ctx.state === "running") this.rearm();
      });
      this.updateGain();
    }
    return ctx;
  }

  async start() {
    await this.claim();
    await this.send("start");
  }

  async action(action, settings) {
    await this.ready;
    this.error = "";
    return this.send(action, settings);
  }

  updateGain() {
    if (this.audio && this.master && this.state) {
      const s = this.state.settings;
      this.master.gain.setTargetAtTime(masterGain(s.volume, s.muted), this.audio.currentTime, 0.01);
    }
  }

  silence(includeChime = true) {
    clearInterval(this.loop);
    for (const timeout of this.visuals) clearTimeout(timeout);
    this.visuals.clear();
    for (const node of this.nodes) {
      if (!includeChime && node.metronomeChime) continue;
      try { node.stop(); } catch (_) { /* already ended */ }
      this.nodes.delete(node);
    }
    if (this.vibration && hapticMode() === "vibrate") navigator.vibrate(0);
  }

  interrupt(error) {
    this.silence();
    const wasReady = this.readyForAudio;
    this.readyForAudio = false;
    if (wasReady) { scheduleSuspend(); playbackSession(false); }
    if (wasReady) this.send("release").catch(() => {});
    if (error) this.fail(error);
  }

  tone(when, frequency, duration, level, chime = false) {
    const oscillator = this.audio.createOscillator();
    oscillator.metronomeChime = chime;
    const envelope = this.audio.createGain();
    oscillator.frequency.value = frequency;
    oscillator.connect(envelope);
    envelope.connect(this.master);
    envelope.gain.setValueAtTime(0.0001, when);
    envelope.gain.exponentialRampToValueAtTime(level, when + 0.002);
    envelope.gain.exponentialRampToValueAtTime(0.0001, when + duration);
    oscillator.onended = () => {
      this.nodes.delete(oscillator); oscillator.disconnect(); envelope.disconnect();
    };
    this.nodes.add(oscillator);
    oscillator.start(when);
    oscillator.stop(when + duration + TONE_TAIL);
    if (!chime) this.lastToneEnd = Math.max(this.lastToneEnd || 0, when + duration + TONE_TAIL);
  }

  /* Beats run on the audio clock when the context runs, otherwise on a silent clock (HA
   * time): dots and haptics never depend on audible sound. A state change of the context
   * reschedules (see attachAudio). */
  schedule() {
    clearInterval(this.loop);
    for (const timeout of this.visuals) clearTimeout(timeout);
    this.visuals.clear();
    const state = this.state;
    const period = 60 / state.settings.bpm;
    const audible = this.audio?.state === "running";
    const clock = audible ? () => this.audio.currentTime : () => this.now();
    // Convert once per timeline update, then schedule against the chosen clock.
    const base = audible ? this.audio.currentTime + state.anchor_at - this.now() : state.anchor_at;
    let index = Math.max(Math.ceil(state.anchor_beat), Math.ceil(beatPosition(state, this.now() + 0.005)));
    const tick = () => {
      if (!this.readyForAudio) return this.interrupt();
      if (audible !== (this.audio?.state === "running")) return this.schedule();
      if (state.ends_at != null && this.now() >= state.ends_at) {
        this.silence(); this.finished(); return;
      }
      const now = clock();
      let when = base + (index - state.anchor_beat) * period;
      // Do not burst through missed beats after a foreground main-thread stall.
      if (when < now - 0.03) {
        index = Math.ceil(state.anchor_beat + (now - base) / period);
        when = base + (index - state.anchor_beat) * period;
      }
      while (when < now + 0.10) {
        const utc = state.anchor_at + (index - state.anchor_beat) * period;
        if (state.ends_at != null && utc >= state.ends_at) break;
        const beat = ((index % METERS[state.settings.signature]) + METERS[state.settings.signature]) % METERS[state.settings.signature];
        const countIn = index < 0;
        const accent = beat === 0 && this.state.settings.accent;
        if (audible) {
          const t = countIn ? TONES.countIn : accent ? TONES.accent : TONES.beat;
          this.tone(Math.max(when, now), t.frequency, t.duration, t.level);
        }
        const timeout = setTimeout(() => {
          this.visuals.delete(timeout);
          this.emit("beat", {beat, countIn});
          if (this.vibration && !document.hidden) this.buzz();
        }, Math.max(0, when - now) * 1000);
        this.visuals.add(timeout);
        index++;
        when = base + (index - state.anchor_beat) * period;
      }
    };
    this.loop = setInterval(tick, 25);
    tick();
  }

  // Test vibration: one pulse, cycling through every type the iOS app accepts, so a test
  // shows whether any of them reaches the Taptic Engine (Android: the pulse length).
  testHaptic() {
    const types = ["light", "medium", "heavy", "success", "warning", "failure", "selection"];
    this.testIndex = ((this.testIndex ?? -1) + 1) % types.length;
    this.buzz(types[this.testIndex]);
  }

  buzz(type) {
    const mode = hapticMode();
    this.lastHaptic = `${new Date().toLocaleTimeString()} ${mode || "none"} ${this.pulse} ms`;
    if (mode === "vibrate") navigator.vibrate(this.pulse);
    else if (mode === "companion") {
      // Exactly what HA 2026.10's frontend does with its window "haptic" event inside the
      // app (attachExternalToApp): external bus message {type: "haptic", payload:
      // {hapticType}}. Sent directly on hass.auth.external when it exists (inside the app),
      // otherwise through the window event HA forwards.
      const hapticType = type || HAPTIC_TYPES[this.pulse] || "light";
      this.lastHaptic += ` type ${hapticType}`;
      const external = document.querySelector("home-assistant")?.hass?.auth?.external;
      if (external?.fireMessage) external.fireMessage({type: "haptic", payload: {hapticType}});
      else window.dispatchEvent(new CustomEvent("haptic", {detail: hapticType}));
      this.lastHaptic += external?.fireMessage ? " via external bus" : " via window event";
    }
  }

  finished() {
    if (!this.readyForAudio || !this.audio || this.lastFinished === this.state.session_id) return;
    if (this.audio.state !== "running") { this.lastFinished = this.state.session_id; return; }
    this.lastFinished = this.state.session_id;
    if (this.state.settings.muted) return;
    // After the last beat has ended, so the chime never sums with a beat.
    const at = Math.max(this.audio.currentTime, this.lastToneEnd || 0);
    for (const t of TONES.chime) this.tone(at + t.start, t.frequency, t.duration, t.level, true);
  }
}
