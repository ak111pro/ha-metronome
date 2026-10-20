# Changelog

## 0.1.0-alpha.5 (unreleased)

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

## 0.1.0-alpha.4 (unreleased)

From the owner's alpha.3 re-test (everything else passed).

### Added

- Card option `show_title` (default `true`) hides the name; the dialog opened from a compact
  card keeps it.

### Changed

- The timer's "Ends …" time uses a 24-hour clock unless the HA profile's time format is set
  to 12-hour explicitly.

## 0.1.0-alpha.3 (unreleased)

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
