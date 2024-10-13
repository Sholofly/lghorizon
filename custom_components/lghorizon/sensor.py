"""Support for interface with a LGHorizon Settopbox."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from .const import (
    API,
    CONF_COUNTRY_CODE,
    COUNTRY_CODES,
    DOMAIN
)
from datetime import timedelta
import logging

SCAN_INTERVAL = timedelta(hours=1)
_LOGGER = logging.getLogger(__name__)

from lghorizon import LGHorizonApi


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    sensors = []
    
    country = COUNTRY_CODES[entry.data[CONF_COUNTRY_CODE]][0:2]
    if country == "gb":
         _LOGGER.debug("Recording capacity feature available in GB. No sensor added.")
         return

    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    capacity = await hass.async_add_executor_job(api.get_recording_capacity)
    if not capacity:
        _LOGGER.info("No recording capacity available. No sensor added.")
        return

    username = hass.data[DOMAIN][entry.entry_id][CONF_USERNAME]
    sensors.append(LGHorizonSensor(hass, username, api))
    async_add_entities(sensors, True)


class LGHorizonSensor(SensorEntity):
    """The LG Horizon Sensor."""

    username: str
    hass: HomeAssistant

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

    def __init__(self, hass: HomeAssistant, username: str, api: LGHorizonApi) -> None:
        """Init the media player."""
        self.api = api
        self.hass = hass
        self.username = username

    async def async_update(self):
        """Update the box."""
        await self.hass.async_add_executor_job(self.api.get_recording_capacity)
