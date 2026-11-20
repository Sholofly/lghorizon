"""Options flow for LGHorizon integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)
import homeassistant.helpers.config_validation as cv

from lghorizon import LGHorizonApi, LGHorizonAuth

from .const import (
    CONF_CHANNEL_SORT,
    CONF_COUNTRY_CODE,
    CONF_EXCLUDED_CHANNELS,
    CONF_PROFILE_ID,
    CONF_REFRESH_TOKEN,
    CONF_INTERRUPT_APP,
    CONF_SELECTED_DEVICES,
)


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for LG Horizon integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        client_session = async_get_clientsession(self.hass)
        auth = LGHorizonAuth(
            client_session,
            self.config_entry.data[CONF_COUNTRY_CODE],
            self.config_entry.data[CONF_REFRESH_TOKEN],
            self.config_entry.data[CONF_USERNAME],
            self.config_entry.data[CONF_PASSWORD],
        )
        api: LGHorizonApi = LGHorizonApi(
            auth, profile_id=self.config_entry.data[CONF_PROFILE_ID]
        )
        await api.initialize()
        profile_id = self.config_entry.data[CONF_PROFILE_ID]
        channels = await api.get_profile_channels(profile_id)
        devices = await api.get_devices()
        await api.disconnect()

        device_selectors = [
            SelectOptionDict(
                value=device.device_id,
                label=f"{device.device_friendly_name} ({device.model or 'unknown'})",
            )
            for device in devices.values()
        ]
        # Drop boxes the account no longer has, they cannot be selected
        current_devices = [
            device_id
            for device_id in self.config_entry.data.get(CONF_SELECTED_DEVICES, [])
            if device_id in devices
        ] or list(devices)

        channel_selectors = [
            SelectOptionDict(value=str(channel.channel_number), label=channel.title)
            for channel in channels.values()
        ]

        OPTIONS_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_DEVICES, default=current_devices
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=device_selectors,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    ),
                ),
                vol.Required(
                    CONF_CHANNEL_SORT, default=self.config_entry.data[CONF_CHANNEL_SORT]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=["number", "alpha"],
                        translation_key="channel_sort",
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(
                    CONF_EXCLUDED_CHANNELS,
                    default=self.config_entry.data[CONF_EXCLUDED_CHANNELS],
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=channel_selectors,
                        translation_key="excluded_channels",
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    ),
                ),
                vol.Optional(
                    CONF_INTERRUPT_APP,
                    default=self.config_entry.data[CONF_INTERRUPT_APP],
                ): cv.boolean,
            }
        )

        if user_input is not None:
            # Kept in data, where setup and SSDP discovery read the selection
            selected = user_input.pop(CONF_SELECTED_DEVICES)
            if (
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_SELECTED_DEVICES: selected},
                )
                and user_input == self.config_entry.options
            ):
                # The automatic reload only follows changed options
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
