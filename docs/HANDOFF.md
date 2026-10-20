# Handoff to Opus 5.5

## Assignment

Create the repository, perform full testing, fix issues found and continue development from this implementation. The user explicitly assigned repository creation and comprehensive testing to the next stage. This package is a source handoff, not proof of HA or mobile compatibility. No Git repository, remote repository, deployment or live HA change has been made by this build.

Target: **HA Core 2026.10.1 in Docker on Raspberry Pi 4 / 8 GB**, with **Android and iOS Companion apps** as intended clients. OS/Companion/WebView versions have not been supplied. Identify them during device testing, not as a prerequisite to reading this code.

The user's earlier “Not current device for now” was corrected explicitly to **current device only**. Do not introduce HA speaker casting or a fake output selector. Background/locked-screen playback is outside v1 scope.

## Decisions to preserve

- Deliver both an integration and a card. Normal HA entities enable native Tile cards and automations. Full custom controls are in the metronome card and its compact-card dialog; leave native media-player more-info intact.
- Tempo 1–200, ±1 only. No ±5/±10 shortcuts. Centered title/device information, no header icon. Active/Paused/Idle above the numeric value. Below it: `BPM · meter · tempo marking`.
- Tap has no icon. Running dots occupy the Tap location, ease with the sound, and remain tappable. Feedback can be disabled; reduced motion removes scaling and glow. Number size never pulses. The glow has no hard visible boundary.
- A single row of Start, Stop, Pause, Timer; 48px primary controls, no divider lines. Pause disabled in indefinite mode. Advanced is a separate view, with a top-left Back button. Its entry button says only **Advanced**.
- Timer expands downward. Inverted arc, 5–120-second edit range, independent hours/minutes/seconds fields, selected-field ±1. Fields accept 1–359999 seconds. Outside the arc's edit range it is grey; while a session runs, any duration uses a proportional countdown arc without a handle. Count-in precedes the timer. Stop resets; pause saves time; completion chimes unless muted.
- Finish label is a real local clock time. Finish sensor is UTC. Resume recalculates it. State/ownership never auto-resume after restart/interruption.
- Meters 2/4, 3/4, 4/4, 6/8. 6/8 means two dotted-quarter beats per bar. Count-in Off/1/2 bars. Subdivisions, swing, polyrhythms and additional meters are future work.
- Thick horizontal volume slider with marker clipped inside the fill at very low values. Mute also suppresses the finish sound. Vibration only where the browser exposes the capability, with 20/40/70ms duration, no purported intensity control.
- One output owner per instance, multiple named instances, settings persisted in HA, haptics local. No per-beat service calls, state writes or event entities. Session events only.
- Card options: entity, optional name, full/compact, tempo/meter visibility, timer/Advanced visibility, dots/dots+glow/off, remaining/remaining+finish. Runtime settings are not card YAML options. Theme colours/font/time format come from HA.

### Owner decisions after the alpha.2 phone test (override the list above)

- Advanced is a fifth square 48 px button in the transport row (Start, Stop, Pause, Timer,
  Advanced), not a separate entry row; it still opens the separate Advanced view with Back.
- No device line under the title (title only, centred). Output information lives in
  Advanced → Output with "Play on this device" (idle only). Still no speaker picker.
- Card options `primary_color` / `secondary_color` (any CSS colour) may override the theme
  colours for one card; defaults remain the theme tokens.

## What is implemented

The package contains the pure state model, HA lifecycle/config flow/storage, entity platforms, permission-checked websocket subscription/control path, output lease, Web Audio engine, full/compact cards, editor and shared expanded view. Examples and architecture notes are included. The model and frontend helpers have small dependency-free checks.

There is no unfinished placeholder audio implementation or speaker preview: local audio generation and the control protocol are real code. That does not substitute for running it in HA. Read `docs/TESTING.md` for the precise validation boundary and test plan.

## First work items

