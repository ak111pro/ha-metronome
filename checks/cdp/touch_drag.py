"""Touch-drag the BPM and timer dial handles: the value follows, the page must not scroll.

A vertical swipe that starts in the dial centre or on the arc track (anywhere but the
handle) must still scroll and must not change the value.
"""

import math

from cdp import aiohttp, asyncio, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full')"
GEOM = f"""
(sel => {{
  const c = {FULL};
  const r = c.shadowRoot.querySelector(sel).querySelector('svg').getBoundingClientRect();
  return {{x: r.left, y: r.top, w: r.width, top: c.getBoundingClientRect().top,
          bpm: c.player.state.settings.bpm, duration: c.player.state.settings.duration}};
}})
"""


async def swipe(cdp, points, step=0.03):
    first = {"x": points[0][0], "y": points[0][1]}
    await cdp.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[first])
    for x, y in points[1:]:
        await asyncio.sleep(step)
        await cdp.call("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x, "y": y}])
    await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    await asyncio.sleep(0.6)


def arc_points(g, start_deg, end_deg, n=14):
    s = g["w"] / 320
    cx, cy = g["x"] + 160 * s, g["y"] + 160 * s
    out = []
    for i in range(n + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / n)
        out.append((cx + 145 * s * math.cos(a), cy + 145 * s * math.sin(a)))
    return out


async def main():
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 640)
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        await login(cdp)
        settings = "{bpm: 100, timer_enabled: true, duration: 30}"
        await cdp.js(f"{FULL}.player.action('configure', {settings})")
        await cdp.idle(1.5)
        await cdp.js("window.scrollTo(0, 40); 1")  # dial below the HA toolbar
        await cdp.idle(1)

        g = await cdp.js(GEOM + "('.bpm-dial')")
        a0 = 135 + 270 * (g["bpm"] - 1) / 199
        await swipe(cdp, arc_points(g, a0, a0 + 60))
        g2 = await cdp.js(GEOM + "('.bpm-dial')")
        print(f"BPM drag: {g['bpm']} -> {g2['bpm']}, page moved {g2['top'] - g['top']:.0f}px")
        assert g2["bpm"] >= 140 and g2["top"] == g["top"]

        cx, cy = g2["x"] + g2["w"] / 2, g2["y"] + g2["w"] / 2
        await swipe(cdp, [(cx, cy - 10 * i) for i in range(12)])
        g3 = await cdp.js(GEOM + "('.bpm-dial')")
        print(f"centre swipe: page moved {g3['top'] - g2['top']:.0f}px (must scroll)")
        assert g3["top"] < g2["top"] - 50

        # A swipe that starts on the arc track (not the handle) scrolls too (alpha.6).
        await cdp.js("window.scrollTo(0, 40); 1")
        await cdp.idle(1)
        g4 = await cdp.js(GEOM + "('.bpm-dial')")
        tx, ty = arc_points(g4, 180, 180, 1)[0]
        await swipe(cdp, [(tx, ty - 10 * i) for i in range(12)])
        g5 = await cdp.js(GEOM + "('.bpm-dial')")
        print(
            f"track swipe: page moved {g5['top'] - g4['top']:.0f}px, BPM {g4['bpm']} -> {g5['bpm']} (must scroll, no change)"
        )
        assert g5["top"] < g4["top"] - 50 and g5["bpm"] == g4["bpm"]

        await cdp.js(
            f"{FULL}.shadowRoot.querySelector('.timer-dial').scrollIntoView({{block:'center'}}); 1"
        )
        await cdp.idle(1)
        t = await cdp.js(GEOM + "('.timer-dial')")
        a0 = 225 - 270 * (t["duration"] - 5) / 115
        await swipe(cdp, arc_points(t, a0, a0 - 50))
        t2 = await cdp.js(GEOM + "('.timer-dial')")
        moved = t2["top"] - t["top"]
        print(f"timer drag: {t['duration']} -> {t2['duration']} s, page moved {moved:.0f}px")
        assert t2["duration"] >= 45 and moved == 0

        reset = "{bpm: 120, timer_enabled: false, duration: 30}"
        await cdp.js(f"{FULL}.player.action('configure', {reset})")
        await cdp.idle(1)
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        assert not errors, errors
        print("touch drag OK")
        await cdp.ws.close()


run(main)
