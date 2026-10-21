"""Home Assistant metronome with explicitly selected frontend audio output."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PLATFORMS
from .coordinator import MetronomeCoordinator
from .resource import async_register_card, async_unregister_card
from .websocket import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/metronome", str(Path(__file__).parent / "frontend"), False)]
    )
    async_register_commands(hass)
    return True


async def async_setup_entry(hass, entry):
    await async_register_card(hass)  # once per HA start, see resource.py
    coordinator = MetronomeCoordinator(hass, entry)
    await coordinator.async_load()
    # Runs on unload and also when the platform setup below fails.
    entry.async_on_unload(coordinator.async_cancel_timers)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_unload()
        return True
    return False


async def async_remove_entry(hass, entry):
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
    if not [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]:
        await async_unregister_card(hass)
