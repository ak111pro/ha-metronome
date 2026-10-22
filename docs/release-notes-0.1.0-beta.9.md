# Metronome 0.1.0-beta.9

Small polish from daily use.

## Changed
- **Compact card without −1/+1** (`show_step_buttons: false`): the BPM number moves to the right end of the header row and the name/state line uses the freed width, so it no longer cuts off early. In the `bottom` layout the extra tempo row is gone, which saves height.
- **Quieter connection notices:** the red "Connection lost…" and other temporary connection/playback messages only appear with *Advanced → Show diagnostics*. Otherwise the card shows a short grey line ("Reconnecting…", "No sound – tap to resume") or nothing. Errors you have to act on (e.g. another device is playing, no device ready) stay red.

**Update:** HACS → Metronome → Update, then reload the app or browser. The card resource gets its new version number at the next Home Assistant restart; until then, bump the resource's `?v=` yourself or clear the frontend cache (Companion app: Settings → Companion app → Reset frontend cache).

Full details in the [CHANGELOG](https://github.com/ak111pro/ha-metronome/blob/main/CHANGELOG.md).
