"""primary_color / secondary_color on the test dashboard, light and dark theme.

python colours.py <out-dir>
Needs a card with primary_color: teal and secondary_color: '#9c27b0' (Practice instance)
next to a default card. Checks the computed colours of the arc, Tap text, beat dots, the
active-toggle tint, count-in dots and the selected timer field, and that the default card
still uses the theme's colours (media-player active colour, which falls back to the primary
colour, and the accent colour). The idle BPM arc is a muted mix of the primary colour. Turns the Practice timer on for the shot
and restores it.
"""

import base64
import sys

from cdp import aiohttp, login, open_page, run

CUSTOM = "window.__cards.find(c => c.config.primary_color)"
DEFAULT = "window.__cards.find(c => !c.config.primary_color && c.config.layout === 'full')"
MEASURE = """(c => {
  const r = c.shadowRoot, css = (sel, prop) => getComputedStyle(r.querySelector(sel))[prop];
  const card = r.querySelector('ha-card');
  card.classList.add('count-in');
  const countIn = css('.dots span', 'backgroundColor');
  card.classList.remove('count-in');
  const theme = getComputedStyle(document.querySelector('home-assistant'));
  return {handle: css('.bpm-dial .knob', 'stroke'), tap: css('.tap', 'color'),
    dot: css('.dots span', 'backgroundColor'), countIn,
    timerPressed: css('[data-action=timer]', 'color'),
    field: r.querySelector('.fields input.selected') ? css('.fields input.selected', 'color') : null,
    themePrimary: (theme.getPropertyValue('--state-media_player-active-color') || theme.getPropertyValue('--primary-color')).trim(),
    themeAccent: theme.getPropertyValue('--accent-color').trim()};
})"""
TEAL, PURPLE = "rgb(0, 128, 128)", "rgb(156, 39, 176)"


def rgb(hex_or_rgb):
    v = hex_or_rgb.strip()
    if v.startswith("#") and len(v) == 7:
        return f"rgb({int(v[1:3], 16)}, {int(v[3:5], 16)}, {int(v[5:7], 16)})"
    return v


async def card_shot(cdp, expr, path):
    rect = await cdp.js(
        f"(() => {{ const r = {expr}.getBoundingClientRect();"
        " return {x: r.left, y: r.top + window.scrollY, w: r.width, h: r.height}; })()"
    )
    clip = {"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1}
    r = await cdp.call(
        "Page.captureScreenshot", format="png", clip=clip, captureBeyondViewport=True
    )
    with open(path, "wb") as f:
        f.write(base64.b64decode(r["data"]))


async def main():
    out = sys.argv[1]
    bad = []
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 1000, 2400)
        for theme in ("light", "dark"):
            await login(cdp, theme=theme, wait=15)
            await cdp.js(
                f"{CUSTOM}.player.action('configure', {{timer_enabled: true, duration: 45}})"
            )
            await cdp.idle(1.5)
            custom = await cdp.js(f"{MEASURE}({CUSTOM})")
            default = await cdp.js(f"{MEASURE}({DEFAULT})")
            print(theme, "custom", custom)
            print(theme, "default", default)
            for key in ("handle", "tap", "dot", "timerPressed"):
                if custom[key] != TEAL:
                    bad.append((theme, "custom", key, custom[key]))
            for key in ("countIn", "field"):
                if custom[key] != PURPLE:
                    bad.append((theme, "custom", key, custom[key]))
            if default["tap"] != rgb(default["themePrimary"]):
                bad.append((theme, "default primary", default["tap"]))
            if default["countIn"] != rgb(default["themeAccent"]):
                bad.append((theme, "default accent", default["countIn"]))
            await card_shot(cdp, CUSTOM, f"{out}/colours-custom-{theme}.png")
            await card_shot(cdp, DEFAULT, f"{out}/colours-default-{theme}.png")
            await cdp.js(f"{CUSTOM}.player.action('configure', {{timer_enabled: false}})")
            await cdp.idle(1)
        await cdp.ws.close()
    print("problems:", len(bad))
    for item in bad:
        print("  ", item)


run(main)
