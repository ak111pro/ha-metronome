"""Pure session model. No Home Assistant or wall-clock dependencies.

Callers supply UTC epoch seconds. Audio clients map this timeline to their audio
clock. Negative beat positions are count-in; zero is the first exercise beat.
"""

from math import isfinite
from uuid import uuid4

from .const import DEFAULTS, MAX_DURATION, SIGNATURES


def validate_settings(changes):
    """Validate the complete patch before applying any part of it."""
    result = {}
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"Unknown setting: {key}")
        if key in ("accent", "timer_enabled", "muted"):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
        elif key == "signature":
            if value not in SIGNATURES:
                raise ValueError("Choose 2/4, 3/4, 4/4 or 6/8")
        else:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{key} must be a finite number")
            low, high = {
                "bpm": (1, 200),
                "duration": (1, MAX_DURATION),
                "count_in": (0, 2),
                "volume": (0, 1),
            }[key]
            if not low <= value <= high or (key != "volume" and int(value) != value):
                raise ValueError(f"{key} must be between {low} and {high}")
            value = float(value) if key == "volume" else int(value)
        result[key] = value
    return result


class Session:
    """An idle session is always safe to restore after a process restart."""

    def __init__(self, settings=None):
        self.settings = DEFAULTS | validate_settings(settings or {})
        self.state = "idle"
        self.session_id = None
        self.revision = 0
        self.anchor_at = 0.0
        self.anchor_beat = 0.0
        self.ends_at = None
        self.remaining = float(self.settings["duration"])
        self.last_event = None
        self.completed = False

    def position(self, now):
        if self.state == "playing":
            return self.anchor_beat + max(0.0, now - self.anchor_at) * self.settings["bpm"] / 60
        return self.anchor_beat

    def remaining_at(self, now):
        # While playing, self.remaining is the time left at the last (re)start. It caps
        # the value during the start lead and count-in, when ends_at - now is larger.
        if self.state == "playing" and self.ends_at is not None:
            return max(0.0, min(self.remaining, self.ends_at - now))
        return self.remaining

    def _event(self, name):
        self.revision += 1
        self.last_event = name
        return name

    def start(self, now):
        if self.state == "playing":
            return None
        resume = self.state == "paused"
        self.completed = False
        if not resume:
            self.session_id = uuid4().hex
            self.anchor_beat = -self.settings["count_in"] * SIGNATURES[self.settings["signature"]]
            self.remaining = float(self.settings["duration"])
        self.anchor_at = now + 0.20
        self.state = "playing"
        count_in = max(0, -self.anchor_beat) * 60 / self.settings["bpm"]
        self.ends_at = (
            self.anchor_at + count_in + self.remaining if self.settings["timer_enabled"] else None
        )
        return self._event("resumed" if resume else "started")

    def pause(self, now):
        if not self.settings["timer_enabled"]:
            raise ValueError("Pause is available when the timer is enabled")
        if self.state != "playing":
            return None
        self.anchor_beat = self.position(now)
        self.remaining = self.remaining_at(now)
        self.ends_at = None
        self.state = "paused"
        return self._event("paused")

    def stop(self, reason="stopped"):
        if self.state == "idle":
            return None
        self.state = "idle"
        self.ends_at = None
        self.anchor_beat = 0
        self.remaining = float(self.settings["duration"])
        self.completed = reason == "finished"
        return self._event(reason)

    def finish_due(self, now):
        if self.state == "playing" and self.ends_at is not None and now >= self.ends_at:
            return self.stop("finished")
        return None

    def configure(self, changes, now):
        changes = validate_settings(changes)
        locked = {"duration", "timer_enabled", "signature", "count_in"}
        if self.state != "idle" and any(
            k in locked and v != self.settings[k] for k, v in changes.items()
        ):
            raise ValueError("Stop the metronome before changing timer, meter or count-in")
        position = self.position(now)
        old_bpm = self.settings["bpm"]
        self.settings.update(changes)
        self.completed = False
        if self.state == "idle":
            self.remaining = float(self.settings["duration"])
        elif self.state == "playing" and self.settings["bpm"] != old_bpm:
            self.anchor_beat = position
            self.anchor_at = max(now, self.anchor_at)
            if position < 0 and self.ends_at is not None:
                self.ends_at = (
                    self.anchor_at - position * 60 / self.settings["bpm"] + self.remaining
                )
        self.revision += 1

    def snapshot(self, now):
        return {
            "settings": dict(self.settings),
            "state": self.state,
            "phase": "count_in" if self.state != "idle" and self.position(now) < 0 else "running",
            "session_id": self.session_id,
            "revision": self.revision,
            "anchor_at": self.anchor_at,
            "anchor_beat": self.anchor_beat,
            "ends_at": self.ends_at,
            "remaining": self.remaining_at(now),
            "last_event": self.last_event,
            "server_time": now,
            "completed": self.completed,
        }
