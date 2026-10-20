"""Expected finish time for native HA dashboards and automations."""

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([FinishSensor(entry.runtime_data)])


class FinishSensor(MetronomeEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator):
        super().__init__(coordinator, "finish", "Expected finish", "mdi:clock-end")

    @property
    def native_value(self):
        value = self.coordinator.model.ends_at
        return datetime.fromtimestamp(value, UTC) if value is not None else None
