# Changelog

## 0.1.0-beta.5 (unreleased)

0.1.0-beta.3 and 0.1.0-beta.4 were never released; their changes are part of this version
(the version moved on so phones do not keep cached card files).

### Changed

- Expanded dialog: the close button sits at the top left like HA's more-info dialog, with
  the title next to it, and its focus ring stays inside the dialog. In the Advanced view Back
  takes that corner (Escape or a tap outside still close the dialog).

### Added

- Card option `show_step_buttons` (default `true`): hide the −1/+1 buttons of both dials and
  of the compact card's tempo row; the dials move up to close the gap.
- Compact card: a timer bar like HA's tile feature sliders: full width, 42 px like the buttons,
  rounded, fill in the timer arc's colours over a tinted track, smooth movement, with the
  remaining time and "Ends …" inside it; option `show_timer_bar` (default `true`).
- Compact card: a tap anywhere that is not a control opens the full card, like a Tile card
  (not after a drag or scroll).

## 0.1.0-beta.2 (2026-10-21)

First regular (non-pre-release) beta, so HACS offers a version instead of a commit.
No code changes since 0.1.0-beta.1.

- README: screenshots, CI/HACS/release badges, absolute image and link URLs so the README
  renders in HACS.

## 0.1.0-beta.1 (2026-10-21)

First public version (pre-release). Tested on Android (Galaxy S21 Ultra), iPhone 14 (iOS 27)
and iPad Pro (iPadOS 26) in the Companion app, HA 2026.10.1/2026.10.2.

### Highlights since the first alpha

- **Install:** HACS custom repository; the card resource is registered (and kept at the
  current version) automatically in storage-mode dashboards.
- **Play from anywhere:** Start in the card, or Play on a native Tile, in more-info or on the
  device page. The phone you tap on plays; automations use the selected device.
- **Card:** full card with BPM and timer dials (drag the handle only), a fifth "Advanced"
  button, count-in status, smooth countdown; a compact card in Tile style (inline or bottom
  controls, pulsing BPM number); primary/secondary colour options; a working visual editor.
- **Sound:** every click at −1 dBFS (accent by pitch), volume slider that works on iOS.
- **iOS:** sound with the silent switch on, recovery after another app took the audio,
  haptics through the Companion app (needs iOS haptic feedback enabled).
- **HA:** media_player `phase` attribute (`count_in`/`running`), session events, expected
  finish sensor; optional diagnostics (Advanced toggle, debug log).

### Details

The per-alpha notes below record every change.


## 0.1.0-alpha.9

From the alpha.8 re-test (everything passed on the iPhone; haptics need iOS haptic feedback
enabled).

### Changed

- Louder: every sound peaks at −1 dBFS at volume 100 % (was about −15 dBFS for the accent,
  −19 to −20 dBFS for the rest). The accent now differs by pitch only.
- Diagnostics are behind an Advanced → "Show diagnostics" toggle (off by default, per page);
  the HA log line is debug level.

## 0.1.0-alpha.8

From the alpha.7 iOS re-test (silent switch, volume and Tile play confirmed fixed).

### Fixed

- No sound after another app (e.g. YouTube) took the audio on iOS: a stuck AudioContext is
  replaced by a fresh one inside the tap, the playback session re-applied.
- Advanced → Diagnostics did not open on iOS; it is now always visible.

### Changed

- Test vibration cycles through the iOS app's haptic types; diagnostics show the type sent.
- Idle timer arc uses the same muted colour as the idle BPM arc; the running countdown moves
  smoothly (every frame; whole seconds with reduced motion).

## 0.1.0-alpha.7

From the first iPhone 14 / iPad Pro test (Companion app).

### Fixed

