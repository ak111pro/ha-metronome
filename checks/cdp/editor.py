"""Card editor round trip in HA's real dashboard editor (edit dashboard -> edit card).

Drives the actual ha-form controls (switches, dropdowns, text field) of the first card on
the test dashboard, and after every change checks that HA's Save button is enabled, that
HA's card config (what the YAML editor shows) has the option, that defaults are never
written, and that the preview card visibly changed. Ends with all defaults restored, the
YAML editor showing only type + entity; then one change is saved for real (Save writes
the dashboard) and the original dashboard config is restored through the websocket API.
"""

import json
import sys

from cdp import HA, aiohttp, login, open_page, run, token

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None  # optional screenshot directory

DEEP = """window.deep = (sel, root = document) => { const out = [];
  const walk = r => { for (const el of r.querySelectorAll('*')) {
    if (el.matches(sel)) out.push(el); if (el.shadowRoot) walk(el.shadowRoot); } };
  walk(root); return out; }; 1"""
DIALOG = "deep('hui-dialog-edit-card')[0]"
EDITOR = "deep('metronome-card-editor')[0]"
PREVIEW = f"deep('metronome-card', {DIALOG}.shadowRoot)[0]"
STATE = f"""(() => {{
  const d = {DIALOG}, p = {PREVIEW}, r = p?.shadowRoot;
  const shown = el => !!el && !el.hidden && !!el.offsetParent;
  return {{save: !d.shadowRoot.querySelector('[slot=primaryAction]').hasAttribute('disabled'),
    config: d._cardConfig, preview: p && {{
      layout: r.querySelector('.compact-grid') ? 'compact' : 'full',
      name: r.querySelector('.main .name')?.textContent,
      meta: (r.querySelector('.metadata') || r.querySelector('.compact-info .meta'))?.textContent,
      timer: shown(r.querySelector('[data-action=timer]')),
      advanced: shown(r.querySelector('[data-action=advanced]')),
      steps: shown(r.querySelector('[data-action=plus]')),
      feedbackOff: r.querySelector('ha-card').classList.contains('feedback-off'),
      timerDisplay: p.config.timer_display, primary: getComputedStyle(p).getPropertyValue('--metronome-primary-color').trim(),
      secondary: getComputedStyle(p).getPropertyValue('--metronome-secondary-color').trim()}}}};
}})()"""


def switch(label):
    return f"""(() => {{ const s = deep('ha-switch', {EDITOR}.shadowRoot)
      .find(e => e.getAttribute('aria-label') === {json.dumps(label)}); s.click(); return 1; }})()"""


def dropdown_open(label):
    return f"""(() => {{ const sel = deep('ha-selector-select', {EDITOR}.shadowRoot)
      .find(e => e.label === {json.dumps(label)});
      window.__sel = sel; deep('ha-picker-field', sel.shadowRoot)[0].click(); return 1; }})()"""


def dropdown_pick(text):
    return f"""(() => {{ const item = deep('ha-dropdown-item', __sel.shadowRoot)
      .find(e => e.textContent.trim() === {json.dumps(text)}); item.click(); return 1; }})()"""


def type_text(label, text):
    return f"""(() => {{ const sel = deep('ha-selector-text', {EDITOR}.shadowRoot)
      .find(e => e.label === {json.dumps(label)});
      const input = deep('input', sel.shadowRoot)[0]; input.focus(); input.value = {json.dumps(text)};
      input.dispatchEvent(new InputEvent('input', {{bubbles: true, composed: true}}));
      input.dispatchEvent(new Event('change', {{bubbles: true, composed: true}})); return 1; }})()"""


def keyboard(label, text):
    """Real key-by-key typing (the form round-trips the config after every keystroke)."""

    async def run_keys(cdp):
        await cdp.js(f"""(() => {{ const sel = deep('ha-selector-text', {EDITOR}.shadowRoot)
          .find(e => e.label === {json.dumps(label)});
          const input = deep('input', sel.shadowRoot)[0]; input.focus(); input.select(); return 1; }})()""")
        for ch in text:
            await cdp.call("Input.insertText", text=ch)
            await cdp.idle(0.15)

    return run_keys


async def open_editor(cdp):
    await login(cdp, "/metronome-test/full?edit=1", wait=15)
    await cdp.js(DEEP)
    await cdp.js(
        "deep('hui-card-edit-mode')[0].shadowRoot.querySelector('.control').click(); 1",
        gesture=True,
    )
    await cdp.idle(5)
    await cdp.js(DEEP)


