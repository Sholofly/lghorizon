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
from homeassistant.helpers.selector import (
    SelectSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

import homeassistant.helpers.config_validation as cv


from lghorizon import (
    LGHorizonApi,
    LGHorizonApiUnauthorizedError,
    LGHorizonApiConnectionError,
    LGHorizonApiLockedError,
    LGHorizonCustomer,
)

from .const import (
    DOMAIN,
    CONF_COUNTRY_CODE,
    CONF_REFRESH_TOKEN,
    COUNTRY_CODES,
    CONF_IDENTIFIER,
    CONF_PROFILE_ID,
)


_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AccountLocked(HomeAssistantError):
    """Error to indicate account is locked."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for lghorizon."""

    VERSION = 1
    CONFIG_DATA: dict[str, Any] = {}
    customer: LGHorizonCustomer = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        user_schema = vol.Schema(
            {
                vol.Required(
                    CONF_COUNTRY_CODE, default=list(COUNTRY_CODES.keys())[0]
                ): vol.In(list(COUNTRY_CODES.keys())),
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_IDENTIFIER): cv.string,
                vol.Optional(CONF_REFRESH_TOKEN): cv.string,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=user_schema)

        errors = {}

        try:
            await self.validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except AccountLocked:
            errors["base"] = "account_locked"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.CONFIG_DATA.update(user_input)
            profile_step = await self.async_step_profile(user_input=user_input)
            return profile_step
        user_form = await self.async_show_form(
            step_id="user", data_schema=user_schema, errors=errors
        )
        return user_form

    async def validate_input(self, hass: HomeAssistant, data: dict[str, Any]):
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
            # store customer for profile extraction
            self.customer = api.customer
            await hass.async_add_executor_job(api.disconnect)
        except LGHorizonApiUnauthorizedError:
            raise InvalidAuth
        except LGHorizonApiConnectionError:
            raise CannotConnect
        except LGHorizonApiLockedError:
            raise AccountLocked
        except Exception as ex:
            _LOGGER.error(ex)
            raise CannotConnect

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        profile_selectors = []
        for profile in self.customer.profiles.values():
            profile_selectors.append(
                SelectOptionDict(value=profile.profile_id, label=profile.name),
            )
        profile_schema = vol.Schema(
            {
                vol.Required(CONF_PROFILE_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=profile_selectors, mode=SelectSelectorMode.DROPDOWN
                    ),
                ),
            }
        )

        if (
            user_input is None
            or CONF_PROFILE_ID not in user_input
            or not user_input[CONF_PROFILE_ID]
        ):
            return self.async_show_form(step_id="profile", data_schema=profile_schema)
        self.CONFIG_DATA.update(user_input)
        return self.async_create_entry(
            title=self.CONFIG_DATA[CONF_USERNAME], data=self.CONFIG_DATA
        )
