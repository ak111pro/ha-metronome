"""Expanded dialog from the compact card: close button on the title row, little space
above the dial, and the whole content (timer open; Advanced) reachable by scrolling.

python dialog.py [out-dir]   Phones 360x800, 384x854 (Galaxy S21 Ultra), 412x915 and a short
360x640 (forces scrolling), light and dark. With the timer open: either everything fits,
or a swipe starting on an arc track scrolls the dialog. Advanced: header clear of the X,
swipe-scrollable to the end.
Uses the compact Practice card on the Full view and turns its timer on (restored).
"""

import sys

from cdp import FIND, aiohttp, asyncio, login, open_page, run

COMPACT = "window.__cards.find(c => c.config.layout === 'compact' && c.config.entity === 'media_player.practice')"
DIALOG = f"{COMPACT}.shadowRoot.querySelector('dialog')"
INNER = f"{DIALOG}.querySelector('metronome-card')"
MEASURE = f"""(() => {{ const d = {DIALOG}, r = {INNER}.shadowRoot;
  const box = el => el.getBoundingClientRect(), db = box(d), x = box(d.querySelector('.dialog-close'));
  const title = box(r.querySelector('.header .name')), dial = box(r.querySelector('.bpm-dial svg'));
  const timer = box(r.querySelector('.timer-dial svg'));
  return {{dialog: [Math.round(db.top), Math.round(db.bottom), Math.round(db.width)],
    closeCenter: Math.round(x.top + x.height / 2 - db.top), titleCenter: Math.round(title.top + title.height / 2 - db.top),
    titleCentred: Math.abs((title.left + title.right) / 2 - (db.left + db.right) / 2) < 2,
    titleClear: title.right <= x.left, dialTop: Math.round(dial.top - db.top), titleToDial: Math.round(dial.top - title.bottom),
    scrollable: d.scrollHeight > d.clientHeight + 1, scrollTop: d.scrollTop,
    timerOpen: r.querySelector('.timer-panel').classList.contains('open'),
    timerBottomVisible: timer.bottom <= db.bottom + 0.5 && timer.height > 0}}; }})()"""
ADV = f"""(() => {{ const d = {DIALOG}, r = {INNER}.shadowRoot, db = d.getBoundingClientRect();
  const x = d.querySelector('.dialog-close').getBoundingClientRect();
  const back = r.querySelector('[data-action=back]').getBoundingClientRect();
  const crumb = r.querySelector('.subheader .name').getBoundingClientRect();
  const items = [...r.querySelectorAll('.advanced-view *')].filter(e => e.offsetParent);
  const last = Math.max(...items.map(e => e.getBoundingClientRect().bottom));
  return {{overlap: crumb.right > x.left || back.right > x.left, closeVisible: x.top >= db.top,
    lastVisible: last <= db.bottom + 0.5, scrollTop: d.scrollTop}}; }})()"""


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    results = []

    def check(label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 800)
        await login(cdp, wait=12)
        await cdp.js(FIND)
        saved = await cdp.js(f"{COMPACT}.player.state.settings.timer_enabled")
        await cdp.js(f"{COMPACT}.player.action('configure', {{timer_enabled: true}})")
        for width, height in ((360, 800), (384, 854), (412, 915), (360, 640)):
            for theme in ("light", "dark"):
                await cdp.call(
                    "Emulation.setDeviceMetricsOverride",
                    width=width,
                    height=height,
                    deviceScaleFactor=2,
                    mobile=True,
                )
                await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
                await login(cdp, wait=10, theme=theme)
                await cdp.js(FIND)
                await cdp.js(
                    f"{COMPACT}.shadowRoot.querySelector('.compact-info').click(); 1", gesture=True
                )
                await cdp.idle(1.5)
                m = await cdp.js(MEASURE)
                tag = f"{width}x{height} {theme}"
                check(
                    f"{tag} X on the title row",
                    abs(m["closeCenter"] - m["titleCenter"]) <= 4
                    and m["titleCentred"]
                    and m["titleClear"],
                    m,
                )
                check(
                    f"{tag} dial right after the title",
                    m["titleToDial"] <= 16 and m["dialTop"] <= 72,
                    f"dial top {m['dialTop']} px, title->dial {m['titleToDial']} px",
                )
                if out:
                    await cdp.shot(f"{out}/dialog-{width}-{theme}-top.png")
                # Swipe up on the timer arc track (no handle there) scrolls the dialog.
                x, y = await cdp.js(
                    f"(() => {{ const b = {INNER}.shadowRoot.querySelector('.bpm-dial svg').getBoundingClientRect(); return [b.left + b.width * 0.06, b.top + b.height * 0.5]; }})()"
                )
                await cdp.call(
                    "Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}]
                )
                for i in range(1, 14):
                    await asyncio.sleep(0.03)
                    await cdp.call(
                        "Input.dispatchTouchEvent",
                        type="touchMove",
                        touchPoints=[{"x": x, "y": y - 30 * i}],
                    )
                await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
                await cdp.idle(1)
                swiped = await cdp.js(f"{DIALOG}.scrollTop")
                await cdp.js(f"{DIALOG}.scrollTop = 1e6; 1")
                await cdp.idle(0.5)
                m2 = await cdp.js(MEASURE)
                # Either everything fits, or a swipe that starts on the arc scrolls the dialog.
                check(
                    f"{tag} timer reachable",
                    m["timerOpen"]
                    and m2["timerBottomVisible"]
                    and (not m["scrollable"] or swiped > 100),
                    f"fits: {not m['scrollable']}, swipe on arc scrolled {swiped} px, timer end visible {m2['timerBottomVisible']}",
                )
                if out:
                    await cdp.shot(f"{out}/dialog-{width}-{theme}-bottom.png")
                await cdp.js(
                    f"{DIALOG}.scrollTop = 0; {INNER}.shadowRoot.querySelector('[data-action=advanced]').click(); 1",
                    gesture=True,
                )
                await cdp.idle(0.8)
                a1 = await cdp.js(ADV)
                await cdp.call(
                    "Input.dispatchTouchEvent",
                    type="touchStart",
                    touchPoints=[{"x": width / 2, "y": height * 0.7}],
                )
                for i in range(1, 14):
                    await asyncio.sleep(0.03)
                    await cdp.call(
                        "Input.dispatchTouchEvent",
                        type="touchMove",
                        touchPoints=[{"x": width / 2, "y": height * 0.7 - 25 * i}],
                    )
                await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
                await cdp.idle(0.8)
                a1["swiped"] = await cdp.js(f"{DIALOG}.scrollTop")
                await cdp.js(f"{DIALOG}.scrollTop = 1e6; 1")
                await cdp.idle(0.4)
                a2 = await cdp.js(ADV)
                check(
                    f"{tag} Advanced: header clear, all reachable",
                    not a1["overlap"]
                    and a1["closeVisible"]
                    and a2["lastVisible"]
                    and (a1["lastVisible"] or a1["swiped"] > 0),
                    {"top": a1, "end": a2},
                )
                if out and theme == "dark":
                    await cdp.js(f"{DIALOG}.scrollTop = 0; 1")
                    await cdp.shot(f"{out}/dialog-{width}-{theme}-advanced.png")
                await cdp.js(f"{DIALOG}.close(); 1")
        await cdp.js(
            f"{COMPACT}.player.action('configure', {{timer_enabled: {'true' if saved else 'false'}}})"
        )
        await cdp.idle(1)
        await cdp.ws.close()
    print(f"{sum(results)}/{len(results)} passed")


run(main)
