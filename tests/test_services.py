"""Tests for the entity services of the LG Horizon media player."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from lghorizon import LGHorizonDevice, LGHorizonRunningState
from pytest_homeassistant.common import MockConfigEntry

DEVICE_JSON = {
    "deviceId": "device-1",
    "hashedCPEId": "hashed-1",
    "platformType": "EOS",
    "settings": {"deviceFriendlyName": "Living Room"},
}


def make_device() -> LGHorizonDevice:
    mqtt_client = MagicMock()
    mqtt_client.publish_message = AsyncMock()
    mqtt_client.client_id = "client"
    device = LGHorizonDevice(DEVICE_JSON, mqtt_client, MagicMock(), MagicMock(), {})
    device.device_state.state = LGHorizonRunningState.ONLINE_RUNNING
    device.send_key_to_box = AsyncMock()
    device.skip_ad_break = AsyncMock()
    device.rewind = AsyncMock()
    return device


def make_api(device: LGHorizonDevice) -> MagicMock:
    """Return an API that, like the real one, refuses calls once disconnected."""
    api = MagicMock()
    initialized = True

    async def get_devices() -> dict:
        if not initialized:
            raise RuntimeError("LGHorizonApi not initialized")
        return {device.device_id: device}

    async def disconnect() -> None:
        nonlocal initialized
        initialized = False

    api.initialize = AsyncMock()
    api.get_devices = AsyncMock(side_effect=get_devices)
    api.disconnect = AsyncMock(side_effect=disconnect)
    api.get_profile_channels = AsyncMock(return_value={})
    api.get_epg = AsyncMock(return_value=MagicMock(entries=[]))
    api.get_replay_channels = AsyncMock(return_value=[])
    api.has_pvr = False
    api.has_local_dvr = False
    api.has_recording = False
    return api


@pytest.fixture
def two_apis() -> tuple[LGHorizonDevice, LGHorizonDevice, list[MagicMock]]:
    """The devices and APIs of the first setup and of the setup after a reload."""
    devices = [make_device(), make_device()]
    apis = [make_api(d) for d in devices]
    with patch(
        "custom_components.lghorizon.LGHorizonApi", side_effect=apis
    ), patch("custom_components.lghorizon.PLATFORMS", ["media_player"]):
        yield devices[0], devices[1], apis


async def set_up(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    (entity_id,) = hass.states.async_entity_ids("media_player")
    return entity_id


async def test_service_reaches_the_device_of_the_current_setup_after_a_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, two_apis
) -> None:
    first_device, second_device, _ = two_apis
    entity_id = await set_up(hass, mock_config_entry)
    await hass.services.async_call(
        "lghorizon",
        "remote_key_press",
        {"entity_id": entity_id, "remote_key": "Info"},
        blocking=True,
    )
    first_device.send_key_to_box.assert_awaited_once_with("Info")

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "lghorizon",
        "remote_key_press",
        {"entity_id": entity_id, "remote_key": "Guide"},
        blocking=True,
    )

    second_device.send_key_to_box.assert_awaited_once_with("Guide")
    first_device.send_key_to_box.assert_awaited_once_with("Info")


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param("rewind", "rewind", id="rewind"),
        pytest.param("skip_ad_break", "skip_ad_break", id="skip-ad-break"),
    ],
)
async def test_other_services_work_after_a_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    two_apis,
    service: str,
    method: str,
) -> None:
    _, second_device, _ = two_apis
    entity_id = await set_up(hass, mock_config_entry)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "lghorizon", service, {"entity_id": entity_id}, blocking=True
    )

    getattr(second_device, method).assert_awaited_once()
