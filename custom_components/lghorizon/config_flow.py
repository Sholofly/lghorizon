"""Config flow for LGHorizon integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import Mapping
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
    CONF_INTERRUPT_APP,
    CONF_SELECTED_DEVICES,
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

    VERSION = 3
    MINOR_VERSION = 1

    CONFIG_DATA: dict[str, Any] = None

    customer: LGHorizonCustomer = None
    _channels = []
    _profiles = []
    _devices = {}
    _username = ""
    _country_code = ""
    _discovered_name = ""
    _discovered_model = ""
    _existing_entry: config_entries.ConfigEntry | None = None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        self._username = entry_data[CONF_USERNAME]
        self._country_code = entry_data[CONF_COUNTRY_CODE]
        return await self.async_step_reauth_confirm()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle discovery of an LG Horizon device via SSDP."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)

        friendly_name = discovery_info.upnp.get("friendlyName", "LG Horizon")
        model_name = discovery_info.upnp.get("modelName", "")
        self._discovered_name = friendly_name
        self._discovered_model = model_name
        self.context["title_placeholders"] = {"name": friendly_name}

        existing_entries = self._async_current_entries()

        if existing_entries:
            # Integration already configured — offer to add this device
            self._existing_entry = existing_entries[0]
            selected = self._existing_entry.data.get(CONF_SELECTED_DEVICES, [])

            if not selected:
                # Empty list = all devices already included (backwards compat)
                return self.async_abort(reason="already_configured")

            # Use discovered name as flow unique ID to prevent duplicate notifications
            await self.async_set_unique_id(f"{DOMAIN}_add_{friendly_name}")
            self._abort_if_unique_id_configured()

            return await self.async_step_ssdp_add_device()

        # No existing entry — normal first-time setup flow
        await self.async_set_unique_id(f"{DOMAIN}_{friendly_name}")
        self._abort_if_unique_id_configured()

        return await self.async_step_ssdp_confirm()

    async def async_step_ssdp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm SSDP discovery and proceed to normal setup."""
        if user_input is not None:
            # Re-check: another SSDP flow may have completed in the meantime
            existing_entries = self._async_current_entries()
            if existing_entries:
                self._existing_entry = existing_entries[0]
                return await self.async_step_ssdp_add_device()
            return await self.async_step_user()

        return self.async_show_form(
            step_id="ssdp_confirm",
            description_placeholders={
                "name": self._discovered_name,
                "model": self._discovered_model,
            },
        )

    async def async_step_ssdp_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add an SSDP-discovered device to an existing integration entry."""
        if user_input is not None:
            entry = self._existing_entry
            client_session = async_get_clientsession(self.hass)

            try:
                auth = LGHorizonAuth(
                    client_session,
                    entry.data[CONF_COUNTRY_CODE],
                    entry.data.get(CONF_REFRESH_TOKEN),
                    entry.data[CONF_USERNAME],
                    entry.data.get(CONF_PASSWORD),
                )
                api = LGHorizonApi(auth, profile_id=entry.data.get(CONF_PROFILE_ID))
                await api.initialize()
                devices = await api.get_devices()
                await api.disconnect()
            except Exception:
                _LOGGER.exception("Failed to connect while adding SSDP device")
                return self.async_abort(reason="cannot_connect")

            # Find the device matching the discovered friendlyName
            matched_id = None
            for device in devices.values():
                if device.device_friendly_name == self._discovered_name:
                    matched_id = device.device_id
                    break

            if not matched_id:
                _LOGGER.info(
                    "SSDP discovered '%s' not found in existing account, "
                    "offering new integration setup",
                    self._discovered_name,
                )
                return await self.async_step_ssdp_confirm()

            # Check if already selected
            selected = list(entry.data.get(CONF_SELECTED_DEVICES, []))
            if matched_id in selected:
                return self.async_abort(reason="already_configured")

            # Add device and update the existing entry
            selected.append(matched_id)
            new_data = {**entry.data, CONF_SELECTED_DEVICES: selected}
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)

            return self.async_abort(reason="device_added")

        return self.async_show_form(
            step_id="ssdp_add_device",
            description_placeholders={
                "name": self._discovered_name,
                "model": self._discovered_model,
            },
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        if user_input:
            client_session = async_get_clientsession(self.hass)

            try:
                auth = LGHorizonAuth(
                    client_session,
                    self._country_code,
                    user_input.get(CONF_REFRESH_TOKEN, None),
                    self._username,
                    user_input.get(CONF_PASSWORD, None),
                )
                api = LGHorizonApi(auth, profile_id=None)
                await api.initialize()
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
            else:
                await self.async_set_unique_id(self.unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, None),
                        CONF_REFRESH_TOKEN: user_input.get(CONF_REFRESH_TOKEN, None),
                    },
                )

        reauth_schema: vol.Schema = vol.Schema({})

        if COUNTRY_SETTINGS[self._country_code].get("use_refreshtoken", True):
            reauth_schema = reauth_schema.extend(
                {
                    vol.Optional(CONF_REFRESH_TOKEN): cv.string,
                }
            )
        else:
            reauth_schema = reauth_schema.extend(
                {vol.Required(CONF_PASSWORD): cv.string}
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
        )

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

        # SSDP flow: auto-match discovered device by friendlyName
        if self._discovered_name:
            matched_id = None
            for device in self._devices.values():
                if device.device_friendly_name == self._discovered_name:
                    matched_id = device.device_id
                    break
            # If match found, auto-select that single device
            if matched_id:
                self.CONFIG_DATA[CONF_SELECTED_DEVICES] = [matched_id]
            else:
                # No match found — select all devices as fallback
                _LOGGER.warning(
                    "SSDP discovered '%s' but no matching device found in account. "
                    "Adding all devices.",
                    self._discovered_name,
                )
                self.CONFIG_DATA[CONF_SELECTED_DEVICES] = list(self._devices.keys())
            return await self.async_step_profile()

        # Manual flow: show device selection step
        return await self.async_step_devices()

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which set-top boxes to add."""
        if user_input is not None:
            _LOGGER.debug("Device step user_input: %s", user_input)
            selected = user_input.get(CONF_SELECTED_DEVICES, [])
            _LOGGER.debug("Selected devices: %s (from %d available)", selected, len(self._devices))
            # If nothing selected, add all devices (safety net)
            if not selected:
                selected = list(self._devices.keys())
            self.CONFIG_DATA[CONF_SELECTED_DEVICES] = selected
            _LOGGER.debug("CONFIG_DATA selected_devices: %s", self.CONFIG_DATA[CONF_SELECTED_DEVICES])
            return await self.async_step_profile()

        device_selectors = [
            SelectOptionDict(
                value=device.device_id,
                label=f"{device.device_friendly_name} ({device.model or 'unknown'})",
            )
            for device in self._devices.values()
        ]

        # Pre-select all devices by default
        default_selected = list(self._devices.keys())

        device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_DEVICES, default=default_selected
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=device_selectors,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    ),
                ),
            }
        )

        return self.async_show_form(step_id="devices", data_schema=device_schema)

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
                vol.Optional(CONF_INTERRUPT_APP, default=False): cv.boolean,
            }
        )

        if (
            user_input is None
            or CONF_PROFILE_ID not in user_input
            or not user_input[CONF_PROFILE_ID]
        ):
            return self.async_show_form(step_id="profile", data_schema=profile_schema)
        self.CONFIG_DATA.update(user_input)
        _LOGGER.debug(
            "Creating entry with selected_devices=%s",
            self.CONFIG_DATA.get(CONF_SELECTED_DEVICES),
        )
        provider_name = COUNTRY_SETTINGS.get(
            self.CONFIG_DATA[CONF_COUNTRY_CODE], {}
        ).get("name", "LG Horizon")
        entry_title = f"{provider_name} ({self.CONFIG_DATA[CONF_USERNAME]})"
        return self.async_create_entry(
            title=entry_title, data=self.CONFIG_DATA
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
            api = LGHorizonApi(auth, profile_id=self.CONFIG_DATA[CONF_PROFILE_ID])
            await api.initialize()
            profile_id = self.CONFIG_DATA[CONF_PROFILE_ID]
            self._profiles = await api.get_profiles()
            self._channels = await api.get_profile_channels(profile_id)
            self._devices = await api.get_devices()
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
