"""Config flow: named, independent instances."""

from __future__ import annotations

from custom_components.metronome.const import DOMAIN
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


async def _create(hass: HomeAssistant, name: str):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": name})
    await hass.async_block_till_done()
    return result


async def test_user_flow_creates_named_entry(hass: HomeAssistant) -> None:
    result = await _create(hass, "  Practice  ")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Practice"
    assert result["data"] == {}
    assert hass.states.get("media_player.practice").state == "idle"


async def test_blank_name_is_rejected(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "   "})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "name_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Ok"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_two_instances_are_independent(hass: HomeAssistant) -> None:
    await _create(hass, "Metronome")
    await _create(hass, "Practice")
    entries = hass.config_entries.async_entries(DOMAIN)
    assert [e.title for e in entries] == ["Metronome", "Practice"]

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for entry in entries
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    # 9 entities per instance, unique ids built from the config entry id.
    assert len(unique_ids) == 18
    for entry in entries:
        ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
        assert ids == {
            f"{entry.entry_id}_{key}"
            for key in (
                "player",
                "bpm",
                "duration",
                "signature",
                "count_in",
                "timer_enabled",
                "accent",
                "session",
                "finish",
            )
        }

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.practice_tempo", "value": 60}, blocking=True
    )
    assert hass.states.get("number.practice_tempo").state == "60"
    assert hass.states.get("number.metronome_tempo").state == "120"
