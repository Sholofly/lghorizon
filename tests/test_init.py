"""Tests for setting up and unloading the LG Horizon integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState, SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from lghorizon import (
    LGHorizonApiConnectionError,
    LGHorizonApiLockedError,
    LGHorizonApiUnauthorizedError,
)
from pytest_homeassistant.common import MockConfigEntry


@pytest.fixture(autouse=True)
def no_platforms() -> None:
    """Skip forwarding to the platforms; only the integration itself is tested."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        AsyncMock(),
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        yield


async def test_setup_and_unload_disconnects_the_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_api.disconnect.assert_not_awaited()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_api.disconnect.assert_awaited_once()


async def test_reload_disconnects_the_old_api(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_api.disconnect.assert_awaited_once()


async def test_connection_error_retries_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    mock_api.initialize.side_effect = LGHorizonApiConnectionError("down")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(LGHorizonApiUnauthorizedError("Invalid token"), id="unauthorized"),
        pytest.param(LGHorizonApiLockedError("Locked"), id="locked"),
    ],
)
async def test_authentication_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    error: Exception,
) -> None:
    mock_api.initialize.side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler("lghorizon")
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_connection_error_message_no_longer_triggers_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A connection error is never an authentication failure, whatever it says."""
    mock_api.initialize.side_effect = LGHorizonApiConnectionError(
        "Unauthorized: invalid token, bad refresh token"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler("lghorizon")
