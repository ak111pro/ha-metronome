"""Constants for the Metronome integration."""

DOMAIN = "metronome"
VERSION = "0.1.0-alpha.3"
PLATFORMS = ["media_player", "number", "select", "switch", "event", "sensor"]
EVENT_TYPES = ["started", "paused", "resumed", "stopped", "finished", "interrupted"]
SIGNATURES = {"2/4": 2, "3/4": 3, "4/4": 4, "6/8": 2}
MAX_DURATION = 359999  # 99:59:59
LEASE_SECONDS = 12
DEFAULTS = {
    "bpm": 120,
    "signature": "4/4",
    "count_in": 0,
    "accent": True,
    "timer_enabled": False,
    "duration": 30,
    "volume": 0.5,
    "muted": False,
}
