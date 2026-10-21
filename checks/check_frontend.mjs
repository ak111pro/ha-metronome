// Pure math/format checks. Does not exercise HA, a DOM or a real AudioContext.
import assert from "node:assert/strict";
import {readFileSync, readdirSync} from "node:fs";
import {METERS, PEAK, TONES, TONE_TAIL, masterGain, cleanConfig, validColor, tempo, dialFraction, point, remaining, timeText, escapeHTML, hapticMode, HAPTIC_TYPES, VERSION} from "../custom_components/metronome/frontend/shared.js";
assert.equal(METERS["6/8"],2);
for (const [bpm,marking] of [[1,"Larghissimo"],[60,"Larghetto"],[120,"Allegro"],[200,"Prestissimo"]]) assert.equal(tempo(bpm),marking);
for (const inverted of [false,true]) {
  for (const fraction of [0,.25,.5,.75,1]) {
    const p = point((inverted ? 225 : 135) + (inverted ? -1 : 1)*270*fraction);
    assert.ok(Math.abs(dialFraction(p.x-160,p.y-160,inverted)-fraction)<1e-10);
  }
}
assert.equal(timeText(359999),"99:59:59");
assert.equal(timeText(0.01),"00:00:01");
assert.equal(remaining({state:"playing",ends_at:100,remaining:30,settings:{duration:30}},60),30);
assert.equal(remaining({state:"playing",ends_at:100,remaining:30,settings:{duration:30}},101),0);
// Resumed with 20 s left: the 200 ms start lead must not show as extra time.
assert.equal(remaining({state:"playing",ends_at:100.2,remaining:20,settings:{duration:30}},80.1),20);
assert.equal(escapeHTML('<img src="x">'),"&lt;img src=&quot;x&quot;&gt;");
// Haptics: vibrate wins wherever it exists (Android app + browsers), the Companion
// haptic event only without it (iOS app), nothing in plain iOS Safari.
const vib = {vibrate() {}};
assert.equal(hapticMode(vib, {externalApp: {}}), "vibrate");
assert.equal(hapticMode({}, {webkit: {messageHandlers: {externalBus: {}}}}), "companion");
assert.equal(hapticMode({}, {externalApp: {}}), "companion");
assert.equal(hapticMode({}, {webkit: {}}), null);
assert.equal(hapticMode(vib, {webkit: {messageHandlers: {externalBus: {}}}}), "companion"); // iOS app wins over a vibrate stub
assert.deepEqual([20, 40, 70].map(ms => HAPTIC_TYPES[ms]), ["light", "medium", "heavy"]);
// Card editor: YAML keeps type + entity first and only non-default options.
assert.deepEqual(Object.entries(cleanConfig({layout: "full", show_tempo: true, feedback: "dots_glow",
  entity: "media_player.m", type: "custom:metronome-card", name: "  ", show_timer: false, extra: 1})),
  [["type", "custom:metronome-card"], ["entity", "media_player.m"], ["show_timer", false], ["extra", 1]]);
assert.deepEqual(cleanConfig({type: "t", entity: "e", name: "Practice ", timer_display: "remaining"}),
  {type: "t", entity: "e", name: "Practice ", timer_display: "remaining"});
// Colours: validated with CSS.supports('color', …) (stubbed here), blank means theme default.
const supports = (prop, v) => prop === "color" && /^(teal|#[0-9a-f]{3}|#[0-9a-f]{6}|rgb\(.*\)|hsl\(.*\)|var\(--.*\))$/i.test(v);
for (const ok of ["teal", "#fff", "#16809e", "rgb(1, 2, 3)", "hsl(200 80% 40%)", "var(--red-color)", " teal "]) assert.ok(validColor(ok, supports), ok);
for (const bad of ["", "  ", "notacolour", null, 42]) assert.ok(!validColor(bad, supports), String(bad));
// Loudness: every sound peaks at -1 dBFS (0.891) at volume 100 % and is silent when muted;
// tones never overlap (beats at 200 BPM, the two chime tones), so nothing sums above it.
const dbfs = x => 20 * Math.log10(x);
for (const [name, t] of [["beat", TONES.beat], ["accent", TONES.accent], ["countIn", TONES.countIn], ["chime 1", TONES.chime[0]], ["chime 2", TONES.chime[1]]]) {
  const peak = t.level * masterGain(1, false);
  assert.ok(Math.abs(peak - 0.891) <= 0.001, `${name} peak ${peak}`);
  assert.ok(Math.abs(dbfs(peak) + 1) < 0.01, `${name} ${dbfs(peak)} dBFS`);
  assert.equal(t.level * masterGain(1, true), 0);
}
assert.equal(PEAK, 0.891);
assert.equal(masterGain(0.5, false), 0.5);
for (const t of [TONES.beat, TONES.accent, TONES.countIn]) assert.ok(t.duration + TONE_TAIL < 60 / 200, "beats overlap at 200 BPM");
assert.ok(TONES.chime[0].start + TONES.chime[0].duration + TONE_TAIL <= TONES.chime[1].start, "chime tones overlap");
assert.notEqual(TONES.beat.frequency, TONES.accent.frequency);  // the accent differs by pitch
// One version everywhere, and every relative module import is versioned (cache busting).
const root = new URL("../custom_components/metronome/", import.meta.url);
assert.equal(VERSION, JSON.parse(readFileSync(new URL("manifest.json", root))).version);
for (const file of readdirSync(new URL("frontend/", root)).filter(f => f.endsWith(".js"))) {
  const source = readFileSync(new URL(`frontend/${file}`, root), "utf8");
  for (const [, spec] of source.matchAll(/(?:from|import\()\s*"(\.\/[^"]+)"/g)) {
    assert.ok(spec.endsWith(`.js?v=${VERSION}`), `${file}: unversioned import ${spec}`);
  }
}
console.log("Frontend helper checks passed");
