"""Typing into the BPM number: narrow focus box, live preview, commit on Enter, Esc reverts.

python bpm_input.py [screenshot-dir]
"""

import sys

from cdp import aiohttp, asyncio, login, open_page, run

FULL = "window.__cards.find(c => c.config.layout === 'full')"
INFO = f"""(() => {{
  const c = {FULL}, r = c.shadowRoot, i = r.querySelector('.bpm');
  const dial = r.querySelector('.bpm-dial svg').getBoundingClientRect();
  return {{input: Math.round(i.getBoundingClientRect().width), dial: Math.round(dial.width),
    inputH: Math.round(i.getBoundingClientRect().height), value: i.value,
    meta: r.querySelector('.metadata').textContent, bpm: c.player.state.settings.bpm,
    knob: r.querySelector('.bpm-dial .knob').getAttribute('cx'),
    fields: [...r.querySelectorAll('[data-field]')]
      .map(f => Math.round(f.getBoundingClientRect().width)),
    duration: c.player.state.settings.duration}};
}})()"""


async def key(cdp, name, code):
    for kind in ("keyDown", "keyUp"):
        await cdp.call(
            "Input.dispatchKeyEvent", type=kind, key=name, code=name, windowsVirtualKeyCode=code
        )


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 800)
        await login(cdp)
        await cdp.js(f"{FULL}.player.action('configure', {{bpm: 180, timer_enabled: true}})")
        await cdp.idle(1.5)
        before = await cdp.js(INFO)
        print("idle:", before)
        await cdp.js(f"{FULL}.shadowRoot.querySelector('.bpm').focus(); 1", gesture=True)
        await cdp.js(f"{FULL}.shadowRoot.querySelector('.bpm').select(); 1")
        await cdp.call("Input.insertText", text="6")
        await asyncio.sleep(0.3)
        typing_invalid = await cdp.js(INFO)  # "6" is valid too (1-200)
        await cdp.call("Input.insertText", text="0")
        await asyncio.sleep(0.3)
        typing = await cdp.js(INFO)
        print("typing 60:", typing)
        if out:
            await cdp.shot(f"{out}/bpm-typing-60.png")
        assert typing["input"] < 160, "focus box must hug the number"
        assert typing["inputH"] == before["inputH"]
        assert typing["meta"].endswith("Larghetto"), typing["meta"]
        assert typing["bpm"] == 180 and typing["knob"] != before["knob"]
        assert typing_invalid["meta"].endswith("Larghissimo")
        await cdp.call("Input.insertText", text="0")  # 600: out of range, no marking
        await asyncio.sleep(0.3)
        bad = await cdp.js(INFO)
        print("typing 600:", bad["meta"])
        assert bad["meta"] in ("BPM · 4/4", "BPM · 2/4", "BPM · 3/4", "BPM · 6/8"), bad["meta"]
        await key(cdp, "Backspace", 8)
        await key(cdp, "Enter", 13)
        await cdp.idle(1)
        committed = await cdp.js(INFO)
        print("after Enter:", committed["bpm"], committed["meta"])
        assert committed["bpm"] == 60
        # Escape restores the committed value without sending anything.
        await cdp.js(f"{FULL}.shadowRoot.querySelector('.bpm').focus(); 1", gesture=True)
        await cdp.js(f"{FULL}.shadowRoot.querySelector('.bpm').select(); 1")
        await cdp.call("Input.insertText", text="99")
        await key(cdp, "Escape", 27)
        await cdp.idle(1)
        esc = await cdp.js(INFO)
        print("after Esc:", esc["bpm"], esc["value"], esc["meta"])
        assert esc["bpm"] == 60 and esc["value"] == "60"
        # Timer fields hug two digits as well.
        print("timer field widths:", esc["fields"])
        assert all(w < 70 for w in esc["fields"])
        await cdp.js(f"{FULL}.shadowRoot.querySelector('[data-field=\"1\"]').focus(); 1")
        await cdp.call("Input.insertText", text="7")
        await key(cdp, "Escape", 27)
        await cdp.idle(0.5)
        assert (await cdp.js(INFO))["duration"] == esc["duration"]
        if out:
            await cdp.js(f"{FULL}.shadowRoot.querySelector('[data-field=\"2\"]').focus(); 1")
            await cdp.js(
                f"{FULL}.shadowRoot.querySelector('.timer-dial').scrollIntoView({{block:'center'}})"
            )
            await cdp.idle(0.5)
            await cdp.shot(f"{out}/timer-field-focus.png")
        await cdp.js(f"{FULL}.player.action('configure', {{bpm: 120, timer_enabled: false}})")
        await cdp.idle(1)
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        assert not errors, errors
        print("BPM input OK")
        await cdp.ws.close()


run(main)
