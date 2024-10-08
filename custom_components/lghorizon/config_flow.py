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

from .const import DOMAIN, CONF_COUNTRY_CODE, CONF_REFRESH_TOKEN, COUNTRY_CODES, CONF_IDENTIFIER
from lghorizon import (
    LGHorizonApi,
    LGHorizonApiUnauthorizedError,
    LGHorizonApiConnectionError,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTRY_CODE, default=list(COUNTRY_CODES.keys())[0]): vol.In(
            list(COUNTRY_CODES.keys())
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_IDENTIFIER):cv.string,
        vol.Optional(CONF_REFRESH_TOKEN):cv.string
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    try:
        telenet_identifier = None
        if CONF_IDENTIFIER in data:
            telenet_identifier = data[CONF_IDENTIFIER]

        refresh_token = None
        if CONF_REFRESH_TOKEN in data:
            refresh_token = data[CONF_REFRESH_TOKEN]

        api = LGHorizonApi(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            COUNTRY_CODES[data[CONF_COUNTRY_CODE]],
            telenet_identifier,
            refresh_token,
        )
        await hass.async_add_executor_job(api.connect)
        await hass.async_add_executor_job(api.disconnect)
    except LGHorizonApiUnauthorizedError:
        raise InvalidAuth
    except LGHorizonApiConnectionError:
        raise CannotConnect
    except Exception as ex:
        _LOGGER.error(ex)
        raise CannotConnect

    return {"title": data[CONF_USERNAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for lghorizon."""

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
