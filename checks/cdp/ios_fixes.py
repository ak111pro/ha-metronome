"""alpha.7 (first iPhone/iPad test): volume slider, audio-state handling, diagnostics.

Chromium only (no WebKit on the Pi); the iOS-specific parts (audio session "playback",
"interrupted" state, the app's haptics) need the real devices. Uses the Practice instance
(full card with custom colours on the Full view) and restores its settings.
- Volume: no native range input; tap, drag and keyboard set the value (HA and screen);
  the marker stays inside the fill at 0/1/5/10/100 %.
- Sound paused by the system while playing (context suspended from outside): the session
  keeps running, beat events and haptic pulses continue on the silent clock, a clear
  message shows; a tap resumes the context and tones are scheduled again.
- Advanced -> Diagnostics shows the audio state, session type, owner and haptics path, and
  the page reports once to the HA log after taking output (checked by the caller).
"""

from cdp import aiohttp, asyncio, ha_state, login, open_page, run, service

ENTITY = "media_player.practice"
CARD = "window.__cards.find(c => c.config.primary_color && c.config.layout !== 'compact')"
R = f"{CARD}.shadowRoot"


async def tap(cdp, x, y):
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
        await cdp.js(f"{R}.querySelector('[data-action=advanced]').click(); 1", gesture=True)
        await cdp.idle(1)
        check(
            "no native range input for volume",
            await cdp.js(f"!{R}.querySelector('input.volume, input[type=range].volume')"),
        )
        await cdp.js(f"{R}.querySelector('.volume-wrap').scrollIntoView({{block: 'center'}}); 1")
        await cdp.idle(0.5)
        box = await cdp.js(
            f"(() => {{ const b = {R}.querySelector('.volume-wrap').getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }})()"
        )
        x0, y0, w, h = box
        # Tap at 25 %.
        await tap(cdp, x0 + w * 0.25, y0 + h / 2)
        await cdp.idle(1.2)
        v = (await ha_state(session, ENTITY))["attributes"]["volume_level"]
        check("tap sets the volume", abs(v - 0.25) <= 0.02, v)
        # Drag from 25 % to 80 % with the mouse (pointer events, like a finger on WebKit).
        await cdp.call(
            "Input.dispatchMouseEvent",
            type="mousePressed",
            x=x0 + w * 0.25,
            y=y0 + h / 2,
            button="left",
            clickCount=1,
        )
        for i in range(1, 12):
            await cdp.call(
                "Input.dispatchMouseEvent",
                type="mouseMoved",
                x=x0 + w * (0.25 + 0.05 * i),
                y=y0 + h / 2,
                button="left",
                buttons=1,
            )
            await asyncio.sleep(0.03)
        live = await cdp.js(f"{R}.querySelector('.volume-label output').textContent")
        await cdp.call(
            "Input.dispatchMouseEvent",
            type="mouseReleased",
            x=x0 + w * 0.80,
            y=y0 + h / 2,
            button="left",
            clickCount=1,
        )
        await cdp.idle(1.2)
        v = (await ha_state(session, ENTITY))["attributes"]["volume_level"]
        check(
            "drag sets the volume, label follows live",
            abs(v - 0.80) <= 0.02 and live == "80%",
            f"HA {v}, label during drag {live}",
        )
        # Touch drag too.
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        await cdp.call(
            "Input.dispatchTouchEvent",
            type="touchStart",
            touchPoints=[{"x": x0 + w * 0.8, "y": y0 + h / 2}],
        )
        for i in range(1, 11):
            await cdp.call(
                "Input.dispatchTouchEvent",
                type="touchMove",
                touchPoints=[{"x": x0 + w * (0.8 - 0.05 * i), "y": y0 + h / 2}],
            )
            await asyncio.sleep(0.03)
        await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=False)
        await cdp.idle(1.2)
        v = (await ha_state(session, ENTITY))["attributes"]["volume_level"]
        check("touch drag sets the volume", abs(v - 0.30) <= 0.02, v)
        # Keyboard.
        await cdp.js(f"{R}.querySelector('.volume-wrap').focus(); 1")
        for key, code in (("End", 35), ("PageDown", 34), ("ArrowLeft", 37)):
            await cdp.call(
                "Input.dispatchKeyEvent",
                type="keyDown",
                key=key,
                code=key,
                windowsVirtualKeyCode=code,
            )
            await cdp.call(
                "Input.dispatchKeyEvent",
                type="keyUp",
                key=key,
                code=key,
                windowsVirtualKeyCode=code,
            )
            await cdp.idle(0.6)
        v = (await ha_state(session, ENTITY))["attributes"]["volume_level"]
        aria = await cdp.js(f"{R}.querySelector('.volume-wrap').getAttribute('aria-valuenow')")
        check(
            "keyboard End, PageDown, ArrowLeft = 89 %",
            abs(v - 0.89) <= 0.005 and aria == "89",
            f"HA {v}, aria {aria}",
        )
        for pct in (0, 1, 5, 10, 100):
            await cdp.js(f"{CARD}.player.action('configure', {{volume: {pct / 100}}})")
            await cdp.idle(0.6)
            m = await cdp.js(f"""(() => {{ const f = {R}.querySelector('.volume-fill').getBoundingClientRect(),
              k = {R}.querySelector('.volume-marker').getBoundingClientRect(), t = {R}.querySelector('.volume-wrap').getBoundingClientRect();
              return {{inside: k.width === 0 || (k.left >= f.left - .5 && k.right <= f.right + .5), inTrack: f.right <= t.right + .5, h: Math.round(t.height)}}; }})()""")
            check(f"marker contained at {pct} %", m["inside"] and m["inTrack"] and m["h"] == 48, m)

        # Sound paused by the system while playing.
        await cdp.js(
            f"{CARD}.player.action('configure', {{volume: 0.5, bpm: 120, count_in: 0, timer_enabled: false}})"
        )
        await cdp.js(
            """(() => { window.__vib = 0; Object.defineProperty(navigator, 'vibrate', {configurable: true, value: () => { window.__vib++; return true; }}); return 1; })()"""
        )
        await cdp.js(f"{CARD}.player.vibration = true; 1")
        await cdp.js(f"{R}.querySelector('[data-action=back]').click(); 1", gesture=True)
        await cdp.js(
            f"(p => {{ p.__beats = 0; p.__tones = 0; p.addEventListener('beat', () => p.__beats++); const t = p.tone.bind(p); p.tone = (...a) => {{ p.__tones++; return t(...a); }}; return 1; }})({CARD}.player)"
        )
        sx, sy = await cdp.js(
            f"(() => {{ const b = {R}.querySelector('[data-action=start]').getBoundingClientRect(); return [b.left + 24, b.top + 24]; }})()"
        )
        await cdp.js(
            f"{R}.querySelector('[data-action=start]').scrollIntoView({{block: 'center'}}); 1"
        )
        await cdp.idle(0.5)
        sx, sy = await cdp.js(
            f"(() => {{ const b = {R}.querySelector('[data-action=start]').getBoundingClientRect(); return [b.left + 24, b.top + 24]; }})()"
        )
        await tap(cdp, sx, sy)
        await cdp.idle(2)
        a = await cdp.js(
            f"(p => ({{beats: p.__beats, tones: p.__tones, vib: window.__vib, ctx: p.audio.state}}))({CARD}.player)"
        )
        await cdp.js(f"{CARD}.player.audio.suspend().then(() => 1)")
        await cdp.idle(2)
        b = await cdp.js(
            f"(p => ({{beats: p.__beats, tones: p.__tones, vib: window.__vib, ctx: p.audio.state, owner: p.state.is_owner, ready: p.readyForAudio, msg: {R}.querySelector('.message').textContent}}))({CARD}.player)"
        )
        ha = (await ha_state(session, ENTITY))["state"]
        check(
            "audio paused by the system: beats and haptics continue silently",
            b["ctx"] == "suspended"
            and ha == "playing"
            and b["owner"]
            and b["beats"] >= a["beats"] + 3
            and b["vib"] >= a["vib"] + 3
            and b["tones"] <= a["tones"] + 2
            and b["msg"].startswith("No sound"),
            {"before": a, "suspended": b, "HA": ha},
        )
        # Any tap resumes the context (here: on the card's dial centre, which does nothing else).
        cx, cy = await cdp.js(
            f"(() => {{ const b = {R}.querySelector('.bpm-dial svg').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height * 0.2]; }})()"
        )
        await tap(cdp, cx, cy)
        await cdp.idle(2)
        c = await cdp.js(
            f"(p => ({{tones: p.__tones, ctx: p.audio.state, msg: {R}.querySelector('.message').hidden}}))({CARD}.player)"
        )
        check(
            "a tap resumes sound",
            c["ctx"] == "running" and c["tones"] >= b["tones"] + 3 and c["msg"],
            c,
        )
        # Diagnostics while playing.
        await cdp.js(
            f"{R}.querySelector('[data-action=advanced]').click(); {R}.querySelector('.diagnostics').open = true; 1",
            gesture=True,
        )
        await cdp.idle(0.8)
        diag = await cdp.js(
            f"[...{R}.querySelectorAll('.diag dt')].map(d => d.textContent + ': ' + d.nextElementSibling.textContent)"
        )
        print("   diagnostics:", diag)
        text = " | ".join(diag)
        check(
            "Diagnostics shows audio, session, owner, haptics",
            "Audio: running" in text
            and "This page is the output: yes" in text
            and "Haptics path: vibrate · on" in text
            and "Last audio error:" in text,
            text,
        )
        await cdp.js(f"{R}.querySelector('[data-action=test-haptic]').click(); 1", gesture=True)
        await cdp.idle(0.3)
        check("Test vibration pulses once", await cdp.js("window.__vib") >= 1)
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        settings = {k: before[k] for k in ("volume", "bpm", "count_in", "timer_enabled")}
        await service(
            session,
            "number",
            "set_value",
            {"entity_id": "number.practice_tempo", "value": settings["bpm"]},
        )
        await service(
            session,
            "media_player",
            "volume_set",
            {"entity_id": ENTITY, "volume_level": settings["volume"]},
        )
        await cdp.ws.close()
    errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
    check("no card exceptions", not errors, errors[:2])
    print(f"{sum(results)}/{len(results)} passed")


run(main)
