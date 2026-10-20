"""Count-in beats light the dots (and glow) in HA's accent colour, exercise beats in the
active colour; also with prefers-reduced-motion. python count_in.py [screenshot-dir]"""

import sys

from cdp import aiohttp, asyncio, login, open_page, run, service

FULL = "window.__cards.find(c => c.config.layout === 'full')"
PROBE = f"""(() => {{ const r = {FULL}.shadowRoot, card = r.querySelector('ha-card');
  const dot = r.querySelector('.dots span'), glow = r.querySelector('.glow');
  return {{countIn: card.classList.contains('count-in'), dot: getComputedStyle(dot).backgroundColor,
    glow: getComputedStyle(glow).backgroundImage.slice(0, 60),
    accent: getComputedStyle(card).getPropertyValue('--count-in').trim(),
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
    if out:
        await cdp.shot(f"{out}/count-in-{label}.png")
    await asyncio.sleep(3.5)
    after = await cdp.js(PROBE)
    await service(session, "media_player", "media_stop", {"entity_id": "media_player.metronome"})
    await cdp.idle(1)
    stopped = await cdp.js(PROBE)
    print(label, "count-in:", during)
    print(label, "exercise:", after)
    assert during["countIn"] and not after["countIn"] and not stopped["countIn"]
    assert during["dot"] != after["dot"]
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
        await cdp.js(f"{FULL}.player.action('configure', {{bpm: 120, count_in: 0}})")
        await cdp.idle(1)
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        assert not errors, errors
        print("count-in colours OK")
        await cdp.ws.close()


run(main)
