"""Support for interface with a ArrisDCX960 Settopbox."""

import asyncio
import datetime as dt
import logging
import random
from typing import cast


import voluptuous as vol

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    MediaPlayerDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from lghorizon import (
    LGHorizonDevice,
    LGHorizonRecording,
    LGHorizonRecordingList,
    LGHorizonRecordingSeason,
    LGHorizonRecordingShow,
    LGHorizonRecordingSingle,
    LGHorizonRecordingType,
    LGHorizonRunningState,
    LGHorizonShowRecordingList,
    LGHorizonUIStateType,
    LGHorizonApi,
    LGHorizonMediaType,
    LGHorizonSourceType,
)

from .const import (
    API,
    CONF_CHANNEL_SORT,
    CONF_EXCLUDED_CHANNELS,
    CONF_REMOTE_KEY,
    DOMAIN,
    FAST_FORWARD,
    RECORD,
    REMOTE_KEY_PRESS,
    REWIND,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    players = []
    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    device_dic: dict[str, LGHorizonDevice] = await api.get_devices()
    for device in device_dic.values():
        players.append(LGHorizonMediaPlayer(device, api, hass, entry))
    async_add_entities(players, True)

    platform = entity_platform.async_get_current_platform()
    default_service_schema = cv.make_entity_service_schema({})

    async def handle_default_services(entity, call):
        _LOGGER.debug(
            "Service %s was called for box %s", call.service, entity.unique_id
        )
        devices = await api.get_devices()
        device = devices[entity.unique_id]
        if call.service == REWIND:
            await device.rewind()
        elif call.service == FAST_FORWARD:
            await device.fast_forward()
        elif call.service == RECORD:
            await device.record()
        elif call.service == REMOTE_KEY_PRESS:
            key = call.data[CONF_REMOTE_KEY]
            await device.send_key_to_box(key)

    platform.async_register_entity_service(
        RECORD,
        default_service_schema,
        handle_default_services,
    )
    platform.async_register_entity_service(
        REWIND,
        default_service_schema,
        handle_default_services,
    )
    platform.async_register_entity_service(
        FAST_FORWARD,
        default_service_schema,
        handle_default_services,
    )
    key_schema = cv.make_entity_service_schema(
        {vol.Required(CONF_REMOTE_KEY): cv.string}
    )
    platform.async_register_entity_service(
        REMOTE_KEY_PRESS,
        key_schema,
        handle_default_services,
    )


class LGHorizonMediaPlayer(MediaPlayerEntity):
    """The home assistant media player."""

    _device: LGHorizonDevice

    def __init__(
        self,
        device: LGHorizonDevice,
        api: LGHorizonApi,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Init the media player."""
        self._device = device
        self.api = api
        self.hass = hass
        self.entry = entry
        self._channels = {}

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._device.device_id

    @property
    def available(self):
        """Return True if the device is available."""
        return self._device.is_available

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device.device_friendly_name

    @property
    def state(self):
        """Return the state of the player."""
        if self._device.device_state.state == LGHorizonRunningState.ONLINE_RUNNING:
            if (
                self._device.device_state is not None
                and self._device.device_state.paused
            ):
                return MediaPlayerState.PAUSED
            return MediaPlayerState.PLAYING
        if self._device.device_state.state == LGHorizonRunningState.ONLINE_STANDBY:
            return MediaPlayerState.OFF
        return STATE_UNAVAILABLE

    @property
    def supported_features(self):
        """Return the supported features."""

        common_features = [
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.STOP,
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.TURN_OFF,
            MediaPlayerEntityFeature.SELECT_SOURCE,
            MediaPlayerEntityFeature.PLAY_MEDIA,
            MediaPlayerEntityFeature.BROWSE_MEDIA,
        ]
        if self._device.device_state.ui_state_type != LGHorizonUIStateType.APPS:
            common_features.extend(
                [
                    MediaPlayerEntityFeature.NEXT_TRACK,
                    MediaPlayerEntityFeature.PREVIOUS_TRACK,
                    MediaPlayerEntityFeature.SEEK,
                ]
            )
        combined = MediaPlayerEntityFeature(0)
        for f in common_features:
            combined |= f
        return combined

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "ui_mode": self._device.device_state.ui_state_type,
            "play_mode": self._device.device_state.source_type,
            "channel": self._device.device_state.channel_name,
            "recording_capacity": self._device.recording_capacity,
        }

    @property
    def should_poll(self):
        """Shoud it poll."""
        return True

    @property
    def app_id(self) -> str | None:
        """Return the unique id."""
        if (
            self._device.device_state.ui_state_type
            and self._device.device_state.ui_state_type == LGHorizonUIStateType.APPS
        ):
            return self._device.device_state.id
        return None

    @property
    def app_name(self) -> str | None:
        """Return the unique id."""
        if (
            self._device.device_state.ui_state_type
            and self._device.device_state.ui_state_type == LGHorizonUIStateType.APPS
        ):
            return self._device.device_state.show_title
        return None

    @property
    def device_class(self):
        """Device class of the media player."""
        return MediaPlayerDeviceClass.TV

    @property
    def media_channel(self) -> str | None:
        """Return the unique id."""
        return (
            self._device.device_state.channel_name
        )  # self._device.device_state.channel_name

    @property
    def media_content_id(self) -> str | None:
        """Return the media type."""
        return self._device.device_state.id

    @property
    def media_content_type(self) -> str | None:
        """Return the media type."""
        if self._device.device_state.media_type == LGHorizonMediaType.UNKNOWN:
            return None
        match self._device.device_state.media_type:
            case LGHorizonMediaType.CHANNEL:
                return MediaType.CHANNEL
            case LGHorizonMediaType.EPISODE:
                return MediaType.TVSHOW
            case LGHorizonMediaType.MOVIE:
                return MediaType.MOVIE
            case LGHorizonMediaType.APP:
                return MediaType.APP

        return None

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if not self._device.device_state.duration:
            return 0
        return round(self._device.device_state.duration)

    @property
    def media_episode(self) -> str | None:
        """Return the media type."""
        if self._device.device_state.episode_number:
            return str(self._device.device_state.episode_number).zfill(2)
        return None

    @property
    def media_image_remotely_accessible(self):
        """Is image remotely accessible."""
        return True

    @property
    def media_image_url(self):
        """Return the media image URL."""
        image_url = self._device.device_state.image
        if image_url is None:
            return None

        if self._device.device_state.state == LGHorizonRunningState.ONLINE_RUNNING:
            join_param = "?"
            if join_param in image_url:
                join_param = "&"
            image_url = f"{image_url}{join_param}random={random.randrange(1000000)!s}"
        return image_url

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.device_id)
            },
            "name": self._device.device_friendly_name,
            "manufacturer": self._device.manufacturer or "unknown",
            "model": self._device.model or "unknown",
        }

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if not self._device.device_state.position:
            return None
        return self._device.device_state.position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        return dt_util.utc_from_timestamp(
            int(self._device.device_state.last_position_update or 0)
        )

    @property
    def media_season(self) -> str | None:
        """Return the media title."""
        if self._device.device_state.season_number:
            return str(self._device.device_state.season_number).zfill(2)
        return None

    @property
    def media_series_title(self):
        """Return the media title."""
        return self._device.device_state.episode_title or ""

    @property
    def media_title(self):
        """Return the media title."""
        return self._device.device_state.show_title

    @property
    def source(self):
        """Name of the current channel."""
        return self._device.device_state.channel_name

    @property
    def source_list(self):
        """Return a list with available sources."""
        # Prefer runtime options (entry.options) over initial setup data (entry.data)
        sort_mode = self.entry.options.get(
            CONF_CHANNEL_SORT, self.entry.data.get(CONF_CHANNEL_SORT, "number")
        )
        excluded_channels = self.entry.data.get(CONF_EXCLUDED_CHANNELS) or []
        # Use a set of strings so we can compare reliably to channel_number
        excluded_set = {str(ch) for ch in excluded_channels}
        channels = self._channels.values() or {}
        # Filter out excluded channels by channel number
        if excluded_set:
            channels = [
                ch for ch in channels if str(ch.channel_number) not in excluded_set
            ]

        if sort_mode == "number":
            sorted_channels = sorted(channels, key=lambda ch: int(ch.channel_number))
        else:
            sorted_channels = sorted(channels, key=lambda ch: ch.title.lower())
        return [ch.title for ch in sorted_channels]

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""

        async def state_callback(box_id):
            self.schedule_update_ha_state(True)

        await self._device.set_callback(state_callback)
        self._channels = await self.api.get_profile_channels()

    async def async_update(self):
        """Update the box."""

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._device.turn_on()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._device.turn_off()

    async def async_select_source(self, source: str) -> None:
        """Select a new source."""
        await self._device.set_channel(source)

    async def async_media_play(self):
        """Play selected box."""
        await self._device.play()

    async def async_media_pause(self):
        """Pause the given box."""
        await self._device.pause()

    async def async_media_stop(self):
        """Stop the given box."""
        await self._device.stop()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._device.next_channel()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._device.previous_channel()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._device.set_player_position(int(position * 1000))

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type == MediaType.EPISODE:
            await self._device.play_recording(media_id)
        elif media_type == MediaType.APP:
            await self._device.set_channel(media_id)
        elif media_type == MediaType.CHANNEL:
            # media_id should only be a channel number
            try:
                cv.positive_int(media_id)
            except vol.Invalid:
                _LOGGER.error("Media ID must be positive integer")
                return

            if self._device.device_state.source_type != LGHorizonSourceType.LINEAR:
                await asyncio.sleep(1)
                await self._device.send_key_to_box("TV")

            for digit in media_id:
                await self._device.send_key_to_box(f"{digit}")

        else:
            _LOGGER.error("Unsupported media type")

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Support browsing media."""
        if media_content_type in [None, "main"]:
            main = BrowseMedia(
                title="Opnames",
                media_class=MediaClass.DIRECTORY,
                media_content_type="main",
                media_content_id="main",
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MediaClass.DIRECTORY,
            )
            recordings_list: LGHorizonRecordingList = (
                await self.api.get_all_recordings()
            )
            recording: LGHorizonRecording
            for recording in recordings_list.recordings:
                match recording.type:
                    case LGHorizonRecordingType.SEASON:
                        recording.__class__ = LGHorizonRecordingSeason
                        season_recording = cast(LGHorizonRecordingSeason, recording)
                        show_media = BrowseMedia(
                            title=season_recording.title,
                            media_class=MediaClass.TV_SHOW,
                            media_content_type=MediaType.TVSHOW,
                            media_content_id=f"{season_recording.show_id}|{recording.channel_id}",
                            can_play=False,
                            can_expand=True,
                            thumbnail=season_recording.poster_url,
                            children=[],
                            children_media_class=MediaClass.DIRECTORY,
                        )
                        main.children.append(show_media)
                    case LGHorizonRecordingType.SEASON:
                        recording.__class__ = LGHorizonRecordingShow
                        show_recording = cast(LGHorizonRecordingShow, recording)
                        show_media = BrowseMedia(
                            title=show_recording.title,
                            media_class=MediaClass.TV_SHOW,
                            media_content_type=MediaType.TVSHOW,
                            media_content_id=f"{show_recording.id}|{recording.channel_id}",
                            can_play=False,
                            can_expand=True,
                            thumbnail=show_recording.poster_url,
                            children=[],
                            children_media_class=MediaClass.DIRECTORY,
                        )
                        main.children.append(show_media)
                    case LGHorizonRecordingType.SINGLE:
                        recording.__class__ = LGHorizonRecordingSingle
                        single_recording = cast(LGHorizonRecordingSingle, recording)
                        show_media = BrowseMedia(
                            title=single_recording.title,
                            media_class=MediaClass.EPISODE,
                            media_content_type=MediaType.EPISODE,
                            media_content_id=single_recording.id,
                            can_play=True,
                            can_expand=False,
                            thumbnail=single_recording.poster_url,
                        )
                        main.children.append(show_media)
            return main
        if media_content_type == MediaType.TVSHOW:
            show_id, channel_id = media_content_id.split("|", 1)
            show_recordings_list: LGHorizonShowRecordingList = (
                await self.api.get_show_recordings(show_id, channel_id)
            )
            children = []
            list_show_recording: LGHorizonRecording
            for list_show_recording in show_recordings_list.recordings:
                list_show_recording.__class__ = LGHorizonRecordingSingle
                single_show_recording = cast(
                    LGHorizonRecordingSingle, list_show_recording
                )
                show_media = BrowseMedia(
                    title=f"S{str(single_show_recording.season_number).zfill(2)}E{str(single_show_recording.episode_number).zfill(2)} {single_show_recording.episode_title or ''}",
                    media_class=MediaClass.EPISODE,
                    media_content_type=MediaType.EPISODE,
                    media_content_id=single_show_recording.episode_id,
                    can_play=True,
                    can_expand=False,
                    thumbnail=single_show_recording.poster_url,
                )
                children.append(show_media)
            return BrowseMedia(
                title=show_recordings_list.show_title,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.TVSHOW,
                media_content_id="subview",
                can_play=False,
                can_expand=False,
                children=children,
                children_media_class=MediaClass.EPISODE,
                thumbnail=show_recordings_list.show_image,
            )
        return None
