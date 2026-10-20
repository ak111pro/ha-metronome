"""Entity platforms: states, features and native actions."""

from __future__ import annotations

import pytest

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported

from .conftest import PLAYER

BASE_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
)


async def _call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data):
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)


async def test_initial_states(hass: HomeAssistant, loaded) -> None:
    player = hass.states.get(PLAYER)
    assert player.state == "idle"
    assert player.attributes["supported_features"] == BASE_FEATURES
    assert player.attributes["volume_level"] == 0.5
    assert player.attributes["is_volume_muted"] is False
    assert player.attributes["media_title"] == "120 BPM · 4/4"
    assert player.attributes["output"] == "Current device"
    assert player.attributes["output_ready"] is False
    assert player.attributes["friendly_name"] == "Metronome"

    tempo = hass.states.get("number.metronome_tempo")
    assert tempo.state == "120"
    assert (tempo.attributes["min"], tempo.attributes["max"], tempo.attributes["step"]) == (
        1,
        200,
        1,
    )
    duration = hass.states.get("number.metronome_timer_duration")
    assert duration.state == "30"
    assert (duration.attributes["min"], duration.attributes["max"]) == (1, 359999)
    assert duration.attributes["unit_of_measurement"] == "s"

    signature = hass.states.get("select.metronome_time_signature")
    assert signature.state == "4/4"
    assert signature.attributes["options"] == ["2/4", "3/4", "4/4", "6/8"]
    count_in = hass.states.get("select.metronome_count_in")
    assert count_in.state == "Off"
    assert count_in.attributes["options"] == ["Off", "1 bar", "2 bars"]

    assert hass.states.get("switch.metronome_timer").state == "off"
    assert hass.states.get("switch.metronome_accent_first_beat").state == "on"
    event = hass.states.get("event.metronome_session")
    assert event.state == "unknown"
    assert event.attributes["event_types"] == [
        "started",
        "paused",
        "resumed",
        "stopped",
        "finished",
        "interrupted",
    ]
    finish = hass.states.get("sensor.metronome_expected_finish")
    assert finish.state == "unknown"
    assert finish.attributes["device_class"] == "timestamp"


async def test_native_setters(hass: HomeAssistant, loaded) -> None:
    await _call(hass, "number", "set_value", "number.metronome_tempo", value=1)
    await _call(hass, "number", "set_value", "number.metronome_timer_duration", value=359999)
    await _call(hass, "select", "select_option", "select.metronome_time_signature", option="6/8")
    await _call(hass, "select", "select_option", "select.metronome_count_in", option="2 bars")
    await _call(hass, "switch", "turn_on", "switch.metronome_timer")
    await _call(hass, "switch", "turn_off", "switch.metronome_accent_first_beat")
    await _call(hass, "media_player", "volume_set", PLAYER, volume_level=0.3)
    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)

    settings = loaded.runtime_data.model.settings
    assert settings == {
        "bpm": 1,
        "duration": 359999,
        "signature": "6/8",
        "count_in": 2,
        "timer_enabled": True,
        "accent": False,
        "volume": 0.3,
        "muted": True,
    }
    assert isinstance(settings["bpm"], int)
    player = hass.states.get(PLAYER)
    assert player.attributes["supported_features"] == BASE_FEATURES | (
        MediaPlayerEntityFeature.PAUSE
    )
    assert player.attributes["media_title"] == "1 BPM · 6/8"
    assert hass.states.get("number.metronome_tempo").state == "1"
    assert hass.states.get("select.metronome_count_in").state == "2 bars"


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data"),
    [
        ("number", "set_value", "number.metronome_tempo", {"value": 0}),
        ("number", "set_value", "number.metronome_tempo", {"value": 201}),
        ("number", "set_value", "number.metronome_tempo", {"value": 90.5}),
        ("number", "set_value", "number.metronome_timer_duration", {"value": 0}),
        ("number", "set_value", "number.metronome_timer_duration", {"value": 360000}),
        ("select", "select_option", "select.metronome_time_signature", {"option": "7/8"}),
    ],
)
async def test_out_of_range_values_rejected(
    hass: HomeAssistant, loaded, domain, service, entity_id, data
) -> None:
    before = dict(loaded.runtime_data.model.settings)
    with pytest.raises((HomeAssistantError, ValueError)):
        await _call(hass, domain, service, entity_id, **data)
    assert loaded.runtime_data.model.settings == before


