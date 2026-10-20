"""Timer dial: every text line stays inside the arc's inner circle.

python timer_text.py [out-dir]
Card widths 264 (a 280 px phone in Sections) to 500 px, text at 100 % and 130 % (Android
text zoom, emulated by scaling every font-size and px line-height in the card by 1.3),
for 30:00:32 (outside the dial range: hint shown), 45 s (unit hint) and the longest
finish label of a running countdown ("Ends Oct 21, 12:59:59 PM", 12 h with a date). Measures the text's own line boxes (Range rects) against
the inner edge of the 24-unit stroke, radius 133 of 320, minus a 2 px margin.
"""

import sys

from cdp import aiohttp, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full' && !c.config.primary_color)"
ZOOM = """((c, k) => {
  const els = [c.shadowRoot.querySelector('ha-card'), ...c.shadowRoot.querySelectorAll('ha-card *')];
  els.forEach(e => { e.style.fontSize = ''; e.style.lineHeight = ''; });
  if (k === 1) return 1;
  const sizes = els.map(e => { const cs = getComputedStyle(e); return [parseFloat(cs.fontSize), cs.lineHeight]; });
  els.forEach((e, i) => { e.style.fontSize = sizes[i][0] * k + 'px';
    if (sizes[i][1].endsWith('px')) e.style.lineHeight = parseFloat(sizes[i][1]) * k + 'px'; });
  return 1; })"""
MEASURE = f"""(() => {{
  const c = {FULL}, r = c.shadowRoot, svg = r.querySelector('.timer-dial svg').getBoundingClientRect();
  const cx = svg.left + svg.width / 2, cy = svg.top + svg.height / 2;
  const inner = svg.width * 133 / 320 - 2;
  const out = [];
  const add = (el, rects, what) => {{
    for (const b of rects) {{ if (!b.width || !b.height) continue;
      const far = Math.max(...[[b.left, b.top], [b.right, b.top], [b.left, b.bottom], [b.right, b.bottom]]
        .map(([x, y]) => Math.hypot(x - cx, y - cy)));
      out.push({{what, far: Math.round(far * 10) / 10}}); }}
  }};
  for (const el of r.querySelectorAll('.timer-center *')) {{
    if (!el.offsetParent) continue;
    if (el.localName === 'input') {{
      // The digits, not the (transparent) input box.
      const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
      const w = Math.min(b.width, el.value.length * parseFloat(cs.fontSize) * 0.6);
      add(el, [{{left: b.left + (b.width - w) / 2, right: b.left + (b.width + w) / 2,
                 top: b.top + (b.height - parseFloat(cs.fontSize)) / 2,
                 bottom: b.top + (b.height + parseFloat(cs.fontSize)) / 2,
                 width: w, height: parseFloat(cs.fontSize)}}], 'field ' + el.value);
      continue;
    }}
    for (const node of el.childNodes) {{
      if (node.nodeType !== 3 || !node.textContent.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      add(el, range.getClientRects(), node.textContent.trim().slice(0, 24));
    }}
  }}
  // Nothing may reach up into the timer's -1/+1 buttons.
  const buttons = Math.max(...[...r.querySelectorAll('.timer-adjust button')].map(b => b.getBoundingClientRect().bottom));
  const top = Math.min(...[...r.querySelectorAll('.timer-center *')].filter(e => e.offsetParent)
    .map(e => e.getBoundingClientRect().top));
  if (top < buttons + 2) out.push({{what: 'touches -1/+1 buttons', far: Infinity}});
  const worst = out.reduce((a, b) => b.far > a.far ? b : a, {{far: 0}});
  return {{inner: Math.round(inner), worst, outside: out.filter(o => o.far > inner),
    hint: r.querySelector('.timer-hint').textContent, card: Math.round(c.getBoundingClientRect().width)}};
}})()"""


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    bad, rows = [], []
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 376, 1600)
        await login(cdp, theme="dark", wait=15)
        for duration in (108032, 45, "running"):
            # "running": a long finish label as while playing, set before every measurement
            # (the card's 100 ms clock is paused for it).
            if duration != "running":
                await cdp.js(
                    f"{FULL}.player.action('configure', "
                    f"{{timer_enabled: true, duration: {duration}}})"
                )
                await cdp.js(f"{FULL}.selectedField = 0; 1")
                await cdp.idle(1)
            for width in (264, 280, 320, 360, 440, 500):
                await cdp.call(
                    "Emulation.setDeviceMetricsOverride",
                    width=width + 16,
                    height=1600,
                    deviceScaleFactor=1,
                    mobile=True,
                )
                await cdp.idle(0.8)
                for zoom in (1, 1.3):
                    await cdp.js(f"{ZOOM}({FULL}, {zoom})")
                    if duration == "running":
                        await cdp.js(
                            f"(c => {{ clearInterval(c.tick); c.shadowRoot.querySelector("
                            f"'.timer-hint').textContent = 'Ends Oct 21, 12:59:59 PM';"
                            f" return 1; }})({FULL})"
                        )
                    await cdp.idle(0.3)
                    m = await cdp.js(MEASURE)
                    rows.append((duration, width, zoom, m))
                    print(
                        f"{duration:>7} card {m['card']} zoom {zoom}: inner {m['inner']} worst "
                        f"{m['worst']} hint {m['hint']!r}"
                        + (f" OUTSIDE {m['outside']}" if m["outside"] else "")
                    )
                    if m["outside"]:
                        bad.append((duration, width, zoom, m["outside"]))
                    if out and width in (264, 360) and duration == 108032:
                        await cdp.js(
                            f"{FULL}.shadowRoot.querySelector('.timer-dial').scrollIntoView({{block: 'center'}}); 1"
                        )
                        await cdp.shot(f"{out}/timer-text-{width}-{int(zoom * 100)}.png")
                await cdp.js(f"{ZOOM}({FULL}, 1)")
        await cdp.js(f"{FULL}.player.action('configure', {{timer_enabled: false, duration: 30}})")
        await cdp.ws.close()
    print("problems:", len(bad))
    for item in bad:
        print("  ", item)


run(main)
