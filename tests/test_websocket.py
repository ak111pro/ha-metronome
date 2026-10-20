"""Websocket protocol: subscription, output ownership, lease and permissions."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import PLAYER


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_subscribe_sends_snapshot(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    sub, snapshot = await ws.subscribe()
    assert snapshot["subscription"] == sub
    assert snapshot["name"] == "Metronome"
    assert snapshot["state"] == "idle"
    assert snapshot["settings"]["bpm"] == 120
    assert snapshot["output_ready"] is False
    assert snapshot["output_user"] is None
    assert snapshot["is_owner"] is False
    assert {"instance_id", "sequence", "server_time", "revision", "session_id"} <= set(snapshot)


async def test_full_session_over_websocket(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    sub, first = await ws.subscribe()

    claimed = await ws.ok("claim", sub)
    assert claimed["is_owner"] is True
    assert claimed["output_ready"] is True
    assert hass.states.get(PLAYER).attributes["output_ready"] is True

    result = await ws.ok("configure", sub, settings={"bpm": 96, "timer_enabled": True})
    assert result["settings"]["bpm"] == 96
    started = await ws.ok("start", sub)
    assert started["state"] == "playing"
    assert started["session_id"]
    assert started["ends_at"] is not None
    paused = await ws.ok("pause", sub)
    assert paused["state"] == "paused"
    assert paused["ends_at"] is None
    resumed = await ws.ok("start", sub)
    assert resumed["state"] == "playing"
    assert resumed["session_id"] == started["session_id"]
    stopped = await ws.ok("stop", sub)
    assert stopped["state"] == "idle"
    assert stopped["last_event"] == "stopped"

    events = await ws.drain(sub)
    assert [e["state"] for e in events if "state" in e][-1] == "idle"
    sequences = [e["sequence"] for e in events]
    assert sequences == sorted(sequences)
    assert all(e["instance_id"] == first["instance_id"] for e in events)


async def test_configure_is_validated_atomically(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    for settings in (
        {"bpm": 201},
        {"bpm": 0},
        {"bpm": 90, "duration": 0},
        {"duration": 360000},
        {"volume": 1.5},
        {"signature": "5/4"},
        {"count_in": 3},
        {"accent": "yes"},
        {"unknown": 1},
    ):
        msg = await ws.control("configure", settings=settings)
        assert not msg["success"], settings
        assert msg["error"]["code"] == "home_assistant_error"
    assert loaded.runtime_data.model.settings["bpm"] == 120

    msg = await ws.control("start")
    assert not msg["success"]
    assert "Tap Start" in msg["error"]["message"]

    msg = await ws.control("dance")
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_ownership_requires_own_subscription(hass: HomeAssistant, loaded, ws_factory) -> None:
    first = await ws_factory()
    second = await ws_factory()
    sub1, _ = await first.subscribe()
    await second.send(type="ping")  # message ids are per connection; make them differ
    sub2, _ = await second.subscribe()
    assert sub1 != sub2

    # No subscription id, a stale one, or another connection's id cannot claim.
    for client, sub in ((first, None), (first, 999), (second, sub1)):
        msg = await client.control("claim", sub)
        assert not msg["success"]
        assert "no matching metronome subscription" in msg["error"]["message"]
    assert loaded.runtime_data.owner is None

    assert (await first.ok("claim", sub1))["is_owner"] is True
    await first.ok("start", sub1)

    # While a session is active (or paused) another device cannot take over.
    msg = await second.control("claim", sub2)
    assert not msg["success"]
    assert "Another device is playing" in msg["error"]["message"]

    # It can still control the shared session through HA permissions.
    assert (await second.ok("stop", sub2))["state"] == "idle"
    events = await first.drain(sub1)
    assert events[-1]["state"] == "idle"
    assert events[-1]["is_owner"] is True

    # When idle, claiming moves output to the new device.
    moved = await second.ok("claim", sub2)
    assert moved["is_owner"] is True
    last = (await first.drain(sub1))[-1]
    assert last["is_owner"] is False
    assert last["output_ready"] is True


async def test_release_and_unsubscribe_interrupt(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    observer = await ws_factory()
    sub, _ = await ws.subscribe()
    obs, _ = await observer.subscribe()
    await ws.ok("claim", sub)
    await ws.ok("configure", sub, settings={"timer_enabled": True})
    await ws.ok("start", sub)
    await ws.ok("pause", sub)

    released = await ws.ok("release", sub)
    assert released["state"] == "idle"
    assert released["last_event"] == "interrupted"
    assert released["output_ready"] is False
    assert hass.states.get("event.metronome_session").attributes["event_type"] == "interrupted"

    await ws.ok("claim", sub)
    await ws.ok("start", sub)
    await ws.unsubscribe(sub)
    last = (await observer.drain(obs))[-1]
    assert last["state"] == "idle"
    assert last["last_event"] == "interrupted"
    assert last["output_ready"] is False
    # Releasing a token that is not the owner changes nothing.
    assert (await observer.ok("release", obs))["state"] == "idle"
    # The unsubscribed token can no longer heartbeat.
    msg = await ws.control("heartbeat", sub)
    assert not msg["success"]


async def test_connection_loss_interrupts(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    sub, _ = await ws.subscribe()
    await ws.ok("claim", sub)
    await ws.ok("start", sub)
    await ws.client.close()
    await hass.async_block_till_done()
    coordinator = loaded.runtime_data
    assert coordinator.owner is None
    assert coordinator.clients == {}
    assert hass.states.get(PLAYER).state == "idle"
    assert hass.states.get("event.metronome_session").attributes["event_type"] == "interrupted"


async def test_lease_expires_without_heartbeat(
    hass: HomeAssistant, loaded, ws_factory, freezer: FrozenDateTimeFactory
) -> None:
    ws = await ws_factory()
    observer = await ws_factory()
    sub, _ = await ws.subscribe()
    obs, _ = await observer.subscribe()
    await ws.ok("claim", sub)
    await ws.ok("start", sub)

    # Heartbeats every 3 s keep the session alive well past the 12 s lease.
    for _ in range(10):
        await tick(hass, freezer, 3)
        await ws.ok("heartbeat", sub)
    assert hass.states.get(PLAYER).state == "playing"

    # A vanished client is released 12-15 s after its last heartbeat.
    await tick(hass, freezer, 9)
    assert hass.states.get(PLAYER).state == "playing"
    await tick(hass, freezer, 6)
    assert hass.states.get(PLAYER).state == "idle"
    assert loaded.runtime_data.owner is None
    last = (await observer.drain(obs))[-1]
    assert last["last_event"] == "interrupted"
    assert last["output_ready"] is False
    # The subscription itself survives; the client can claim again.
    assert (await ws.ok("claim", sub))["is_owner"] is True


async def test_start_rejected_once_lease_is_stale(
    hass: HomeAssistant, loaded, ws_factory, freezer: FrozenDateTimeFactory
) -> None:
    ws = await ws_factory()
    sub, _ = await ws.subscribe()
    await ws.ok("claim", sub)
    freezer.tick(timedelta(seconds=13))  # lease check has not run yet
    msg = await ws.control("start", sub)
    assert not msg["success"]
    assert "Tap Start" in msg["error"]["message"]


async def test_wrong_and_unloaded_entities(hass: HomeAssistant, loaded, ws_factory) -> None:
    ws = await ws_factory()
    for entity_id in ("media_player.nothing", "number.metronome_tempo"):
        msg = await ws.send(type="metronome/subscribe", entity_id=entity_id)
        assert not msg["success"]
        assert "Select a Metronome media player" in msg["error"]["message"]
        msg = await ws.control("stop", entity_id=entity_id)
        assert not msg["success"]

    sub, _ = await ws.subscribe()
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    # The subscriber is told the session ended, then the instance is gone.
    assert (await ws.next_event(sub))["state"] == "idle"
    msg = await ws.send(type="metronome/subscribe", entity_id=PLAYER)
    assert not msg["success"]
    assert msg["error"]["message"] == "Metronome is unavailable"
    msg = await ws.control("start", sub)
    assert not msg["success"]


async def test_read_only_user_can_watch_but_not_control(
    hass: HomeAssistant, loaded, ws_factory, hass_read_only_access_token
) -> None:
    viewer = await ws_factory(hass_read_only_access_token)
    sub, snapshot = await viewer.subscribe()
    assert snapshot["state"] == "idle"
    for action, extra in (
        ("claim", {}),
        ("heartbeat", {}),
        ("release", {}),
        ("start", {}),
        ("stop", {}),
        ("configure", {"settings": {"bpm": 60}}),
    ):
        msg = await viewer.control(action, sub, **extra)
        assert not msg["success"], action
        assert msg["error"]["code"] == "unauthorized", action
    assert loaded.runtime_data.owner is None
    assert loaded.runtime_data.model.settings["bpm"] == 120

    # The viewer still receives state changes made by others.
    admin = await ws_factory()
    await admin.ok("configure", settings={"bpm": 60})
    assert (await viewer.next_event(sub))["settings"]["bpm"] == 60


async def test_ordinary_user_can_play(
    hass: HomeAssistant, loaded, ws_factory, hass_user_access_token
) -> None:
    ws = await ws_factory(hass_user_access_token)
    sub, _ = await ws.subscribe()
    assert (await ws.ok("claim", sub))["is_owner"] is True
    assert (await ws.ok("start", sub))["state"] == "playing"
    assert (await ws.ok("stop", sub))["state"] == "idle"


async def test_output_user_names_the_owner(
    hass: HomeAssistant, loaded, ws_factory, hass_user_access_token, hass_admin_user
) -> None:
    """Other pages see whose page holds the output; it clears on release/disconnect."""
    admin = await ws_factory()
    ordinary = await ws_factory(hass_user_access_token)
    sub_a, _ = await admin.subscribe()
    await ordinary.send(type="ping")
    sub_o, _ = await ordinary.subscribe()

    claimed = await ordinary.ok("claim", sub_o)
    assert claimed["is_owner"] is True
    assert claimed["output_user"] == "Ordinary"
    seen = (await admin.drain(sub_a))[-1]
    assert seen["output_ready"] is True
    assert seen["is_owner"] is False
    assert seen["output_user"] == "Ordinary"
    # Not exposed as an entity attribute (it is a per-page detail for the card).
    assert "output_user" not in hass.states.get(PLAYER).attributes

    # Hand-off while idle: the admin's page takes over.
    moved = await admin.ok("claim", sub_a)
    assert moved["output_user"] == hass_admin_user.name
    released = await admin.ok("release", sub_a)
    assert released["output_ready"] is False
    assert released["output_user"] is None


async def test_two_instances_have_separate_owners(hass: HomeAssistant, loaded, ws_factory) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    second = MockConfigEntry(domain="metronome", title="Practice", data={})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    ws = await ws_factory()
    sub1, _ = await ws.subscribe()
    sub2, snap2 = await ws.subscribe("media_player.practice")
    assert snap2["name"] == "Practice"
    await ws.ok("claim", sub1)
    await ws.ok("start", sub1)
    # Same device may own both instances; each runs its own session.
    msg = await ws.control("claim", sub2, entity_id="media_player.practice")
    assert msg["success"]
    msg = await ws.control("claim", sub1, entity_id="media_player.practice")
    assert not msg["success"]  # subscription of the other instance
    assert hass.states.get("media_player.practice").state == "idle"
    assert hass.states.get(PLAYER).state == "playing"


async def test_expected_rejections_are_not_logged_as_errors(
    hass: HomeAssistant, loaded, ws_factory, caplog: pytest.LogCaptureFixture
) -> None:
    first = await ws_factory()
    second = await ws_factory()
    sub1, _ = await first.subscribe()
    sub2, _ = await second.subscribe()
    await first.ok("claim", sub1)
    await first.ok("start", sub1)
    caplog.clear()
    assert not (await second.control("claim", sub2))["success"]
    assert not (await second.control("heartbeat", 999))["success"]
    assert not (await second.control("configure", sub2, settings={"count_in": 1}))["success"]
    assert not (await second.send(type="metronome/subscribe", entity_id="media_player.x"))[
        "success"
    ]
    assert [r for r in caplog.records if r.levelname == "ERROR"] == []
