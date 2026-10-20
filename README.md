# Home Assistant Metronome

**0.1.0-alpha.5 · native Tile play and a Tile-style compact card after the Android re-tests; still for review and device testing**

A custom integration and dashboard card that play a metronome on the foreground phone or browser. Target environment: Home Assistant Core **2026.10.1**, Docker on a Raspberry Pi 4 (8 GB), with Android and iOS Companion apps.

This repository contains the integration, the card, installation examples, an HA test suite and the original [handoff](docs/HANDOFF.md). The backend is tested with Home Assistant 2026.10.1 and was run on a test instance; the card has been rendered in a desktop browser. It has **not yet been tested on either Companion app** (see [TESTING.md](docs/TESTING.md)). It is not yet a public release or a HACS package.

## What is included

- Named integration instances with a media player, tempo/duration numbers, meter/count-in selects, timer/accent switches, session events and expected-finish timestamp.
- Full and compact cards, visual configuration editor, and an expanded dialog from the compact card.
- Tempo 1–200 BPM, ±1 buttons, tap tempo, tempo markings, beat dots and optional diffuse glow.
- 2/4, 3/4, 4/4 and 6/8. In 6/8, BPM counts **two dotted-quarter beats per bar**. Subdivisions are not part of this version.
- Optional countdown, 5–120-second dial, separate hours/minutes/seconds fields up to 99:59:59, pause/resume, actual expected finish time, count-in and completion sound.
- Volume, mute, accent and capability-dependent vibration. Haptic pulse length is available; vibration intensity is not exposed. See [Haptics](#haptics).
- Web Audio scheduling on the selected foreground device. The Pi manages state and settings; it does not synthesize or stream the beats.

## Install for testing

1. Copy the entire `custom_components/metronome` directory into the Home Assistant configuration volume, at `/config/custom_components/metronome` **inside the container**. Use the host directory that is already bind-mounted to `/config`; do not assume the host path is also `/config`.
2. Restart Home Assistant, then add **Metronome** under **Settings → Devices & services → Add integration**. Give the instance a name. Multiple instances are supported.
3. Add a dashboard resource of type **JavaScript module** with this URL:

   ```text
   /metronome/metronome-card.js?v=0.1.0-alpha.5
   ```

   Dashboard resources may require Advanced Mode in the user profile. For YAML-managed resources, use `examples/resource.yaml` in the existing Lovelace resources configuration. Do not create a second conflicting Lovelace configuration.

4. Add a **Metronome** card using the visual card picker, or paste:

   ```yaml
   type: custom:metronome-card
   entity: media_player.metronome
   ```

   Replace the entity ID with the media player created by your instance. HA chooses the actual ID from the device name and existing entities.
5. On the phone/browser that should play sound, open the card and tap **Start**. This user gesture enables local audio and selects that client as output. Keep the app visible.

There is no separate audio dependency, Node build step or software to install on the Raspberry Pi. The JS modules are bundled inside the integration and served by HA. Refresh the frontend after replacing files or reloading the integration.

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
| `feedback` | `dots_glow` | `dots`, `dots_glow`, `off`. Compact card: the BPM number pulses (`dots`) and glows (`dots_glow`) on each beat |
| `features_position` | `bottom` | Compact card: `bottom` (tempo row below the name) or `inline` (beside the name, like the Tile card's features position; falls back to bottom on cards of 340 px and narrower) |
| `timer_display` | `remaining_finish` | `remaining`, `remaining_finish` |
| `primary_color` | theme | Any CSS colour, see [Colours](#colours) |
| `secondary_color` | theme | Any CSS colour, see [Colours](#colours) |

**Compact card** follows HA's Tile card: a coloured icon circle, name and state line, and
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
- **iOS Companion app** (no `navigator.vibrate` in WebKit): the card sends Home Assistant's own frontend `haptic` event, which HA forwards to the app. Short/Medium/Long map to the app's `light`/`medium`/`heavy` haptics; the app decides their strength.
- **Other browsers without vibration** (e.g. Safari on iOS): the Haptics section is hidden.

A phone in silent/mute/vibrate-off sound mode (for example Samsung's "Mute" mode) can suppress app vibration entirely; the card says so under Haptics. There is no intensity control.

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

The two small checks cover pure countdown/state transitions and frontend math. `tests/` runs the integration inside Home Assistant (config flow, lifecycle, entities, countdown with frozen time, websocket ownership and permissions). None of them measure audio accuracy or Companion behavior. Read [TESTING.md](docs/TESTING.md) before promoting this alpha. Licensed under the MIT licence (see [LICENSE](LICENSE)).

## Credits

The brand icon (`custom_components/metronome/brand/`, source `docs/brand/icon.svg`) draws the `mdi:metronome` glyph from [Material Design Icons](https://pictogrammers.com/library/mdi/) by Pictogrammers (`@mdi/svg`), licensed under the [Apache License 2.0](https://github.com/Templarian/MaterialDesign-SVG/blob/master/LICENSE), in white on a rounded teal tile.
