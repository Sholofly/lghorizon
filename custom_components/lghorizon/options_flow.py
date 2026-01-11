"""Options flow for LGHorizon integration."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CHANNEL_SORT,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHANNEL_SORT, default="number"): SelectSelector(
            SelectSelectorConfig(
                options=["number", "alpha"],
                translation_key="channel_sort",
                mode=SelectSelectorMode.DROPDOWN,
            ),
        ),
    }
)


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for LG Horizon integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
