"""Items from 0.1.0-beta.3 to beta.9 that no other check covers, on the "Compact vs Tile" view.

python beta_items.py [out-dir]
- Compact timer bar: 24 px high with fully round caps, remaining time and finish time inside the
  bar in the same font size and weight, nothing outside the card; while playing (started from the
  native Tile on this page) the countdown runs and the finish time is shown.
- No grey/blue flash on taps: the compact card and its buttons have a transparent tap highlight.
- Without the -1/+1 buttons (show_step_buttons: false) the BPM number sits in the header row,
  24 px, and the step buttons are gone.
- Connection notices: quiet grey "Reconnecting…" without Show diagnostics, red full text with it.
- Full-card dialog: the close button sits at the top left.
- Screenshots light/dark at 360 px with the timer bar running (README).
"""

import json
import sys

from cdp import FIND, aiohttp, login, open_page, run, service

ENTITY = "media_player.practice"
BOTTOM = "window.__cards.find(c => c.config.layout === 'compact' && c.config.features_position !== 'inline' && c.config.entity === 'media_player.practice')"
BAR = f"""(() => {{ const c = {BOTTOM}, r = c.shadowRoot, card = c.getBoundingClientRect();
  const bar = r.querySelector('.timerbar .bar'), b = bar.getBoundingClientRect(), cs = getComputedStyle(bar);
  const spans = [...r.querySelectorAll('.bar-label:not(.on-fill) span')];
  const inside = spans.filter(s => s.textContent).every(s => {{ const x = s.getBoundingClientRect();
    return x.left >= b.left - .5 && x.right <= b.right + .5 && x.top >= b.top - .5 && x.bottom <= b.bottom + .5; }});
  const fonts = [...new Set(spans.map(s => getComputedStyle(s).fontSize + ' ' + getComputedStyle(s).fontWeight))];
  return {{visible: !r.querySelector('.timerbar').hidden, height: Math.round(b.height),
    radius: parseFloat(cs.borderTopLeftRadius), inside, fonts,
    texts: spans.map(s => s.textContent), withinCard: b.left >= card.left - .5 && b.right <= card.right + .5}}; }})()"""
TAP = f"""(() => {{ const r = {BOTTOM}.shadowRoot;
  return [getComputedStyle(r.querySelector('ha-card')).webkitTapHighlightColor,
    ...[...r.querySelectorAll('button')].map(b => getComputedStyle(b).webkitTapHighlightColor)]; }})()"""
NOSTEPS = f"""(() => {{ const r = {BOTTOM}.shadowRoot;
  const bpm = r.querySelector('.compact-bpm'), info = r.querySelector('.compact-info');
  const steps = [...r.querySelectorAll('.compact-adjust .feature')].filter(b => b.offsetParent).length;
  const bb = bpm.getBoundingClientRect(), ib = info.getBoundingClientRect();
  return {{steps, bpmVisible: !!bpm.offsetParent, fontSize: getComputedStyle(bpm).fontSize,
    sameRow: bb.top < ib.bottom && bb.bottom > ib.top, rightOfInfo: bb.left >= ib.right - .5}}; }})()"""
DEEP = """window.deep = (sel, root = document) => { const out = [];
  const walk = r => { for (const el of r.querySelectorAll('*')) {
    if (el.matches(sel)) out.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
  walk(root); return out; }; 1"""
PLAY = """(() => { const b = deep('ha-control-button', deep('hui-tile-card')[0].shadowRoot).find(b => (b.getAttribute('aria-label') || b.label) === 'Play');
  const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()"""
