"""Support for interface with a LGHorizon Settopbox."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from .const import API, CONF_COUNTRY_CODE, DOMAIN
from datetime import timedelta
import logging

SCAN_INTERVAL = timedelta(hours=1)
_LOGGER = logging.getLogger(__name__)

from lghorizon import LGHorizonApi, LGHorizonRecordingQuota  # noqa: E402


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform."""
    sensors = []

    country = entry.data[CONF_COUNTRY_CODE][0:2]
    if country == "gb":
        return

    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]

    if not api.has_cloud_recording:
        _LOGGER.debug("No recording capacity available. No sensor added.")
        return

    username = hass.data[DOMAIN][entry.entry_id][CONF_USERNAME]
    sensors.append(LGHorizonSensor(hass, username, api))
    async_add_entities(sensors, True)


class LGHorizonSensor(SensorEntity):
    """The LG Horizon Sensor."""

    username: str
    hass: HomeAssistant
    _quota: LGHorizonRecordingQuota | None = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self.username}_recording_capacity"

    @property
    def name(self):
        """Return the name."""
        return f"{self.username} Recording capacity"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:percent-outline"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    @property
    def native_value(self):
        """Return the name."""
        if self._quota:
            return int(self._quota.percentage_used)
        return None

    @property
    def state_class(self):
        """State class."""
        return "total"

    def __init__(self, hass: HomeAssistant, username: str, api: LGHorizonApi) -> None:
        """Init the media player."""
        self.api = api
        self.hass = hass
        self.username = username

    async def async_update(self):
        """Update the box."""
        self._quota = await self.api.get_recording_quota()
