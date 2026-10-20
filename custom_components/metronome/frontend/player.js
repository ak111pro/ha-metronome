/* A single engine per HA connection/entity, independent of card attachment.
 * No audio is generated on the HA host. WS sends session changes, never beats.
 */
import {METERS, HAPTIC_TYPES, beatPosition, hapticMode} from "./shared.js";

const REGISTRY = Symbol.for("metronome.players.v1");
globalThis[REGISTRY] ||= new WeakMap();
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
    this.lastFinished = null;
    this.error = "";
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
      if (this.audio.state !== "running") await this.audio.resume();
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

  async start() {
    // resume() is invoked directly during the click gesture, before network waits.
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) throw new Error("Audio is unavailable in this browser");
    if (!this.audio || this.audio.state === "closed") {
      this.audio = new Audio({latencyHint: "interactive"});
      this.master = this.audio.createGain();
      this.master.connect(this.audio.destination);
      this.audio.addEventListener("statechange", () => {
        if (this.readyForAudio && this.audio.state !== "running") this.interrupt("Audio was interrupted. Tap Start to enable it again.");
        else if (this.audio.state === "running") this.rearm();
      });
    }
    await this.audio.resume();
    if (this.audio.state !== "running") throw new Error("Tap Start again to allow audio on this device");
    await this.ready;
    this.readyForAudio = true;
    this.armed = true;
    this.error = "";
    try {
      await this.send("claim");
      await this.send("start");
    } catch (error) {
      if (!this.state?.is_owner) this.readyForAudio = false;
      throw error;
    }
  }

  async action(action, settings) {
    await this.ready;
    this.error = "";
    return this.send(action, settings);
  }

  updateGain() {
    if (this.audio && this.master && this.state) {
      const s = this.state.settings;
      this.master.gain.setTargetAtTime(s.muted ? 0 : s.volume * 0.65, this.audio.currentTime, 0.01);
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
    oscillator.stop(when + duration + 0.01);
  }

  schedule() {
    const state = this.state;
    const period = 60 / state.settings.bpm;
    // Convert once per timeline update, then schedule against the audio clock.
    const base = this.audio.currentTime + state.anchor_at - this.now();
    let index = Math.max(Math.ceil(state.anchor_beat), Math.ceil(beatPosition(state, this.now() + 0.005)));
    const tick = () => {
      if (!this.readyForAudio || this.audio.state !== "running") return this.interrupt();
      if (state.ends_at != null && this.now() >= state.ends_at) {
        this.silence(); this.finished(); return;
      }
      let when = base + (index - state.anchor_beat) * period;
      // Do not burst through missed beats after a foreground main-thread stall.
      if (when < this.audio.currentTime - 0.03) {
        index = Math.ceil(state.anchor_beat + (this.audio.currentTime - base) / period);
        when = base + (index - state.anchor_beat) * period;
      }
      while (when < this.audio.currentTime + 0.10) {
        const utc = state.anchor_at + (index - state.anchor_beat) * period;
        if (state.ends_at != null && utc >= state.ends_at) break;
        const beat = ((index % METERS[state.settings.signature]) + METERS[state.settings.signature]) % METERS[state.settings.signature];
        const countIn = index < 0;
        const accent = beat === 0 && this.state.settings.accent;
        this.tone(Math.max(when, this.audio.currentTime), countIn ? 800 : accent ? 1500 : 1000,
          countIn ? 0.055 : 0.045, countIn ? 0.15 : accent ? 0.27 : 0.18);
        const timeout = setTimeout(() => {
          this.visuals.delete(timeout);
          this.emit("beat", {beat, countIn});
          if (this.vibration && !document.hidden) this.buzz();
        }, Math.max(0, when - this.audio.currentTime) * 1000);
        this.visuals.add(timeout);
        index++;
        when = base + (index - state.anchor_beat) * period;
      }
    };
    this.loop = setInterval(tick, 25);
    tick();
  }

  buzz() {
    const mode = hapticMode();
    if (mode === "vibrate") navigator.vibrate(this.pulse);
    // HA's frontend listens for this on window and passes it to the Companion app.
    else if (mode === "companion") window.dispatchEvent(new CustomEvent("haptic", {detail: HAPTIC_TYPES[this.pulse] || "light"}));
  }

  finished() {
    if (!this.readyForAudio || !this.audio || this.lastFinished === this.state.session_id) return;
    this.lastFinished = this.state.session_id;
    if (this.state.settings.muted) return;
    this.tone(this.audio.currentTime + 0.01, 659.25, 0.20, 0.18, true);
    this.tone(this.audio.currentTime + 0.23, 880, 0.36, 0.16, true);
  }
}
