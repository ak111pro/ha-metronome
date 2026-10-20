"""Native Tile / more-info play on a page that never tapped Start (gesture arming).

On the test dashboard's "Tile only" view (a native Tile for media_player.practice, no
metronome card on the view): a real (CDP-dispatched, trusted) tap on the Tile's Play button
starts audio on this page: shared AudioContext running, the scheduler producing tones, HA
state playing, this page the owner. Then the same with the Play button in HA's more-info
dialog after a reload, and by touch after another reload. A service call without any gesture fails with the helpful message.
The AudioContext is suspended again ~5 s after a gesture that did not lead to playback.
Uses the Practice instance and restores its settings.
"""

import json

from cdp import aiohttp, ha_state, login, open_page, run, service

ENTITY = "media_player.practice"
DEEP = """window.deep = (sel, root = document) => { const out = [];
  const walk = r => { for (const el of r.querySelectorAll('*')) {
    if (el.matches(sel)) out.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
  walk(root); return out; }; 1"""
PLAYER = f"""(() => {{ const hass = document.querySelector('home-assistant').hass;
  return globalThis[Symbol.for('metronome.players.v1')].get(hass.connection).get('{ENTITY}'); }})()"""
COUNT = f"""(() => {{ const p = {PLAYER}; if (!p.__counted) {{ const tone = p.tone.bind(p);
  p.__tones = 0; p.__counted = true; p.tone = (...a) => {{ p.__tones++; return tone(...a); }}; }}
  return 1; }})()"""
STATUS = f"""(() => {{ const p = {PLAYER}, sh = window[Symbol.for('metronome.audio.v1')];
  return {{ready: p.readyForAudio, owner: p.state?.is_owner, local: p.state?.state,
    ctx: sh.ctx?.state ?? null, tones: p.__tones ?? 0, loop: !!p.loop}}; }})()"""


async def tap(cdp, x, y):
    for kind in ("mousePressed", "mouseReleased"):
        await cdp.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)


async def center(cdp, expr):
    r = await cdp.js(
        f"(() => {{ const r = ({expr}).getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2]; })()"
    )
    return r