async def step(cdp, results, label, actions, expect):
    for action in actions:
        if callable(action):
            await action(cdp)
        else:
            await cdp.js(action, gesture=True)
        await cdp.idle(0.8)
    st = await cdp.js(STATE)
    problems = expect(st)
    results.append((label, problems))
    print(
        f"{'OK ' if not problems else 'BAD'} {label}: yaml={json.dumps(st['config'])}"
        f" save={st['save']} {problems or ''}"
    )
    return st


def no_defaults(config):
    defaults = {
        "layout": "full",
        "show_tempo": True,
        "show_signature": True,
        "show_timer": True,
        "show_advanced": True,
        "feedback": "dots_glow",
        "timer_display": "remaining_finish",
        "features_position": "bottom",
        "show_title": True,
        "show_step_buttons": True,
        "show_timer_bar": True,
    }
    return [k for k, v in config.items() if defaults.get(k, object()) == v]


def check(**want):
    def expect(st):
        bad = [] if st["save"] else ["Save disabled"]
        bad += [f"default written: {k}" for k in no_defaults(st["config"])]
        for key, value in want.items():
            got = st["config"].get(key[5:]) if key.startswith("yaml_") else st["preview"].get(key)
            if callable(value) and not value(got) or not callable(value) and got != value:
                bad.append(f"{key}={got!r}")
        return bad

    return expect


async def main():
    results = []
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 1000, 1000)
        await open_editor(cdp)
        st = await cdp.js(STATE)
        print("initial", st["config"], "save", st["save"])
        assert st["config"] == {"type": "custom:metronome-card", "entity": "media_player.metronome"}
        await step(
            cdp,
            results,
            "name",
            [keyboard("Name (optional)", "Practice room")],
            check(yaml_name="Practice room", name="Practice room"),
        )
        await step(
            cdp,
            results,
            "layout compact",
            [dropdown_open("Layout"), dropdown_pick("Compact")],
            check(yaml_layout="compact", layout="compact"),
        )
        await step(
            cdp,
            results,
            "layout full",
            [dropdown_open("Layout"), dropdown_pick("Full")],
            check(yaml_layout=None, layout="full"),
        )
        await step(
            cdp,
            results,
            "show_tempo off",
            [switch("Show tempo marking")],
            check(yaml_show_tempo=False, meta="BPM · 4/4"),
        )
        await step(
            cdp,
            results,
            "show_signature off",
            [switch("Show time signature")],
            check(yaml_show_signature=False, meta="BPM"),
        )
        await step(
            cdp,
            results,
            "show_timer off",
            [switch("Show timer controls")],
            check(yaml_show_timer=False, timer=False),
        )
        await step(
            cdp,
            results,
            "show_advanced off",
            [switch("Show Advanced button")],
            check(yaml_show_advanced=False, advanced=False),
        )
        await step(
            cdp,
            results,
            "show_step_buttons off",
            [switch("Show −1/+1 buttons")],
            check(yaml_show_step_buttons=False, steps=False),
        )
        await step(
            cdp,
            results,
            "show_step_buttons on",
            [switch("Show −1/+1 buttons")],
            check(yaml_show_step_buttons=None, steps=True),
        )
        await step(
            cdp,
            results,
            "features_position inline",
            [
                dropdown_open("Compact: tempo controls position"),
                dropdown_pick("Inline (next to the name)"),
            ],
            check(yaml_features_position="inline"),
        )
        await step(
            cdp,
            results,
            "features_position bottom",
            [dropdown_open("Compact: tempo controls position"), dropdown_pick("Bottom")],
            check(yaml_features_position=None),
        )
        await step(
            cdp,
            results,
            "feedback dots",
            [dropdown_open("Beat feedback"), dropdown_pick("Dots")],
            check(yaml_feedback="dots", feedbackOff=False),
        )
        await step(
            cdp,
            results,
            "feedback off",
            [dropdown_open("Beat feedback"), dropdown_pick("Off")],
            check(yaml_feedback="off", feedbackOff=True),
        )
        await step(
            cdp,
            results,
            "timer_display remaining",
            [dropdown_open("Timer display"), dropdown_pick("Remaining time")],
            check(yaml_timer_display="remaining", timerDisplay="remaining"),
        )
        if await cdp.js(
            f"!!deep('ha-selector-text', {EDITOR}.shadowRoot).find(e => e.label === 'Primary colour')"
        ):
            await colour_steps(cdp, results)
        # Back to every default: only type + entity remain, which equals the saved card,
        # so HA disables Save again.
        original = {"type": "custom:metronome-card", "entity": "media_player.metronome"}
        await step(
            cdp,
            results,
            "all defaults again",
            [
                type_text("Name (optional)", ""),
                switch("Show tempo marking"),
                switch("Show time signature"),
                switch("Show timer controls"),
                switch("Show Advanced button"),
                dropdown_open("Beat feedback"),
                dropdown_pick("Dots and subtle glow"),
                dropdown_open("Timer display"),
                dropdown_pick("Remaining time and finish time"),
            ],
            lambda st: (
                []
                if st["config"] == original
                and not st["save"]
                and st["preview"]["meta"] == "BPM · 4/4 · " + st["preview"]["meta"].split(" · ")[-1]
                and st["preview"]["timer"]
                and st["preview"]["advanced"]
                else [st]
            ),
        )
        # The YAML (code) editor shows the same config.
        await cdp.js(f"{DIALOG}.shadowRoot.querySelector('.gui-mode-button').click(); 1")
        await cdp.idle(1.5)
        yaml = await cdp.js(f"deep('ha-code-editor', {DIALOG}.shadowRoot)[0]?.value")
        print("YAML editor:", repr(yaml))
        results.append(
            (
                "yaml editor",
                []
                if yaml
                and yaml.strip().splitlines()
                == ["type: custom:metronome-card", "entity: media_player.metronome"]
                else [yaml],
            )
        )
        await cdp.js(f"{DIALOG}.shadowRoot.querySelector('.gui-mode-button').click(); 1")
        await cdp.idle(1.5)
        await cdp.js(DEEP)
        # Save really writes the dashboard; the original dashboard is restored afterwards.
        before = await ws_call(session, {"type": "lovelace/config", "url_path": "metronome-test"})
        await step(
            cdp,
            results,
            "change before save",
            [switch("Show tempo marking")],
            check(yaml_show_tempo=False),
        )
        await cdp.js(f"{DIALOG}.shadowRoot.querySelector('[slot=primaryAction]').click(); 1")
        await cdp.idle(4)
        after = await ws_call(session, {"type": "lovelace/config", "url_path": "metronome-test"})
        saved = after["views"][0]["sections"][0]["cards"][0]
        results.append(
            (
                "Save writes the dashboard",
                [] if saved == {**original, "show_tempo": False} else [saved],
            )
        )
        print("saved card:", saved)
        await ws_call(
            session,
            {"type": "lovelace/config/save", "url_path": "metronome-test", "config": before},
        )
        await cdp.ws.close()
    bad = [r for r in results if r[1]]
    print(f"{len(results) - len(bad)}/{len(results)} passed", HA)
    for item in bad:
        print("  ", item)