- iPhone silent switch muted the metronome: the output page now uses the "playback" audio
  session (other apps' audio pauses while it plays).
- iOS haptics: sent as the app's own external-bus `haptic` message, preferred over any
  `navigator.vibrate` inside the iOS app; haptics and beat dots no longer stop when the
  system pauses the sound.
- Volume slider: draggable on iPad, no second (native) handle on iPhone.

### Added

- Advanced → Haptics "Test vibration"; Advanced → Diagnostics, also logged once to HA when a
  page takes output.

## 0.1.0-alpha.6

From the owner's alpha.5 re-test.

### Added

- Count-in state: the card says "Count-in" until the first exercise beat, then "Active";
  `media_player` attribute `phase` (`count_in` / `running`, `null` when idle) is flipped by
  HA at the end of the count-in. The state stays `playing`.

### Changed

- The BPM and timer dials move only when the handle is dragged (48 px hit circle); a tap
  or swipe on the arc changes nothing, and a swipe there scrolls the page or dialog.
- Expanded dialog: the close button is on the title row and the dial starts right below the
  title.

## 0.1.0-alpha.5

From the owner's alpha.3/alpha.4 re-test.

### Added

- Native Tile, more-info and device-page Play works on a page that never tapped Start: the
  card module arms the page on every tap (shared AudioContext resumed in the gesture,
  `metronome/arm` to HA) and keeps standby subscriptions; a native play from the same user
  within 3 s selects the tapped page, even over another ready device. Automations unchanged.
- Card option `features_position` (`bottom`/`inline`) for the compact card.

### Changed

- Compact card in HA Tile style (icon circle, tile typography, 42 px feature buttons); no
  expand button: tap the icon/name to open the full card. The BPM number pulses and glows on
  each beat (respects `feedback` and reduced motion).

## 0.1.0-alpha.4

From the owner's alpha.3 re-test (everything else passed).

### Added

- Card option `show_title` (default `true`) hides the name; the dialog opened from a compact
  card keeps it.

### Changed

- The timer's "Ends …" time uses a 24-hour clock unless the HA profile's time format is set
  to 12-hour explicitly.

## 0.1.0-alpha.3

Second pass after the owner's Android re-test of alpha.2 (which confirmed the alpha.2 fixes).

### Changed

- Advanced is a fifth 48 × 48 button in the transport row (after Timer) instead of its own
  row; `show_advanced: false` hides it. Narrow cards shrink the gaps (12/8/4 px), never the
  buttons. The compact card keeps four buttons; its expand control opens the full view.
- The device line under the card title is gone. Advanced has an **Output** group: This
  device / Another device (HA user) / No device selected, and **Play on this device**
  (selects this page without starting; only while idle, like Start). The compact card says
  "Active on another device" while a session plays elsewhere. The websocket snapshot carries
  `output_user` for this.
- Timer dial text stays inside the arc at 280–500 px cards with 130 % text zoom: hint
  "Dial: 5 s – 2 min", one centred column below the −1/+1 buttons, sizes follow the dial.

### Fixed

- Card editor: Save stayed greyed out and no option had any effect (the change listener was
  assigned to `ShadowRoot.onchange`, which does not exist). The editor now uses HA's ha-form
  with selectors (entity selector filtered to Metronome media players) and writes only
  non-default options.
- Dragging the timer handle updates the hours/minutes/seconds fields live (like BPM); both
  dials keep the dragged value until HA confirmed it.

### Added

- Card options `primary_color` and `secondary_color` (any CSS colour; theme colours by
  default; validated in the editor).
- `checks/cdp/`: editor round trip, colours, timer text geometry, output group, timer drag.

## 0.1.0-alpha.2

Fixes from the owner's first phone test (Samsung Galaxy S21 Ultra, Android, HA Companion app).

### Fixed

- Dragging the BPM or timer handle on a touch screen no longer scrolls the page; a swipe
  that starts outside the arc still scrolls.
- The BPM number's focus box is only as wide as the number (timer fields likewise), with a
  subtle HA-style focus treatment. While typing, the arc and tempo marking preview the typed
  value; an invalid value hides the marking instead of contradicting the number. Enter or
  blur commits, Escape reverts.
- Native media-player actions (more-info, Tile, device page, automations) failed with
  "Tap Start ..." after the page had been hidden once (screen off, app switch) or the
  websocket had reconnected. A page that tapped Start now selects itself again when it is
  visible/connected again, unless another device was selected meanwhile. Playback never
  auto-resumes; a page that never tapped Start is never selected. Clearer error text.
- Advanced view: one 48 px control style for dropdowns and toggles, single-line labels,
  one column below 420 px card width, Haptics row aligned; Advanced entry button centred at
  content width; Sections minimum is the full section (compact card: 9 columns).
- Relative module imports carry the version query, so phones do not keep stale submodules
  after an update (HA serves these files without Cache-Control).

### Added

- Count-in beats light the dots and glow in the theme's accent colour.
- iOS Companion app haptics through HA's frontend `haptic` event (light/medium/heavy) where
  `navigator.vibrate` is missing; `navigator.vibrate` (20/40/70 ms) stays primary elsewhere.
  Hint that silent/mute mode can turn vibration off (the Android "no vibration" report was
  the phone's Samsung "Mute" mode).
- Brand icon (white `mdi:metronome` on a teal tile).
- `checks/cdp/`: Chrome DevTools scripts for a test HA instance (touch drag, BPM input,
  output readiness, layout, haptics, count-in colours).

## 0.1.0-alpha.1

Repository import of the Codex-written alpha, with Home Assistant tests and fixes.

### Fixed

- Setup no longer fails when the stored settings file holds something other than a settings
  object; invalid stored values are logged and skipped.
- Pausing shortly after resuming no longer adds up to 200 ms (the start lead) to the remaining
  time on every pause/resume cycle, in the backend and in the card's countdown.
- Rejected card actions (claim while another device plays, expired subscription, locked
  setting, wrong entity) are no longer logged as errors in the HA log. Native entity actions
  report them as validation errors.
- A failed platform setup no longer leaves the lease timer running.

### Added

- HA test suite (pytest-homeassistant-custom-component, HA 2026.10.1), CI workflows (tests,
  ruff, frontend checks, hassfest, HACS), `hacs.json`, manifest links and codeowner.