1. Import this source into the repository requested by the user. Choose the licence with the user before public release. Add real documentation/issue URLs and codeowners; do not retain fake placeholders. Add CI, formatting/type checks and HA integration tests. Decide whether bundled frontend manual registration remains the distribution approach or whether to publish a separate HACS frontend package.
2. Start an isolated HA **2026.10.1** environment and install the component. Verify config flow, platform loading, entities, resource serving and all websocket flows. The source was checked against the 2026.10.1 API, but was not imported under that HA runtime here.
3. Test actual Android/iOS Companion audio unlocking and interruption behavior early. Confirm that local `AudioContext` scheduling works in each target WebView. iOS vibration must disappear when unsupported; API presence on other devices does not guarantee a physical vibration.
4. Exercise multi-client permissions, ownership, unload/reload, reconnect and race conditions before calling this a release. Read-only subscriptions must not enable mutations. Generic media-player actions should fail helpfully until a foreground client has been enabled.
5. Audit layout and accessibility in native light/dark HA themes at 280/320/360/440px and in Sections/Masonry dashboards. The component uses actual `ha-card`/`ha-icon`, but dials, menus, transport buttons, editor form and dialog are custom semantic controls styled to HA. **Do not claim total native-component parity.** Compare against the installed frontend; where stable HA primitives are appropriate, adopt them without importing guessed private bundle paths.

## Known limits and follow-ups

- The package has not been run in HA, a browser rendering test harness, or the Companion apps. No measured audio drift, latency, real mobile layout, accessibility or security test result is claimed.
- Only English UI/config-flow text is included. HA colours and time-format preference are inherited; full localisation and a native HA form-based editor are follow-up improvements.
- The output manager intentionally lives until page reload. Integration unload/reload or deleting/re-adding an instance requires a frontend refresh in this alpha. Add lifecycle cleanup/re-subscription tests and implementation if automatic recovery is wanted.
- Haptics are best effort and tied to main-thread timing. No browser-level background guarantee. Since 0.1.0-alpha.2 the iOS Companion app (no `navigator.vibrate`) uses HA's frontend `haptic` event (forwarded to the app's external bus; Short/Medium/Long → light/medium/heavy); everywhere `navigator.vibrate` exists it stays the primary path with exact 20/40/70 ms pulses. Phone silent/mute modes can suppress vibration (seen on Samsung "Mute").
- A 200ms start lead and 100ms audio lookahead are initial values. Test under realistic Wi-Fi delay and main-thread load. Tune clock offset/re-anchoring and small live-tempo-change artifacts based on measurements; do not promise multi-device synchronization.
- HA's wall clock is the shared session clock. Explicit wall-clock jumps/NTP corrections have not been tested; monotonic lease expiry is independent. Define and test a policy for large clock jumps.
- Card settings edits are coalesced for dragging. Test very fast taps/± clicks, concurrent controllers and config edits against incoming state. Do not assume syntax checks establish those behaviors.
- The primary tempo label chooses a deterministic representative at overlapping published boundaries. The reference contains overlapping traditional tempo ranges. The current primary labels are in `shared.js`; an explanatory range tooltip can be restored as a follow-up if desired.
- There is no standalone HA `timer` entity, no backend audio stream and no external speaker output. Avoid adding a separate timer unless its ownership and pause semantics are redesigned coherently.
- Manifest/HACS release metadata, brand assets, a public licence and repository workflows are intentionally pending repository creation. Manual development installation is the current package format.

## Reference sources

The user's visual references were HA thermostat, vacuum and light controls. The final design eliminated ±10 shortcuts and moved Advanced into a separate view.

- [HA design approach](https://contributors.home-assistant.io/design/how-we-design/)
- [Thermostat card](https://www.home-assistant.io/dashboards/thermostat/)
- [Tile card](https://www.home-assistant.io/dashboards/tile/)
- [Clock card](https://www.home-assistant.io/dashboards/clock/)
- [Tempo-marking reference PDF](https://mosaicmusicinstruction.com/wp-content/uploads/2018/07/basic-tempo-markings.pdf)
- [Custom cards](https://contributors.home-assistant.io/frontend/custom-ui/card/)
- [Media-player entity API](https://contributors.home-assistant.io/core/entities/media-player/)
- [Native Tile features](https://www.home-assistant.io/dashboards/features/)
- [HA 2026.10.1 config-flow example](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/met/config_flow.py)
- [HA 2026.10.1 websocket decorators](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/websocket_api/decorators.py)
- [HA 2026.10.1 HTTP static-path API](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/http/server.py)
- [Browser autoplay guidance](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay)
- [Vibration API](https://developer.mozilla.org/en-US/docs/Web/API/Vibration_API)

The original inline mockup is preserved separately in the user's Codex chat. Production source is self-contained and does not depend on it or on local screenshot paths.
