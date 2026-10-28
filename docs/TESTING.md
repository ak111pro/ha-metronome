# Validation record and next-stage test plan

## Browser suite on beta.9 (2026-10-28, ha-dev on the current stable HA image)

All 19 scripts in `checks/cdp` pass in headless Chromium 155 at phone widths, including the new
`beta_items.py` for the beta.3–beta.9 changes that had only been checked on the owner's phone
(compact timer bar, tap highlight, BPM in the header without -1/+1, quiet connection notices,
close button at the top left). Found and fixed on the way: the expanded dialog opened 8 px
scrolled on a 360×640 phone with the timer open. Harness fixes: HA's service worker reloaded
the test page ~40 s after the first load in a fresh profile (now disabled in the checks);
`haptics.py` and `dialog.py` expectations updated to the intended beta.3 behaviour.

## Status (2026-10-21, 0.1.0-beta.1)

| Area | Status |
| --- | --- |
| Backend in HA (pytest) | **Verified**: 82 tests, HA 2026.10.1 harness |
| hassfest 2026.10.1 | **Passes** without warnings (run locally) |
| HACS action | Not run yet (runs in CI once the repository is public) |
| Live HA instance (websocket, REST, restart) | **Verified** on the ha-dev test instance (HA 2026.10.2) |
| Card in a real browser | **Rendered and driven** in headless Chromium 155 (no audible output) |
| Android Companion app | **Owner tests** (Galaxy S21 Ultra, 2026-10-20): alpha.1 audio and vibration work (vibration needs the phone out of Samsung "Mute" mode); alpha.2 re-test confirmed its fixes and asked for the changes in alpha.3 (below); alpha.3/alpha.4 re-test passed except the requests done in alpha.5 (below); alpha.5 re-test: Tile play and compact card OK, three requests done in alpha.6 (below); alpha.6 onwards: all passed (alpha.9 final) |
| iOS Companion app | **First test** (iPhone 14 iOS 27.0.1, iPad Pro iPadOS 26.7.1): iPad sound OK, volume not draggable; iPhone silent (silent switch, confirmed), no haptics, double volume handle — alpha.7 re-test: silent switch, volume, Tile play fixed; haptics still silent on the iPhone (card sends the same external-bus message as HA, cause on the device/app side, under investigation); recovery after YouTube and Diagnostics fixed in alpha.8; **alpha.8/alpha.9: all passed** (see "iOS results") |
| Audio timing, accessibility | **Not tested** — needs real devices |

### iOS results (summary)

| Item | iPhone 14 (iOS 27.0.1) | iPad Pro (iPadOS 26.7.1) |
| --- | --- | --- |
| Sound | Works, also with the ring/silent switch on ("playback" audio session, alpha.7) | Works |
| Haptics | Work through the Companion app once iOS haptic feedback is enabled (Settings → Sounds & Haptics) | No haptic engine (expected) |
| Recovery after another app (YouTube) took the audio | Works (fresh AudioContext in the tap, alpha.8) | – |
| Volume slider | Works, single marker (alpha.7) | Draggable (alpha.7) |
| Tile / more-info Play without Start | Works | – |

### iOS re-test of alpha.8

Everything passed on the iPhone; haptics needed iOS haptic feedback turned on. alpha.9 changes
loudness (−1 dBFS) and puts Diagnostics behind a toggle; browser checks were not run for it
(host swap at 72 %, planned after the production restart). beta.1 adds the automatic card
resource (pytest, and verified on ha-dev: the existing resource updated in place).

### iOS re-test of alpha.7

Fixed: silent switch, volume slider, Tile play. Still open: iPhone haptics (log: haptics=companion,
vibration_on=True, last haptic sent via the external bus, external_bus=True, vibrate_api=False).
Broken, fixed in alpha.8: Diagnostics not visible in the UI; after YouTube had the audio, Start
stopped YouTube but the metronome stayed silent until YouTube was killed.

### First iOS test (alpha.6)

