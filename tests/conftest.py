"""Shared fixtures for the Metronome tests."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import CLIENT_ID, MockConfigEntry, MockUser

from custom_components.metronome.const import DOMAIN
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.models import Credentials
from homeassistant.core import HomeAssistant

PLAYER = "media_player.metronome"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components."""
    return


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Metronome", data={})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def coordinator(loaded: MockConfigEntry):
    return loaded.runtime_data


@pytest.fixture
async def hass_user_access_token(hass: HomeAssistant, local_auth) -> str:
    """Access token of an ordinary (non-admin) user, as created in the HA UI."""
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    user = MockUser(name="Ordinary", groups=[group]).add_to_hass(hass)
    credential = Credentials(
        id="mock-user-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "ordinary"},
        is_new=False,
    )
    user.credentials.append(credential)
    refresh_token = await hass.auth.async_create_refresh_token(
        user, CLIENT_ID, credential=credential
    )
    return hass.auth.async_create_access_token(refresh_token)


class Ws:
    """Websocket client that keeps subscription events apart from command results."""

    def __init__(self, client) -> None:
        self.client = client
        self.events: dict[int, list[dict[str, Any]]] = {}
        self.results: dict[int, dict[str, Any]] = {}

    async def _read_one(self) -> None:
        msg = await self.client.receive_json(timeout=5)
        if msg["type"] == "event":
            self.events.setdefault(msg["id"], []).append(msg["event"])
        else:
            self.results[msg["id"]] = msg

    async def send(self, **message: Any) -> dict[str, Any]:
        await self.client.send_json_auto_id(message)
        while message["id"] not in self.results:
            await self._read_one()
        return self.results.pop(message["id"])

    async def subscribe(self, entity_id: str = PLAYER) -> tuple[int, dict[str, Any]]:
        msg = await self.send(type="metronome/subscribe", entity_id=entity_id)
        assert msg["success"], msg
        assert msg["result"] == {"subscription": msg["id"]}
        return msg["id"], await self.next_event(msg["id"])

    async def next_event(self, sub: int) -> dict[str, Any]:
        while not self.events.get(sub):
            await self._read_one()
        return self.events[sub].pop(0)

    async def control(
        self, action: str, sub: int | None = None, entity_id: str = PLAYER, **extra: Any
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "type": "metronome/control",
            "entity_id": entity_id,
            "action": action,
            **extra,
        }
        if sub is not None:
            message["subscription"] = sub
        return await self.send(**message)

    async def ok(self, action: str, sub: int | None = None, **extra: Any) -> dict[str, Any]:
        msg = await self.control(action, sub, **extra)
        assert msg["success"], msg
        return msg["result"]

    async def unsubscribe(self, sub: int) -> None:
        msg = await self.send(type="unsubscribe_events", subscription=sub)
        assert msg["success"], msg

    async def drain(self, sub: int) -> list[dict[str, Any]]:
        """All events received for a subscription so far (a ping round trip flushes them)."""
        await self.send(type="ping")
        return self.events.pop(sub, [])


@pytest.fixture
def ws_factory(hass: HomeAssistant, hass_ws_client):
    async def create(token: str | None = None) -> Ws:
        if token is None:
            return Ws(await hass_ws_client(hass))
        return Ws(await hass_ws_client(hass, token))

    return create


@pytest.fixture
async def owner(loaded, ws_factory):
    """A connected client that claimed audio output, as the card does after Start."""
    ws = await ws_factory()
    sub, _ = await ws.subscribe()
    await ws.ok("claim", sub)
    await ws.drain(sub)
    return ws, sub
