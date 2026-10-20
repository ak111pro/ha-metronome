"""Countdown, count-in, pause/resume, completion and session events with controlled time."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import PLAYER

FINISH = "sensor.metronome_expected_finish"
EVENT = "event.metronome_session"
LEAD = 0.2


@pytest.fixture(autouse=True)
def frozen(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    freezer.move_to("2026-10-20 12:00:00+00:00")
    return freezer


async def advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def call(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data) -> None:
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)


async def configure(hass: HomeAssistant, **settings) -> None:
    for key, value in settings.items():
        if key == "bpm":
            await call(hass, "number", "set_value", "number.metronome_tempo", value=value)
        elif key == "duration":
            await call(hass, "number", "set_value", "number.metronome_timer_duration", value=value)
        elif key == "timer":
            await call(hass, "switch", "turn_on" if value else "turn_off", "switch.metronome_timer")
        elif key == "signature":
            await call(
                hass, "select", "select_option", "select.metronome_time_signature", option=value
            )
        elif key == "count_in":
            option = ["Off", "1 bar", "2 bars"][value]
            await call(hass, "select", "select_option", "select.metronome_count_in", option=option)


def session_events(events) -> list[tuple[str, str | None]]:
    """(event_type, session_id) of every event-entity state change."""
    result = []
    for event in events:
        if event.data["entity_id"] != EVENT:
            continue
        new = event.data["new_state"]
        if new.attributes.get("event_type"):
            result.append((new.attributes["event_type"], new.attributes.get("session_id")))
    return result


def finish_time(hass: HomeAssistant) -> datetime | None:
    """Expected finish from the sensor, checked against the exact coordinator value.

    HA writes timestamp sensor states with whole seconds, so the exact instant is taken
    from the model and the sensor must show the same second.
    """
    state = hass.states.get(FINISH).state
    ends_at = hass.config_entries.async_entries("metronome")[0].runtime_data.model.ends_at
    if state == "unknown":
        assert ends_at is None
        return None
    exact = datetime.fromtimestamp(ends_at, UTC)
    assert datetime.fromisoformat(state) == exact.replace(microsecond=0)
    return exact


@pytest.fixture
def long_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the output lease alive across large time jumps without heartbeats."""
    monkeypatch.setattr("custom_components.metronome.coordinator.LEASE_SECONDS", 10**7)


START = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("duration", [1, 4, 5, 120, 121, 359999])
async def test_countdown_finishes_exactly_once(
    hass: HomeAssistant, owner, frozen, long_lease, duration: int
) -> None:
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await configure(hass, timer=True, duration=duration)
    await call(hass, "media_player", "media_play", PLAYER)
    assert finish_time(hass) == START + timedelta(seconds=duration + LEAD)

    await advance(hass, frozen, duration + LEAD - 0.05)
    assert hass.states.get(PLAYER).state == "playing"
    await advance(hass, frozen, 0.05)
    assert hass.states.get(PLAYER).state == "idle"
    assert finish_time(hass) is None
    await advance(hass, frozen, 30)
    await call(hass, "media_player", "media_stop", PLAYER)

    types = [t for t, _ in session_events(events)]
    assert types == ["started", "finished"]
    sessions = {s for _, s in session_events(events)}
    assert len(sessions) == 1 and None not in sessions

    # Long jumps outlive the websocket heartbeat of the test client, so the final
    # snapshot is taken from the coordinator (it is what every subscriber is sent).
    snapshot = hass.config_entries.async_entries("metronome")[0].runtime_data.snapshot()
    assert snapshot["state"] == "idle"
    assert snapshot["completed"] is True
    assert snapshot["last_event"] == "finished"
    # The configured duration is kept for the next run.
    assert snapshot["remaining"] == duration
    assert snapshot["settings"]["duration"] == duration


