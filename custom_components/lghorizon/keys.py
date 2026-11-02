"""Remote key names of the settopbox."""

import logging

from lghorizon import const as lghorizon_const

_LOGGER = logging.getLogger(__name__)

# The box ignores key names with the wrong case ("CHANNELUP" instead of "ChannelUp").
REMOTE_KEYS = {
    value.casefold(): value
    for name, value in vars(lghorizon_const).items()
    if name.startswith("MEDIA_KEY_")
}


def resolve_remote_key(key: str) -> str:
    """Return the name the box expects for a key, whatever case it was given in."""
    if (known_key := REMOTE_KEYS.get(key.casefold())) is None:
        _LOGGER.warning(
            "Unknown remote key %r, sending it as is; the box ignores unknown keys",
            key,
        )
        return key
    return known_key
