"""The lghorizon integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from lghorizon import LGHorizonApi, LGHorizonAuth

from .const import API, CONF_COUNTRY_CODE, CONF_PROFILE_ID, CONF_REFRESH_TOKEN, DOMAIN

PLATFORMS = ["media_player", "sensor"]
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_COUNTRY_CODE, default="nl"): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_REFRESH_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lghorizon api from a config entry."""

    refresh_token = None
    if CONF_REFRESH_TOKEN in entry.data:
        refresh_token = entry.data[CONF_REFRESH_TOKEN]

    profile_id = None
    if CONF_PROFILE_ID in entry.data:
        profile_id = entry.data[CONF_PROFILE_ID]

    websession = async_get_clientsession(hass)

    auth = LGHorizonAuth(
        websession,
        entry.data[CONF_COUNTRY_CODE],
        refresh_token=refresh_token,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    api = LGHorizonApi(auth, profile_id)
    await api.initialize()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        API: api,
        CONF_USERNAME: entry.data[CONF_USERNAME],
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if CONF_REFRESH_TOKEN in entry.data:
        new_data = {**entry.data}
        new_data[CONF_REFRESH_TOKEN] = api.auth.refresh_token
        hass.config_entries.async_update_entry(entry, data=new_data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
