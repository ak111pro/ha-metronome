# Changelog

## 0.1.0-alpha.2 (unreleased)

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
