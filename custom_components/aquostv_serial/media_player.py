"""
Support for interface with an Aquos TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.aquostv/
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_TIMEOUT,
    CONF_USERNAME)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# restore when pulling from proper python package
#REQUIREMENTS = ['sharp_aquos_rc==0.3.2']

CONF_TYPE = 'connection_type'
CONF_IPPORT = 'ip_port'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Sharp Aquos TV'
DEFAULT_PORT = 10002
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'password'
DEFAULT_TIMEOUT = 0.5
DEFAULT_RETRIES = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Exclusive(CONF_HOST, CONF_TYPE): {
        vol.Optional(CONF_IPPORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string
        },
    vol.Exclusive(CONF_PORT, CONF_TYPE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.string,
    vol.Optional('retries', default=DEFAULT_RETRIES): cv.string,
    vol.Optional('power_on_enabled', default=True): cv.boolean,
})

SOURCES = {0: 'TV / Antenna',
           1: 'HDMI_IN_1',
           2: 'HDMI_IN_2',
           3: 'HDMI_IN_3',
           4: 'HDMI_IN_4',
           5: 'COMPONENT IN',
           6: 'VIDEO_IN_1',
           7: 'VIDEO_IN_2',
           8: 'PC_IN'}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType, 
    add_entities: AddEntitiesCallback, 
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sharp Aquos TV platform."""
    from . import tv

    name = config.get(CONF_NAME)
    ipport = config.get(CONF_IPPORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    power_on_enabled = config.get('power_on_enabled')

    if discovery_info:
        _LOGGER.debug('%s', discovery_info)
        vals = discovery_info.split(':')
        if len(vals) > 1:
            ipport = vals[1]

        host = vals[0]
        #   this call will not work until IP comms added back to tv.py
        remote = tv.TV(host, ipport, username, password, timeout=20)
        add_entities([SharpAquosTVDevice(name, remote, power_on_enabled)])
        return True

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    if host is not None:
        #   this call will not work until IP comms added back to tv.py
        remote = tv.TV(host, ipport, username, password, 15, 1)
    elif port is not None:
        _LOGGER.debug("Creating AQUOS TV instance at %s", port)
        remote = tv.TV(port)

    add_entities([SharpAquosTVDevice(name, remote, power_on_enabled)])


def _retry(func):
    """Handle query retries."""
    def wrapper(obj, *args, **kwargs):
        """Wrap all query functions."""
        update_retries = 3
        while update_retries > 0:
            try:
                func(obj, *args, **kwargs)
                break
            except (OSError, TypeError, ValueError):
                update_retries -= 1
                if update_retries == 0:
                    obj.set_state(MediaPlayerState.OFF)
    return wrapper


class SharpAquosTVDevice(MediaPlayerEntity):
    """Representation of a Aquos TV."""

    _attr_source_list = list(SOURCES.values())
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY
    )

    def __init__(
        self, name: str, remote, power_on_enabled: bool = False
    ) -> None:
        """Initialize the aquos device."""
        self._power_on_enabled = power_on_enabled
        if power_on_enabled:
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
        # Save a reference to the imported class
        self._attr_name = name
        # Assume that the TV is not muted
        self._remote = remote

    def set_state(self, state):
        """Set TV state."""
        self._attr_state = state

    @_retry
    def update(self) -> None:
        """Retrieve the latest data."""
        if self._remote.power() == 1:
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF
        # Set TV to be able to remotely power on
        if self._power_on_enabled:
            self._remote.power_on_command_settings(2)
        else:
            self._remote.power_on_command_settings(0)
        # Get mute state
        if self._remote.mute() == 2:
            self._attr_is_volume_muted = False
        else:
            self._attr_is_volume_muted = True
        # Get source
        input = self._remote.input()
        if type(input) == int:
            self._attr_source = SOURCES.get(input)
        # Get volume
        self._attr_volume_level = self._remote.volume() / 60
        _LOGGER.debug("state: {}, input: {} source: {}".format(self._state, type(input), self._source))

    @_retry
    def turn_off(self) -> None:
        """Turn off tvplayer."""
        self._remote.power(0)

    @_retry
    def volume_up(self) -> None:
        """Volume up the media player."""
        if self.volume_level is None:
            _LOGGER.debug("Unknown volume in volume_up")
            return
        self._remote.volume(int(self.volume_level * 60) + 2)

    @_retry
    def volume_down(self) -> None:
        """Volume down media player."""
        if self.volume_level is None:
            _LOGGER.debug("Unknown volume in volume_down")
            return
        self._remote.volume(int(self.volume_level * 60) - 2)

    @_retry
    def set_volume_level(self, volume: float) -> None:
        """Set Volume media player."""
        self._remote.volume(int(volume * 60))

    @_retry
    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._remote.mute(0)

    @_retry
    def turn_on(self) -> None:
        """Turn the media player on."""
        self._remote.power(1)

    @_retry
    def media_play_pause(self) -> None:
        """Simulate play pause media player."""
        self._remote.remote_button(40)

    @_retry
    def media_play(self) -> None:
        """Send play command."""
        self._remote.remote_button(16)

    @_retry
    def media_pause(self) -> None:
        """Send pause command."""
        self._remote.remote_button(16)

    @_retry
    def media_next_track(self) -> None:
        """Send next track command."""
        self._remote.remote_button(21)

    @_retry
    def media_previous_track(self) -> None:
        """Send the previous track command."""
        self._remote.remote_button(19)

    @_retry
    def select_source(self, source: str) -> None:
        """Set the input source."""
        for key, value in SOURCES.items():
            if source == value:
                self._remote.input(key)
