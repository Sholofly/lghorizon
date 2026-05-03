"""Support for interface with a ArrisDCX960 Settopbox."""

import asyncio
import datetime as dt
import logging
import random
import time
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from lghorizon import (
    LGHorizonDevice,
    LGHorizonEpg,
    LGHorizonEpgEvent,
    LGHorizonEventDetail,
    LGHorizonRecording,
    LGHorizonRecordingList,
    LGHorizonRecordingSeason,
    LGHorizonRecordingShow,
    LGHorizonRecordingSingle,
    LGHorizonRecordingState,
    LGHorizonRecordingType,
    LGHorizonReplayChannel,
    LGHorizonRunningState,
    LGHorizonShowRecordingList,
    LGHorizonUIStateType,
    LGHorizonApi,
    LGHorizonMediaType,
    LGHorizonSourceType,
    MEDIA_KEY_TV,
)

from .const import (
    API,
    CONF_CHANNEL_SORT,
    CONF_EXCLUDED_CHANNELS,
    CONF_REMOTE_KEY,
    CONF_SELECTED_DEVICES,
    DOMAIN,
    FAST_FORWARD,
    RECORD,
    REMOTE_KEY_PRESS,
    REWIND,
    SKIP_AD_BREAK,
)

_LOGGER = logging.getLogger(__name__)

# Refresh the EPG cache every 2 hours (segments are 6h each)
EPG_REFRESH_INTERVAL = 7200


