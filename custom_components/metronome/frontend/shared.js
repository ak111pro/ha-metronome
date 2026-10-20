/* Pure helpers shared by the card and local audio engine. */
// Keep equal to manifest.json. Every relative import carries ?v=VERSION as well: HA serves
// these modules without Cache-Control, so a phone could otherwise keep stale submodules
// after the resource URL was bumped (checks/check_frontend.mjs enforces both).
export const VERSION = "0.1.0-alpha.2";
export const METERS = {"2/4": 2, "3/4": 3, "4/4": 4, "6/8": 2};
export const DEFAULT_CONFIG = {
  layout: "full", show_tempo: true, show_signature: true, show_timer: true,
  show_advanced: true, feedback: "dots_glow", timer_display: "remaining_finish",
};
export const clamp = (value, min, max) => Math.max(min, Math.min(max, Number(value) || 0));
export const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
export function tempo(bpm) {
  return [[1,"Larghissimo"],[25,"Grave"],[40,"Largo"],[60,"Larghetto"],
    [66,"Adagio"],[76,"Andante"],[108,"Moderato"],[120,"Allegro"],
    [168,"Vivace"],[176,"Presto"],[200,"Prestissimo"]].filter(([n]) => bpm >= n).at(-1)?.[1] || "";
}
export const beatPosition = (state, now) => state.anchor_beat +
  (state.state === "playing" ? (now - state.anchor_at) * state.settings.bpm / 60 : 0);
export function remaining(state, now) {
  return state.state === "playing" && state.ends_at != null
    ? clamp(state.ends_at - now, 0, state.remaining) : state.remaining;
}
export function splitTime(seconds) {
  const s = Math.ceil(Math.max(0, seconds));
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60];
}
export const timeText = seconds => splitTime(seconds).map(n => String(n).padStart(2, "0")).join(":");
export function point(angle) {
  const a = angle * Math.PI / 180;
  return {x: 160 + 145 * Math.cos(a), y: 160 + 145 * Math.sin(a)};
}
export function arc(start, sweep) {
  const a = point(start), b = point(start + sweep);
  return `M ${a.x} ${a.y} A 145 145 0 ${Math.abs(sweep) > 180 ? 1 : 0} ${sweep >= 0 ? 1 : 0} ${b.x} ${b.y}`;
}
export function dialFraction(x, y, inverted = false) {
  const a = Math.atan2(y, x) * 180 / Math.PI;
  const delta = ((inverted ? 225 - a : a - 135) % 360 + 360) % 360;
  return delta <= 270 ? delta / 270 : delta < 315 ? 1 : 0;
}
/* Haptics: navigator.vibrate where the browser/WebView has it (Android app and browsers;
 * exact 20/40/70 ms pulses). Otherwise, inside the HA Companion app (iOS has no
 * navigator.vibrate), HA's own "haptic" event, which the frontend forwards to the app.
 * The app picks the strength for light/medium/heavy; there is no intensity control. */
export const HAPTIC_TYPES = {20: "light", 40: "medium", 70: "heavy"};
export function hapticMode(nav = globalThis.navigator, win = globalThis.window) {
  if (typeof nav?.vibrate === "function") return "vibrate";
  if (win?.externalApp || win?.webkit?.messageHandlers?.externalBus) return "companion";
  return null;
}
