"""Meter and count-in controls."""

from homeassistant.components.select import SelectEntity
from .const import SIGNATURES
from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        MetronomeSelect(entry.runtime_data, "signature", "Time signature", list(SIGNATURES)),
        MetronomeSelect(entry.runtime_data, "count_in", "Count-in", ["Off", "1 bar", "2 bars"]),
    ])


class MetronomeSelect(MetronomeEntity, SelectEntity):
    def __init__(self, coordinator, key, name, options):
        super().__init__(coordinator, key, name, "mdi:music-note")
        self.key = key
        self._attr_options = options

    @property
    def current_option(self):
        value = self.settings[self.key]
        return self.options[value] if self.key == "count_in" else value

    async def async_select_option(self, option):
        self.coordinator.configure({self.key: self.options.index(option) if self.key == "count_in" else option})
