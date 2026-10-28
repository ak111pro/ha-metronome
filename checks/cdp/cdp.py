"""Minimal Chrome DevTools Protocol helpers for driving the card against a test HA.

Not part of CI. Needs a running Home Assistant with the integration, a dashboard at
METRONOME_URL (default /metronome-test/full) and a headless Chromium started with
--remote-debugging-port=9333. Set METRONOME_HA (default http://localhost:8124) and
METRONOME_TOKEN_FILE (a file holding a long-lived access token; never commit it).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os

import aiohttp

HA = os.environ.get("METRONOME_HA", "http://localhost:8124")
TOKEN_FILE = os.environ.get("METRONOME_TOKEN_FILE", "ha-dev.tok")
PORT = int(os.environ.get("METRONOME_CDP_PORT", "9333"))
DASHBOARD = os.environ.get("METRONOME_URL", "/metronome-test/full")

# Collects every metronome-card (also inside shadow roots and dialogs) into window.__cards.
FIND = """
(() => {
  const found = [];
  const walk = root => {
    for (const el of root.querySelectorAll('*')) {
      if (el.localName === 'metronome-card') found.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  window.__cards = found;
  return found.map(c => ({
    layout: c.config?.layout, entity: c.config?.entity,
    state: c.player?.state?.state, owner: c.player?.state?.is_owner,
    ready: c.player?.readyForAudio, error: c.player?.error || '',
    message: c.shadowRoot.querySelector('.message')?.textContent,
  }));
})()
"""


class Cdp:
    """One page target; collects console output and exceptions."""

    def __init__(self, ws):
        self.ws, self.n, self.console = ws, 0, []

    async def call(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.send_json({"id": my, "method": method, "params": params})
        while True:
            msg = await self.ws.receive_json(timeout=60)
            method_ = msg.get("method")
            if method_ == "Runtime.consoleAPICalled":
                args = " ".join(
                    str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"]
                )
                self.console.append(f"{msg['params']['type']}: {args}")
            elif method_ == "Runtime.exceptionThrown":
                self.console.append("EXCEPTION: " + json.dumps(msg["params"]["exceptionDetails"]))
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    async def js(self, expr, gesture=False):
        r = await self.call(
            "Runtime.evaluate",
            expression=expr,
            awaitPromise=True,
            returnByValue=True,
            userGesture=gesture,
        )
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"])
        return r["result"].get("value")

    async def shot(self, path):
        r = await self.call("Page.captureScreenshot", format="png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))

    async def idle(self, seconds):
        """Wait while still draining console events."""
        end = asyncio.get_running_loop().time() + seconds
        while asyncio.get_running_loop().time() < end:
            with contextlib.suppress(Exception):
                await self.js("1")
            await asyncio.sleep(0.25)


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


async def open_page(session, width=360, height=800, new=False):
    if new:
        async with session.put(f"http://127.0.0.1:{PORT}/json/new?about:blank") as r:
            page = await r.json()
    else:
        async with session.get(f"http://127.0.0.1:{PORT}/json/list") as r:
            page = [p for p in await r.json() if p["type"] == "page"][0]
    ws = await session.ws_connect(page["webSocketDebuggerUrl"], max_msg_size=0)
    cdp = Cdp(ws)
    cdp.target = page["id"]
    for domain in ("Page", "Runtime", "Network"):
        await cdp.call(f"{domain}.enable")
    # Always fetch the card modules from the server, never from HA's service worker.
    await cdp.call("Network.setCacheDisabled", cacheDisabled=True)
    await cdp.call("Network.setBypassServiceWorker", bypass=True)
    # No service worker at all: in a fresh profile HA's worker takes control ~40 s after the
    # first load and HA reloads the page on "controllerchange", which wipes every check's state.
    await cdp.call(
        "Page.addScriptToEvaluateOnNewDocument",
        source="delete Navigator.prototype.serviceWorker;",
    )
    await cdp.call(
        "Emulation.setDeviceMetricsOverride",
        width=width,
        height=height,
        deviceScaleFactor=1,
        mobile=True,
    )
    return cdp


async def login(cdp, path=DASHBOARD, wait=20, theme=None):
    cdp.console.clear()  # Runtime.enable replays messages from the previous page
    await cdp.call("Page.navigate", url=f"{HA}/auth/authorize")
    await cdp.idle(3)
    tokens = {
        "access_token": token(),
        "token_type": "Bearer",
        "expires_in": 315360000,
        "hassUrl": HA,
        "clientId": f"{HA}/",
        "expires": 4102444800000,
        "refresh_token": "unused",
    }
    await cdp.js(f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))}); 1")
    if theme is not None:
        selected = json.dumps(json.dumps({"theme": "default", "dark": theme == "dark"}))
        await cdp.js(f"localStorage.setItem('selectedTheme', {selected}); 1")
    await cdp.call("Page.navigate", url=f"{HA}{path}")
    await cdp.idle(wait)
    return await cdp.js(FIND)


async def ha_state(session, entity):
    async with session.get(
        f"{HA}/api/states/{entity}", headers={"Authorization": f"Bearer {token()}"}
    ) as r:
        return await r.json()


async def service(session, domain, svc, data):
    async with session.post(
        f"{HA}/api/services/{domain}/{svc}",
        json=data,
        headers={"Authorization": f"Bearer {token()}"},
    ) as r:
        return r.status, await r.text()


def run(main):
    asyncio.run(main())


__all__ = [
    "DASHBOARD",
    "FIND",
    "HA",
    "Cdp",
    "aiohttp",
    "asyncio",
    "ha_state",
    "json",
    "login",
    "open_page",
    "run",
    "service",
    "token",
]
