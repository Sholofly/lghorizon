"""Support for interface with a ArrisDCX960 Settopbox."""
import logging
import random
import voluptuous as vol
import time
import homeassistant.helpers.config_validation as cv

from homeassistant.components.media_player import MediaPlayerEntity, BrowseMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from .const import (
    API,
    RECORD,
    REWIND,

    FAST_FORWARD,
    REMOTE_KEY_PRESS,
    CONF_OMIT_CHANNEL_QUALITY,
    CONF_REMOTE_KEY,
    DOMAIN,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_STOP,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_BROWSE_MEDIA,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
)

from homeassistant.const import (
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)

from arris_dcx960 import (
    ArrisDCX960,
    ArrisDCX960Box,
    ONLINE_RUNNING,
    ONLINE_STANDBY,
    ArrisDCX960RecordingShow,
    ArrisDCX960RecordingSingle,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    players = []
    api = hass.data[DOMAIN][entry.entry_id][API]
    omit_channel_quality = hass.data[DOMAIN][entry.entry_id][CONF_OMIT_CHANNEL_QUALITY]
    for box in api.settop_boxes.values():
        players.append(ArrisDCX960MediaPlayer(box, api, omit_channel_quality))
    async_add_entities(players, True)

    SCHEMA = cv.make_entity_service_schema({})

    def service_handle_custom(call):
        """Handle the custom services."""
        entity_ids = call.data.get("entity_id")
        entity_id = entity_ids[0]
        _LOGGER.debug("Custom Service for " + entity_id + " - " + call.service)

        for player in players:
            if player.entity_id == entity_id:
                if call.service == RECORD:
                    player.api.record(player.box_id)
                elif call.service == REWIND:
                    player.api.rewind(player.box_id)
                elif call.service == FAST_FORWARD:
                    player.api.fast_forward(player.box_id)

    hass.services.async_register(
        DOMAIN,
        RECORD,
        service_handle_custom,
        schema=SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        REWIND,
        service_handle_custom,
        schema=SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        FAST_FORWARD,
        service_handle_custom,
        schema=SCHEMA,
    )

    key_schema = cv.make_entity_service_schema(
        {vol.Required(CONF_REMOTE_KEY): cv.string}
    )

    def service_handle_press_remote_key(service_call):
        """Handle button press service"""
        entity_ids = service_call.data.get("entity_id")
        entity_id = entity_ids[0]
        remote_key = service_call.data[CONF_REMOTE_KEY]
        for player in players:
            if player.entity_id == entity_id:
                player.api._send_key_to_box(player.unique_id, f"{remote_key}")

    hass.services.async_register(
        DOMAIN,
        REMOTE_KEY_PRESS,
        service_handle_press_remote_key,
        schema=key_schema,
    )


class ArrisDCX960MediaPlayer(MediaPlayerEntity):
    """The home assistant media player."""

    @property
    def unique_id(self):
        """Return the unique id."""
        return self.box_id

    @property
    def media_image_remotely_accessible(self):
        return True

    @property
    def device_class(self):
        return "tv"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.box_id)
            },
            "name": self.box_name,
            "manufacturer": "Arris",
            "model": "DCX960",
        }

    def __init__(self, box: ArrisDCX960Box, api: ArrisDCX960, omit_channel_quality: bool):
        """Init the media player."""
        self._box = box
        self.api = api
        self.box_id = box.box_id
        self.box_name = box.name
        self._create_channel_map(omit_channel_quality)
        self._omit_channel_quality = omit_channel_quality

    def _create_channel_map(self, omit_channel_quality: bool):
        self._channels = {}
        for channel in self.api.channels.values():
            if omit_channel_quality:
                title = self._strip_quality(channel.title)
                self._channels[title] = channel.title
            else:
                self._channels[channel.title] = channel.title

    def _strip_quality(self, text: str):
        """Strip quality from text."""
        if text is None:
            return text
        return text.replace(" HD", "")

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""

        def callback(box_id):
            self.schedule_update_ha_state(True)

        self._box.set_callback(callback)

    async def async_update(self):
        """Update the box."""
        pass

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.box_name

    @property
    def state(self):
        """Return the state of the player."""
        if self._box.state == ONLINE_RUNNING:
            if self._box.info is not None and self._box.info.paused:
                return STATE_PAUSED
            return STATE_PLAYING
        if self._box.state == ONLINE_STANDBY:
            return STATE_OFF
        return STATE_UNAVAILABLE

    @property
    def media_content_type(self):
        """Return the media type."""
        return MEDIA_TYPE_EPISODE

    @property
    def supported_features(self):
        """Return the supported features."""
        if self._box.info.source_type == "app":
            return (
                SUPPORT_PLAY
                | SUPPORT_PAUSE
                | SUPPORT_STOP
                | SUPPORT_TURN_ON
                | SUPPORT_TURN_OFF
                | SUPPORT_SELECT_SOURCE
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_BROWSE_MEDIA
            )
        return (
            SUPPORT_PLAY
            | SUPPORT_PAUSE
            | SUPPORT_STOP
            | SUPPORT_TURN_ON
            | SUPPORT_TURN_OFF
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_NEXT_TRACK
            | SUPPORT_PREVIOUS_TRACK
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_BROWSE_MEDIA
        )

    @property
    def available(self):
        """Return True if the device is available."""
        available = self.api.is_available(self.box_id)
        return available

    async def async_turn_on(self):
        """Turn the media player on."""
        self.api.turn_on(self.box_id)

    async def async_turn_off(self):
        """Turn the media player off."""
        self.api.turn_off(self.box_id)

    @property
    def media_image_url(self):
        """Return the media image URL."""
        if self._box.info.image is not None:
            image_url = self._box.info.image
            if self._box.info.source_type == "linear":
                join_param = "?"
                if join_param in self._box.info.image:
                    join_param = "&"
                image_url = f"{image_url}{join_param}{str(random.randrange(1000000))}"
            return image_url
        return None

    @property
    def media_title(self):
        """Return the media title."""
        return self._box.info.title

    @property
    def source(self):
        """Name of the current channel."""
        if self._omit_channel_quality:
            return self._strip_quality(self._box.info.channel_title)
        return self._box.info.channel_title

    @property
    def source_list(self):
        """Return a list with available sources."""
        return [channel for channel in self._channels.keys()]

    async def async_select_source(self, source):
        """Select a new source."""
        self.api.select_source(self._channels[source], self.box_id)

    async def async_media_play(self):
        """Play selected box."""
        self.api.play(self.box_id)

    async def async_media_pause(self):
        """Pause the given box."""
        self.api.pause(self.box_id)

    async def async_media_stop(self):
        """Stop the given box."""
        self.api.stop(self.box_id)

    async def async_media_next_track(self):
        """Send next track command."""
        self.api.next_channel(self.box_id)

    async def async_media_previous_track(self):
        """Send previous track command."""
        self.api.previous_channel(self.box_id)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type == "recording_episode":
            self.api.play_recording(self.box_id, media_id)
        elif media_type == MEDIA_TYPE_APP:
            self.api.select_source(media_id, self.box_id)
        elif media_type == MEDIA_TYPE_CHANNEL:
            # media_id should only be a channel number
            try:
                cv.positive_int(media_id)
            except vol.Invalid:
                _LOGGER.error("Media ID must be positive integer")
                return
            if self._box.info.source_type == "app":
                self.api._send_key_to_box(self.box_id, "TV")
                time.sleep(1)

            for digit in media_id:
                self.api._send_key_to_box(self.box_id, f"{digit}")
        else:
            _LOGGER.error("Unsupported media type")

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "play_mode": self._box.info.source_type,
            "channel": self._box.info.channel_title,
            "title": self._box.info.title,
            "image": self._box.info.image,
        }

    @property
    def should_poll(self):
        return True

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        if media_content_type in [None, "main"]:
            self._recordings = await self.hass.async_add_executor_job(
                self.api.get_recordings
            )

            main = BrowseMedia(
                title="Recordings",
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type="main",
                media_content_id="main",
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MEDIA_CLASS_DIRECTORY,
            )
            singleRecordingsCount = 0
            for recording in self._recordings:
                if recording["type"] == "show":
                    show = self._build_show_item(recording["show"])
                    main.children.append(show)
                elif recording["type"] == "recording":
                    singleRecordingsCount += 1
                else:
                    _LOGGER.error("Unknown recording type")

            if singleRecordingsCount > 0:
                singlecontainer = BrowseMedia(
                    title="Losse opnames",
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_type="singles",
                    media_content_id="singles",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MEDIA_CLASS_EPISODE,
                )
                main.children.append(singlecontainer)
            return main
        elif media_content_type == "show":
            show_collection = await self._build_show_collection(media_content_id)
            return show_collection
        elif media_content_type == "singles":
            single_collection = self._build_singles_collection()
            return single_collection
        else:
            return None

    def _build_singles_collection(self):
        """Create response payload to describe contents of a specific library.Used by async_browse_media."""
        singles = BrowseMedia(
            title="Losse opnames",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="singles",
            media_content_id="singles",
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_EPISODE,
            children=[],
        )
        for recording in self._recordings:
            if recording["type"] != "recording":
                continue
            singles.children.append(self._build_episode_item(recording["recording"]))
        return singles

    async def _build_show_collection(self, media_content_id):
        """Create response payload to describe contents of a specific library.Used by async_browse_media."""
        payload = await self.hass.async_add_executor_job(
            self.api.get_show_recording, media_content_id
        )
        recorded_show = payload["show"]
        show = self._build_show_item(recorded_show)
        for child in recorded_show.children:
            show.children.append(self._build_episode_item(child["recording"]))
        return show

    def _build_show_item(self, recorded_show: ArrisDCX960RecordingShow):
        """Create response payload to describe contents of a specific library.Used by async_browse_media."""
        return BrowseMedia(
            title=recorded_show.title,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="show",
            media_content_id=recorded_show.media_group_id,
            can_play=False,
            can_expand=True,
            thumbnail=recorded_show.image,
            children=[],
            children_media_class=MEDIA_CLASS_EPISODE,
        )

    def _build_episode_item(self, recording: ArrisDCX960RecordingSingle):
        """Create response payload to describe contents of a specific library.Used by async_browse_media."""
        title = recording.title
        if recording.season and recording.episode:
            title = f"S{recording.season:02}E{recording.episode:02} - {title}"
        return BrowseMedia(
            title=title,
            media_class=MEDIA_CLASS_EPISODE,
            media_content_type="recording_episode",
            media_content_id=recording.recording_id,
            can_play=True,
            can_expand=False,
            thumbnail=recording.image,
        )