@pytest.mark.parametrize(
    ("signature", "bars", "count_in_seconds"),
    [
        ("4/4", 0, 0),
        ("4/4", 1, 2.0),
        ("4/4", 2, 4.0),
        ("6/8", 1, 1.0),
        ("6/8", 2, 2.0),
        ("3/4", 2, 3.0),
    ],
)
async def test_count_in_precedes_timer(
    hass: HomeAssistant, owner, frozen, signature, bars, count_in_seconds
) -> None:
    ws, sub = owner
    await configure(hass, timer=True, duration=5, signature=signature, count_in=bars)
    await call(hass, "media_player", "media_play", PLAYER)
    expected = START + timedelta(seconds=LEAD + count_in_seconds + 5)
    assert finish_time(hass) == expected

    snapshot = (await ws.drain(sub))[-1]
    beats_per_bar = {"4/4": 4, "3/4": 3, "6/8": 2}[signature]
    assert snapshot["anchor_beat"] == -bars * beats_per_bar
    assert snapshot["phase"] == ("count_in" if bars else "running")
    assert snapshot["remaining"] == 5

    await advance(hass, frozen, LEAD + count_in_seconds + 4.9)
    assert hass.states.get(PLAYER).state == "playing"
    await advance(hass, frozen, 0.1)
    assert hass.states.get(PLAYER).state == "idle"


async def test_pause_and_resume_recalculate_finish(
    hass: HomeAssistant, owner, frozen, long_lease
) -> None:
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await configure(hass, timer=True, duration=30)
    await call(hass, "media_player", "media_play", PLAYER)
    await advance(hass, frozen, 10.2)  # 10 s of the exercise have run
    await call(hass, "media_player", "media_pause", PLAYER)
    assert hass.states.get(PLAYER).state == "paused"
    assert finish_time(hass) is None
    coordinator = hass.config_entries.async_entries("metronome")[0].runtime_data
    assert coordinator.model.remaining == pytest.approx(20)

    # Time passing while paused never finishes the session.
    await advance(hass, frozen, 600)
    assert hass.states.get(PLAYER).state == "paused"

    await call(hass, "media_player", "media_play", PLAYER)
    assert hass.states.get(PLAYER).state == "playing"
    resumed_at = START + timedelta(seconds=610.2)
    assert finish_time(hass) == resumed_at + timedelta(seconds=LEAD + 20)

    await advance(hass, frozen, LEAD + 20)
    assert hass.states.get(PLAYER).state == "idle"
    recorded = session_events(events)
    assert [t for t, _ in recorded] == ["started", "paused", "resumed", "finished"]
    assert len({s for _, s in recorded}) == 1


async def test_pause_right_after_resume_does_not_add_time(
    hass: HomeAssistant, owner, frozen
) -> None:
    coordinator = hass.config_entries.async_entries("metronome")[0].runtime_data
    await configure(hass, timer=True, duration=30)
    await call(hass, "media_player", "media_play", PLAYER)
    await advance(hass, frozen, 10.2)
    await call(hass, "media_player", "media_pause", PLAYER)
    assert coordinator.model.remaining == pytest.approx(20)
    # Pausing again inside the 200 ms start lead must not credit the lead as time.
    for _ in range(5):
        await call(hass, "media_player", "media_play", PLAYER)
        await advance(hass, frozen, 0.1)
        await call(hass, "media_player", "media_pause", PLAYER)
    assert coordinator.model.remaining == pytest.approx(20)


async def test_pause_during_count_in(hass: HomeAssistant, owner, frozen, long_lease) -> None:
    coordinator = hass.config_entries.async_entries("metronome")[0].runtime_data
    await configure(hass, timer=True, duration=30, count_in=1)  # 4 beats at 120 BPM = 2 s
    await call(hass, "media_player", "media_play", PLAYER)
    await advance(hass, frozen, LEAD + 1.0)  # half way through the count-in
    await call(hass, "media_player", "media_pause", PLAYER)
    assert coordinator.model.anchor_beat == pytest.approx(-2)
    assert coordinator.model.remaining == 30
    await advance(hass, frozen, 5)
    await call(hass, "media_player", "media_play", PLAYER)
    resumed_at = START + timedelta(seconds=LEAD + 1.0 + 5)
    # Two count-in beats (1 s) are left, then the full 30 s.
    assert finish_time(hass) == resumed_at + timedelta(seconds=LEAD + 1.0 + 30)


