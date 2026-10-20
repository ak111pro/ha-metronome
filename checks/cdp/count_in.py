"""Count-in beats light the dots (and glow) in HA's accent colour, exercise beats in the
active colour; also with prefers-reduced-motion. The status reads "Count-in", then "Active"
(full card and compact state line), and HA's media_player keeps state "playing" with the
phase attribute count_in -> running. python count_in.py [screenshot-dir]"""

import sys

from cdp import FIND, aiohttp, asyncio, ha_state, login, open_page, run, service

FULL = "window.__cards.find(c => c.config.layout === 'full')"
PROBE = f"""(() => {{ const r = {FULL}.shadowRoot, card = r.querySelector('ha-card');
  const dot = r.querySelector('.dots span'), glow = r.querySelector('.glow');
  return {{status: r.querySelector('.status')?.textContent,
    countIn: card.classList.contains('count-in'), dot: getComputedStyle(dot).backgroundColor,
    glow: getComputedStyle(glow).backgroundImage.slice(0, 60),
    accent: getComputedStyle(card).getPropertyValue('--highlight').trim(),
    opacities: [...r.querySelectorAll('.dots span')].map(e => getComputedStyle(e).opacity)}};
}})()"""


async def run_once(cdp, session, label, out):
    await cdp.js(
        f"{FULL}.player.action('configure', {{bpm: 60, count_in: 1, timer_enabled: false}})"
    )
    await cdp.idle(1)
    await cdp.js(f"{FULL}.shadowRoot.querySelector('[data-action=start]').click(); 1", gesture=True)
    await asyncio.sleep(2.2)
    during = await cdp.js(PROBE)
    ha_during = await ha_state(session, "media_player.metronome")
    if out:
        await cdp.shot(f"{out}/count-in-{label}.png")
    await asyncio.sleep(3.5)
    after = await cdp.js(PROBE)
    ha_after = await ha_state(session, "media_player.metronome")
    await service(session, "media_player", "media_stop", {"entity_id": "media_player.metronome"})
    await cdp.idle(1)
    stopped = await cdp.js(PROBE)
    print(label, "count-in:", during)
    print(label, "exercise:", after)
    assert during["countIn"] and not after["countIn"] and not stopped["countIn"]
    assert during["dot"] != after["dot"]
    assert during["status"] == "Count-in" and after["status"] == "Active", (during, after)
    assert ha_during["state"] == ha_after["state"] == "playing"
    assert ha_during["attributes"]["phase"] == "count_in"
    assert ha_after["attributes"]["phase"] == "running"
    assert stopped["status"] == "Idle"
    print(
        label,
        "status:",
        during["status"],
        "->",
        after["status"],
        "| HA phase:",
        ha_during["attributes"]["phase"],
        "->",
        ha_after["attributes"]["phase"],
    )
    return during, after


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 800)
        await login(cdp)
        await run_once(cdp, session, "motion", out)
        await cdp.call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-reduced-motion", "value": "reduce"}],
        )
        during, _ = await run_once(cdp, session, "reduced-motion", out)
        assert "1" in during["opacities"]  # stable highlight instead of scaling
        await cdp.call("Emulation.setEmulatedMedia", features=[])
        # Compact state line on the Compact view (Metronome instance).
        await login(cdp, "/metronome-test/compact")
        await cdp.js(FIND)
        compact = "window.__cards.find(c => c.config.layout === 'compact')"
        meta = f"{compact}.shadowRoot.querySelector('.compact-info .meta').textContent"
        await cdp.js(
            f"{compact}.shadowRoot.querySelector('[data-action=start]').click(); 1", gesture=True
        )
        await asyncio.sleep(2.2)
        line_during = await cdp.js(meta)
        await asyncio.sleep(3.5)
        line_after = await cdp.js(meta)
        await service(
            session, "media_player", "media_stop", {"entity_id": "media_player.metronome"}
        )
        print("compact:", line_during, "->", line_after)
        assert line_during.startswith("Count-in · ") and line_after.startswith("Active · ")
        await cdp.js(f"{compact}.player.action('configure', {{bpm: 120, count_in: 0}})")
        await cdp.idle(1)
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        assert not errors, errors
        print("count-in colours OK")
        await cdp.ws.close()


run(main)
