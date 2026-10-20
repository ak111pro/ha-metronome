// Pure math/format checks. Does not exercise HA, a DOM or a real AudioContext.
import assert from "node:assert/strict";
import {METERS, tempo, dialFraction, point, remaining, timeText, escapeHTML} from "../custom_components/metronome/frontend/shared.js";
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
assert.equal(remaining({state:"playing",ends_at:100,settings:{duration:30}},60),30);
assert.equal(remaining({state:"playing",ends_at:100,settings:{duration:30}},101),0);
assert.equal(escapeHTML('<img src="x">'),"&lt;img src=&quot;x&quot;&gt;");
console.log("Frontend helper checks passed");