async def test_tempo_change_keeps_running_finish_fixed(
    hass: HomeAssistant, owner, frozen, long_lease
) -> None:
    await configure(hass, timer=True, duration=60)
    await call(hass, "media_player", "media_play", PLAYER)
    finish = finish_time(hass)
    await advance(hass, frozen, 10)
    for bpm in (60, 200, 1):
        await configure(hass, bpm=bpm)
        assert finish_time(hass) == finish
    await advance(hass, frozen, 50.2)
    assert hass.states.get(PLAYER).state == "idle"


async def test_tempo_change_during_count_in_moves_finish(
    hass: HomeAssistant, owner, frozen
) -> None:
    await configure(hass, timer=True, duration=5, count_in=1)
    await call(hass, "media_player", "media_play", PLAYER)
    assert finish_time(hass) == START + timedelta(seconds=LEAD + 2 + 5)
    await advance(hass, frozen, LEAD + 0.5)  # one of four count-in beats played
    await configure(hass, bpm=60)  # three beats left, now one second each
    assert finish_time(hass) == START + timedelta(seconds=LEAD + 0.5 + 3 + 5)
    # Exactly on the count-in boundary the exercise has begun: the finish stays.
    await advance(hass, frozen, 3)
    await configure(hass, bpm=120)
    assert finish_time(hass) == START + timedelta(seconds=LEAD + 0.5 + 3 + 5)


async def test_pause_or_stop_after_deadline_resolves_finish_first(
    hass: HomeAssistant, owner, frozen
) -> None:
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    coordinator = hass.config_entries.async_entries("metronome")[0].runtime_data
    await configure(hass, timer=True, duration=5)
    await call(hass, "media_player", "media_play", PLAYER)
    # The deadline has passed but the scheduled finish has not run yet.
    frozen.tick(timedelta(seconds=6))
    coordinator.command("pause")
    coordinator.command("stop")
    await hass.async_block_till_done()
    assert [t for t, _ in session_events(events)] == ["started", "finished"]
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert [t for t, _ in session_events(events)] == ["started", "finished"]


async def test_repeated_start_stop_creates_new_sessions(hass: HomeAssistant, owner, frozen) -> None:
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await configure(hass, timer=True, duration=5)
    for _ in range(3):
        await call(hass, "media_player", "media_play", PLAYER)
        await call(hass, "media_player", "media_play", PLAYER)  # no-op while playing
        await advance(hass, frozen, 1)
        await call(hass, "media_player", "media_stop", PLAYER)
        await call(hass, "media_player", "media_stop", PLAYER)  # no-op while idle
    await advance(hass, frozen, 10)
    recorded = session_events(events)
    assert [t for t, _ in recorded] == ["started", "stopped"] * 3
    sessions = [s for _, s in recorded]
    assert sessions[0] == sessions[1] != sessions[2] == sessions[3] != sessions[4]


async def test_interruption_never_emits_finished(hass: HomeAssistant, owner, frozen) -> None:
    ws, sub = owner
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await configure(hass, timer=True, duration=5)
    await call(hass, "media_player", "media_play", PLAYER)
    await ws.unsubscribe(sub)
    assert hass.states.get(PLAYER).state == "idle"
    assert finish_time(hass) is None
    await advance(hass, frozen, 30)
    assert [t for t, _ in session_events(events)] == ["started", "interrupted"]


async def test_no_state_writes_per_beat(hass: HomeAssistant, owner, frozen) -> None:
    ws, sub = owner
    await configure(hass, bpm=200)
    await call(hass, "media_player", "media_play", PLAYER)
    await ws.drain(sub)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    for _ in range(10):  # 10 s = 33 beats, heartbeats keep the lease alive
        await ws.ok("heartbeat", sub)
        await advance(hass, frozen, 1)
    assert events == []
    assert (await ws.drain(sub)) == []
    assert hass.states.get(PLAYER).state == "playing"
