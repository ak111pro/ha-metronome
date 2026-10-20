// Pure math/format checks. Does not exercise HA, a DOM or a real AudioContext.
import assert from "node:assert/strict";
import {readFileSync, readdirSync} from "node:fs";
import {METERS, tempo, dialFraction, point, remaining, timeText, escapeHTML, hapticMode, HAPTIC_TYPES, VERSION} from "../custom_components/metronome/frontend/shared.js";
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
assert.deepEqual([20, 40, 70].map(ms => HAPTIC_TYPES[ms]), ["light", "medium", "heavy"]);
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