NOTICE = f"""((diag) => {{ const c = {BOTTOM}, p = c.player;
  const saved = {{error: p.error, errorKind: p.errorKind, connection: p.connection, diag: p.showDiagnostics}};
  p.error = 'Connection to Home Assistant lost'; p.errorKind = 'notice';
  p.connection = {{...(p.connection || {{}}), connected: false}}; p.showDiagnostics = diag;
  c.update(); const m = c.shadowRoot.querySelector('.message');
  const out = {{text: m.textContent, quiet: m.classList.contains('quiet'), hidden: m.hidden, color: getComputedStyle(m).color}};
  Object.assign(p, {{error: saved.error, errorKind: saved.errorKind, connection: saved.connection, showDiagnostics: saved.diag}});
  c.update(); return out; }})"""


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    results = []

    def check(label, ok, detail):
        results.append((label, bool(ok)))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 376, 1200)
        await login(cdp, "/metronome-test/compact-tile", wait=12)
        await cdp.js(FIND)
        base = await cdp.js(f"({BOTTOM}).config")

        # Timer bar, idle and running.
        await cdp.js(
            f"{BOTTOM}.setConfig({{...{BOTTOM}.config, show_timer: true, show_timer_bar: true, show_step_buttons: true}}); 1"
        )
        await cdp.js(f"{BOTTOM}.player.action('configure', {{timer_enabled: true, duration: 20}})")
        await cdp.idle(1.5)
        for phase in ("idle", "playing"):
            if phase == "playing":
                await cdp.js(DEEP)
                x, y = await cdp.js(PLAY)
                for kind in ("mousePressed", "mouseReleased"):
                    await cdp.call(
                        "Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1
                    )
                await cdp.idle(7)
            g = await cdp.js(BAR)
            g["phase"] = await cdp.js(
                f"(s => s && [s.state, s.phase || null])({BOTTOM}.player.state)"
            )
            ok = (
                (phase == "idle" or (g["texts"][0] != "00:00:20" and g["texts"][1]))
                and g["visible"]
                and g["height"] == 24
                and g["radius"] >= 12
                and g["inside"]
                and len(g["fonts"]) == 1
                and g["withinCard"]
            )
            check(f"timer bar {phase}", ok, g)
        if out:
            for theme in ("light", "dark"):
                await cdp.call(
                    "Emulation.setEmulatedMedia",
                    features=[{"name": "prefers-color-scheme", "value": theme}],
                )
                await cdp.idle(1)
                await cdp.shot(f"{out}/compact-timer-bar-{theme}-360.png")
            await cdp.call("Emulation.setEmulatedMedia", features=[])
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.idle(1)

        # Tap highlight.
        colours = await cdp.js(TAP)
        check(
            "transparent tap highlight",
            all(c == "rgba(0, 0, 0, 0)" for c in colours),
            sorted(set(colours)),
        )

        # Without the -1/+1 buttons.
        await cdp.js(f"{BOTTOM}.setConfig({{...{BOTTOM}.config, show_step_buttons: false}}); 1")
        await cdp.idle(1)
        g = await cdp.js(NOSTEPS)
        ok = (
            g["steps"] == 0
            and g["bpmVisible"]
            and g["fontSize"] == "24px"
            and g["sameRow"]
            and g["rightOfInfo"]
        )
        check("no step buttons: BPM in the header row", ok, g)

        # Connection notices.
        quiet = await cdp.js(f"{NOTICE}(false)")
        loud = await cdp.js(f"{NOTICE}(true)")
        check(
            "notice quiet without diagnostics",
            quiet["quiet"] and quiet["text"] == "Reconnecting…" and not quiet["hidden"],
            quiet,
        )
        check(
            "notice red with diagnostics",
            not loud["quiet"] and loud["text"] == "Connection to Home Assistant lost",
            loud,
        )

        # Dialog close button at the top left.
        await cdp.js(f"{BOTTOM}.shadowRoot.querySelector('.compact-info').click(); 1")
        await cdp.idle(1)
        pos = await cdp.js(
            f"""(() => {{ const d = {BOTTOM}.shadowRoot.querySelector('dialog[open]');
              if (!d) return null; const b = d.querySelector('.dialog-close').getBoundingClientRect(),
              r = d.getBoundingClientRect();
              return {{left: Math.round(b.left - r.left), top: Math.round(b.top - r.top),
                width: Math.round(b.width), dialog: Math.round(r.width)}}; }})()"""
        )
        check(
            "dialog close button top left",
            pos and pos["left"] <= 12 and pos["top"] <= 12 and pos["width"] >= 44,
            pos,
        )
        await cdp.js(f"{BOTTOM}.shadowRoot.querySelector('dialog')?.close(); 1")

        # Restore.
        await cdp.js(f"{BOTTOM}.player.action('configure', {{timer_enabled: false, duration: 30}})")
        await cdp.js(f"{BOTTOM}.setConfig({json.dumps(base)}); 1")
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        await cdp.ws.close()
    print(f"{sum(ok for _, ok in results)}/{len(results)} passed")


run(main)
