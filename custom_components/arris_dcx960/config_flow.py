"""Config flow for arrisdcx960 integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_COUNTRY_CODE, CONF_OMIT_CHANNEL_QUALITY, COUNTRY_CODES
from arris_dcx960 import ArrisDCX960, ArrisDCX960AuthenticationError, ArrisDCX960ConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_COUNTRY_CODE, default=list(COUNTRY_CODES.keys())[0]): vol.In(
            list(COUNTRY_CODES.keys())
        ),
        vol.Optional(CONF_OMIT_CHANNEL_QUALITY, default=False): cv.boolean,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    try:
        api = ArrisDCX960(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            COUNTRY_CODES[data[CONF_COUNTRY_CODE]],
        )
        await hass.async_add_executor_job(api.connect)
        await hass.async_add_executor_job(api.disconnect)
    except ArrisDCX960AuthenticationError:
        raise InvalidAuth
    except ArrisDCX960ConnectionError:
        raise CannotConnect
    except Exception as ex:
        _LOGGER.error(ex)
        raise CannotConnect

    return {"title": data[CONF_USERNAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for arrisdcx960."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
