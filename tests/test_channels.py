"""Tests for selecting and browsing channels."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.core import HomeAssistant
from lghorizon import LGHorizonChannel, LGHorizonSourceType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lghorizon.const import (
    CONF_CHANNEL_SORT,
    CONF_EXCLUDED_CHANNELS,
    DOMAIN,
)
from custom_components.lghorizon.media_player import LGHorizonMediaPlayer


def make_channel(number: int, name: str) -> LGHorizonChannel:
    return LGHorizonChannel(
        {
            "id": f"NL_{number:06d}",
            "name": name,
            "logicalChannelNumber": str(number),
            "logo": {"focused": f"https://logos.example.com/{number}.png"},
        }
    )


LINEUP = [
    make_channel(401, "Ziggo Sport 1"),
    make_channel(14, "Ziggo Sport 1"),
    make_channel(2, "NPO 2"),
    make_channel(1, "NPO 1"),
    make_channel(18, "ESPN"),
]


@pytest.fixture
def player(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {}
    device = MagicMock()
    device.send_key_to_box = AsyncMock()
    device.device_state.source_type = LGHorizonSourceType.LINEAR
    api = MagicMock()
    entity = LGHorizonMediaPlayer(device, api, hass, mock_config_entry)
    entity._channels = {channel.id: channel for channel in LINEUP}
    return entity


async def test_source_list_keeps_the_lowest_number_per_name(player) -> None:
    assert player.source_list == ["NPO 1", "NPO 2", "Ziggo Sport 1", "ESPN"]


async def test_source_list_can_be_sorted_by_name(
    hass: HomeAssistant, player, mock_config_entry: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CHANNEL_SORT: "name"}
    )

    assert player.source_list == ["ESPN", "NPO 1", "NPO 2", "Ziggo Sport 1"]


async def test_root_has_a_folder_for_recordings_and_one_for_channels(player) -> None:
    root = await player.async_browse_media()

    assert root.title == "LG Horizon"
    assert [(c.title, c.media_content_type) for c in root.children] == [
        ("Opnames", "recordings"),
        ("Kanalen", "channels"),
    ]
    assert all(c.can_expand and not c.can_play for c in root.children)


async def test_channel_folder_lists_every_channel_including_duplicate_names(
    player,
) -> None:
    folder = await player.async_browse_media("channels", "channels")

    assert [c.title for c in folder.children] == [
        "1 · NPO 1",
        "2 · NPO 2",
        "14 · Ziggo Sport 1",
        "18 · ESPN",
        "401 · Ziggo Sport 1",
    ]
    second_sport = folder.children[-1]
    assert second_sport.media_content_id == "NL_000401"
    assert second_sport.media_content_type == MediaType.CHANNEL
    assert second_sport.media_class == MediaClass.APP
    assert second_sport.can_play and not second_sport.can_expand
    assert second_sport.thumbnail == "https://logos.example.com/401.png"


async def test_channel_folder_follows_the_sort_and_exclude_options(
    hass: HomeAssistant, player, mock_config_entry: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_EXCLUDED_CHANNELS: ["14", 18]},
        options={CONF_CHANNEL_SORT: "name"},
    )

    folder = await player.async_browse_media("channels", "channels")

    assert [c.title for c in folder.children] == [
        "1 · NPO 1",
        "2 · NPO 2",
        "401 · Ziggo Sport 1",
    ]


async def test_recordings_folder_is_unchanged(player) -> None:
    player.api.get_all_recordings = AsyncMock(return_value=MagicMock(recordings=[]))

    folder = await player.async_browse_media("recordings", "recordings")

    assert folder.title == "Opnames"
    assert folder.media_content_type == "recordings"
    assert folder.children == []


@pytest.mark.parametrize(
    ("media_id", "expected_keys"),
    [
        pytest.param("14", ["1", "4"], id="channel-number"),
        pytest.param("NL_000401", ["4", "0", "1"], id="channel-id-of-a-duplicate-name"),
        pytest.param("NL_000001", ["1"], id="channel-id"),
    ],
)
async def test_play_channel_presses_the_digits_of_the_channel_number(
    player, media_id: str, expected_keys: list[str]
) -> None:
    await player.async_play_media(MediaType.CHANNEL, media_id)

    assert [c.args[0] for c in player._device.send_key_to_box.await_args_list] == (
        expected_keys
    )


@pytest.mark.parametrize("media_id", ["NL_999999", "not-a-channel", "-3"])
async def test_play_unknown_channel_does_nothing_and_logs(
    player, caplog: pytest.LogCaptureFixture, media_id: str
) -> None:
    with caplog.at_level(logging.ERROR):
        await player.async_play_media(MediaType.CHANNEL, media_id)

    player._device.send_key_to_box.assert_not_awaited()
    assert "not a channel number or the id of a known channel" in caplog.text


async def test_play_channel_switches_to_tv_first_when_not_watching_live_tv(
    player,
) -> None:
    player._device.device_state.source_type = LGHorizonSourceType.NDVR

    with patch("custom_components.lghorizon.media_player.asyncio.sleep", AsyncMock()):
        await player.async_play_media(MediaType.CHANNEL, "NL_000002")

    keys = [c.args[0] for c in player._device.send_key_to_box.await_args_list]
    assert keys == ["TV", "2"]
