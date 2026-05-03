"""Support for interface with a LGHorizon Settopbox."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.core import HomeAssistant
from .const import API, CONF_COUNTRY_CODE, DOMAIN
from datetime import timedelta
import logging

SCAN_INTERVAL = timedelta(hours=1)
_LOGGER = logging.getLogger(__name__)

from lghorizon import LGHorizonApi, LGHorizonRecordingQuota, COUNTRY_SETTINGS  # noqa: E402


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
    sensors.append(LGHorizonSensor(hass, username, api, entry))
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
        return "Recording capacity"

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
        """Return the state value."""
        if self._quota:
            return int(self._quota.percentage_used)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self._quota:
            return {
                "quota_mb": self._quota.quota,
                "occupied_mb": self._quota.occupied,
            }
        return None

    @property
    def state_class(self):
        """State class."""
        return "measurement"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to link this sensor to the account device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"{self._provider_name} account",
            manufacturer=self._provider_name,
            model="Account",
            entry_type=DeviceEntryType.SERVICE,
        )

    def __init__(self, hass: HomeAssistant, username: str, api: LGHorizonApi, entry: ConfigEntry) -> None:
        """Init the sensor."""
        self.api = api
        self.hass = hass
        self.username = username
        self._entry = entry
        country_code = entry.data.get(CONF_COUNTRY_CODE, "")
        self._provider_name = COUNTRY_SETTINGS.get(country_code, {}).get("name", "LG Horizon")

    async def async_update(self):
        """Update the sensor."""
        self._quota = await self.api.get_recording_quota()
