"""Output group in Advanced (no device line under the title any more).

Two pages of the same HA user: page A selects itself with "Play on this device" (no
Start), page B then shows "Another device (<user>)" with the button enabled; while A plays,
B's button is disabled with a hint and B's compact card says "on another device"; after
Stop, B takes over and A shows "Another device". Leaves both pages closed (output released).
python output.py [out-dir]
"""

import sys

from cdp import FIND, aiohttp, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full' && c.config.entity === 'media_player.metronome' && !c.config.primary_color)"
COMPACT = "window.__cards.find(c => c.config.layout === 'compact' && c.config.entity === 'media_player.metronome')"
READ = f"""(() => {{ const c = {FULL}, r = c.shadowRoot, b = r.querySelector('.output-claim');
  return {{header: r.querySelector('.header').textContent.trim(),
    deviceLine: !!r.querySelector('.device'),
    titleAlign: getComputedStyle(r.querySelector('.header')).textAlign,
    output: r.querySelector('.output-device').textContent,
    button: b.hidden ? 'hidden' : b.disabled ? 'disabled' : 'enabled',
    note: r.querySelector('.output-note').textContent,
    state: c.player.state.state, owner: c.player.state.is_owner}}; }})()"""
PIN_VISIBLE = """(() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  return 1; })()"""
NAV = """(path => { history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', {detail: {replace: false}}));
  return 1; })"""
CLICK = f"(sel => {{ {FULL}.shadowRoot.querySelector(sel).click(); return 1; }})"


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    results = []

    def expect(label, got, **want):
        bad = {k: got[k] for k, v in want.items() if got[k] != v and not (
            callable(v) and v(got[k]))}
        results.append((label, bad))
        print(f"{'OK ' if not bad else 'BAD'} {label}: {got}" + (f" -> {bad}" if bad else ""))

    async with aiohttp.ClientSession() as session:
        a = await open_page(session, 360, 1400)
        await login(a, wait=12)
        # Headless shows one tab at a time: keep page A "visible" while B is in front
        # (a hidden owner page releases the output, as on a phone).
        await a.js(PIN_VISIBLE)
        await a.js(f"{FULL}.player.action('configure', {{timer_enabled: false, count_in: 0}})")
        await a.js(CLICK + "('[data-action=advanced]')", gesture=True)
        await a.idle(1)
        user = await a.js("document.querySelector('home-assistant').hass.user.name")
        first = await a.js(READ)
        expect("title only, centred", first, deviceLine=False, titleAlign="center")
        expect("A before", first, output=lambda v: v in ("No device selected",)
               or v.startswith("Another device"), button="enabled")
        await a.js(CLICK + "('.output-claim')", gesture=True)
        await a.idle(1.5)
        expect("A after Play on this device", await a.js(READ), output="This device",
               button="hidden", state="idle", owner=True)
        if out:
            await a.shot(f"{out}/output-this-device.png")

        b = await open_page(session, 360, 1400, new=True)
        await login(b, wait=12)
        await b.js(CLICK + "('[data-action=advanced]')", gesture=True)
        expect("B sees A", await b.js(READ), output=f"Another device ({user})",
               button="enabled", owner=False)

        await a.js(CLICK + "('[data-action=back]')", gesture=True)
        await a.js(CLICK + "('[data-action=start]')", gesture=True)
        await a.idle(1.5)
        expect("B while A plays", await b.js(READ), output=f"Another device ({user})",
               button="disabled", note="Stop the session to move playback to this device.",
               state="playing")
        if out:
            await b.shot(f"{out}/output-another-device.png")
        await b.js(NAV + "('/metronome-test/compact')")
        await b.idle(3)
        await b.js(FIND)
        meta = await b.js(f"{COMPACT}.shadowRoot.querySelector('.compact-info .meta').textContent")
        expect("B compact line", {"meta": meta}, meta=lambda v: v.startswith("Active on another device · BPM"))
        await a.js(f"{FULL}.player.action('stop')")
        await a.idle(1)
        meta = await b.js(f"{COMPACT}.shadowRoot.querySelector('.compact-info .meta').textContent")
        expect("B compact idle", {"meta": meta}, meta=lambda v: v.startswith("Idle · BPM"))

        await b.js(NAV + "('/metronome-test/full')")
        await b.idle(3)
        await b.js(FIND)
        await b.js(CLICK + "('[data-action=advanced]')", gesture=True)
        await b.js(CLICK + "('.output-claim')", gesture=True)
        await b.idle(1.5)
        expect("B took over", await b.js(READ), output="This device", button="hidden", owner=True)
        expect("A sees B", await a.js(READ), output=f"Another device ({user})",
               button="enabled", owner=False)
        for page in (b, a):
            await page.call("Page.navigate", url="about:blank")
            await page.idle(1)
        await b.ws.close()
        await a.ws.close()
    bad = [r for r in results if r[1]]
    print(f"{len(results) - len(bad)}/{len(results)} passed")


run(main)
