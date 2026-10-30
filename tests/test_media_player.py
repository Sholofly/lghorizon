"""Tests for the best-effort data fetches of the LG Horizon media player."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from lghorizon import (
    LGHorizonApiConnectionError,
    LGHorizonApiUnauthorizedError,
)
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lghorizon.const import DOMAIN
from custom_components.lghorizon.media_player import LGHorizonMediaPlayer

API_ERRORS = [
    pytest.param(LGHorizonApiConnectionError("down"), id="connection-error"),
    pytest.param(LGHorizonApiUnauthorizedError("revoked"), id="unauthorized"),
    pytest.param(KeyError("id"), id="malformed-payload-key"),
    pytest.param(TypeError("bad"), id="malformed-payload-type"),
    pytest.param(ValueError("bad"), id="malformed-payload-value"),
]


@pytest.fixture
def player(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> tuple[LGHorizonMediaPlayer, dict, MagicMock]:
    api = MagicMock()
    store: dict = {}
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = store
    entity = LGHorizonMediaPlayer(MagicMock(), api, hass, mock_config_entry)
    return entity, store, api


@pytest.mark.parametrize("error", API_ERRORS)
async def test_replay_channel_api_errors_are_logged(
    player, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    entity, store, api = player
    api.get_replay_channels = AsyncMock(side_effect=error)

    with caplog.at_level(logging.WARNING):
        await entity._refresh_replay_channels()

    assert store["replay_channel_ids"] == set()
    assert "Failed to fetch replay channels" in caplog.text


async def test_replay_channel_bugs_are_not_hidden(player) -> None:
    entity, _, api = player
    api.get_replay_channels = AsyncMock(side_effect=AttributeError("bug"))

    with pytest.raises(AttributeError):
        await entity._refresh_replay_channels()


@pytest.mark.parametrize("error", API_ERRORS)
async def test_epg_api_errors_are_logged_and_retried_later(
    player, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    entity, store, api = player
    api.get_epg = AsyncMock(side_effect=error)

    with caplog.at_level(logging.WARNING):
        await entity._refresh_epg()

    assert "epg_fetched_at" not in store
    assert "Failed to refresh EPG data" in caplog.text


async def test_epg_bugs_are_not_hidden(player) -> None:
    entity, _, api = player
    api.get_epg = AsyncMock(side_effect=AttributeError("bug"))

    with pytest.raises(AttributeError):
        await entity._refresh_epg()


@pytest.mark.parametrize("error", API_ERRORS)
async def test_event_detail_api_errors_return_none(
    player, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    entity, _, api = player
    api.get_event_detail = AsyncMock(side_effect=error)

    with caplog.at_level(logging.WARNING):
        detail = await entity._get_event_detail("event-1")

    assert detail is None
    assert "Failed to fetch event detail for event-1" in caplog.text


async def test_event_detail_bugs_are_not_hidden(player) -> None:
    entity, _, api = player
    api.get_event_detail = AsyncMock(side_effect=AttributeError("bug"))

    with pytest.raises(AttributeError):
        await entity._get_event_detail("event-1")


async def test_event_detail_is_cached(player) -> None:
    entity, _, api = player
    api.get_event_detail = AsyncMock(return_value="detail")

    assert await entity._get_event_detail("event-1") == "detail"
    assert await entity._get_event_detail("event-1") == "detail"

    api.get_event_detail.assert_awaited_once()
