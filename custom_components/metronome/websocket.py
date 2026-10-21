"""Authenticated controls. Ownership is bound to a server-side WS connection."""

from functools import wraps
import logging
from time import monotonic

import probatio as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er

from .const import ARM_SECONDS, ARMED, DOMAIN

_LOGGER = logging.getLogger(__name__.rpartition(".")[0])


def _resolve(hass, connection, entity_id, policy):
    if not connection.user.permissions.check_entity(entity_id, policy):
        raise Unauthorized()
    item = er.async_get(hass).async_get(entity_id)
    if item is None or item.platform != DOMAIN or item.domain != "media_player":
        raise ServiceValidationError("Select a Metronome media player entity")
    entry = hass.config_entries.async_get_entry(item.config_entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("Metronome is unavailable")
    return entry.runtime_data


def _expected_errors(handler):
    """Answer user errors (stale subscription, claim while playing, ...) with an error
    result only. Raising them would make HA log every rejected tap as an ERROR."""

    @wraps(handler)
    def wrapper(hass, connection, msg):
        try:
            handler(hass, connection, msg)
        except ServiceValidationError as err:
            connection.send_error(msg["id"], websocket_api.ERR_HOME_ASSISTANT_ERROR, str(err))

    return wrapper


@callback
def async_register_commands(hass):
    websocket_api.async_register_command(hass, subscribe)
    websocket_api.async_register_command(hass, control)
    websocket_api.async_register_command(hass, arm)
    websocket_api.async_register_command(hass, diagnostics)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "metronome/subscribe",
        vol.Required("entity_id"): str,
    }
)
@callback
@_expected_errors
def subscribe(hass, connection, msg):
    coordinator = _resolve(hass, connection, msg["entity_id"], POLICY_READ)
    token = (connection, msg["id"])
    coordinator.add_client(token, lambda state: connection.send_event(msg["id"], state))
    connection.subscriptions[msg["id"]] = lambda: coordinator.drop_client(token)
    connection.send_result(msg["id"], {"subscription": msg["id"]})
    # The subscription ID is included so the client can bind later commands to it.
    connection.send_event(msg["id"], coordinator.snapshot(token) | {"subscription": msg["id"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "metronome/control",
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(
            ["configure", "start", "stop", "pause", "claim", "heartbeat", "release"]
        ),
        vol.Optional("subscription"): int,
        vol.Optional("settings"): dict,
    }
)
@callback
@_expected_errors
def control(hass, connection, msg):
    coordinator = _resolve(hass, connection, msg["entity_id"], POLICY_CONTROL)
    token = (connection, msg.get("subscription"))
    action = msg["action"]
    if action in ("claim", "heartbeat", "release"):
        if token not in coordinator.clients:
            raise ServiceValidationError("This connection has no matching metronome subscription")
        getattr(coordinator, action)(token)
    elif action == "configure":
        coordinator.configure(msg.get("settings", {}))
    else:
        coordinator.command(action)
    connection.send_result(msg["id"], coordinator.snapshot(token))


@websocket_api.websocket_command({vol.Required("type"): "metronome/arm"})
@callback
def arm(hass, connection, msg):
    """A user gesture on this page (sent by the card module in the capture phase, so it
    arrives before the Tile's own media_play on the same connection). Fire and forget:
    remembered for ARM_SECONDS, keyed by connection; stale entries are pruned here."""
    armed = hass.data.setdefault(ARMED, {})
    now = monotonic()
    for key, (_, at) in tuple(armed.items()):
        if now - at > ARM_SECONDS * 4:
            del armed[key]
    armed[id(connection)] = (connection, now)
    connection.send_result(msg["id"])


DIAGNOSTIC_KEYS = (
    "audio",
    "sample_rate",
    "audio_session",
    "owner",
    "ready",
    "haptics",
    "vibration_on",
    "last_haptic",
    "last_error",
    "contexts",
    "app",
    "external_bus",
    "vibrate_api",
)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "metronome/diagnostics",
        vol.Required("entity_id"): str,
        vol.Required("diagnostics"): dict,
    }
)
@callback
@_expected_errors
def diagnostics(hass, connection, msg):
    """A page that took output reports its audio/haptics state once, for the HA log
    (logger custom_components.metronome, debug level). Only known keys, short values, and the HA
    user name; nothing else about the device."""
    coordinator = _resolve(hass, connection, msg["entity_id"], POLICY_CONTROL)
    report = {
        key: str(msg["diagnostics"][key])[:120]
        for key in DIAGNOSTIC_KEYS
        if key in msg["diagnostics"]
    }
    _LOGGER.debug(
        "%s: output page of %s reports %s",
        coordinator.entry.title,
        connection.user.name,
        ", ".join(f"{k}={v}" for k, v in report.items()),
    )
    connection.send_result(msg["id"])
