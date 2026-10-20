# Validation record and next-stage test plan

## Status (2026-10-20, repository import)

| Area | Status |
| --- | --- |
| Backend in HA (pytest) | **Verified**: 60 tests, HA 2026.10.1 harness |
| hassfest 2026.10.1 | **Passes** without warnings (run locally) |
| HACS action | Not run yet (needs the GitHub repository) |
| Live HA instance (websocket, REST, restart) | **Verified** on the ha-dev test instance (HA 2026.10.2) |
| Card in a real browser | **Rendered and driven** in headless Chromium 155 (no audible output) |
| Android/iOS Companion apps, audio timing, accessibility | **Not tested** — needs real devices |

### HA tests (pytest)

`tests/` uses pytest-homeassistant-custom-component 0.13.372 (= HA 2026.10.1, Python 3.14)
with frozen time (`freezer` + `async_fire_time_changed`) and real websocket clients
(`hass_ws_client`). Run on the development Pi as

```sh
taskset -c 3 nice -n 19 ionice -c3 .venv/bin/python -m pytest -q -p no:cacheprovider
```

Covered from the list below:

- Config flow: named entries, blank name rejected, two independent instances, entity unique ids
  `<entry_id>_<key>`, entry rename reaches the card snapshot.
- Setup, unload, reload, removal (store deleted), save on unload, one-second delayed save,
  failed platform setup (no leaked timer).
- Settings restored after a restart while idle with no output owner; invalid, unknown or
  wrongly typed stored data is skipped/ignored with a warning, setup still succeeds.
- Every platform's states and attributes; media-player features (pause only with the timer);
  native setters and range rejection; timer, duration, meter and count-in locked while playing
  or paused, tempo/accent/volume/mute still adjustable.
- Native media actions before any client claimed output (helpful validation error), after a
  claim, and after the client left; read-only users rejected by native actions.
- Countdowns 1/4/5/120/121 s and 99:59:59 finish exactly once; count-in off/1/2 bars in 4/4,
  3/4 and 6/8; pause in count-in; pause/resume and pause inside the 200 ms start lead;
  pause/stop arriving after the deadline (finish resolved first); repeated start/stop with new
  session ids; interruption never emits `finished`; no state writes or websocket events per beat.
- Event entity: `started/paused/resumed/stopped/finished/interrupted` with the session id.
- Expected-finish sensor fixed during tempo changes, cleared on pause, recalculated on resume,
  moved by tempo changes during the count-in. HA stores timestamp sensor states with whole
  seconds; the exact instant is in the websocket snapshot (`ends_at`).
- Websocket: subscribe snapshot, full session, atomic validation, claim only through the
  connection's own subscription (missing, stale and foreign ids rejected), claim rejected while
  active/paused, hand-off while idle, release, unsubscribe and disconnect interrupt, lease expiry
  12–15 s after the last heartbeat, stale lease rejects start, wrong and unloaded entities,
  read-only viewer (subscribe yes, every control `unauthorized`), ordinary non-admin user can
  play, two instances with separate owners, expected rejections not logged as HA errors.
- Static module: every frontend file is served with a JavaScript content type, nothing outside
  `frontend/` is reachable.

Not covered by pytest: wall-clock jumps (NTP corrections), timezone/DST display (frontend),
anonymous websocket transport (rejected by HA itself before any metronome code runs).

### Live check on ha-dev (HA 2026.10.2, Docker on the Pi)

- Both instances ("Metronome", "Practice") created through the REST config-flow API, 18
  entities with the expected ids and states.
- `/metronome/metronome-card.js?v=0.1.0-alpha.1` and the other modules: HTTP 200,
  `text/javascript`. Registered as a dashboard resource (module) through the websocket API.
- A websocket script drove two connections: subscribe, start rejected before claim, native
  `media_play` rejected before claim (HTTP 400) and accepted after it, claim, configure,
  count-in start (`ends_at` = anchor + count-in + duration), second connection's claim rejected
  while active, live tempo change from the second connection, locked duration, pause (finish
  sensor cleared), resume (same session, sensor set), natural timer finish with the `finished`
  event and session id, lease expiry ~12 s after the client stopped heartbeating
  (`interrupted`), hand-off while idle, stale and foreign subscription ids rejected, second
  instance independent, owner disconnect interrupts immediately, unsubscribe releases output.
- Settings changed right before `docker restart ha-dev` were restored (the delayed save is
  flushed at shutdown); after the restart every instance was idle without an owner.
- HA log: no errors or warnings from the integration (only HA's standard custom-integration
  notice).
- Headless Chromium 155 (360 px wide, mobile emulation) on the test dashboard: the full and
  compact cards render, no console errors from the card; tapping Start enables audio
  (`AudioContext` running), claims output and starts the session; scheduled tones for 3/4 with a
  one-bar count-in at 120 BPM were 3 × 800 Hz count-in, then accented bars (1500/1000/1000 Hz)
  0.500 s apart, and the two-tone chime once at the deadline; the compact card's dialog shares
  the same player; leaving the page releases output (`interrupted`). Audio was muted, so this
  checks scheduling, not sound.

