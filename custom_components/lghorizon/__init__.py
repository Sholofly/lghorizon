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
    CONF_REFRESH_TOKEN,
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
                vol.Optional(CONF_COUNTRY_CODE, default="nl"): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_IDENTIFIER):cv.string,
                vol.Optional(CONF_REFRESH_TOKEN):cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lghorizon api from a config entry."""
    telenet_identifier = None
    if CONF_IDENTIFIER in entry.data:
        telenet_identifier = entry.data[CONF_IDENTIFIER]

    refresh_token = None
    if CONF_REFRESH_TOKEN in entry.data:
       refresh_token = entry.data[CONF_REFRESH_TOKEN]
    
    api = LGHorizonApi(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        COUNTRY_CODES[entry.data[CONF_COUNTRY_CODE]],
        telenet_identifier,
        refresh_token,
    )
    await hass.async_add_executor_job(api.connect)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        API: api,
        CONF_USERNAME: entry.data[CONF_USERNAME],
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if CONF_REFRESH_TOKEN in entry.data:
        _LOGGER.info("New JWT stored: %s", api.refresh_token)
        new_data = {**entry.data}
        new_data[CONF_REFRESH_TOKEN] = api.refresh_token
        hass.config_entries.async_update_entry(entry, data=new_data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