iPad Pro: sound works; no haptics (no haptic engine, expected); other apps' audio or leaving
HA stops it (expected); the volume handle cannot be dragged. iPhone 14: no sound (the silent
switch; sound works with it off) and no haptics even with sound; the volume bar shows a second
thin handle (the native WebKit range thumb). Fixed in alpha.7, haptics root cause still open
(see README → iPhone and iPad; the next test reads Advanced → Diagnostics).

### Owner's Android re-test of alpha.5

Requests, done in alpha.6: "in expanded view a lot space is wasted at the top" (and the timer
arc looked cut off at the dialog's bottom); "Metronome should have a new state when counting
in"; "the bpm and timer bars should be only adjustable via dragging handle and not by tapping
on the bar, to avoid accidental adjustment".

### Owner's Android re-test of alpha.3/alpha.4

Passed apart from these requests, done in alpha.5: "metronome can't be played from the tile
card, if not activated before"; compact view should look like the Tile card, with an inline
option for the first button row; the BPM number should pulse and glow while active; no
maximize button, tapping the card should open it.

### Owner's Android re-test of alpha.2 (Galaxy S21 Ultra, Companion app, ha-dev)

Confirmed fixed: dragging a dial no longer scrolls the page; BPM/timer input focus box
width; native `media_player` play works reliably (selected output survives hide/reconnect);
count-in beats in the accent colour; Advanced view controls consistent.

New requests, done in alpha.3: Advanced as a fifth square button next to Timer; card editor
(Save stayed greyed out, options had no effect — the change listener was never attached);
primary/secondary colour options; timer hint text ran over the timer arc at phone width
(and the h/m/s row at 30:00:32 was tight); hide the "This device" line and handle output in
Advanced; timer fields should follow the handle while dragging, like BPM.

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
- Count-in phase: `phase` attribute flips once at the end of the count-in (state stays
  `playing`), `running` without count-in, pause and stop during count-in leave no stale flip,
  tempo changes during count-in move the flip earlier or later.
- Gesture arming (`tests/test_gesture.py`): a page that sent `metronome/arm` takes output on
  the same user's native play within 3 s, even over a ready owner; no gesture keeps the ready
  owner; arm expires; another user's gesture is ignored; automations (no user) unchanged;
  helpful error without any owner; a paused session resumes on its owner; arming without a
  subscription does nothing.
- `output_user` in the snapshot names the HA user whose page holds the output, follows a
  hand-off and clears on release; it is not an entity attribute.
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

### Browser checks against a test instance (`checks/cdp/`)

Chrome DevTools scripts that drive the real card in headless Chromium against a running HA
(ha-dev). Start `chromium --headless=new --remote-debugging-port=9333 --mute-audio`, then
`METRONOME_TOKEN_FILE=<token file> python checks/cdp/<script>.py` (needs `aiohttp`). They
bypass HA's service worker and the HTTP cache. Results for alpha.2 (Chromium 155, 360 px),
re-run for alpha.3 where noted:

| Script | What it checks | Result |
| --- | --- | --- |
| `touch_drag.py` | Touch drag on the BPM/timer arcs changes the value without scrolling; a swipe from the dial centre scrolls | BPM 100→144, timer 30→51 s, 0 px page movement; centre swipe 95 px (before: BPM drag stopped at 106, timer drag scrolled 81 px) |
| `bpm_input.py` | BPM focus box width, preview while typing, Enter commits, Escape reverts; timer field width | 124 px box (dial 318 px), marking follows typed value, none for 600; fields 52 px |
| `ready_client.py` | Native `media_play` after Start/Stop, view switches, compact dialog, more-info, Advanced, page hidden/visible, websocket reconnect, other HA page, 20 s idle; hidden while playing; a second page | 14/14 (before: 7/11, every hide or reconnect lost the selection) |
| `layout.py` | Transport row = five 48 × 48 buttons on one line inside the card (alpha.3); Advanced controls 48 px, no wrapped/truncated labels, no overflow; card widths 264/280/320/360/440/500 px, light and dark | alpha.3: 0 problems (five buttons fit down to a 258 px card: gaps 12 → 8 → 4 px) |
| `haptics.py` | `navigator.vibrate` path, simulated iOS Companion `haptic` path (Long → heavy), hidden without either | passes |
| `editor.py` (alpha.3) | HA's real dashboard editor (edit dashboard → edit card): every option through the actual ha-form controls (switches, dropdowns, typed text) → Save enabled, HA's card config/YAML has it, preview changes; defaults never written; colours (name, hex, rgb, hsl, var(), invalid text rejected with an inline error, cleared = removed); back at defaults the YAML is `type` + `entity`; one change saved for real, dashboard restored | 22/22 (before the fix: Save stayed disabled, config unchanged) |
| `colours.py` (alpha.3) | Computed colours of a `primary_color: teal` / `secondary_color: "#9c27b0"` card (handle, Tap, dots, pressed Timer = teal; count-in dots and selected timer field = purple) vs a default card (theme colours), light and dark | 0 problems |
| `timer_text.py` (alpha.3) | Every text line in the timer dial (Range rects; input digits) inside the arc's inner circle (r 133/320 − 2 px) and below the −1/+1 buttons; card widths 264–500 px; 100 % and 130 % text (Android text zoom emulated by scaling all font sizes); 30:00:32, 45 s, longest finish label | 0 of 36 outside (before: 12 of 24, worst 146 px vs 131 px) |
| `output.py` (alpha.3) | Title only (no device line); Advanced → Output on two pages: No device / This device / Another device (user), Play on this device without Start, disabled while the other page plays, compact line "Active on another device", hand-off | 9/9 |
| `timer_drag.py` (alpha.3) | Timer fields sampled 20 ms after each touch move follow the handle; after release fields = HA value with no flick back; BPM drag for comparison | 20/20 live (before: 0/20), BPM 10/10 |
| `native_play.py` (alpha.5) | View with only a native Tile: mouse and touch tap on the Tile's Play, and more-info Play after a reload, start audio on a page that never tapped Start (shared AudioContext running, tones scheduled, HA playing, page owner); service call without gesture fails helpfully; idle context suspends ~5 s after a gesture | 9/9 |
| `compact.py` (alpha.5) | Tile-style compact card at 264–500 px (36 px icon circle, 42 px / 12 px-radius features, nothing outside, no expand button, inline beside the name above 340 px, else bottom); icon/name button opens the dialog by Enter and tap; BPM pulse keyframes per feedback mode, accent stronger, count-in colour, reduced motion without scale; real session from the Tile pulses the number | all pass |
| `dialog.py` (alpha.6) | Expanded dialog at 360x800, 384x854, 412x915 and 360x640, light/dark, timer open: X on the title row, dial 56 px below the top, timer fits or a swipe on an arc scrolls to its end; Advanced header clear of the X and scrollable | 32/32 |
| `handle_only.py` (alpha.6) | BPM and timer dial: tap/click on the track and a tap on the handle change nothing (HA value, number/fields, knob); swipe from the track scrolls; handle drag changes the value without scrolling | 10/10 (old build 4/10) |
| `ios_fixes.py` (alpha.7, Chromium only) | Volume: no native range input; tap, mouse drag, touch drag, keyboard; marker inside the fill at 0/1/5/10/100 %. Context suspended while playing: session continues, beats and haptic pulses continue, "No sound" message; a tap resumes tones. Diagnostics content; Test vibration | see report |
| `ios_recovery.py` (alpha.8) | Simulated stuck context (closed; resume() never settles): Start/tap replaces it and plays; Diagnostics visible; Test vibration cycles the iOS types | 5/5 |
| `timer_arc.py` (alpha.8) | Idle timer arc muted like the BPM arc, outside 5–120 s grey, full colour running; 30 different arcs in 30 frames, whole seconds with reduced motion; frame loop stops after Stop | 6/6 |
| `count_in.py` | Count-in dots/glow in `--accent-color`, exercise beats in the active colour, also with reduced motion; status "Count-in" → "Active" (full and compact), HA `phase` count_in → running with state `playing` (alpha.6) | passes |

The iOS path is simulated (no `navigator.vibrate`, a stub external bus); HA's frontend
forwarding of the `haptic` event to the app was read from frontend 20260930.4
(`attachExternalToApp`), not observed on an iPhone.

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
