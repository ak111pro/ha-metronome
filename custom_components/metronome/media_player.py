"""Primary media player: control plane for a selected foreground audio client."""

from time import time

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)

from .entity import MetronomeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MetronomePlayer(entry.runtime_data)])


class MetronomePlayer(MetronomeEntity, MediaPlayerEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "player", None, "mdi:metronome")

    @property
    def supported_features(self):
        features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        if self.settings["timer_enabled"]:
            features |= MediaPlayerEntityFeature.PAUSE
        return features

    @property
    def state(self):
        return {
            "idle": MediaPlayerState.IDLE,
            "playing": MediaPlayerState.PLAYING,
            "paused": MediaPlayerState.PAUSED,
        }[self.coordinator.model.state]

    @property
    def volume_level(self):
        return self.settings["volume"]

    @property
    def is_volume_muted(self):
        return self.settings["muted"]

    @property
    def media_title(self):
        return f"{self.settings['bpm']} BPM · {self.settings['signature']}"

    @property
    def extra_state_attributes(self):
        model = self.coordinator.model
        return self.settings | {
            "output_ready": self.coordinator.owner is not None,
            "output": "Current device",
            # "count_in" from start until the first exercise beat, then "running"; None when
            # idle. The state stays "playing" throughout (not "buffering").
            "phase": model.phase(time()),
            "session_id": model.session_id,
            "ends_at": model.ends_at,
            "last_event": model.last_event,
        }

    async def async_media_play(self):
        # The service call's user lets the page that user just tapped take output.
        context = self._context
        self.coordinator.command("start", user_id=context.user_id if context else None)

    async def async_media_pause(self):
        self.coordinator.command("pause")

    async def async_media_stop(self):
        self.coordinator.command("stop")

    async def async_set_volume_level(self, volume):
        self.coordinator.configure({"volume": volume})

    async def async_mute_volume(self, mute):
        self.coordinator.configure({"muted": mute})
