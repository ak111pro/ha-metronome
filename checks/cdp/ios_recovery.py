"""alpha.8: audio recovery after another app took the sound, Diagnostics always visible,
Test vibration cycling through the iOS app's haptic types. Chromium only; a "stuck"
WebKit context is simulated: (a) a closed context, (b) a context whose resume() never
settles. Uses the Practice instance (custom-colour full card) and restores it.
"""

from cdp import aiohttp, ha_state, login, open_page, run, service

ENTITY = "media_player.practice"
CARD = "window.__cards.find(c => c.config.primary_color && c.config.layout !== 'compact')"
R = f"{CARD}.shadowRoot"
SH = "window[Symbol.for('metronome.audio.v1')]"
STATUS = f"""(p => ({{ctx: {SH}.ctx?.state, contexts: {SH}.contexts, tones: p.__tones, owner: p.state.is_owner,
  ha: p.state.state, last: {SH}.lastError, msg: {R}.querySelector('.message').hidden ? '' : {R}.querySelector('.message').textContent}}))({CARD}.player)"""


async def tap_start(cdp):
    await cdp.js(f"{R}.querySelector('[data-action=start]').scrollIntoView({{block: 'center'}}); 1")
    await cdp.idle(0.3)
    x, y = await cdp.js(
        f"(() => {{ const b = {R}.querySelector('[data-action=start]').getBoundingClientRect(); return [b.left + 24, b.top + 24]; }})()"
    )
    for kind in ("mousePressed", "mouseReleased"):
        await cdp.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)


async def main():
    results = []

    def check(label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        before = (await ha_state(session, ENTITY))["attributes"]
        cdp = await open_page(session, 376, 900)
        await login(cdp, wait=12)
        await cdp.js(f"{CARD}.player.action('configure', {{count_in: 0, timer_enabled: false}})")
        await cdp.js(
            f"(p => {{ p.__tones = 0; const t = p.tone.bind(p); p.tone = (...a) => {{ p.__tones++; return t(...a); }}; return 1; }})({CARD}.player)"
        )
        await tap_start(cdp)
        await cdp.idle(1.5)
        first = await cdp.js(STATUS)
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        # (a) Another app left the context dead: closed.
        await cdp.js(f"{SH}.ctx.close().then(() => 1)")
        await cdp.idle(0.5)
        t0 = first["tones"]
        await tap_start(cdp)
        await cdp.idle(2)
        a = await cdp.js(STATUS)
        check(
            "closed context: Start makes a fresh one and plays",
            a["ctx"] == "running"
            and a["contexts"] == first["contexts"] + 1
            and a["tones"] > t0
            and a["ha"] == "playing"
            and "replaced" in a["last"],
            a,
        )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.idle(0.5)
        # (b) resume() never settles and the state stays suspended.
        await cdp.js(
            f"(c => {{ return c.suspend().then(() => {{ c.resume = () => new Promise(() => {{}}); return 1; }}); }})({SH}.ctx)"
        )
        t1 = a["tones"]
        await tap_start(cdp)
        await cdp.idle(4)
        b = await cdp.js(STATUS)
        check(
            "stuck resume: replaced after the 1.5 s limit, plays",
            b["ctx"] == "running"
            and b["contexts"] == a["contexts"] + 1
            and b["tones"] > t1
            and b["ha"] == "playing"
            and not b["msg"],
            b,
        )
        # Diagnostics visible without any interaction, values present.
        await cdp.js(f"{R}.querySelector('[data-action=advanced]').click(); 1", gesture=True)
        await cdp.idle(1.5)
        rows = await cdp.js(
            f"(() => {{ const d = {R}.querySelector('.diag'); return {{visible: !!d.offsetParent && d.getBoundingClientRect().height > 40, rows: [...d.querySelectorAll('dt')].map(x => x.textContent + ': ' + x.nextElementSibling.textContent)}}; }})()"
        )
        check(
            "Diagnostics visible with values",
            rows["visible"]
            and any(r.startswith("Audio: running") for r in rows["rows"])
            and any(r.startswith("Audio contexts:") for r in rows["rows"]),
            rows["rows"],
        )
        # Test vibration: each press one pulse, cycling the app's types (simulated iOS bus).
        await cdp.js(
            "window.__bus = []; window.webkit = {messageHandlers: {externalBus: {postMessage() {}}}};"
            "document.querySelector('home-assistant').hass.auth.external = {fireMessage: m => window.__bus.push(m), config: {}}; 1"
        )
        await cdp.js(f"{R}.querySelector('.haptics').hidden = false; 1")
        for _ in range(8):
            await cdp.js(f"{R}.querySelector('[data-action=test-haptic]').click(); 1", gesture=True)
        types = await cdp.js("window.__bus.map(m => m.payload.hapticType)")
        last = await cdp.js(
            f"[...{R}.querySelectorAll('.diag dt')].find(d => d.textContent === 'Last haptic').nextElementSibling.textContent"
        )
        check(
            "Test vibration cycles the app's types, diagnostics show it",
            types
            == ["light", "medium", "heavy", "success", "warning", "failure", "selection", "light"]
            and "type light" in last
            and "via external bus" in last,
            f"{types} | {last}",
        )
        await cdp.js(
            "delete document.querySelector('home-assistant').hass.auth.external; delete window.webkit; 1"
        )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        await service(
            session,
            "select",
            "select_option",
            {
                "entity_id": "select.practice_count_in",
                "option": ["Off", "1 bar", "2 bars"][before["count_in"]],
            },
        )
        if before["timer_enabled"]:
            await service(session, "switch", "turn_on", {"entity_id": "switch.practice_timer"})
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        check("no card exceptions", not errors, errors[:2])
        await cdp.ws.close()
    print(f"{sum(results)}/{len(results)} passed")


run(main)
