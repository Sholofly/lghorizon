"""Remote control of a LG Horizon settopbox."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from lghorizon import LGHorizonApi, LGHorizonDevice, LGHorizonRunningState

from .const import API, CONF_SELECTED_DEVICES, DOMAIN, signal_device_state
from .keys import resolve_remote_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a remote for every selected settopbox."""
    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    devices = await api.get_devices()
    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])
    async_add_entities(
        LGHorizonRemote(device)
        for device in devices.values()
        if not selected_devices or device.device_id in selected_devices
    )


class LGHorizonRemote(RemoteEntity):
    """Remote that sends key presses to a settopbox."""

    _attr_has_entity_name = True
    _attr_name = "Remote"
    _attr_should_poll = False

    def __init__(self, device: LGHorizonDevice) -> None:
        """Init the remote."""
        self._device = device
        self._attr_unique_id = f"{device.device_id}_remote"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_friendly_name,
            manufacturer=device.manufacturer or "unknown",
            model=device.model or "unknown",
        )

    @property
    def available(self) -> bool:
        """Return True if the box is online."""
        return self._device.is_available

    @property
    def is_on(self) -> bool:
        """Return True if the box is running."""
        return self._device.device_state.state == LGHorizonRunningState.ONLINE_RUNNING

    async def async_added_to_hass(self) -> None:
        """Follow the state updates the media player receives from the box."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_device_state(self._device.device_id),
                self.async_write_ha_state,
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the box from standby."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the box in standby."""
        await self._device.turn_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more keys to the box."""
        keys = [resolve_remote_key(key) for key in command]
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for repeat in range(kwargs.get(ATTR_NUM_REPEATS, 1)):
            for index, key in enumerate(keys):
                if repeat or index:
                    await asyncio.sleep(delay)
                await self._device.send_key_to_box(key)