def _find_now_next(
    events: list[LGHorizonEpgEvent], now_ts: float
) -> tuple[LGHorizonEpgEvent | None, LGHorizonEpgEvent | None]:
    """Find the currently airing and next program from a list of EPG events.

    Args:
        events: Sorted list of EPG events for a channel.
        now_ts: Current Unix timestamp in seconds.

    Returns:
        Tuple of (current_event, next_event). Either may be None.
    """
    for i, event in enumerate(events):
        if event.start_time is not None and event.end_time is not None:
            if event.start_time <= now_ts < event.end_time:
                next_event = events[i + 1] if i + 1 < len(events) else None
                return event, next_event
    return None, None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    players = []
    api: LGHorizonApi = hass.data[DOMAIN][entry.entry_id][API]
    device_dic: dict[str, LGHorizonDevice] = await api.get_devices()

    # Filter devices based on selection (empty/missing = all devices for backwards compat)
    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])
    _LOGGER.debug(
        "Device filter: selected_devices=%s, available=%s",
        selected_devices,
        list(device_dic.keys()),
    )
    for device in device_dic.values():
        if not selected_devices or device.device_id in selected_devices:
            players.append(LGHorizonMediaPlayer(device, api, hass, entry))
    _LOGGER.debug("Adding %d media players (of %d devices)", len(players), len(device_dic))
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
        elif call.service == SKIP_AD_BREAK:
            await device.skip_ad_break()

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
    platform.async_register_entity_service(
        SKIP_AD_BREAK,
        default_service_schema,
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
        self._current_event_detail: LGHorizonEventDetail | None = None
        self._ad_break_checker: CALLBACK_TYPE | None = None
        self._ad_break_active: bool = False

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
        attrs = {
            "ui_mode": self._device.device_state.ui_state_type,
            "play_mode": self._device.device_state.source_type,
            "channel": self._device.device_state.channel_name,
            "local_recording_capacity": self._device.local_recording_capacity,
            "has_pvr": self.api.has_pvr,
            "has_local_dvr": self.api.has_local_dvr,
            "has_recording": self.api.has_recording,
        }

        # Ad break info (real-time via 1-second checker)
        ad_breaks = self._device.device_state.ad_breaks
        if ad_breaks:
            attrs["ad_break_active"] = self._ad_break_active
            if self._ad_break_active:
                current_pos_s = self._get_realtime_position()
                if current_pos_s is not None:
                    pos_ms = int(current_pos_s * 1000)
                    for ab in ad_breaks:
                        if ab.start_ms <= pos_ms < ab.end_ms:
                            attrs["ad_break_end_position"] = ab.end_s
                            break
            attrs["ad_break_count"] = len(ad_breaks)
            attrs["ad_breaks"] = [
                {"start": ab.start_s, "end": ab.end_s}
                for ab in ad_breaks
            ]
        else:
            attrs["ad_break_active"] = False

        # Replay support for current channel
        channel_id = self._device.device_state.channel_id
        replay_ids = self.hass.data[DOMAIN][self.entry.entry_id].get("replay_channel_ids", set())
        if channel_id:
            attrs["replay_supported"] = channel_id in replay_ids

        # EPG now/next
        if self._epg and channel_id:
            now_ts = time.time()
            events = self._epg.get_channel_events(channel_id)
            try:
                current, next_prog = _find_now_next(events, now_ts)
            except (TypeError, ValueError):
                _LOGGER.exception("EPG _find_now_next failed")
                current, next_prog = None, None
            if current:
                attrs["epg_now_title"] = current.title
                attrs["epg_now_start"] = (
                    dt_util.utc_from_timestamp(current.start_time).isoformat()
                    if current.start_time
                    else None
                )
                attrs["epg_now_end"] = (
                    dt_util.utc_from_timestamp(current.end_time).isoformat()
                    if current.end_time
                    else None
                )
                # Progress as percentage
                if current.start_time and current.end_time:
                    duration = current.end_time - current.start_time
                    if duration > 0:
                        elapsed = now_ts - current.start_time
                        attrs["epg_now_progress"] = round(
                            max(0, min(elapsed / duration * 100, 100)), 1
                        )
                # Event detail enrichment
                detail = self._current_event_detail
                if detail and detail.event_id == current.event_id:
                    if detail.description:
                        attrs["epg_now_description"] = detail.description
                    if detail.genres:
                        attrs["epg_now_genres"] = ", ".join(detail.genres)
                    if detail.episode_name:
                        attrs["epg_now_episode_name"] = detail.episode_name
                    if detail.actors:
                        attrs["epg_now_actors"] = ", ".join(detail.actors)
                    if detail.directors:
                        attrs["epg_now_directors"] = ", ".join(detail.directors)
            if not current and events:
                _LOGGER.debug(
                    "EPG no match for channel_id=%s at now_ts=%.0f",
                    channel_id,
                    now_ts,
                )
            if next_prog:
                attrs["epg_next_title"] = next_prog.title
                attrs["epg_next_start"] = (
                    dt_util.utc_from_timestamp(next_prog.start_time).isoformat()
                    if next_prog.start_time
                    else None
                )

        return attrs

    @property
    def _epg(self) -> LGHorizonEpg | None:
        """Return the shared EPG cache."""
        return self.hass.data[DOMAIN][self.entry.entry_id].get("epg")

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

        # Deduplicate by name: keep channel with the lowest number
        seen: dict[str, object] = {}
        for ch in channels:
            num = int(ch.channel_number)
            if ch.title not in seen or num < int(seen[ch.title].channel_number):
                seen[ch.title] = ch
        channels = list(seen.values())

        if sort_mode == "number":
            sorted_channels = sorted(channels, key=lambda ch: int(ch.channel_number))
        else:
            sorted_channels = sorted(channels, key=lambda ch: ch.title.lower())
        return [ch.title for ch in sorted_channels]

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""

        async def state_callback(box_id):
            self._update_ad_break_checker()
            self._ad_break_active = self._is_in_ad_break()
            self.schedule_update_ha_state(True)

        await self._device.set_callback(state_callback)
        self._channels = await self.api.get_profile_channels()
        await self._refresh_epg()
        await self._refresh_replay_channels()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self._stop_ad_break_checker()

    def _get_realtime_position(self) -> float | None:
        """Calculate real-time playback position in seconds."""
        ds = self._device.device_state
        if ds.position is None or ds.last_position_update is None:
            return None
        elapsed = time.time() - ds.last_position_update
        speed = ds.speed if ds.speed is not None else 1
        if speed == 0:
            return ds.position
        return ds.position + (elapsed * speed)

    def _is_in_ad_break(self) -> bool:
        """Check if current real-time position is within an ad break."""
        ds = self._device.device_state
        if not ds.ad_breaks:
            return False
        current_pos_s = self._get_realtime_position()
        if current_pos_s is None:
            return False
        pos_ms = int(current_pos_s * 1000)
        return any(ab.start_ms <= pos_ms < ab.end_ms for ab in ds.ad_breaks)

    def _update_ad_break_checker(self) -> None:
        """Start or stop the 1-second ad break checker based on playback state."""
        ds = self._device.device_state
        needs_checker = (
            ds.ad_breaks
            and ds.source_type == LGHorizonSourceType.NDVR
            and ds.speed is not None
            and ds.speed > 0
        )
        if needs_checker and self._ad_break_checker is None:
            self._ad_break_checker = async_track_time_interval(
                self.hass, self._check_ad_break, dt.timedelta(seconds=1)
            )
        elif not needs_checker and self._ad_break_checker is not None:
            self._stop_ad_break_checker()

    def _stop_ad_break_checker(self) -> None:
        """Stop the ad break checker interval."""
        if self._ad_break_checker is not None:
            self._ad_break_checker()
            self._ad_break_checker = None

    async def _check_ad_break(self, _now) -> None:
        """Called every second to detect ad break transitions."""
        currently_in = self._is_in_ad_break()
        if currently_in != self._ad_break_active:
            self._ad_break_active = currently_in
            self.async_write_ha_state()

    async def _refresh_replay_channels(self):
        """Fetch replay channel IDs once."""
        store = self.hass.data[DOMAIN][self.entry.entry_id]
        if "replay_channel_ids" in store:
            return
        try:
            channels = await self.api.get_replay_channels()
            store["replay_channel_ids"] = {ch.id for ch in channels}
            _LOGGER.debug(
                "Replay channels loaded: %d channels support replay",
                len(store["replay_channel_ids"]),
            )
        except Exception:
            _LOGGER.warning("Failed to fetch replay channels", exc_info=True)
            store["replay_channel_ids"] = set()

    async def _refresh_epg(self):
        """Fetch or refresh the shared EPG cache if stale."""
        store = self.hass.data[DOMAIN][self.entry.entry_id]
        now = time.time()
        if now - store.get("epg_fetched_at", 0) < EPG_REFRESH_INTERVAL:
            return
        try:
            store["epg"] = await self.api.get_epg()
            store["epg_fetched_at"] = now
            _LOGGER.debug(
                "EPG refreshed: %d channels loaded",
                len(store["epg"].entries) if store["epg"] else 0,
            )
        except Exception:
            _LOGGER.warning("Failed to refresh EPG data", exc_info=True)

    async def async_update(self):
        """Update the box."""
        await self._refresh_epg()
        # Pre-fetch event detail for current program
        channel_id = self._device.device_state.channel_id
        if self._epg and channel_id:
            events = self._epg.get_channel_events(channel_id)
            try:
                current, _ = _find_now_next(events, time.time())
            except (TypeError, ValueError):
                current = None
            if current and current.event_id:
                self._current_event_detail = await self._get_event_detail(current.event_id)
            else:
                self._current_event_detail = None
        else:
            self._current_event_detail = None

    async def _get_event_detail(self, event_id: str) -> LGHorizonEventDetail | None:
        """Fetch event detail with caching."""
        store = self.hass.data[DOMAIN][self.entry.entry_id]
        cache: dict = store.setdefault("event_detail_cache", {})
        if event_id in cache:
            return cache[event_id]
        try:
            detail = await self.api.get_event_detail(event_id)
            if len(cache) > 10:
                cache.clear()
            cache[event_id] = detail
            return detail
        except Exception:
            _LOGGER.warning("Failed to fetch event detail for %s", event_id, exc_info=True)
            return None

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._device.turn_on()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._device.turn_off()

    async def async_select_source(self, source: str) -> None:
        """Select a new source."""
        # Find channel by name; if duplicates exist, pick the lowest number
        match = None
        for ch in self._channels.values():
            if ch.title == source:
                if match is None or int(ch.channel_number) < int(match.channel_number):
                    match = ch
        if match:
            await self._device.set_channel_by_number(match.channel_number)
            return
        # Fallback to set_channel by name
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
                await self._device.send_key_to_box(MEDIA_KEY_TV)

            for digit in media_id:
                await self._device.send_key_to_box(digit)

        else:
            _LOGGER.error("Unsupported media type")

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Support browsing media."""
        if media_content_type in [None, "main", "recordings"]:
            main = BrowseMedia(
                title="Opnames",
                media_class=MediaClass.DIRECTORY,
                media_content_type="recordings",
                media_content_id="recordings",
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
                ongoing = recording.recording_state == LGHorizonRecordingState.ONGOING
                match recording.type:
                    case LGHorizonRecordingType.SEASON:
                        recording.__class__ = LGHorizonRecordingSeason
                        season_recording = cast(LGHorizonRecordingSeason, recording)
                        show_media = BrowseMedia(
                            title=f"🔴 {season_recording.title}" if ongoing else season_recording.title,
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
                    case LGHorizonRecordingType.SHOW:
                        recording.__class__ = LGHorizonRecordingShow
                        show_recording = cast(LGHorizonRecordingShow, recording)
                        show_media = BrowseMedia(
                            title=f"🔴 {show_recording.title}" if ongoing else show_recording.title,
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
                            title=f"🔴 {single_recording.title}" if ongoing else single_recording.title,
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
                ep_ongoing = list_show_recording.recording_state == LGHorizonRecordingState.ONGOING
                ep_title = f"S{str(single_show_recording.season_number).zfill(2)}E{str(single_show_recording.episode_number).zfill(2)} {single_show_recording.episode_title or ''}"
                show_media = BrowseMedia(
                    title=f"🔴 {ep_title}" if ep_ongoing else ep_title,
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
