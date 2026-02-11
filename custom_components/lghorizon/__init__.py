"""The lghorizon integration."""

from __future__ import annotations
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from lghorizon import LGHorizonApi, LGHorizonAuth, COUNTRY_SETTINGS
from lghorizon import LGHorizonApiUnauthorizedError

from .const import (
    API,
    CONF_COUNTRY_CODE,
    CONF_PROFILE_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    CONF_INTERRUPT_APP,
)

PLATFORMS = ["media_player", "sensor", "notify"]
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
_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    new_data = {**config_entry.data}

    if config_entry.version > 3:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version < 3:
        new_data[CONF_INTERRUPT_APP] = False

    if config_entry.version < 2:
        # migrate key config
        for country_code_key in COUNTRY_SETTINGS:
            if (
                config_entry.data[CONF_COUNTRY_CODE]
                == COUNTRY_SETTINGS[country_code_key]["name"]
            ):
                new_data[CONF_COUNTRY_CODE] = country_code_key
                break

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, minor_version=1, version=2
    )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lghorizon api from a config entry."""

    refresh_token = None
    if CONF_REFRESH_TOKEN in entry.data:
        refresh_token = entry.data[CONF_REFRESH_TOKEN]

    profile_id = None
    if CONF_PROFILE_ID in entry.data:
        profile_id = entry.data[CONF_PROFILE_ID]

    websession = async_get_clientsession(hass)

    @callback
    def _save_refresh_token(refresh_token: str):
        """Save the refresh token."""
        new_data = {**entry.data}
        new_data[CONF_REFRESH_TOKEN] = refresh_token
        hass.config_entries.async_update_entry(entry, data=new_data)

    auth = LGHorizonAuth(
        websession,
        entry.data[CONF_COUNTRY_CODE],
        refresh_token=refresh_token,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        token_refresh_callback=_save_refresh_token,
    )

    try:
        api = LGHorizonApi(auth, profile_id=profile_id)
        await api.initialize()
    except LGHorizonApiUnauthorizedError:
        entry.async_start_reauth(hass=hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        API: api,
        CONF_USERNAME: entry.data[CONF_USERNAME],
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
