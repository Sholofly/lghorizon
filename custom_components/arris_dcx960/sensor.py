"""Support for interface with a ArrisDCX960 Settopbox."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from .const import (
    API,
    DOMAIN,
)


from arris_dcx960 import ArrisDCX960


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    sensors = []
    api = hass.data[DOMAIN][entry.entry_id][API]
    username = hass.data[DOMAIN][entry.entry_id][CONF_USERNAME]
    sensors.append(ArrisDCX960Sensor(hass, username, api))
    async_add_entities(sensors, True)


class ArrisDCX960Sensor(SensorEntity):
    """The Arris DCX960 Sensor."""

    username: str
    hass: HomeAssistantType

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self.username}_recording_capacity"

    @property
    def name(self):
        return f"{self.username} Recording capacity"
    
    @property
    def icon(self):
        return "mdi:percent-outline"

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def native_value(self):
        return self.api.recording_capacity

    @property
    def state_class(self):
        return "total"

    def __init__(
        self, hass: HomeAssistantType, username: str, api: ArrisDCX960
    ) -> None:
        """Init the media player."""
        self.api = api
        self.hass = hass
        self.username = username

    async def async_update(self):
        """Update the box."""
        await self.hass.async_add_executor_job(self.api.get_recording_capacity)
