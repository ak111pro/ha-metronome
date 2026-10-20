"""Shared entity identity and state subscriptions."""

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, VERSION


class MetronomeEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, icon):
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Metronome",
            model="Current-device metronome",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.listen(self.async_write_ha_state))

    @property
    def settings(self):
        return self.coordinator.model.settings
