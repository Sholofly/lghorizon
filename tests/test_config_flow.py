"""Tests for the LG Horizon reauthentication flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from lghorizon import (
    LGHorizonApiConnectionError,
    LGHorizonApiLockedError,
    LGHorizonApiUnauthorizedError,
)
from pytest_homeassistant.common import MockConfigEntry


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


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(LGHorizonApiUnauthorizedError("x"), "invalid_auth", id="invalid-auth"),
        pytest.param(LGHorizonApiLockedError("x"), "account_locked", id="locked"),
        pytest.param(LGHorizonApiConnectionError("x"), "cannot_connect", id="cannot-connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
async def test_reauth_shows_the_error_on_the_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.lghorizon.config_flow.LGHorizonApi"
    ) as flow_api:
        flow_api.return_value.initialize = AsyncMock(side_effect=error)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected}


async def test_reauth_succeeds_with_valid_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    with patch(
        "custom_components.lghorizon.config_flow.LGHorizonApi"
    ) as flow_api:
        flow_api.return_value.initialize = AsyncMock()
        flow_api.return_value.disconnect = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-secret"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    assert mock_config_entry.state is ConfigEntryState.LOADED
