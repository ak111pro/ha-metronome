"""Register the card's JavaScript module as a dashboard resource (storage-mode Lovelace).

Uses HA's own Lovelace resource collection (hass.data[LOVELACE_DATA].resources, the
collection behind Settings -> Dashboards -> Resources). Only resources whose URL path is
exactly /metronome/metronome-card.js are ours; nothing else is ever touched.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

CARD_PATH = "/metronome/metronome-card.js"
CARD_URL = f"{CARD_PATH}?v={VERSION}"
DONE = f"{DOMAIN}_resource_done"


def _lovelace(hass: HomeAssistant):
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: PLC0415
    except ImportError:  # pragma: no cover - lovelace is part of every HA install
        return None
    return hass.data.get(LOVELACE_DATA)


def _ours(resources) -> list[dict]:
    return [item for item in resources.async_items() if urlsplit(item["url"]).path == CARD_PATH]


async def async_register_card(hass: HomeAssistant) -> None:
    """Add the card resource, or bring an existing one to this version. Once per HA start
    (the first config entry to load runs it)."""
    if hass.data.get(DONE):
        return
    hass.data[DONE] = True
    lovelace = _lovelace(hass)
    if lovelace is None:
        _LOGGER.debug("Dashboards not loaded; card resource not registered")
        return
    if lovelace.resource_mode != "storage":
        _LOGGER.info(
            "Dashboard resources are managed in YAML: add %s as a JavaScript module resource",
            CARD_URL,
        )
        return
    resources = lovelace.resources
    await resources.async_get_info()  # loads the stored resources
    ours = _ours(resources)
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": CARD_URL})
        _LOGGER.info("Registered the Metronome card resource %s", CARD_URL)
        return
    for item in ours:
        if item["url"] != CARD_URL or item.get("type") != "module":
            await resources.async_update_item(item["id"], {"res_type": "module", "url": CARD_URL})
            _LOGGER.info("Updated the Metronome card resource to %s", CARD_URL)


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove our resource when the last Metronome entry is removed (the card cannot work
    without one). Re-adding an entry registers it again."""
    hass.data.pop(DONE, None)
    lovelace = _lovelace(hass)
    if lovelace is None or lovelace.resource_mode != "storage":
        return
    resources = lovelace.resources
    await resources.async_get_info()
    for item in _ours(resources):
        await resources.async_delete_item(item["id"])
        _LOGGER.info("Removed the Metronome card resource")
