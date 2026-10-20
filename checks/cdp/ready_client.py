"""Does the selected client stay ready for native media_player actions in the real UI?

After one Start tap on the Full view, walk through the things a phone user does (view
switches, compact dialog, more-info, Advanced, page hidden/visible, websocket reconnect,
device page, idle time) and after each step call media_player.media_play / media_stop
through the REST API, like the native more-info, Tile or device page do.
"""

import sys

from cdp import DASHBOARD, FIND, aiohttp, ha_state, login, open_page, run, service

ENTITY = "media_player.metronome"
PLAYER = "window.__metronomePlayer"
GRAB = """(() => {
  const c = window.__cards.find(c => c.config.layout === 'full' && c.config.entity ===
    'media_player.metronome');
  const p = window.__metronomePlayer = c.player;
  if (!p.__counted) { const tone = p.tone.bind(p); p.__tones = 0; p.__counted = true;
    p.tone = (...args) => { p.__tones++; return tone(...args); }; }
  return !!c.player;
})()"""
NAV = """(path => { history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', {detail: {replace: false}}));
  return 1; })"""
HIDE = """(hidden => {
  Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
  Object.defineProperty(document, 'visibilityState', {configurable: true,
    get: () => hidden ? 'hidden' : 'visible'});
  document.dispatchEvent(new Event('visibilitychange')); return 1; })"""
MORE_INFO = """(id => { document.querySelector('home-assistant').dispatchEvent(new CustomEvent(
  'hass-more-info', {detail: {entityId: id}, bubbles: true, composed: true})); return 1; })"""


async def native_play(session, cdp, label, results):
    before = await cdp.js(f"{PLAYER}.__tones")
    status, text = await service(session, "media_player", "media_play", {"entity_id": ENTITY})
    await cdp.idle(1.2)
    st = await ha_state(session, ENTITY)
    audio = await cdp.js(
        f"({{ready: {PLAYER}.readyForAudio, tones: {PLAYER}.__tones - {before},"
        f" ctx: {PLAYER}.audio?.state, local: {PLAYER}.state?.state,"
        f" owner: {PLAYER}.state?.is_owner}})"
    )
    ok = status == 200 and st["state"] == "playing" and audio["tones"] > 0
    results.append((label, ok))
    reason = "" if status == 200 else text[:120]
    print(f"{'OK  ' if ok else 'FAIL'} {label}: HTTP {status} state={st['state']} {audio} {reason}")
    await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
    await cdp.idle(0.8)
    return ok


