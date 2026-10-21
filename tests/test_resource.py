"""The card resource is registered in storage-mode dashboards, once per start."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.metronome.const import DOMAIN, VERSION
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

URL = f"/metronome/metronome-card.js?v={VERSION}"


async def resources(hass: HomeAssistant) -> list[dict]:
    collection = hass.data[LOVELACE_DATA].resources
    await collection.async_get_info()
    return [dict(item) for item in collection.async_items()]


async def setup(hass: HomeAssistant, lovelace: dict | None = None) -> MockConfigEntry:
    assert await async_setup_component(hass, "lovelace", {"lovelace": lovelace or {}})
    entry = MockConfigEntry(domain=DOMAIN, title="Metronome", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_adds_the_resource(hass: HomeAssistant) -> None:
    await setup(hass)
    assert [(r["type"], r["url"]) for r in await resources(hass)] == [("module", URL)]


async def test_updates_an_old_version_in_place_and_leaves_others(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    collection = hass.data[LOVELACE_DATA].resources
    await collection.async_get_info()
    old = await collection.async_create_item(
        {"res_type": "module", "url": "/metronome/metronome-card.js?v=0.1.0-alpha.2"}
    )
    other = await collection.async_create_item({"res_type": "module", "url": "/local/other.js"})
    similar = await collection.async_create_item(
        {"res_type": "js", "url": "/metronome-extra/metronome-card.js"}
    )
    entry = MockConfigEntry(domain=DOMAIN, title="Metronome", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    items = {r["id"]: r for r in await resources(hass)}
    assert len(items) == 3
    assert items[old["id"]]["url"] == URL and items[old["id"]]["type"] == "module"
    assert items[other["id"]] == dict(other)
    assert items[similar["id"]] == dict(similar)


async def test_no_duplicates_with_two_entries_and_reload(hass: HomeAssistant) -> None:
    first = await setup(hass)
    second = MockConfigEntry(domain=DOMAIN, title="Practice", data={})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    assert await hass.config_entries.async_reload(first.entry_id)
    await hass.async_block_till_done()
    assert [r["url"] for r in await resources(hass)] == [URL]


async def test_current_version_is_left_alone(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    collection = hass.data[LOVELACE_DATA].resources
    await collection.async_get_info()
    item = await collection.async_create_item({"res_type": "module", "url": URL})
    entry = MockConfigEntry(domain=DOMAIN, title="Metronome", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await resources(hass) == [dict(item)]


async def test_yaml_mode_only_logs(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="custom_components.metronome")
    entry = await setup(hass, {"mode": "yaml"})
    assert entry.state.name == "LOADED"
    assert hass.data[LOVELACE_DATA].resource_mode == "yaml"
    assert "managed in YAML: add /metronome/metronome-card.js" in caplog.text


async def test_without_dashboards_setup_still_works(hass: HomeAssistant, loaded) -> None:
    assert loaded.state.name == "LOADED"


async def test_removing_the_last_entry_removes_the_resource(hass: HomeAssistant) -> None:
    first = await setup(hass)
    second = MockConfigEntry(domain=DOMAIN, title="Practice", data={})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(first.entry_id)
    await hass.async_block_till_done()
    assert [r["url"] for r in await resources(hass)] == [URL]  # one entry left
    await hass.config_entries.async_remove(second.entry_id)
    await hass.async_block_till_done()
    assert await resources(hass) == []
    # Adding an entry again registers it again (no restart needed).
    third = MockConfigEntry(domain=DOMAIN, title="Again", data={})
    third.add_to_hass(hass)
    assert await hass.config_entries.async_setup(third.entry_id)
    await hass.async_block_till_done()
    assert [r["url"] for r in await resources(hass)] == [URL]
