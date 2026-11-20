"""Tests for the LG Horizon options flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lghorizon.const import (
    CONF_CHANNEL_SORT,
    CONF_COUNTRY_CODE,
    CONF_EXCLUDED_CHANNELS,
    CONF_INTERRUPT_APP,
    CONF_PROFILE_ID,
    CONF_REFRESH_TOKEN,
    CONF_SELECTED_DEVICES,
    DOMAIN,
)

OPTIONS = {
    CONF_CHANNEL_SORT: "number",
    CONF_EXCLUDED_CHANNELS: [],
    CONF_INTERRUPT_APP: False,
}


@pytest.fixture(autouse=True)
def no_platforms() -> None:
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        AsyncMock(),
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        yield


@pytest.fixture
def entry(hass: HomeAssistant, mock_api: MagicMock) -> MockConfigEntry:
    """Return a loaded entry whose selected box is not in the account any more."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_COUNTRY_CODE: "be-nl",
            CONF_REFRESH_TOKEN: "token",
            CONF_PROFILE_ID: "profile-1",
            CONF_SELECTED_DEVICES: ["old-box"],
            **OPTIONS,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def flow_api() -> MagicMock:
    box = MagicMock(device_id="new-box", device_friendly_name="Living Room")
    box.model = "DCX960"
    with (
        patch("custom_components.lghorizon.options_flow.LGHorizonAuth"),
        patch("custom_components.lghorizon.options_flow.LGHorizonApi") as api_cls,
    ):
        api = api_cls.return_value
        api.initialize = AsyncMock()
        api.disconnect = AsyncMock()
        api.get_profile_channels = AsyncMock(return_value={})
        api.get_devices = AsyncMock(return_value={"new-box": box})
        yield api


def _selected_default(result) -> list[str]:
    key = next(k for k in result["data_schema"].schema if k == CONF_SELECTED_DEVICES)
    return key.default()


@pytest.mark.parametrize(
    "options",
    [pytest.param({}, id="options-changed"), pytest.param(OPTIONS, id="only-devices")],
)
async def test_options_change_the_device_selection_and_reload(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_api: MagicMock,
    flow_api: MagicMock,
    options: dict,
) -> None:
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert mock_api.initialize.await_count == 1

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    # The unknown box is not offered as default, it could not be submitted
    assert _selected_default(result) == ["new-box"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SELECTED_DEVICES: ["new-box"], **OPTIONS}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_SELECTED_DEVICES] == ["new-box"]
    assert CONF_SELECTED_DEVICES not in entry.options
    assert mock_api.initialize.await_count == 2
