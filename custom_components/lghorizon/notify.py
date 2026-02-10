from __future__ import annotations
import logging

from lghorizon import (
    LGHorizonApi,
    LGHorizonDevice,
    LGHorizonRunningState,
    LGHorizonUIStateType,
)
from .const import DOMAIN, API, CONF_INTERRUPT_APP

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.notify import NotifyEntity, DOMAIN as NOTIFY_DOMAIN
from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    players = []
    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    device_dic: dict[str, LGHorizonDevice] = await api.get_devices()
    for device in device_dic.values():
        players.append(LGHorizonNotifyEntity(device, entry))
    async_add_entities(players, True)


class LGHorizonNotifyEntity(NotifyEntity):
    """LGHorizon notify entity."""

    _box: LGHorizonDevice
    _interrupt_app: bool

    def __init__(self, box: LGHorizonDevice, config_entry: ConfigEntry) -> None:
        """Initialize a Notify entity."""
        self._box = box
        self._interrupt_app = config_entry.data.get(CONF_INTERRUPT_APP, False)
        unique_id = f"{box.device_id}_notify"
        self._attr_unique_id = unique_id
        self._attr_supported_features = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, box.device_id)},
            name=box.device_friendly_name,
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to a box."""
        if self._box.device_state.state != LGHorizonRunningState.ONLINE_RUNNING:
            _LOGGER.debug(
                f"Can't send a message to box {self._box.device_friendly_name} but it's not running."
            )
            return
        if (
            self._box.device_state.ui_state_type == LGHorizonUIStateType.APPS
            and not self._interrupt_app
        ):
            _LOGGER.debug(
                f"Message to box {self._box.device_friendly_name} suppressed. It's playing an app and interrupt app setting is 'False'."
            )
            return
        await self._box.display_message(message, self._box.device_state.source_type)
        _LOGGER.debug(f"Message sent to box {self._box.device_friendly_name}.")
