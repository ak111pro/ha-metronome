# Validation record and next-stage test plan

## Performed in this build

- Parsed every Python file with Python's AST parser, every JSON file with the JSON parser, and every frontend JS module with Node's syntax checker.
- Ran 10 dependency-free pure-model checks: 6/8 count-in and one-time finish; ordinary pause/resume; pause during count-in; live tempo with fixed exercise deadline; tempo changes during count-in; rejection of pause in indefinite mode; stop/reset; atomic validation; locked session settings; settings-only restart restore.
- Ran frontend helper assertions for 6/8 beat count, representative tempo labels, normal/inverted arc endpoints and intermediate positions, duration formatting, countdown bounds and HTML escaping.
- Checked final package contents and local frontend module references.

These checks passed. They use Python 3.11.4 and Node 24.19.0 in the build environment. **They are not HA integration or device tests.** No HA installation, Companion app, DOM render, audio measurement or end-to-end websocket test was run here. The user's next development stage owns that testing.

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