async def test_pause_needs_timer(hass: HomeAssistant, owner) -> None:
    await _call(hass, "media_player", "media_play", PLAYER)
    assert hass.states.get(PLAYER).state == "playing"
    with pytest.raises(ServiceNotSupported):
        await _call(hass, "media_player", "media_pause", PLAYER)
    assert hass.states.get(PLAYER).state == "playing"


@pytest.mark.parametrize("paused", [False, True])
async def test_structural_settings_locked_while_active(
    hass: HomeAssistant, loaded, owner, paused: bool
) -> None:
    await _call(hass, "switch", "turn_on", "switch.metronome_timer")
    await _call(hass, "media_player", "media_play", PLAYER)
    if paused:
        await _call(hass, "media_player", "media_pause", PLAYER)
    assert hass.states.get(PLAYER).state == ("paused" if paused else "playing")

    for domain, service, entity_id, data in (
        ("switch", "turn_off", "switch.metronome_timer", {}),
        ("number", "set_value", "number.metronome_timer_duration", {"value": 90}),
        ("select", "select_option", "select.metronome_time_signature", {"option": "3/4"}),
        ("select", "select_option", "select.metronome_count_in", {"option": "1 bar"}),
    ):
        with pytest.raises(HomeAssistantError, match="Stop the metronome"):
            await _call(hass, domain, service, entity_id, **data)

    # Tempo and sound stay adjustable.
    await _call(hass, "number", "set_value", "number.metronome_tempo", value=90)
    await _call(hass, "switch", "turn_off", "switch.metronome_accent_first_beat")
    await _call(hass, "media_player", "volume_set", PLAYER, volume_level=0.9)
    await _call(hass, "media_player", "volume_mute", PLAYER, is_volume_muted=True)
    settings = loaded.runtime_data.model.settings
    assert (settings["bpm"], settings["accent"], settings["volume"], settings["muted"]) == (
        90,
        False,
        0.9,
        True,
    )

    await _call(hass, "media_player", "media_stop", PLAYER)
    await _call(hass, "number", "set_value", "number.metronome_timer_duration", value=90)
    assert settings["duration"] == 90


async def test_media_actions_before_any_client(hass: HomeAssistant, loaded) -> None:
    with pytest.raises(HomeAssistantError, match="Tap Start in the metronome card"):
        await _call(hass, "media_player", "media_play", PLAYER)
    assert hass.states.get(PLAYER).state == "idle"
    # Stop is harmless while idle; volume works without a client.
    await _call(hass, "media_player", "media_stop", PLAYER)
    await _call(hass, "media_player", "volume_set", PLAYER, volume_level=0.2)
    assert hass.states.get(PLAYER).attributes["volume_level"] == 0.2


async def test_media_actions_after_client_claimed(hass: HomeAssistant, owner) -> None:
    ws, sub = owner
    assert hass.states.get(PLAYER).attributes["output_ready"] is True
    await _call(hass, "media_player", "media_play", PLAYER)
    assert hass.states.get(PLAYER).state == "playing"
    event = await ws.next_event(sub)
    assert event["state"] == "playing"
    assert event["is_owner"] is True
    await _call(hass, "media_player", "media_stop", PLAYER)
    assert hass.states.get(PLAYER).state == "idle"

    # After the client goes away, native play fails again with a helpful message.
    await ws.unsubscribe(sub)
    assert hass.states.get(PLAYER).attributes["output_ready"] is False
    with pytest.raises(HomeAssistantError, match="Tap Start"):
        await _call(hass, "media_player", "media_play", PLAYER)


async def test_read_only_user_cannot_use_native_actions(
    hass: HomeAssistant, loaded, hass_read_only_user
) -> None:
    from homeassistant.core import Context
    from homeassistant.exceptions import Unauthorized

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.metronome_tempo", "value": 60},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    assert loaded.runtime_data.model.settings["bpm"] == 120
