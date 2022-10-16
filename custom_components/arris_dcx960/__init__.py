"""The arrisdcx960 integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging
from .const import (
    DOMAIN,
    CONF_COUNTRY_CODE,
    CONF_OMIT_CHANNEL_QUALITY,
    API,
    COUNTRY_CODES,
)

from arris_dcx960 import ArrisDCX960

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "sensor"]
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_COUNTRY_CODE, default="nl"): cv.string,
                vol.Optional(CONF_OMIT_CHANNEL_QUALITY, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up arrisdcx960 from a config entry."""
    api = ArrisDCX960(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        COUNTRY_CODES[entry.data[CONF_COUNTRY_CODE]],
    )
    await hass.async_add_executor_job(api.connect)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        API: api,
        CONF_OMIT_CHANNEL_QUALITY: entry.data[CONF_OMIT_CHANNEL_QUALITY],
        CONF_USERNAME: entry.data[CONF_USERNAME],
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
