"""Config flow for LGHorizon integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from .options_flow import OptionsFlowHandler
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.selector import (
    SelectSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from homeassistant.helpers.aiohttp_client import async_get_clientsession

import homeassistant.helpers.config_validation as cv


from lghorizon import (
    LGHorizonApiUnauthorizedError,
    LGHorizonApiConnectionError,
    LGHorizonApiLockedError,
    LGHorizonCustomer,
    LGHorizonApi,
    LGHorizonAuth,
    COUNTRY_SETTINGS,
)


from .const import (
    DOMAIN,
    CONF_COUNTRY_CODE,
    CONF_REFRESH_TOKEN,
    CONF_PROFILE_ID,
    CONF_CHANNEL_SORT,
    CONF_EXCLUDED_CHANNELS,
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
    CONFIG_DATA: dict[str, Any] = None

    customer: LGHorizonCustomer = None
    _channels = []
    _profiles = []

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""

        country_selectors = [
            SelectOptionDict(
                value=country_code_key,
                label=COUNTRY_SETTINGS[country_code_key]["name"],
            )
            for country_code_key in COUNTRY_SETTINGS
        ]

        user_schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY_CODE): SelectSelector(
                    SelectSelectorConfig(
                        options=country_selectors, mode=SelectSelectorMode.DROPDOWN
                    ),
                ),
                vol.Required(CONF_USERNAME): cv.string,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_schema, errors=errors
            )

        self.CONFIG_DATA = {
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_COUNTRY_CODE: None,
            CONF_PROFILE_ID: None,
            CONF_REFRESH_TOKEN: None,
        }

        self.CONFIG_DATA.update(user_input)

        return await self.async_step_credentials()

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """Enter credentials step."""

        cred_schema: vol.Schema = vol.Schema({})

        if COUNTRY_SETTINGS[self.CONFIG_DATA[CONF_COUNTRY_CODE]].get(
            "use_refreshtoken", True
        ):
            cred_schema = cred_schema.extend(
                {
                    vol.Optional(CONF_REFRESH_TOKEN): cv.string,
                }
            )
        else:
            cred_schema = cred_schema.extend({vol.Required(CONF_PASSWORD): cv.string})

        if user_input is None:
            return self.async_show_form(step_id="credentials", data_schema=cred_schema)

        self.CONFIG_DATA.update(user_input)

        errors: dict[str, str] = {}

        try:
            await self.validate_config(self.hass)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except AccountLocked:
            errors["base"] = "account_locked"
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "unknown"
            _LOGGER.exception("Unexpected exception")
        if len(errors) > 0:
            return self.async_show_form(
                step_id="credentials", data_schema=cred_schema, errors=errors
            )
        return await self.async_step_profile()

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select profile step."""
        profile_selectors = [
            SelectOptionDict(value=profile.id, label=profile.name)
            for profile in self._profiles.values()
        ]

        sort_selectors = [
            "number",
            "alpha",
        ]

        channel_selectors = [
            SelectOptionDict(value=str(channel.channel_number), label=channel.title)
            for channel in self._channels.values()
        ]

        profile_schema = vol.Schema(
            {
                vol.Required(CONF_PROFILE_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=profile_selectors, mode=SelectSelectorMode.DROPDOWN
                    ),
                ),
                vol.Required(CONF_CHANNEL_SORT, default="number"): SelectSelector(
                    SelectSelectorConfig(
                        options=sort_selectors,
                        translation_key="channel_sort",
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(CONF_EXCLUDED_CHANNELS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=channel_selectors,
                        translation_key="excluded_channels",
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
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

    async def validate_config(self, hass: HomeAssistant):
        """Validate the user input allows us to connect."""
        client_session = async_get_clientsession(hass)
        try:
            auth = LGHorizonAuth(
                client_session,
                self.CONFIG_DATA[CONF_COUNTRY_CODE],
                self.CONFIG_DATA[CONF_REFRESH_TOKEN],
                self.CONFIG_DATA[CONF_USERNAME],
                self.CONFIG_DATA[CONF_PASSWORD],
            )
            api = LGHorizonApi(auth, self.CONFIG_DATA[CONF_PROFILE_ID])
            await api.initialize()
            profile_id = self.CONFIG_DATA[CONF_PROFILE_ID]
            self._profiles = await api.get_profiles()
            self._channels = await api.get_profile_channels(profile_id)
            await api.disconnect()
        except LGHorizonApiUnauthorizedError as lgau_err:
            raise InvalidAuth from lgau_err
        except LGHorizonApiConnectionError as lgac_err:
            raise CannotConnect from lgac_err
        except LGHorizonApiLockedError as lgal_err:
            raise AccountLocked from lgal_err
        except Exception as ex:
            _LOGGER.error(ex)
            raise CannotConnect from ex

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()
