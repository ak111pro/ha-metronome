"""Timer and first-beat accent controls."""

from homeassistant.components.switch import SwitchEntity
from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        MetronomeSwitch(entry.runtime_data, "timer_enabled", "Timer", "mdi:timer-outline"),
        MetronomeSwitch(entry.runtime_data, "accent", "Accent first beat", "mdi:waveform"),
    ])


class MetronomeSwitch(MetronomeEntity, SwitchEntity):
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator, key, name, icon)
        self.key = key

    @property
    def is_on(self):
        return self.settings[self.key]

    async def async_turn_on(self, **kwargs):
        self.coordinator.configure({self.key: True})

    async def async_turn_off(self, **kwargs):
        self.coordinator.configure({self.key: False})
