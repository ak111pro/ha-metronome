"""Automation-accessible tempo and configured timer duration."""

from homeassistant.components.number import NumberEntity, NumberMode
from .const import MAX_DURATION
from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        MetronomeNumber(entry.runtime_data, "bpm", "Tempo", "mdi:metronome", 1, 200, "BPM"),
        MetronomeNumber(entry.runtime_data, "duration", "Timer duration", "mdi:timer-outline", 1, MAX_DURATION, "s"),
    ])


class MetronomeNumber(MetronomeEntity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, key, name, icon, low, high, unit):
        super().__init__(coordinator, key, name, icon)
        self.key = key
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        return self.settings[self.key]

    async def async_set_native_value(self, value):
        self.coordinator.configure({self.key: value})
