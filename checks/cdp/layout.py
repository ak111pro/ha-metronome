"""Screenshots and layout measurements of the Advanced view (and main view) per width/theme.

python layout.py <out-dir> [label]   e.g. label=before / after
Checks: one control height, single-line labels, nothing wider than the card.
"""

import base64
import sys

from cdp import aiohttp, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full')"
MEASURE = f"""(() => {{
  const c = {FULL}, r = c.shadowRoot, card = c.getBoundingClientRect();
  const h = sel => [...r.querySelectorAll(sel)].filter(e => e.offsetParent)
    .map(e => Math.round(e.getBoundingClientRect().height));
  const wrapped = [...r.querySelectorAll('.select-label,.select-value,.tile>span')]
    .filter(e => e.offsetParent && e.getClientRects().length > 1 ||
      e.offsetParent &&
      e.getBoundingClientRect().height > 2 * parseFloat(getComputedStyle(e).fontSize))
    .map(e => e.textContent);
  const truncated = [...r.querySelectorAll('.select-label,.select-value,.tile>span')]
    .filter(e => e.offsetParent && e.scrollWidth > e.clientWidth + 1).map(e => e.textContent);
  const overflow = [...r.querySelectorAll('*')].filter(e => e.offsetParent && (
      e.getBoundingClientRect().right > card.right + 0.5 ||
      e.getBoundingClientRect().left < card.left - 0.5)).map(e => e.className || e.localName);
  const adv = r.querySelector('.footer .advanced');
  return {{triggers: h('.advanced-view .select-trigger'), tiles: h('.advanced-view .tile'),
    volume: h('.volume-wrap'), wrapped, truncated, overflow: [...new Set(overflow)].slice(0, 8),
    advancedButton: adv ? Math.round(adv.getBoundingClientRect().width) : null,
    card: Math.round(card.width)}};
}})()"""


async def card_shot(cdp, path):
    rect = await cdp.js(
        f"(() => {{ const r = {FULL}.getBoundingClientRect();"
        " return {x: r.left, y: r.top + window.scrollY, w: r.width, h: r.height}; })()"
    )
    clip = {"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1}
    r = await cdp.call(
        "Page.captureScreenshot", format="png", clip=clip, captureBeyondViewport=True
    )
    with open(path, "wb") as f:
        f.write(base64.b64decode(r["data"]))


async def main():
    out, label = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "shot"
    bad = []
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 1400)
        for theme in ("light", "dark"):
            await login(cdp, theme=theme, wait=15)
            for width in (280, 320, 360, 440):
                await cdp.call(
                    "Emulation.setDeviceMetricsOverride",
                    width=width,
                    height=1400,
                    deviceScaleFactor=2 if width == 360 else 1,
                    mobile=True,
                )
                await cdp.idle(1.5)
                await cdp.js("window.scrollTo(0, 0); 1")
                main_view = await cdp.js(MEASURE)
                if width == 360:
                    await card_shot(cdp, f"{out}/{label}-main-{theme}-{width}.png")
                await cdp.js(
                    f"{FULL}.shadowRoot.querySelector('[data-action=advanced]').click(); 1",
                    gesture=True,
                )
                await cdp.idle(0.8)
                m = await cdp.js(MEASURE)
                print(theme, width, "advanced button", main_view["advancedButton"], m)
                if width in (320, 360):
                    await card_shot(cdp, f"{out}/{label}-advanced-{theme}-{width}.png")
                heights = set(m["triggers"] + m["tiles"])
                if m["wrapped"] or m["truncated"] or m["overflow"] or len(heights) > 1:
                    bad.append((theme, width, m))
                await cdp.js(
                    f"{FULL}.shadowRoot.querySelector('[data-action=back]').click(); 1",
                    gesture=True,
                )
        await cdp.call(
            "Emulation.setDeviceMetricsOverride",
            width=360,
            height=800,
            deviceScaleFactor=1,
            mobile=True,
        )
        await cdp.ws.close()
    print("problems:", len(bad))
    for item in bad:
        print("  ", item)


run(main)