async def ws_call(session, message):
    async with session.ws_connect(f"{HA}/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": token()})
        await ws.receive_json()
        await ws.send_json({"id": 1, **message})
        reply = await ws.receive_json()
        assert reply.get("success"), reply
        return reply["result"]


async def colour_steps(cdp, results):
    await step(
        cdp,
        results,
        "primary teal",
        [type_text("Primary colour", "teal")],
        check(yaml_primary_color="teal", primary="teal"),
    )
    await step(
        cdp,
        results,
        "secondary hex",
        [type_text("Secondary colour", "#16809e")],
        check(yaml_secondary_color="#16809e", secondary="#16809e"),
    )
    # Invalid: shown as an error, not saved (config keeps the last valid value).
    await keyboard("Primary colour", "notacolour")(cdp)
    await cdp.idle(0.8)
    if SHOTS:
        await cdp.shot(f"{SHOTS}/editor-colour-error.png")
    st = await cdp.js(STATE)
    err = await cdp.js(f"{EDITOR}.form.error?.primary_color || ''")
    bad = [] if st["config"].get("primary_color") == "teal" and err else [st["config"], err]
    print(f"{'OK ' if not bad else 'BAD'} invalid primary: error={err!r}", bad or "")
    results.append(("invalid colour rejected", bad))
    for value in ("rgb(200, 30, 60)", "hsl(200 80% 40%)", "var(--red-color)", "#fff"):
        await step(
            cdp,
            results,
            f"primary {value}",
            [type_text("Primary colour", value)],
            check(yaml_primary_color=value),
        )
    await step(
        cdp,
        results,
        "colours cleared",
        [type_text("Primary colour", ""), type_text("Secondary colour", "")],
        check(yaml_primary_color=None, yaml_secondary_color=None, primary="", secondary=""),
    )


run(main)
