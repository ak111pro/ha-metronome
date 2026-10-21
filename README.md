# Home Assistant Metronome

[![Validate](https://github.com/ak111pro/ha-metronome/actions/workflows/validate.yml/badge.svg)](https://github.com/ak111pro/ha-metronome/actions/workflows/validate.yml)
[![Tests](https://github.com/ak111pro/ha-metronome/actions/workflows/tests.yml/badge.svg)](https://github.com/ak111pro/ha-metronome/actions/workflows/tests.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Release](https://img.shields.io/github/v/release/ak111pro/ha-metronome?include_prereleases)](https://github.com/ak111pro/ha-metronome/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/ak111pro/ha-metronome/blob/main/LICENSE)

**0.1.0-beta.6 · beta, experimental · AI-assisted (built with Codex and Claude) · MIT licence**

A custom integration and dashboard card that play a metronome on the phone or browser you are
holding. Home Assistant keeps the shared settings and session; the clicks are synthesized on
the foreground device (Web Audio), not on the server.

> **Why this exists:** I got tired of looking for a good free metronome app. I mainly use one for my calisthenics workouts: during handstands or back levers you can't really look at a stopwatch, so I count seconds with a metronome while I train. That's also why it comes with a timer, as a double check in case I lose count of the seconds. It's just as useful for music practice. And all of it runs in Home Assistant, with HA's native look.

**Requirements:** Home Assistant **2026.10.1** or newer.

**Tested on** Home Assistant 2026.10.1 (test suite) and 2026.10.2 (live), with the Companion
app on an Android phone (Samsung Galaxy S21 Ultra), an iPhone 14 (iOS 27.0.1) and an iPad Pro
(iPadOS 26.7.1), plus desktop Chromium. Details in [TESTING.md](https://github.com/ak111pro/ha-metronome/blob/main/docs/TESTING.md). This is a
beta: expect rough edges, and please report issues.

## Screenshots

<table>
  <tr>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/full-idle-light.png" width="260" alt="Full card, idle, light theme: tempo dial at 96 BPM with Tap, transport row and timer dial"><br><sub>Full card · idle · light</sub></td>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/full-playing-dark.png" width="260" alt="Full card playing in dark theme: Active status, beat dots and the timer counting down with its finish time"><br><sub>Playing with timer · dark</sub></td>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/advanced-dark.png" width="260" alt="Advanced view: rhythm, sound, output, haptics and diagnostics settings"><br><sub>Advanced settings</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/compact-tile-light.png" width="260" alt="Compact cards (bottom and inline) next to native HA Tile cards, light theme"><br><sub>Compact (bottom / inline) next to native Tiles</sub></td>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/compact-tile-dark.png" width="260" alt="Compact cards next to native Tile cards, dark theme"><br><sub>Compact · dark</sub></td>
    <td align="center"><img src="https://raw.githubusercontent.com/ak111pro/ha-metronome/main/docs/images/full-idle-dark.png" width="260" alt="Full card, idle, dark theme"><br><sub>Full card · idle · dark</sub></td>
  </tr>
</table>

## What is included

- Named integration instances with a media player, tempo/duration numbers, meter/count-in selects, timer/accent switches, session events and expected-finish timestamp.
- Full and compact cards, visual configuration editor, and an expanded dialog from the compact card.
- Tempo 1–200 BPM, ±1 buttons, tap tempo, tempo markings, beat dots and optional diffuse glow.
- 2/4, 3/4, 4/4 and 6/8. In 6/8, BPM counts **two dotted-quarter beats per bar**. Subdivisions are not part of this version.
- Optional countdown, 5–120-second dial, separate hours/minutes/seconds fields up to 99:59:59, pause/resume, actual expected finish time, count-in and completion sound.
- Volume (a drag-anywhere 48 px slider with keyboard support), mute, accent and capability-dependent vibration. Haptic pulse length is available; vibration intensity is not exposed. See [Haptics](#haptics).
- Web Audio scheduling on the selected foreground device. Home Assistant manages state and settings; it does not synthesize or stream the beats.

## Install

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/ak111pro/ha-metronome`,
   category **Integration**.
2. Download **Metronome** in HACS and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Metronome.** Give the instance a name;
   several instances are supported.
4. The card's JavaScript is registered as a dashboard resource **automatically**
   (`/metronome/metronome-card.js?v=<version>`, updated on every start, never duplicated).
   Reload the dashboard page (or the app) once.
5. Add a **Metronome** card with the card picker, or:

   ```yaml
   type: custom:metronome-card
   entity: media_player.metronome
   ```

   Use the media player your instance created.
6. On the phone or browser that should play, tap **Start** (or Play on a Tile, see below) and
   keep the app in the foreground.

**Dashboard resources in YAML mode** (`lovelace: resource_mode: yaml`): the integration cannot
add the resource and logs the URL instead. Add it yourself as a JavaScript module, e.g.
`examples/resource.yaml`:

```yaml
lovelace:
  resources:
    - url: /metronome/metronome-card.js?v=0.1.0-beta.6
      type: module
```

### Manual

Copy `custom_components/metronome` to `<config>/custom_components/metronome`, restart, then
continue with step 3 above. There is no build step and nothing to install on the server; the
card modules are served by the integration.

Removing the last Metronome instance also removes the card resource.

## Known limits

- Foreground only: leaving the app, locking the screen or another app taking the audio stops
  the metronome; nothing plays in the background and sessions never resume automatically.
- iPhone: the ring/silent switch is handled (the output page uses the "playback" audio
  session, which pauses other apps' audio while it plays). Haptics need iOS haptic feedback
  turned on (Settings → Sounds & Haptics, see [Haptics](#haptics)).
- Haptics depend on the device: Android `navigator.vibrate`, iOS through the Companion app;
  no haptic engine (iPad) means no vibration.
- YAML-mode dashboard resources need the manual resource step above.
- No speaker or casting output: sound always comes from a page's own audio.

## Playback and device selection

**“Current device” means the phone or browser page you tap on**: Start in the metronome card,
or Play on a native Tile, in more-info or on the device page. It is not a speaker entity.

**Native play without the card.** The card's JavaScript is a dashboard resource, so it runs on
every dashboard page, also pages without a metronome card. On every tap or key press it
(1) resumes the page's AudioContext inside that gesture and (2) sends `metronome/arm` to HA,
in the capture phase, so it arrives before the Tile's own `media_player.media_play` on the
same connection. Each page also keeps a standby subscription for every metronome instance.
When `media_play` (or `media_play_pause`) arrives while the session is idle and a page of the
**same HA user** that calls it was tapped within 3 seconds, that page takes output and plays,
even if another device was ready: the device you tapped on wins. Otherwise the already
selected device plays; otherwise the call fails with "No device is ready to play. Tap Start
once …". A paused session resumes only on the device that holds it. Automations and scripts
have no gesture and use the selected device. The AudioContext is suspended again about 5 s
after the last tap unless this page is the selected output.

**Advanced → Output** shows where the sound comes from: *This device* (this page plays),
*Another device (name)* (another page holds the output; the name is the HA user logged in
there, sent by the integration as `output_user` to the card only, not as an entity
attribute), or *No device selected*. **Play on this device** selects this page without
starting, with the same rule as Start: only while the session is idle (stop it first to move
playback). There is no speaker picker; output is always a page's own audio. The card title
has no device line; the compact card adds "on another device" to its state while a session
plays elsewhere.

After that gesture, native HA controls and automations can control that selected, connected client. Automations cannot unlock audio in a fresh browser, choose a remote phone implicitly, or start a closed Companion app. The selected client remains ready after Stop while its page stays visible. Opening the card elsewhere does not duplicate sound. To move output while a session is active or paused, stop it first, then tap Start on the other device.

Leaving the app, locking the screen, losing the connection or suspending its audio interrupts playback. There is no background-playback guarantee and no automatic resumption of a session. A heartbeat lease provides a server-side fallback if a client vanishes. Navigation between dashboard views, the compact card's dialog, HA more-info dialogs and other HA pages (for example the device page) within the same HA page keep the engine and the selection alive.

When a page that already tapped Start becomes visible again or its connection to HA comes back, it selects itself again as output **without** a new tap, provided no other device was selected meanwhile and the browser lets it resume audio. Playback itself does not resume. If the browser refuses (for example after an OS audio interruption), the card asks for Start again. A page that was never tapped (Start, Play on this device, or a native Play) is never selected.

## Timer behavior

The timer begins **after** count-in. Its dial edits 5–120 seconds; the fields accept 1 second through 99:59:59. A value outside the dial range greys out only the editing dial. During playback, the arc becomes a remaining-time indicator for any duration and its handle and fields are locked.

Pause is available only when the timer is enabled. It preserves the remaining time and beat phase; Start resumes it and recalculates the expected finish time. Stop resets the session to the configured duration. A natural finish plays a short chime unless muted. An interruption never plays the completion chime.

`Ends …` is an actual clock time in the viewing client's local timezone, as a 24-hour clock (12-hour only when the HA profile's time format is set to 12-hour). A date is added when it ends on a different day. The timestamp sensor stores the corresponding UTC instant for HA to display. Tempo can change live without extending an already-running countdown. Changing count-in tempo changes when the exercise begins, so it also changes its expected finish.

## Card options

| Option | Default | Values / meaning |
| --- | --- | --- |
| `entity` | required | The integration's `media_player` entity |
| `name` | entity name | Optional display name |
| `layout` | `full` | `full`, `compact` |
| `show_title` | `true` | Show the name above the dial (compact: above the state line). The expanded dialog always shows it |
| `show_tempo` | `true` | Show the tempo marking |
| `show_signature` | `true` | Show the meter below BPM |
| `show_timer` | `true` | Show timer controls and countdown |
| `show_advanced` | `true` | Show the Advanced button (fifth button of the transport row) |
| `show_step_buttons` | `true` | Show the −1/+1 buttons (BPM and timer dials, compact tempo row). `false` hides them; tempo then changes by dragging the handle, typing or Tap, the timer by its fields; the compact card keeps the BPM number |
| `show_timer_bar` | `true` | Compact card: a slim countdown bar (28 px pill, fill in the arc colours over a tinted track, smooth movement) with the remaining time and "Ends …" inside it in the same 14 px text (only the remaining time, centred, if both do not fit); `false` shows the one-line text instead. Only while the timer is on and `show_timer` is true |
| `feedback` | `dots_glow` | `dots`, `dots_glow`, `off`. Compact card: the BPM number pulses (`dots`) and glows (`dots_glow`) on each beat |
| `features_position` | `bottom` | Compact card: `bottom` (tempo row below the name) or `inline` (beside the name, like the Tile card's features position; falls back to bottom on cards of 340 px and narrower) |
| `timer_display` | `remaining_finish` | `remaining`, `remaining_finish` |
| `primary_color` | theme | Any CSS colour, see [Colours](#colours) |
| `secondary_color` | theme | Any CSS colour, see [Colours](#colours) |

**Compact card** follows HA's Tile card (a tap anywhere on it that is not a control opens the full card): a coloured icon circle, name and state line, and
42 px feature-style buttons (−/BPM/+, then Start, Stop, Pause, Timer). Tap the icon or name
(or focus it and press Enter) to open the full card in a dialog. While playing, the BPM number
pulses gently on each beat in the primary colour (stronger on the accented first beat; the
secondary colour during count-in); with reduced motion it only changes colour/glow. The full
card keeps a stable number and its 48 px controls.

Visibility settings hide controls; they do not change the shared session. A hidden timer can still be enabled by another card or automation. Tempo, duration, count-in, meter, accent, volume and mute belong to the integration instance, not the card configuration. Vibration preferences are local to the current page and reset on reload.

The card uses `ha-card`, `ha-icon`, HA theme tokens, 48px primary controls and semantic keyboard-accessible inputs. Its thermostat-like dials, menus and expanded dialog are custom controls. It is visually aligned with HA; it is **not an upstream HA card or a guarantee that every control is HA's own internal component**. Native-theme and accessibility checks remain part of the handoff.

## Colours

The card follows the HA theme. Two optional card options override it for one card:

| Option | Colours | Default |
| --- | --- | --- |
| `primary_color` | BPM and timer arcs (active part and the muted idle arc), dial handles, countdown progress, the "Active" status, Tap, beat dots of normal beats and the glow, the pressed Timer button, toggles that are on (Accent, Mute, Vibration), volume fill, focus rings and the BPM input highlight | the theme's media-player active colour (`--state-media_player-active-color`, which falls back to `--primary-color`) |
| `secondary_color` | Count-in beats (dots and glow) and the selected hours/minutes/seconds timer field | the theme's accent colour (`--accent-color`) |

Values are any CSS colour: names (`teal`), hex (`"#16809e"`, `"#fff"`; quote them in YAML),
`rgb()`/`hsl()`, or a theme variable (`var(--red-color)`). The card editor checks each value
with the browser's `CSS.supports('color', …)`, shows an error for anything else and does not
save it; a YAML value that is not a colour shows a card error. Leave an option empty for the
theme default. A theme can also set `metronome-primary-color` / `metronome-secondary-color`
for every metronome card.

```yaml
type: custom:metronome-card
entity: media_player.practice
primary_color: teal
secondary_color: "#9c27b0"
```

## Haptics

Vibration is off by default and is a local, per-page setting (Advanced → Haptics).

- **Android app and Android browsers:** `navigator.vibrate` with the exact pulse lengths Short/Medium/Long = 20/40/70 ms.
- **iOS Companion app:** the card sends the app the same external-bus message HA's own frontend sends for its `haptic` event (`{type: "haptic", payload: {hapticType}}`, HA 2026.10 `attachExternalToApp`), directly on `hass.auth.external`. This is used whenever the iOS app's bus is present, even if WebKit exposes a `navigator.vibrate`. Short/Medium/Long map to the app's `light`/`medium`/`heavy` haptics; the app decides their strength.
- **Other browsers without vibration** (e.g. Safari on iOS): the Haptics section is hidden.

**Test vibration** (Advanced → Haptics) sends one pulse on its own, cycling through the iOS
app's haptic types (light, medium, heavy, success, warning, failure, selection) on each press. Haptics run on their own
clock: they continue when the system pauses the sound (see below).

**iPhone:** the app's haptics follow iOS's own haptic settings. If nothing vibrates (Test vibration included), open iOS Settings → Sounds & Haptics and turn on haptic feedback (System Haptics; on the tested iPhone 14 with iOS 27, enabling keyboard haptic feedback there made it work). The iPad has no haptic engine.

A phone in silent/mute/vibrate-off sound mode (for example Samsung's "Mute" mode) can suppress app vibration entirely; the card says so under Haptics. There is no intensity control.

## Loudness

The clicks are synthesized (sine tones, no sound files). At volume 100 % every sound peaks at
**−1 dBFS** (0.891): normal beat 1000 Hz, accented first beat 1500 Hz, count-in 800 Hz and
the two finish-chime tones. The accent is distinguished by **pitch**, not level. The volume
slider scales linearly from there; mute is 0. Tones never overlap (beats are at least 0.3 s
apart, the chime tones are sequential and start after the last beat has ended), so nothing
sums above −1 dBFS. `checks/check_frontend.mjs` asserts this from the constants.

## iPhone and iPad (audio session)

iOS plays Web Audio in the Companion app with the "ambient" audio session by default, which
the **ring/silent switch mutes** (confirmed on an iPhone 14; the iPad has no switch). The page
that becomes the output therefore sets `navigator.audioSession.type = "playback"` (WebKit
Audio Session API, iOS 17+) inside the tap, like a music app: the metronome sounds with the
switch on silent, and **other apps' audio (Spotify, YouTube) pauses while it is the output**.
When the page stops being the output it goes back to `"auto"`. On iOS without that API a
looping silent `<audio>` element started in the tap does the same. Other browsers are
unchanged. Leaving HA or another app taking the audio still stops the metronome.

When the system pauses the sound while playing (WebKit's `interrupted` state: a call, Siri,
another app; or `suspended`), the session keeps running: beat dots and haptics continue on a
silent clock, the card says "No sound: …", and the next tap anywhere resumes the sound.
`resume()` is never awaited for more than 1.5 s. If another app left the context "interrupted" or dead (seen after
YouTube on an iPhone), the next tap or Start replaces it with a fresh AudioContext and
re-applies the playback session; Diagnostics count the contexts and record the replacement.

**Advanced → Show diagnostics** (off by default, local to the page like Vibration) shows a
table with the AudioContext state and sample rate, the audio session type, whether this page
is the output, the haptics path, the app type, the last haptic and the last audio event; it
only refreshes while shown. A page that takes output also sends this once to HA, logged at
**debug** level: enable debug logging for `custom_components.metronome` to see it in the HA
log (HA user name only, nothing else personal).

## Entities and automations

| Entity | Purpose |
| --- | --- |
| `media_player.<name>` | Play, pause, stop, volume and mute; exposes BPM and meter attributes. State stays `playing` during the count-in; attribute `phase` is `count_in` until the first exercise beat, then `running` (`null` when idle), flipped by HA at the exact moment (also after pause/resume or tempo changes during the count-in) |
| `number.<name>_tempo` | 1–200 BPM |
| `number.<name>_timer_duration` | Configured seconds, 1–359999 |
| `select.<name>_time_signature` | 2/4, 3/4, 4/4, 6/8 |
| `select.<name>_count_in` | Off, 1 bar, 2 bars |
| `switch.<name>_timer` | Enable optional timer |
| `switch.<name>_accent_first_beat` | Accent the first beat |
| `event.<name>_session` | started, paused, resumed, stopped, finished, interrupted |
| `sensor.<name>_expected_finish` | Timestamp while the timer is running; unknown otherwise |

Entity IDs above are illustrative. Use the actual IDs assigned by HA. Standard domain actions are used; no custom per-beat services or events are sent. See `examples/automation.yaml` and `examples/native-tile.yaml`.

The countdown has one owner in this integration. A separate HA `timer` helper is deliberately not created. Native Tile cards work with the media player and open its **standard HA media-player more-info**. The full custom controls open from the compact metronome card; this package does not replace more-info globally.

## Development and validation

The backend is Python using HA's APIs. Frontend modules have no build dependencies. `package.json` exists only to mark modules and expose the small helper check.

```sh
python3 checks/check_model.py
node checks/check_frontend.mjs
pip install -r requirements_test.txt   # Python 3.14
pytest -q
ruff check custom_components tests checks && ruff format --check custom_components tests checks
```

The two small checks cover pure countdown/state transitions and frontend math. `tests/` runs the integration inside Home Assistant (config flow, lifecycle, entities, countdown with frozen time, websocket ownership and permissions). None of them measure audio accuracy or Companion behavior. Read [TESTING.md](https://github.com/ak111pro/ha-metronome/blob/main/docs/TESTING.md) before relying on it; device results are summarised there. Licensed under the MIT licence (see [LICENSE](https://github.com/ak111pro/ha-metronome/blob/main/LICENSE)).

## Credits

The brand icon (`custom_components/metronome/brand/`, source `docs/brand/icon.svg`) draws the `mdi:metronome` glyph from [Material Design Icons](https://pictogrammers.com/library/mdi/) by Pictogrammers (`@mdi/svg`), licensed under the [Apache License 2.0](https://github.com/Templarian/MaterialDesign-SVG/blob/master/LICENSE), in white on a rounded teal tile.
