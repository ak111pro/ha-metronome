# Metronome 0.1.0-beta.2

A metronome with a timer for Home Assistant, played on the phone or browser you are holding.
It was built for counting seconds during calisthenics holds (handstands, back levers) without
looking at a stopwatch, and it is just as useful for music practice.

**Beta.** Same code as 0.1.0-beta.1, now a regular release so HACS shows a version number; the README has screenshots and renders in HACS.

Experimental and AI-assisted (built with Codex and Claude); MIT
licence. Requires Home Assistant **2026.10.1** or newer.

## Highlights

- **Integration + card.** Named instances with a media player, tempo and timer numbers,
  meter and count-in selects, timer and accent switches, a session event entity and an
  expected-finish sensor. Tempo 1–200 BPM, 2/4, 3/4, 4/4, 6/8, count-in, timer up to 99:59:59.
- **Plays on your device.** The clicks are synthesized in the browser (Web Audio); HA keeps
  the shared state. Start in the card, or press Play on a native Tile or in more-info: the
  phone you tap on plays. Automations control the selected device.
- **Native HA look.** Thermostat-style dials (drag the handle), a compact card in Tile style,
  a visual editor, theme colours with optional primary/secondary overrides.
- **iPhone/iPad and Android.** Sound with the iPhone silent switch on, recovery after another
  app took the audio, haptics via `navigator.vibrate` (Android) or the Companion app (iOS).
- **Count-in state** in the card and as the media player's `phase` attribute
  (`count_in` / `running`).

## Install

1. HACS → ⋮ → Custom repositories → `https://github.com/ak111pro/ha-metronome`, category
   **Integration**; download **Metronome**; restart Home Assistant.
2. Settings → Devices & services → Add integration → **Metronome**.
3. The card resource is registered automatically (storage-mode dashboards). Reload the
   dashboard and add a **Metronome** card. YAML-mode resources: add
   `/metronome/metronome-card.js?v=0.1.0-beta.1` as a JavaScript module yourself.

## Tested on

Home Assistant 2026.10.1 (test suite) and 2026.10.2 (live); Companion app on a Samsung Galaxy
S21 Ultra (Android), iPhone 14 (iOS 27.0.1) and iPad Pro (iPadOS 26.7.1); desktop Chromium.

## Known limits

- Foreground only: leaving the app, locking the screen or another app taking the audio stops
  it; no background playback, no automatic resume.
- iPhone haptics need iOS haptic feedback enabled (Settings → Sounds & Haptics). The iPad has
  no haptic engine.
- While the iPhone/iPad page is the output, other apps' audio pauses ("playback" session).
- YAML-mode dashboard resources need the manual step above.
- No speaker/casting output.

See the [README](https://github.com/ak111pro/ha-metronome#readme) and the
[CHANGELOG](https://github.com/ak111pro/ha-metronome/blob/main/CHANGELOG.md) for details.
