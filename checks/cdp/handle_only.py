"""Only the handle drags: taps and swipes on the arc track change nothing and scroll.

For the BPM and the timer dial: a touch tap and a mouse click on the track far from the
handle leave HA's value, the number/fields and the knob position unchanged; a vertical
swipe that starts on the track scrolls the page; a tap on the handle itself (no movement)
changes nothing; dragging the handle still changes the value without scrolling.
"""

import math

from cdp import aiohttp, asyncio, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full' && !c.config.primary_color)"
READ = f"""(sel => {{ const c = {FULL}, r = c.shadowRoot, d = r.querySelector(sel);
  const svg = d.querySelector('svg').getBoundingClientRect(), k = d.querySelector('.knob');
  const f = [...r.querySelectorAll('[data-field]')].map(i => i.value).join(':');
  return {{x: svg.left, y: svg.top, w: svg.width, top: c.getBoundingClientRect().top,
    bpm: c.player.state.settings.bpm, duration: c.player.state.settings.duration,
    shownBpm: r.querySelector('.bpm').value, fields: f,
    knob: [Math.round(+k.getAttribute('cx')), Math.round(+k.getAttribute('cy'))]}}; }})"""


def at(g, deg, radius=145):
    s = g["w"] / 320
    a = math.radians(deg)
    return g["x"] + (160 + radius * math.cos(a)) * s, g["y"] + (160 + radius * math.sin(a)) * s


async def touch(cdp, points, step=0.03):
    await cdp.call(
        "Input.dispatchTouchEvent",
        type="touchStart",
        touchPoints=[{"x": points[0][0], "y": points[0][1]}],
    )
    for x, y in points[1:]:
        await asyncio.sleep(step)
        await cdp.call("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x, "y": y}])
    await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    await asyncio.sleep(0.8)


async def click(cdp, x, y):
    await cdp.call("Emulation.setTouchEmulationEnabled", enabled=False)
    for kind in ("mousePressed", "mouseReleased"):
        await cdp.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
    await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    await asyncio.sleep(0.8)


def same(a, b, keys):
    return all(a[k] == b[k] for k in keys)


async def main():
    results = []

    def check(label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 376, 700)
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        await login(cdp)
        saved = await cdp.js(
            f"(() => {{ const s = {FULL}.player.state.settings; return {{bpm: s.bpm, timer_enabled: s.timer_enabled, duration: s.duration}}; }})()"
        )
        await cdp.js(
            f"{FULL}.player.action('configure', {{bpm: 100, timer_enabled: true, duration: 30}})"
        )
        await cdp.idle(1.5)
        for sel, inverted, keys in (
            (".bpm-dial", False, ["bpm", "shownBpm", "knob"]),
            (".timer-dial", True, ["duration", "fields", "knob"]),
        ):
            await cdp.js(
                f"{FULL}.shadowRoot.querySelector('{sel}').scrollIntoView({{block: 'center'}}); 1"
            )
            await cdp.idle(1)
            g = await cdp.js(f"{READ}('{sel}')")
            value = g["duration"] if inverted else g["bpm"]
            knob_deg = (
                (225 - 270 * (value - 5) / 115) if inverted else (135 + 270 * (value - 1) / 199)
            )
            far = knob_deg - 120 if inverted else knob_deg + 120  # on the track, far from the knob
            x, y = at(g, far)
            await touch(cdp, [(x, y)])
            g2 = await cdp.js(f"{READ}('{sel}')")
            check(
                f"{sel} touch tap on track changes nothing",
                same(g, g2, keys),
                {k: (g[k], g2[k]) for k in keys},
            )
            await click(cdp, x, y)
            g3 = await cdp.js(f"{READ}('{sel}')")
            check(
                f"{sel} click on track changes nothing",
                same(g, g3, keys),
                {k: (g[k], g3[k]) for k in keys},
            )
            kx, ky = at(g, knob_deg)
            await touch(cdp, [(kx, ky)])
            g4 = await cdp.js(f"{READ}('{sel}')")
            check(
                f"{sel} tap on the handle changes nothing",
                same(g, g4, keys),
                {k: (g[k], g4[k]) for k in keys},
            )
            # Swipe up starting on the track (left side of the arc) scrolls the page.
            sx, sy = at(g, 180)
            await touch(cdp, [(sx, sy - 12 * i) for i in range(10)])
            g5 = await cdp.js(f"{READ}('{sel}')")
            moved = g["top"] - g5["top"]
            check(
                f"{sel} swipe on track scrolls",
                moved > 40 and same(g, g5, keys[:-1]),
                f"page moved {moved:.0f} px",
            )
            await cdp.js(
                f"{FULL}.shadowRoot.querySelector('{sel}').scrollIntoView({{block: 'center'}}); 1"
            )
            await cdp.idle(1)
            g = await cdp.js(f"{READ}('{sel}')")
            pts = [at(g, knob_deg + (-1 if inverted else 1) * 40 * i / 12) for i in range(13)]
            await touch(cdp, pts)
            g6 = await cdp.js(f"{READ}('{sel}')")
            changed = (g6["duration"] if inverted else g6["bpm"]) != value
            check(
                f"{sel} handle drag changes the value, no scroll",
                changed and g6["top"] == g["top"],
                f"{value} -> {g6['duration'] if inverted else g6['bpm']}, page moved {g['top'] - g6['top']:.0f} px",
            )
        await cdp.js(
            f"{FULL}.player.action('configure', {saved})".replace("True", "true").replace(
                "False", "false"
            )
        )
        await cdp.idle(1)
        await cdp.ws.close()
    print(f"{sum(results)}/{len(results)} passed")


run(main)