## Still needs real devices

Everything in *Required frontend and audio tests* below, in particular on the Android and iOS
Companion apps: first-gesture audio unlock, OS interruptions, screen lock, backgrounding,
reconnect, measured beat spacing/drift at 1/60/120/200 BPM, vibration support, layout at
280–440 px in light/dark themes, keyboard and screen-reader use.

## Performed in the Codex build (before the repository)

- Parsed every Python file with Python's AST parser, every JSON file with the JSON parser, and every frontend JS module with Node's syntax checker.
- Ran 10 dependency-free pure-model checks: 6/8 count-in and one-time finish; ordinary pause/resume; pause during count-in; live tempo with fixed exercise deadline; tempo changes during count-in; rejection of pause in indefinite mode; stop/reset; atomic validation; locked session settings; settings-only restart restore.
- Ran frontend helper assertions for 6/8 beat count, representative tempo labels, normal/inverted arc endpoints and intermediate positions, duration formatting, countdown bounds and HTML escaping.
- Checked final package contents and local frontend module references.

These checks passed. They use Python 3.11.4 and Node 24.19.0 in the build environment. They were not HA integration or device tests.

## Required HA tests

- HA Core 2026.10.1 startup, user config flow, two separately named instances, stable unique IDs, rename, unload/reload, deletion and store cleanup.
- Every entity platform loads and uses the correct native state/features. Pause is unavailable without timer. Timer, duration, meter and count-in reject changes while active/paused. Volume/accent/mute/tempo remain adjustable.
- Settings survive restart while state is idle, no output owner is restored and no audio starts. Corrupt/old stored settings do not prevent setup.
- Full websocket subscription lifecycle: disconnect/unsubscribe/lease expiry; stale subscription; wrong entity; unloaded instance; cross-connection token; anonymous transport rejection; read-only vs control-enabled users. Confirm native service permission behavior as well.
- Countdowns 1/4/5/120/121 seconds and 99:59:59; zero validation; completion exactly once; count-in off/1/2 bars; pause within count-in; repeated start/stop/resume; simultaneous expiry and pause/stop; tempo change at a beat or deadline boundary.
- Event entity transitions carry correct session IDs and reasons. A forced interruption never emits `finished`. No event or state write occurs for every beat.
- Timer timestamp remains fixed during a running exercise's BPM changes; pause clears it; resume creates a new one. Timezone and daylight-saving crossing display checks.
- Standard media-player actions/native Tile before client unlock, after unlock, while another client is selected, and after client loss. Never pretend native actions identify the caller's phone automatically.

## Required frontend and audio tests

- iOS and Android Companion apps, plus a desktop browser: first gesture audio unlock, denied/resumed audio, muted hardware/device volume, OS interruptions, backgrounding, screen lock, switching dashboards, reconnect, HA restart and page refresh.
- One audible output per integration instance despite multiple cards, dialog copies, browser tabs and devices. Test explicit handoff after Stop and rejection of a claim while active/paused.
- BPM 1, 60, 120 and 200 over a sustained run. Measure spacing and drift from captured audio, not visual dots. Test Wi-Fi delay and foreground rendering load. Verify no burst of overdue beats after a stall.
- Accent/reset at bar boundaries; 6/8 has two dotted-quarter pulses, count-in duration matches meter, finish chime occurs once and mute suppresses it. Stop cancels scheduled oscillators and haptics promptly.
- Rapid volume/mute/tempo edits and concurrent controllers. Timer editing fields select the expected unit; ±1 wraps through duration correctly. Out-of-range dial greyed before play, enabled as progress while running, knob hidden.
- Full/compact cards, modal expanded view, Back/close/Escape and focus return. Both copies must share session state and never double the audio engine.
- Native light/dark/custom themes, 280/320/360/440px widths, mobile safe areas, Sections and Masonry, HA panel/dialog scrolling. Check no clip/overlap and menu reachability.
- Volume marker containment at 0%, 1%, 5%, 10%, 50%, 100%. Button height vs slider height. Timer expansion and Tap-to-dots transition.
- Keyboard range input, +/- controls, menu arrows/Home/End/Escape/Tab, focus-visible, screen reader status/labels, contrast and reduced motion. No focus lost while typing as HA states update.
- All card-editor options round-trip to YAML. Hiding timer controls does not secretly disable a running timer. Hiding Advanced remains consistent in the expanded dialog.

## Publishing checks

Add automated HA pytest coverage, frontend component/audio-engine tests with deterministic clocks, CI syntax/lint/type checks, actual-device results and a release checklist. Add a real licence, repository/documentation/issue links, codeowners, brand assets and HACS metadata before public distribution. Do not relabel this alpha as stable solely because the small local checks pass.
