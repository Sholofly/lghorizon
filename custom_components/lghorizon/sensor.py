"""Support for interface with a LGHorizon Settopbox."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from .const import (
    API,
    DOMAIN,
)


from lghorizon import LGHorizonApi


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    sensors = []
    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    username = hass.data[DOMAIN][entry.entry_id][CONF_USERNAME]
    sensors.append(LGHorizonSensor(hass, username, api))
    async_add_entities(sensors, True)


class LGHorizonSensor(SensorEntity):
    """The LG Horizon Sensor."""

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
        self, hass: HomeAssistantType, username: str, api: LGHorizonApi
    ) -> None:
        """Init the media player."""
        self.api = api
        self.hass = hass
        self.username = username

    async def async_update(self):
        """Update the box."""
        await self.hass.async_add_executor_job(self.api.get_recording_capacity)
