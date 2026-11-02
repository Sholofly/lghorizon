"""Tests for the LG Horizon remote entity."""

from unittest.mock import AsyncMock, call, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from lghorizon import LGHorizonDevice, LGHorizonRunningState
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lghorizon.const import DOMAIN

from .test_services import make_api, make_device

REMOTE_ID = "remote.living_room_remote"


@pytest.fixture
def device() -> LGHorizonDevice:
    device = make_device()
    device.turn_on = AsyncMock()
    device.turn_off = AsyncMock()
    return device


@pytest.fixture(autouse=True)
async def remote_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, device: LGHorizonDevice
):
    mock_config_entry.add_to_hass(hass)
    with (
        patch("custom_components.lghorizon.LGHorizonApi", return_value=make_api(device)),
        patch(
            "custom_components.lghorizon.PLATFORMS", ["media_player", "remote"]
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        yield


async def test_remote_belongs_to_the_device_of_the_media_player(
    hass: HomeAssistant,
) -> None:
    entity = er.async_get(hass).async_get(REMOTE_ID)
    media_player = er.async_get(hass).async_get("media_player.living_room")
    assert entity is not None
    assert entity.unique_id == "device-1_remote"
    assert entity.device_id == media_player.device_id
    assert dr.async_get(hass).async_get(entity.device_id).name == "Living Room"


async def test_remote_is_on_while_the_box_is_running(hass: HomeAssistant) -> None:
    assert hass.states.get(REMOTE_ID).state == STATE_ON


@pytest.mark.parametrize(
    ("box_state", "expected"),
    [
        pytest.param(LGHorizonRunningState.ONLINE_STANDBY, STATE_OFF, id="standby"),
        pytest.param(LGHorizonRunningState.OFFLINE, STATE_UNAVAILABLE, id="offline"),
    ],
)
async def test_remote_follows_the_state_the_box_reports(
    hass: HomeAssistant,
    device: LGHorizonDevice,
    box_state: LGHorizonRunningState,
    expected: str,
) -> None:
    device.device_state.state = box_state
    await device._change_callback(device.device_id)
    await hass.async_block_till_done()
    assert hass.states.get(REMOTE_ID).state == expected


@pytest.mark.parametrize(
    ("command", "sent"),
    [
        pytest.param(["ChannelUp"], ["ChannelUp"], id="exact"),
        pytest.param(["CHANNELUP", "guide"], ["ChannelUp", "Guide"], id="any-case"),
        pytest.param(["Settings"], ["Settings"], id="unknown-key-is-sent-as-is"),
    ],
)
async def test_send_command(
    hass: HomeAssistant, device: LGHorizonDevice, command: list[str], sent: list[str]
) -> None:
    await hass.services.async_call(
        "remote",
        "send_command",
        {"entity_id": REMOTE_ID, "command": command},
        blocking=True,
    )
    assert device.send_key_to_box.await_args_list == [call(key) for key in sent]


async def test_send_command_repeats_the_keys_with_a_delay(
    hass: HomeAssistant, device: LGHorizonDevice
) -> None:
    with patch(
        "custom_components.lghorizon.remote.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": REMOTE_ID,
                "command": ["ArrowDown", "Enter"],
                "num_repeats": 2,
                "delay_secs": 0.1,
            },
            blocking=True,
        )
    assert device.send_key_to_box.await_args_list == [
        call("ArrowDown"),
        call("Enter"),
        call("ArrowDown"),
        call("Enter"),
    ]
    assert sleep.await_args_list == [call(0.1)] * 3


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param("turn_on", "turn_on", id="turn-on"),
        pytest.param("turn_off", "turn_off", id="turn-off"),
    ],
)
async def test_turn_on_and_off(
    hass: HomeAssistant, device: LGHorizonDevice, service: str, method: str
) -> None:
    await hass.services.async_call(
        "remote", service, {"entity_id": REMOTE_ID}, blocking=True
    )
    getattr(device, method).assert_awaited_once_with()
