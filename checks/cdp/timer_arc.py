"""alpha.8 timer arc: idle = the same muted colour as the idle BPM arc (outside 5-120 s
stays grey), running = full primary colour; the countdown moves every animation frame (not
in 1 s steps), in whole seconds with reduced motion, and draws nothing while hidden.
Uses the Practice instance (custom-colour full card) and restores it.
"""

from cdp import aiohttp, asyncio, ha_state, login, open_page, run, service

ENTITY = "media_player.practice"
CARD = "window.__cards.find(c => c.config.primary_color && c.config.layout !== 'compact')"
R = f"{CARD}.shadowRoot"
COLOURS = f"""(() => {{ const s = sel => getComputedStyle({R}.querySelector(sel)).stroke;
  return {{bpm: s('.bpm-dial .value'), timer: s('.timer-dial .value'), track: s('.timer-dial .track')}}; }})()"""
SAMPLE = f"""(async n => {{ const v = {R}.querySelector('.timer-dial .value'), seen = [];
  for (let i = 0; i < n; i++) {{ await new Promise(r => requestAnimationFrame(r)); seen.push(v.getAttribute('d')); }}
  return new Set(seen).size; }})"""


async def main():
    results = []

    def check(label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        before = (await ha_state(session, ENTITY))["attributes"]
        cdp = await open_page(session, 376, 1200)
        await login(cdp, wait=12)
        await cdp.js(
            f"{CARD}.player.action('configure', {{timer_enabled: true, duration: 60, count_in: 0}})"
        )
        await cdp.idle(1)
        idle = await cdp.js(COLOURS)
        check("idle timer arc muted like the BPM arc", idle["timer"] == idle["bpm"], idle)
        await cdp.js(f"{CARD}.player.action('configure', {{duration: 300}})")
        await cdp.idle(1)
        outside = await cdp.js(COLOURS)
        check(
            "outside 5-120 s stays grey (track colour)",
            outside["timer"] == outside["track"] != idle["timer"],
            outside,
        )
        await cdp.js(f"{CARD}.player.action('configure', {{duration: 30}})")
        await cdp.idle(0.5)
        await cdp.js(f"{R}.querySelector('[data-action=start]').click(); 1", gesture=True)
        await cdp.idle(1.5)
        running = await cdp.js(COLOURS)
        check("running timer arc in full colour", running["timer"] == "rgb(0, 128, 128)", running)
        frames = await cdp.js(f"{SAMPLE}(30)")
        check(
            "countdown moves every frame (30 frames)",
            frames >= 20,
            f"{frames} different arcs in 30 frames",
        )
        await cdp.call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-reduced-motion", "value": "reduce"}],
        )
        await cdp.idle(0.3)
        steps = await cdp.js(f"{SAMPLE}(30)")
        check(
            "reduced motion: whole-second steps", steps <= 2, f"{steps} different arcs in 30 frames"
        )
        await cdp.call("Emulation.setEmulatedMedia", features=[])
        await cdp.idle(0.5)  # the 100 ms clock tick restarts the frame loop
        raf = await cdp.js(f"!!{CARD}.countdownRaf")
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await asyncio.sleep(0.5)
        stopped = await cdp.js(f"!!{CARD}.countdownRaf")
        check(
            "frame loop runs while counting down, stops after",
            raf and not stopped,
            f"{raf} -> {stopped}",
        )
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        await cdp.ws.close()
        await service(
            session,
            "number",
            "set_value",
            {"entity_id": "number.practice_timer_duration", "value": before["duration"]},
        )
        await service(
            session,
            "switch",
            "turn_on" if before["timer_enabled"] else "turn_off",
            {"entity_id": "switch.practice_timer"},
        )
    print(f"{sum(results)}/{len(results)} passed")


run(main)
