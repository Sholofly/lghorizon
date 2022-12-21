"""The lghorizon integration."""
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
    API,
    COUNTRY_CODES,
    CONF_IDENTIFIER
)

from lghorizon import LGHorizonApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "sensor"]
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_COUNTRY_CODE, default="nl"): cv.string,
                vol.Optional(CONF_IDENTIFIER):cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lghorizon api from a config entry."""
    api = LGHorizonApi(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        COUNTRY_CODES[entry.data[CONF_COUNTRY_CODE]],
        entry.data[CONF_IDENTIFIER]
    )
    await hass.async_add_executor_job(api.connect)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        API: api,
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
