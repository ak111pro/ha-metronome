"""Session transitions, never per-beat state updates."""

from homeassistant.components.event import EventEntity
from .const import EVENT_TYPES
from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MetronomeEvent(entry.runtime_data)])


class MetronomeEvent(MetronomeEntity, EventEntity):
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator):
        super().__init__(coordinator, "session", "Session", "mdi:metronome")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.coordinator.event_listeners.add(self._session_event)
        self.async_on_remove(lambda: self.coordinator.event_listeners.discard(self._session_event))

    def _session_event(self, event, attributes):
        self._trigger_event(event, attributes)
        self.async_write_ha_state()
