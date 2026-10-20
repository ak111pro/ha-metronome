"""Compact card in HA tile style, on the test dashboard's "Compact vs Tile" view.

python compact.py [out-dir]
- Card widths 264-500 px: tile metrics (36 px icon circle, 42 px feature buttons, 12 px
  radius), nothing outside the card, no expand button; features_position inline puts the
  tempo row beside the name above 340 px and falls back to bottom below.
- The icon/name area is a <button> with an aria-label; Enter and a tap open the full dialog.
- BPM number pulse: keyframes per feedback mode (dots_glow: scale + glow, dots: scale only,
  off: none), stronger on the accented first beat, secondary colour in count-in, no scale
  with reduced motion; and a real session started from the native Tile on this page.
- Screenshots light/dark at 360 px next to the native Tile.
"""

import sys

from cdp import FIND, aiohttp, ha_state, login, open_page, run, service

ENTITY = "media_player.practice"
BOTTOM = "window.__cards.find(c => c.config.layout === 'compact' && c.config.features_position !== 'inline' && c.config.entity === 'media_player.practice')"
INLINE = "window.__cards.find(c => c.config.features_position === 'inline')"
DEEP = """window.deep = (sel, root = document) => { const out = [];
  const walk = r => { for (const el of r.querySelectorAll('*')) {
    if (el.matches(sel)) out.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
  walk(root); return out; }; 1"""
GEOM = """(c => { const r = c.shadowRoot, card = c.getBoundingClientRect();
  const box = sel => r.querySelector(sel).getBoundingClientRect();
  const feats = [...r.querySelectorAll('.compact-adjust button, .transport button')].filter(b => b.offsetParent)
    .map(b => b.getBoundingClientRect());
  const outside = [...r.querySelectorAll('*')].filter(e => e.offsetParent && (e.getBoundingClientRect().right > card.right + .5 || e.getBoundingClientRect().left < card.left - .5)).map(e => e.className);
  const info = r.querySelector('.compact-info');
  return {card: Math.round(card.width), icon: Math.round(box('.tile-icon').width),
    featureHeights: [...new Set(feats.map(b => Math.round(b.height)))],
    radius: getComputedStyle(r.querySelector('.transport button')).borderRadius,
    inline: Math.abs(box('.compact-adjust').top - box('.compact-info').top) < 20,
    outside, expandButtons: r.querySelectorAll('[aria-label="Open controls"]').length,
    infoTag: info.localName, infoLabel: info.getAttribute('aria-label')}; })"""
KEYFRAMES = """((c, beat, countIn) => { const el = c.shadowRoot.querySelector('.compact-bpm');
  c.pulse(beat, countIn); const a = el.getAnimations()[0];
  if (!a) return null; const k = a.effect.getKeyframes()[1];
  return {transform: k.transform || null, glow: k.textShadow || null, color: k.color}; })"""


