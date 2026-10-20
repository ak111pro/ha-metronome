"""Timer handle drag: the h/m/s fields follow the finger live, like the BPM number.

Touch-drags the timer handle (the only drag target since alpha.6) in small steps from 30 s and samples the fields after every
move (before HA has answered, the fields must already show the dial's value), then checks
the value after release: fields, committed duration and arc agree, and the fields never
jump back to an older value. Also samples the BPM number during a BPM drag for comparison.
"""

import math

from cdp import aiohttp, asyncio, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full' && !c.config.primary_color)"
GEOM = f"""(sel => {{ const c = {FULL};
  const r = c.shadowRoot.querySelector(sel).querySelector('svg').getBoundingClientRect();
  return {{x: r.left, y: r.top, w: r.width}}; }})"""
READ = f"""(() => {{ const c = {FULL}, r = c.shadowRoot;
  const f = [...r.querySelectorAll('[data-field]')].map(i => Number(i.value));
  return {{fields: f[0] * 3600 + f[1] * 60 + f[2], server: c.player.state.settings.duration,
    bpm: Number(r.querySelector('.bpm').value), serverBpm: c.player.state.settings.bpm}}; }})()"""


def point(g, deg):
    s = g["w"] / 320
    a = math.radians(deg)
    return g["x"] + (160 + 145 * math.cos(a)) * s, g["y"] + (160 + 145 * math.sin(a)) * s


async def drag(cdp, g, start_deg, end_deg, steps, inverted):
    expected, samples = [], []
    x, y = point(g, start_deg)
    await cdp.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
    for i in range(1, steps + 1):
        deg = start_deg + (end_deg - start_deg) * i / steps
        x, y = point(g, deg)
        await cdp.call("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x, "y": y}])
        await asyncio.sleep(0.02)  # far below the 80 ms send coalescing and the HA round trip
        samples.append(await cdp.js(READ))
        fraction = ((225 - deg) if inverted else (deg - 135)) / 270
        expected.append(round(5 + fraction * 115) if inverted else round(1 + fraction * 199))
    await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    after = []
    for _ in range(12):
        await asyncio.sleep(0.1)
        after.append(await cdp.js(READ))
    return expected, samples, after


async def main():
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 376, 900)
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        await login(cdp)
        await cdp.js(
            f"{FULL}.player.action('configure', {{timer_enabled: true, duration: 30, bpm: 100}})"
        )
        await cdp.idle(1.5)
        await cdp.js(
            f"{FULL}.shadowRoot.querySelector('.timer-dial').scrollIntoView({{block:'center'}}); 1"
        )
        await cdp.idle(1)
        g = await cdp.js(GEOM + "('.timer-dial')")
        a0 = 225 - 270 * (30 - 5) / 115
        expected, samples, after = await drag(cdp, g, a0, a0 - 80, 20, True)
        live = sum(abs(s["fields"] - e) <= 1 for s, e in zip(samples, expected, strict=True))
        ahead = sum(s["fields"] != s["server"] for s in samples)
        final = after[-1]
        print(
            f"timer: {live}/{len(samples)} samples show the dial value live "
            f"({ahead} ahead of HA's value); expected {expected[0]}..{expected[-1]} s, "
            f"fields {[s['fields'] for s in samples]}"
        )
        print(
            f"timer after release: fields {final['fields']} s, HA {final['server']} s, "
            f"values seen after release {sorted({a['fields'] for a in after})}"
        )
        timer_ok = (
            live == len(samples)
            and final["fields"] == final["server"] == expected[-1]
            and {a["fields"] for a in after} == {final["fields"]}  # never jumps back
        )

        await cdp.js(
            f"{FULL}.shadowRoot.querySelector('.bpm-dial').scrollIntoView({{block:'center'}}); 1"
        )
        await cdp.idle(1)
        g = await cdp.js(GEOM + "('.bpm-dial')")
        b0 = 135 + 270 * (100 - 1) / 199
        expected, samples, after = await drag(cdp, g, b0, b0 + 40, 10, False)
        bpm_live = sum(abs(s["bpm"] - e) <= 1 for s, e in zip(samples, expected, strict=True))
        print(
            f"BPM: {bpm_live}/{len(samples)} samples live, final {after[-1]['bpm']} "
            f"(HA {after[-1]['serverBpm']})"
        )
        bpm_ok = bpm_live == len(samples) and after[-1]["bpm"] == after[-1]["serverBpm"]

        reset = "{bpm: 120, timer_enabled: false, duration: 30}"
        await cdp.js(f"{FULL}.player.action('configure', {reset})")
        await cdp.idle(1)
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        await cdp.ws.close()
    print(
        "timer drag live:",
        "OK" if timer_ok else "FAIL",
        "| BPM drag live:",
        "OK" if bpm_ok else "FAIL",
        "| errors:",
        errors,
    )


run(main)
