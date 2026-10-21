"""Haptics paths: navigator.vibrate(20/40/70) where it exists, HA's "haptic" event in the
Companion app without navigator.vibrate (simulated iOS app), the external bus message
directly when hass.auth.external exists (even with a navigator.vibrate stub), hidden
otherwise. "Test vibration" sends one pulse."""

from cdp import aiohttp, ha_state, login, open_page, run, service

FULL = "window.__cards.find(c => c.config.layout === 'full')"
CLICK = f"(sel => {{ {FULL}.shadowRoot.querySelector(sel).click(); return 1; }})"
SECTION = f"""(() => {{ const r = {FULL}.shadowRoot;
  return {{hidden: r.querySelector('.haptics').hidden,
          note: r.querySelector('.haptics-note').textContent}}; }})()"""


async def play(cdp, session, seconds=2.2):
    await cdp.js(CLICK + "('[data-action=start]')", gesture=True)
    await cdp.idle(seconds)
    await service(session, "media_player", "media_stop", {"entity_id": "media_player.metronome"})
    await cdp.idle(0.8)


async def main():
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 900)
        await login(cdp)
        await cdp.js(f"{FULL}.player.action('configure', {{bpm: 120, count_in: 0}})")
        await cdp.js(
            "window.__vib = []; window.__hap = [];"
            "const v = navigator.vibrate.bind(navigator);"
            "navigator.vibrate = ms => { window.__vib.push(ms); return v(ms); };"
            "window.addEventListener('haptic', e => window.__hap.push(e.detail)); 1"
        )
        await cdp.js(CLICK + "('[data-action=advanced]')", gesture=True)
        await cdp.js(CLICK + "('[data-toggle=vibration]')", gesture=True)
        browser = await cdp.js(SECTION)
        print("browser with navigator.vibrate:", browser)
        assert not browser["hidden"]
        await play(cdp, session)
        vib, hap = await cdp.js("[window.__vib, window.__hap]")
        print("vibrate calls:", vib, "haptic events:", hap)
        assert 20 in vib and not hap

        # iOS Companion app: no navigator.vibrate, external bus present.
        await cdp.js(
            "Object.defineProperty(navigator, 'vibrate', {value: undefined, configurable: true});"
            "window.webkit = {messageHandlers: {externalBus: {postMessage() {}}}};"
            "window.__vib = []; window.__hap = []; 1"
        )
        await cdp.js(CLICK + "('[data-picker=pulse] .select-trigger')", gesture=True)
        await cdp.js(CLICK + "('[data-picker=pulse] [data-value=\"70\"]')", gesture=True)
        companion = await cdp.js(SECTION)
        print("companion without vibrate:", companion)
        assert not companion["hidden"] and "haptic" in companion["note"]
        await play(cdp, session)
        vib, hap = await cdp.js("[window.__vib, window.__hap]")
        print("vibrate calls:", vib, "haptic events:", hap)
        assert hap and set(hap) == {"heavy"} and not vib

        # iOS app as HA's frontend sees it (alpha.7): hass.auth.external exists, and even
        # with a navigator.vibrate stub the card uses the app's haptics: the external bus
        # message HA itself sends, {type: "haptic", payload: {hapticType}}.
        await cdp.js(
            "Object.defineProperty(navigator, 'vibrate', {configurable: true, value: ms => { window.__vib.push(ms); return true; }});"
            "window.__bus = []; const h = document.querySelector('home-assistant').hass;"
            "h.auth.external = {fireMessage: m => window.__bus.push(m), config: {}};"
            "window.__vib = []; window.__hap = []; 1"
        )
        await play(cdp, session)
        await cdp.js(CLICK + "('[data-action=test-haptic]')", gesture=True)
        vib, hap, bus = await cdp.js("[window.__vib, window.__hap, window.__bus]")
        print(
            "iOS app: vibrate calls:",
            vib,
            "window events:",
            hap,
            "external bus:",
            bus[:2],
            len(bus),
        )
        assert not vib and not hap and len(bus) >= 3
        assert all(m == {"type": "haptic", "payload": {"hapticType": "heavy"}} for m in bus)
        await cdp.js("delete document.querySelector('home-assistant').hass.auth.external; 1")
        await cdp.js(
            "Object.defineProperty(navigator, 'vibrate', {value: undefined, configurable: true}); 1"
        )

        # Plain iOS Safari: neither path, section hidden.
        await cdp.js("delete window.webkit; 1")
        await cdp.js(CLICK + "('[data-toggle=accent]')", gesture=True)
        await cdp.js(CLICK + "('[data-toggle=accent]')", gesture=True)
        await cdp.idle(0.5)
        plain = await cdp.js(SECTION)
        print("no vibrate, no app:", plain)
        assert plain["hidden"]
        await cdp.js(CLICK + "('[data-action=back]')", gesture=True)
        st = await ha_state(session, "media_player.metronome")
        assert st["state"] == "idle"
        # HA's own browser haptic handler (attached at load because this browser has
        # navigator.vibrate) throws once vibrate is removed: an artefact of the simulation.
        # In a real iOS app it is never attached.
        errors = [
            x
            for x in cdp.console
            if "EXCEPTION" in x and "/metronome/" in x and "vibrate is not a function" not in x
        ]
        assert not errors, errors
        print("haptics OK")
        await cdp.ws.close()


run(main)