async def main():
    async with aiohttp.ClientSession() as session:
        cdp = await open_page(session, 360, 800)
        await login(cdp)
        assert await cdp.js(GRAB)
        await cdp.js(f"{PLAYER}.action('configure', {{timer_enabled: false, count_in: 0}})")
        start = (
            "window.__cards.find(c => c.config.layout === 'full').shadowRoot"
            ".querySelector('[data-action=start]').click(); 1"
        )
        await cdp.js(start, gesture=True)
        await cdp.idle(2)
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.idle(1)
        results = []
        await native_play(session, cdp, "after Start/Stop on the card", results)

        base = DASHBOARD.rsplit("/", 1)[0]
        await cdp.js(NAV + f"('{base}/compact')")
        await cdp.idle(3)
        await native_play(session, cdp, "Compact view", results)

        await cdp.js(FIND)
        await cdp.js(
            "window.__cards.find(c => c.config.layout === 'compact' && c.config.entity === "
            "'media_player.metronome').shadowRoot.querySelector('.compact-info').click(); 1",
            gesture=True,
        )
        await cdp.idle(1.5)
        await native_play(session, cdp, "compact dialog open", results)
        await cdp.js(
            "window.__cards.find(c => c.config.layout === 'compact' && c.config.entity === "
            "'media_player.metronome').shadowRoot.querySelector('dialog')?.close(); 1"
        )
        await cdp.idle(1)
        await native_play(session, cdp, "compact dialog closed", results)

        await cdp.js(NAV + f"('{base}/full')")
        await cdp.idle(3)
        await native_play(session, cdp, "back on Full view", results)

        await cdp.js(MORE_INFO + f"('{ENTITY}')")
        await cdp.idle(2)
        await native_play(session, cdp, "HA more-info open", results)
        await cdp.js(MORE_INFO + "(null)")
        await cdp.idle(1)

        await cdp.js(FIND)
        await cdp.js(
            "window.__cards.find(c => c.config.layout === 'full').shadowRoot"
            ".querySelector('[data-action=advanced]').click(); 1",
            gesture=True,
        )
        await cdp.idle(1)
        await native_play(session, cdp, "Advanced view", results)
        await cdp.js(
            "window.__cards.find(c => c.config.layout === 'full').shadowRoot"
            ".querySelector('[data-action=back]').click(); 1",
            gesture=True,
        )

        await cdp.js(HIDE + "(true)")
        await cdp.idle(2)
        await cdp.js(HIDE + "(false)")
        await cdp.idle(2)
        await native_play(session, cdp, "page hidden 2 s, visible again", results)

        await cdp.js("document.querySelector('home-assistant').hass.connection.reconnect(true); 1")
        await cdp.idle(5)
        await native_play(session, cdp, "websocket reconnect", results)

        await cdp.js(NAV + "('/config/integrations/integration/metronome')")
        await cdp.idle(4)
        await native_play(session, cdp, "integration/device page", results)
        await cdp.js(NAV + f"('{base}/full')")
        await cdp.idle(3)

        await cdp.idle(20)
        await native_play(session, cdp, "after 20 s idle", results)

        # Hidden while playing: interrupted, and it must not auto-resume when visible again.
        await service(session, "media_player", "media_play", {"entity_id": ENTITY})
        await cdp.idle(1)
        await cdp.js(HIDE + "(true)")
        await cdp.idle(1.5)
        await cdp.js(HIDE + "(false)")
        await cdp.idle(2)
        st = await ha_state(session, ENTITY)
        ok = st["state"] == "idle" and st["attributes"]["last_event"] == "interrupted"
        ok = ok and await cdp.js(f"{PLAYER}.readyForAudio")
        results.append(("hidden while playing: interrupted, no auto-resume, ready again", ok))
        print(
            f"{'OK  ' if ok else 'FAIL'} hidden while playing -> {st['state']}, "
            f"{st['attributes']['last_event']}"
        )

        # A second page that never tapped Start is never selected; once it taps Start it
        # owns the output and the first page must not take it back when it becomes visible.
        other = await open_page(session, 360, 800, new=True)
        await login(other)
        ready = await other.js(
            "window.__cards.find(c => c.config.layout === 'full').player.readyForAudio"
        )
        results.append(("untapped second page stays unselected", ready is False))
        await other.js(start, gesture=True)
        await other.idle(2)
        await service(session, "media_player", "media_stop", {"entity_id": ENTITY})
        await cdp.idle(1)
        await cdp.js(HIDE + "(true)")
        await cdp.idle(1)
        await cdp.js(HIDE + "(false)")
        await cdp.idle(3)
        mine = await cdp.js(f"({PLAYER}.readyForAudio || {PLAYER}.state.is_owner)")
        theirs = await other.js(
            "window.__cards.find(c => c.config.layout === 'full').player.state.is_owner"
        )
        ok = not mine and theirs
        results.append(("first page does not steal the output back", ok))
        print(f"{'OK  ' if ok else 'FAIL'} second page owns output: {theirs}, first: {mine}")
        await other.call("Page.close")

        failed = [label for label, ok in results if not ok]
        errors = [x for x in cdp.console if "EXCEPTION" in x and "/metronome/" in x]
        print(f"{len(results) - len(failed)}/{len(results)} OK; failed: {failed}; errors: {errors}")
        await cdp.ws.close()
        sys.exit(1 if failed or errors else 0)


run(main)
