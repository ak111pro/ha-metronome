"""Lifecycle, persistence and the served frontend module."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.metronome.const import DEFAULTS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import PLAYER


def _stored(entry: MockConfigEntry, data: Any) -> dict[str, Any]:
    return {"version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}", "data": data}


async def test_setup_unload_reload(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    assert loaded.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids()) == 9

    assert await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.LOADED
    assert hass.states.get(PLAYER).state == "idle"

    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(PLAYER).state == "unavailable"


async def test_unload_saves_and_remove_deletes_store(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    key = f"{DOMAIN}.{loaded.entry_id}"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.metronome_tempo", "value": 77}, blocking=True
    )
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[key]["data"]["bpm"] == 77

    await hass.config_entries.async_remove(loaded.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage
    assert hass.states.get(PLAYER) is None


async def test_settings_restored_idle_without_owner(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    settings = DEFAULTS | {
        "bpm": 96,
        "signature": "6/8",
        "count_in": 2,
        "accent": False,
        "timer_enabled": True,
        "duration": 359999,
        "volume": 0.25,
        "muted": True,
    }
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _stored(entry, settings)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.model.settings == settings
    assert coordinator.model.state == "idle"
    assert coordinator.owner is None
    state = hass.states.get(PLAYER)
    assert state.state == "idle"
    assert state.attributes["output_ready"] is False
    assert state.attributes["volume_level"] == 0.25
    assert state.attributes["is_volume_muted"] is True
    assert hass.states.get("sensor.metronome_expected_finish").state == "unknown"
    assert hass.states.get("select.metronome_count_in").state == "2 bars"
    assert hass.states.get("switch.metronome_accent_first_beat").state == "off"


async def test_invalid_stored_values_are_skipped(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _stored(
        entry, {"bpm": 999, "signature": "7/8", "volume": "loud", "duration": 45, "old_key": 1}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    settings = entry.runtime_data.model.settings
    assert settings == DEFAULTS | {"duration": 45}


async def test_stored_data_of_wrong_type_does_not_block_setup(
    hass: HomeAssistant, entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = _stored(entry, ["not", "a", "dict"])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.model.settings == DEFAULTS


async def test_frontend_module_is_served(hass: HomeAssistant, loaded, hass_client) -> None:
    client = await hass_client()
    for name in ("metronome-card.js", "player.js", "shared.js", "styles.js", "editor.js"):
        response = await client.get(f"/metronome/{name}?v=0.1.0-alpha.1")
        assert response.status == 200, name
        assert response.content_type in ("application/javascript", "text/javascript")
    body = await (await client.get("/metronome/metronome-card.js")).text()
    assert 'customElements.define("metronome-card"' in body

    # Only the frontend directory is exposed, not the integration's Python files.
    for path in (
        "/metronome/__init__.py",
        "/metronome/../manifest.json",
        "/metronome/%2e%2e/const.py",
    ):
        response = await client.get(path)
        assert response.status in (403, 404), path


async def test_failed_platform_setup_leaves_no_timer(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    with patch.object(
        hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError("boom")
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    # The test harness fails the test on a lingering lease timer.


async def test_changes_are_saved_after_a_second(
    hass: HomeAssistant, loaded: MockConfigEntry, hass_storage: dict[str, Any], freezer
) -> None:
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from homeassistant.util import dt as dt_util

    key = f"{DOMAIN}.{loaded.entry_id}"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.metronome_time_signature", "option": "3/4"},
        blocking=True,
    )
    assert key not in hass_storage
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass_storage[key]["data"]["signature"] == "3/4"
    # Session state is never stored.
    assert set(hass_storage[key]["data"]) == set(DEFAULTS)


async def test_renamed_entry_title_reaches_the_card(
    hass: HomeAssistant, loaded: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(loaded, title="Drums")
    assert loaded.runtime_data.snapshot()["name"] == "Drums"
    # Entity ids stay stable.
    assert hass.states.get(PLAYER) is not None