async def main():
    results = []

    def check(label, ok, detail):
        results.append((label, ok))
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {detail}")

    async with aiohttp.ClientSession() as session:
        before = (await ha_state(session, ENTITY))["attributes"]
        await service(
            session,
            "number",
            "set_value",
            {"entity_id": "number.practice_timer_duration", "value": 30},
        )
        cdp = await open_page(session, 376, 900)
        await login(cdp, "/metronome-test/tile-only", wait=12)
        await cdp.js(DEEP)
        cards = await cdp.js("deep('metronome-card').length")
        check("no metronome card on the view", cards == 0, f"{cards} cards")
        st = await cdp.js(STATUS)
        check("standby subscription, nothing armed", st["ready"] is False and st["ctx"] is None, st)

        # No gesture anywhere: a plain service call cannot pick this page.
        status, text = await service(session, "media_player", "media_play", {"entity_id": ENTITY})
        check(
            "service call without gesture fails helpfully",
            status == 400 and "Tap Start once" in text,
            f"HTTP {status} {text[:90]}",
        )

        # Tap on empty page space: context resumes, then suspends after ~5 s.
        await tap(cdp, 200, 600)
        await cdp.idle(0.5)
        running = (await cdp.js(STATUS))["ctx"]
        await cdp.idle(6.5)
        later = (await cdp.js(STATUS))["ctx"]
        check(
            "gesture resumes, idle context suspends",
            running == "running" and later == "suspended",
            f"{running} -> {later}",
        )

        # Tile Play: one real tap.
        await cdp.js(COUNT)
        x, y = await center(
            cdp,
            "deep('ha-control-button', deep('hui-tile-card')[0].shadowRoot)"
            ".find(b => (b.getAttribute('aria-label') || b.label) === 'Play')",
        )
        await tap(cdp, x, y)
        await cdp.idle(1.5)
        a = await cdp.js(STATUS)
        await cdp.idle(1)
        b = await cdp.js(STATUS)
        ha = (await ha_state(session, ENTITY))["state"]
        check(
            "Tile play starts audio here",
            ha == "playing"
            and b["owner"]
            and b["ready"]
            and b["ctx"] == "running"
            and b["loop"]
            and b["tones"] > a["tones"] > 0,
            f"HA {ha}, before {a}, +1 s {b}",
        )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.idle(1)

        # More-info Play on a freshly loaded page (no Start, no earlier selection).
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await login(cdp, "/metronome-test/tile-only", wait=12)
        await cdp.js(DEEP)
        await cdp.js(COUNT)
        st = await cdp.js(STATUS)
        check("reloaded page is not an output", not st["ready"], st)
        await cdp.js(f"""document.querySelector('home-assistant').dispatchEvent(new CustomEvent(
          'hass-more-info', {{detail: {{entityId: '{ENTITY}'}}, bubbles: true, composed: true}})); 1""")
        await cdp.idle(3)
        await cdp.js(DEEP)
        labels = await cdp.js(
            "deep('ha-more-info-dialog').length ? deep('ha-icon-button, ha-control-button, ha-button', deep('ha-more-info-dialog')[0].shadowRoot)"
            ".map(b => b.getAttribute('aria-label') || b.label || b.textContent.trim()).filter(Boolean) : []"
        )
        found = await cdp.js(
            "!!deep('*', deep('ha-more-info-dialog')[0].shadowRoot).find(b => (b.getAttribute?.('aria-label') || b.label) === 'Play' && b.getBoundingClientRect().width)"
        )
        if not found:
            check("more-info play button found", False, labels)
        else:
            x, y = await center(
                cdp,
                "deep('*', deep('ha-more-info-dialog')[0].shadowRoot)"
                ".find(b => (b.getAttribute?.('aria-label') || b.label) === 'Play' && b.getBoundingClientRect().width)",
            )
            await tap(cdp, x, y)
            await cdp.idle(1.5)
            a = await cdp.js(STATUS)
            await cdp.idle(1)
            b = await cdp.js(STATUS)
            ha = (await ha_state(session, ENTITY))["state"]
            check(
                "more-info play starts audio here",
                ha == "playing"
                and b["owner"]
                and b["ctx"] == "running"
                and b["tones"] > a["tones"] > 0,
                f"HA {ha}, before {a}, +1 s {b}",
            )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})

        # Touch (as on the phone: touchend/pointerup, then the synthesized click).
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        await login(cdp, "/metronome-test/tile-only", wait=12)
        await cdp.js(DEEP)
        await cdp.js(COUNT)
        x, y = await center(
            cdp,
            "deep('ha-control-button', deep('hui-tile-card')[0].shadowRoot)"
            ".find(b => (b.getAttribute('aria-label') || b.label) === 'Play')",
        )
        await cdp.call(
            "Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}]
        )
        await cdp.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
        await cdp.idle(2.5)
        b = await cdp.js(STATUS)
        ha = (await ha_state(session, ENTITY))["state"]
        check(
            "Tile play by touch starts audio here",
            ha == "playing" and b["owner"] and b["ctx"] == "running" and b["tones"] > 0,
            f"HA {ha}, {b}",
        )
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.call("Emulation.setTouchEmulationEnabled", enabled=False)
        await cdp.call("Page.navigate", url="about:blank")
        await cdp.idle(1)
        await service(
            session,
            "number",
            "set_value",
            {"entity_id": "number.practice_timer_duration", "value": before["duration"]},
        )
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        check("no card errors", not errors, json.dumps(errors)[:200])
        await cdp.ws.close()
    print(f"{sum(ok for _, ok in results)}/{len(results)} passed")


run(main)
