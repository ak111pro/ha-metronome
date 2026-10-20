"""Home Assistant metronome with explicitly selected frontend audio output."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PLATFORMS
from .coordinator import MetronomeCoordinator
from .websocket import async_register_commands


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/metronome", str(Path(__file__).parent / "frontend"), False)]
    )
    async_register_commands(hass)
    return True


async def async_setup_entry(hass, entry):
    coordinator = MetronomeCoordinator(hass, entry)
    await coordinator.async_load()
    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_unload()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False


async def async_remove_entry(hass, entry):
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
