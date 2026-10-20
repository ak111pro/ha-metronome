"""Session storage, notifications, countdown and foreground-client ownership."""

from datetime import timedelta
from time import time, monotonic
from uuid import uuid4

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LEASE_SECONDS
from .model import Session


class MetronomeCoordinator:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.model = Session()
        self.listeners = set()
        self.event_listeners = set()
        self.clients = {}
        self.owner = None
        self.instance_id = uuid4().hex
        self.sequence = 0
        self._finish_cancel = None
        self._lease_cancel = None
        self._store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")

    async def async_load(self):
        data = await self._store.async_load()
        if data:
            # Invalid persisted settings should not prevent the integration loading.
            for key, value in data.items():
                try:
                    self.model.configure({key: value}, time())
                except (ValueError, TypeError):
                    continue
        self._lease_cancel = async_track_time_interval(self.hass, self._check_lease, timedelta(seconds=3))

    @callback
    def listen(self, listener):
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    @callback
    def snapshot(self, client=None):
        return self.model.snapshot(time()) | {
            "name": self.entry.title,
            "output_ready": self.owner is not None,
            "is_owner": client is not None and client == self.owner,
            "instance_id": self.instance_id, "sequence": self.sequence,
        }

    @callback
    def add_client(self, token, notify):
        self.clients[token] = {"notify": notify, "seen": monotonic()}

    @callback
    def drop_client(self, token):
        self.clients.pop(token, None)
        if self.owner == token:
            self.owner = None
            self._notify(self.model.stop("interrupted"))

    @callback
    def claim(self, token):
        if token not in self.clients:
            raise HomeAssistantError("Open the metronome card on this device first")
        if self.owner is not None and self.owner != token and self.model.state != "idle":
            raise HomeAssistantError("Another device is playing. Stop the session before selecting this device")
        self.owner = token
        self.clients[token]["seen"] = monotonic()
        self._notify()

    @callback
    def heartbeat(self, token):
        if token not in self.clients:
            raise HomeAssistantError("Metronome subscription expired; reopen the card")
        self.clients[token]["seen"] = monotonic()

    @callback
    def release(self, token):
        if self.owner == token:
            self.owner = None
            self._notify(self.model.stop("interrupted"))

    @callback
    def configure(self, changes):
        try:
            self.model.configure(changes, time())
        except (ValueError, TypeError) as err:
            raise HomeAssistantError(str(err)) from err
        self._store.async_delay_save(lambda: dict(self.model.settings), 1)
        self._notify()

    @callback
    def command(self, action):
        now = time()
        # Resolve an elapsed countdown before processing a late user command.
        if event := self.model.finish_due(now):
            self._notify(event)
        try:
            if action == "start":
                if self.owner is None or monotonic() - self.clients[self.owner]["seen"] > LEASE_SECONDS:
                    raise ValueError("Tap Start in the metronome card to enable audio on a foreground device")
                event = self.model.start(now)
            elif action == "pause":
                event = self.model.pause(now)
            elif action == "stop":
                event = self.model.stop()
            else:
                raise ValueError("Unknown action")
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        self._notify(event)

    @callback
    def _notify(self, event=None):
        self.sequence += 1
        if self._finish_cancel:
            self._finish_cancel()
            self._finish_cancel = None
        if self.model.ends_at is not None:
            self._finish_cancel = async_call_later(self.hass, max(0, self.model.ends_at - time()), self._finish)
        for listener in tuple(self.listeners):
            listener()
        for token, client in tuple(self.clients.items()):
            client["notify"](self.snapshot(token))
        if event:
            data = {"session_id": self.model.session_id, "reason": event}
            for listener in tuple(self.event_listeners):
                listener(event, data)

    @callback
    def _finish(self, _now):
        self._finish_cancel = None
        self._notify(self.model.finish_due(time()))

    @callback
    def _check_lease(self, _now):
        if self.owner is not None and monotonic() - self.clients[self.owner]["seen"] > LEASE_SECONDS:
            self.release(self.owner)

    async def async_unload(self):
        self.owner = None
        self._notify(self.model.stop("interrupted"))
        if self._finish_cancel:
            self._finish_cancel()
        if self._lease_cancel:
            self._lease_cancel()
        self.clients.clear()
        await self._store.async_save(dict(self.model.settings))
