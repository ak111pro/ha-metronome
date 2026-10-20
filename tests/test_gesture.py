"""Native play (Tile, more-info) on the page the user just tapped (metronome/arm)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .conftest import PLAYER


async def play(ws, entity_id: str = PLAYER) -> dict:
    """media_play as the Tile/more-info sends it: call_service on the page's connection."""
    return await ws.send(
        type="call_service",
        domain="media_player",
        service="media_play",
        target={"entity_id": entity_id},
    )


async def arm(ws) -> None:
    msg = await ws.send(type="metronome/arm")
    assert msg["success"], msg


async def test_tapped_page_without_start_takes_output(hass: HomeAssistant, loaded, ws_factory):
    """A fresh page that never claimed: gesture + Tile play selects it and starts."""
    page = await ws_factory()
    sub, snapshot = await page.subscribe()
    assert snapshot["output_ready"] is False
    await arm(page)
    msg = await play(page)
    assert msg["success"], msg
    assert hass.states.get(PLAYER).state == "playing"
    events = await page.drain(sub)
    assert events[-1]["is_owner"] is True
    assert events[-1]["state"] == "playing"


async def test_tapped_page_wins_over_ready_owner(hass: HomeAssistant, loaded, ws_factory, owner):
    owner_ws, owner_sub = owner
    phone = await ws_factory()
    await phone.send(type="ping")
    sub, _ = await phone.subscribe()
    await arm(phone)
    assert (await play(phone))["success"]
    assert loaded.runtime_data.owner == (loaded.runtime_data.owner[0], sub)
    assert (await phone.drain(sub))[-1]["is_owner"] is True
    assert (await owner_ws.drain(owner_sub))[-1]["is_owner"] is False


async def test_without_gesture_the_ready_owner_plays(
    hass: HomeAssistant, loaded, ws_factory, owner
):
    owner_ws, owner_sub = owner
    other = await ws_factory()
    await other.send(type="ping")
    await other.subscribe()
    assert (await play(other))["success"]  # no arm: e.g. a remote control or script
    assert (await owner_ws.drain(owner_sub))[-1]["is_owner"] is True
    assert hass.states.get(PLAYER).state == "playing"


async def test_gesture_expires(
    hass: HomeAssistant, loaded, ws_factory, freezer: FrozenDateTimeFactory
) -> None:
    page = await ws_factory()
    await page.subscribe()
    await arm(page)
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass, dt_util.utcnow())
    msg = await play(page)
    assert not msg["success"]
    assert "Tap Start once" in msg["error"]["message"]
    assert hass.states.get(PLAYER).state == "idle"


async def test_other_users_gesture_is_ignored(
    hass: HomeAssistant, loaded, ws_factory, hass_user_access_token, owner
) -> None:
    owner_ws, owner_sub = owner
    ordinary = await ws_factory(hass_user_access_token)
    await ordinary.send(type="ping")
    sub, _ = await ordinary.subscribe()
    await arm(ordinary)
    # The admin presses play elsewhere (e.g. desktop more-info, no gesture there).
    admin = await ws_factory()
    assert (await play(admin))["success"]
    assert (await owner_ws.drain(owner_sub))[-1]["is_owner"] is True
    assert (await ordinary.drain(sub))[-1]["is_owner"] is False


async def test_automation_without_user_keeps_owner(
    hass: HomeAssistant, loaded, ws_factory, owner
) -> None:
    owner_ws, owner_sub = owner
    page = await ws_factory()
    await page.send(type="ping")
    sub, _ = await page.subscribe()
    await arm(page)
    await hass.services.async_call(
        "media_player", "media_play", {"entity_id": PLAYER}, blocking=True, context=Context()
    )
    assert (await owner_ws.drain(owner_sub))[-1]["is_owner"] is True
    assert (await page.drain(sub))[-1]["is_owner"] is False


async def test_automation_without_any_owner_fails_helpfully(hass: HomeAssistant, loaded):
    with pytest.raises(ServiceValidationError, match="Tap Start once"):
        await hass.services.async_call(
            "media_player", "media_play", {"entity_id": PLAYER}, blocking=True
        )


async def test_paused_session_resumes_on_its_owner(hass: HomeAssistant, loaded, ws_factory, owner):
    owner_ws, owner_sub = owner
    await owner_ws.ok("configure", owner_sub, settings={"timer_enabled": True})
    await owner_ws.ok("start", owner_sub)
    await owner_ws.ok("pause", owner_sub)
    phone = await ws_factory()
    await phone.send(type="ping")
    sub, _ = await phone.subscribe()
    await arm(phone)
    assert (await play(phone))["success"]
    assert hass.states.get(PLAYER).state == "playing"
    assert (await owner_ws.drain(owner_sub))[-1]["is_owner"] is True
    assert (await phone.drain(sub))[-1]["is_owner"] is False


async def test_gesture_needs_a_subscription_for_that_instance(
    hass: HomeAssistant, loaded, ws_factory
) -> None:
    """Arming alone does not make a page an output: it must be subscribed (standby)."""
    page = await ws_factory()
    await arm(page)
    msg = await play(page)
    assert not msg["success"]
    assert hass.states.get(PLAYER).state == "idle"
