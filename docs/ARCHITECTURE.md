# Architecture and protocol

## Responsibilities

`model.py` is a pure session state machine. UTC epoch seconds are passed into its methods. `coordinator.py` owns a model per config entry, persists settings through HA Store, schedules completion, handles output ownership and notifies entities/clients. Six entity platforms expose the same state; there is no second countdown in a timer helper.

`websocket.py` resolves a media player through the entity registry and verifies its domain, integration and config entry. Read subscriptions require HA entity read permission. All controls require entity control permission. An output token is the server-side pair `(ActiveConnection, subscription_id)`; possession of a string ID on a different authenticated connection cannot claim that token. No credentials are stored by the card.

`frontend/player.js` holds one engine per HA connection and entity in a global WeakMap, shared by all cards and their dialogs. Removing a card from the DOM only detaches its view listeners. It does not destroy an active audio session when navigating dashboard views. Only the output owner schedules sound. Other clients render the same state and can control it through HA permissions.

`metronome-card.js` owns rendering and inputs; `styles.js` owns theme-aware metrics. `shared.js` contains pure timeline/arc/format helpers. `editor.js` edits presentation options. The compact card's HTML dialog mounts the same full card and reuses the player, so there is no separate playback implementation.

## Timeline

The server records `anchor_at` in UTC seconds and `anchor_beat` as a fractional musical beat. For a playing session:

```text
beat_position = anchor_beat + (now - anchor_at) * BPM / 60
beat_time(n) = anchor_at + (n - anchor_beat) * 60 / BPM
```

A start includes a 200ms delivery lead. Negative integer beats are the count-in; zero is the first exercise beat. The timer begins at beat zero. For 6/8, there are two beats per bar and each represents a dotted quarter; there are no eighth-note subdivisions in this alpha.

The frontend estimates server time from control-request round trips, converts the anchor to `AudioContext.currentTime`, and schedules up to 100ms ahead on a 25ms polling interval. Sound synthesis uses oscillators and short gain envelopes. Main-thread timers trigger visual/haptic feedback, not the audio beats themselves. A stall skips missed beats instead of playing a catch-up burst. This is not sample-accurate synchronization with another device.

A tempo change preserves fractional beat position. During the running exercise, the finish timestamp stays fixed. During count-in, the new beat period changes the remaining count-in time and therefore the finish timestamp. Pause freezes both beat phase and remaining duration; resume establishes a new anchor. Timer/meter/count-in edits are rejected during active or paused sessions, including through native entity actions.

The audio owner also checks the deadline locally so network delivery latency does not prolong sound. The backend alone records the authoritative `finished` event. A session ID suppresses duplicate completion chimes. `completed` controls the temporary zero/finished UI without erasing the configured duration.

## Output lease and interruption

Start resumes Web Audio during a user gesture, then claims output and requests playback. The subscription must already exist before a claim succeeds. Another client cannot claim while this session is active or paused; it must first stop the session. Claiming while idle moves output.

The foreground owner sends a heartbeat every 3 seconds. HA checks for a 12-second expiry every 3 seconds, so an unreported disappearance is normally detected in 12–15 seconds. Visibility changes, pagehide, websocket disconnect and audio suspension silence the local engine immediately and request release. On release/expiry/disconnect, HA transitions an active or paused session to idle with an `interrupted` event. Settings persist; playing state and output ownership never restore after HA restart.

An instance ID and monotonically increasing notification sequence let a client reject stale replies without rejecting a newly loaded HA integration. There is no per-beat backend traffic. Heartbeats do not write HA entity state. Foreground heartbeat polling continues after Stop while the audio-unlocked client remains selected.

## Websocket messages

Subscribe via HA's `connection.subscribeMessage`:

```json
{"type":"metronome/subscribe","entity_id":"media_player.metronome"}
```

The initial event adds `subscription`. Later events contain settings, state, session ID, timeline anchors, `ends_at`, `remaining`, completion state, server time, revision, notification sequence, instance ID, output readiness and whether this particular subscriber owns output. Read-only clients can subscribe but cannot claim or control.

Control:

```json
{"type":"metronome/control","entity_id":"media_player.metronome","subscription":42,"action":"configure","settings":{"bpm":96}}
```

Actions: `configure`, `start`, `pause`, `stop`, `claim`, `heartbeat`, `release`. Claim/heartbeat/release require a matching connection-bound subscription. Configure validates a complete patch before mutation; unknown keys and invalid ranges fail. Commands return a current snapshot. Native HA actions call the same coordinator methods.

## Persistence, resources and packaging

Settings live in HA Store under `metronome.<entry_id>`, delayed by one second to coalesce edits and explicitly saved on unload. Entry deletion removes that store. Entity IDs use config-entry-based unique IDs. The frontend directory alone is served under `/metronome`; no storage files are exposed.

Only the initial module is manually registered as a dashboard resource. Relative module imports are included in the integration directory. No external JS, fonts or audio files are fetched. Reload the frontend after an integration reload; automatic subscription reattachment following config-entry unload/reload is a follow-up task. Registry objects are page-lived, so deliberate unloading/re-adding an instance also requires a frontend refresh in this alpha.

The manifest carries the repository links and codeowner and passes hassfest 2026.10.1; `hacs.json` sets the minimum HA version to 2026.10.1. The HA 2026.10.1 source uses `probatio` for schemas; this package targets that API and does not promise backward compatibility.

Expected rejections (claim while another device plays, stale subscription, locked setting, wrong entity) are `ServiceValidationError`s. The websocket commands answer them with an error result (`home_assistant_error`) without logging; native entity actions report them as validation errors. `Unauthorized` is raised and logged as in HA core.
