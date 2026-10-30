"""Fixtures for the LG Horizon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lghorizon.const import (
    CONF_COUNTRY_CODE,
    CONF_PROFILE_ID,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the custom integration in every test."""


@pytest.fixture(autouse=True)
def mock_ssdp(hass: HomeAssistant) -> None:
    """Treat the ssdp dependency as set up so no sockets are opened."""
    hass.config.components.add("ssdp")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for a Ziggo account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "secret",
            CONF_COUNTRY_CODE: "nl",
            CONF_PROFILE_ID: "profile-1",
        },
    )


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Patch the library API used by the integration."""
    with patch("custom_components.lghorizon.LGHorizonApi", autospec=True) as api_cls:
        api = api_cls.return_value
        api.initialize = AsyncMock()
        api.disconnect = AsyncMock()
        api.get_devices = AsyncMock(return_value={})
        yield api