def scale(keyframe):
    if keyframe and keyframe["transform"]:
        return float(keyframe["transform"].split("(")[1].rstrip(")"))
    return 1


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    results = []

    def check(label, ok, detail):
        results.append((label, bool(ok)))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 376, 1200)
        for theme in ("light", "dark"):
            await login(cdp, "/metronome-test/compact-tile", wait=12, theme=theme)
            if out:
                await cdp.shot(f"{out}/compact-tile-{theme}-360.png")
        await cdp.js(FIND)
        for width in (264, 280, 320, 340, 360, 440, 500):
            await cdp.call(
                "Emulation.setDeviceMetricsOverride",
                width=width + 16,
                height=1200,
                deviceScaleFactor=1,
                mobile=True,
            )
            await cdp.idle(0.8)
            for name, expr in (("bottom", BOTTOM), ("inline", INLINE)):
                g = await cdp.js(f"{GEOM}({expr})")
                want_inline = name == "inline" and g["card"] > 340
                ok = (
                    g["icon"] == 36
                    and g["featureHeights"] == [42]
                    and g["radius"] == "12px"
                    and not g["outside"]
                    and g["expandButtons"] == 0
                    and g["inline"] == want_inline
                    and g["infoTag"] == "button"
                    and g["infoLabel"].startswith("Open ")
                )
                check(f"{name} {width}px", ok, g)
        await cdp.call(
            "Emulation.setDeviceMetricsOverride",
            width=376,
            height=1200,
            deviceScaleFactor=1,
            mobile=True,
        )
        await cdp.idle(0.8)

        # Keyboard and tap open the full dialog.
        await cdp.js(f"{BOTTOM}.shadowRoot.querySelector('.compact-info').focus(); 1")
        await cdp.call(
            "Input.dispatchKeyEvent",
            type="keyDown",
            key="Enter",
            code="Enter",
            windowsVirtualKeyCode=13,
            text="\r",
        )
        await cdp.call(
            "Input.dispatchKeyEvent",
            type="keyUp",
            key="Enter",
            code="Enter",
            windowsVirtualKeyCode=13,
        )
        await cdp.idle(1)
        opened = await cdp.js(f"!!{BOTTOM}.shadowRoot.querySelector('dialog[open] metronome-card')")
        await cdp.js(f"{BOTTOM}.shadowRoot.querySelector('dialog')?.close(); 1")
        await cdp.idle(0.5)
        focus = await cdp.js(f"{BOTTOM}.shadowRoot.activeElement?.className")
        check("Enter opens the dialog, focus returns", opened and focus == "compact-info", focus)
        x, y = await cdp.js(
            f"(() => {{ const r = {INLINE}.shadowRoot.querySelector('.tile-text').getBoundingClientRect(); return [r.left + 10, r.top + 8]; }})()"
        )
        for kind in ("mousePressed", "mouseReleased"):
            await cdp.call(
                "Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1
            )
        await cdp.idle(1)
        opened = await cdp.js(f"!!{INLINE}.shadowRoot.querySelector('dialog[open] metronome-card')")
        check("tap on name opens the dialog", opened, opened)
        await cdp.js(f"{INLINE}.shadowRoot.querySelector('dialog')?.close(); 1")
        await cdp.idle(0.5)

        # Pulse keyframes per mode (simulated beats; settings: accent on).
        await cdp.js(f"{BOTTOM}.player.state.settings.accent = true; 1")
        base = await cdp.js(f"({BOTTOM}).config")
        for feedback in ("dots_glow", "dots", "off"):
            await cdp.js(f"{BOTTOM}.setConfig({{...{BOTTOM}.config, feedback: '{feedback}'}}); 1")
            await cdp.idle(0.3)
            normal = await cdp.js(f"{KEYFRAMES}({BOTTOM}, 1, false)")
            accent = await cdp.js(f"{KEYFRAMES}({BOTTOM}, 0, false)")
            count = await cdp.js(f"{KEYFRAMES}({BOTTOM}, 1, true)")
            if feedback == "off":
                check("feedback off: no pulse", normal is None and accent is None, normal)
                continue
            ok = (
                scale(normal) > 1
                and scale(accent) > scale(normal)
                and bool(normal["glow"]) == (feedback == "dots_glow")
                and count["color"] != normal["color"]
            )
            check(
                f"feedback {feedback}", ok, {"normal": normal, "accent": accent, "count_in": count}
            )
        await cdp.call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-reduced-motion", "value": "reduce"}],
        )
        await cdp.js(f"{BOTTOM}.setConfig({{...{BOTTOM}.config, feedback: 'dots_glow'}}); 1")
        await cdp.idle(0.3)
        k = await cdp.js(f"{KEYFRAMES}({BOTTOM}, 0, false)")
        check("reduced motion: glow/colour, no scale", k and not k["transform"] and k["glow"], k)
        await cdp.call("Emulation.setEmulatedMedia", features=[])
        await cdp.js(
            f"{BOTTOM}.setConfig({{...{BOTTOM}.config, feedback: '{base.get('feedback', 'dots_glow')}'}}); 1"
        )

        # Real session from the native Tile on this page: the compact number pulses.
        await cdp.js(DEEP)
        x, y = await cdp.js(
            "(() => { const b = deep('ha-control-button', deep('hui-tile-card')[0].shadowRoot).find(b => (b.getAttribute('aria-label') || b.label) === 'Play'); const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()"
        )
        for kind in ("mousePressed", "mouseReleased"):
            await cdp.call(
                "Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1
            )
        seen = 0
        for _ in range(20):
            await cdp.idle(0.1)
            seen += await cdp.js(
                f"{BOTTOM}.shadowRoot.querySelector('.compact-bpm').getAnimations().length"
            )
        ha = (await ha_state(session, ENTITY))["state"]
        if out:
            await cdp.shot(f"{out}/compact-tile-playing-dark.png")
        check(
            "playing session pulses the number",
            ha == "playing" and seen > 0,
            f"HA {ha}, animations seen {seen}",
        )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        await cdp.ws.close()
    print(f"{sum(ok for _, ok in results)}/{len(results)} passed")


run(main)
