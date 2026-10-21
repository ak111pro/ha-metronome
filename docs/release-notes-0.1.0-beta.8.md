# Metronome 0.1.0-beta.8

Mostly compact-card and dialog polish from daily use. Tested on Android (Companion app).

## Changed
- **Expanded view:** the close button sits at the top left like HA's own more-info dialogs, with the title next to it; its focus ring no longer touches the dialog edge. In Advanced, Back takes that corner.
- **Compact card:** no tap-highlight flash over the whole card when tapping a button on Android.

## Added
- **Timer bar in the compact card:** a slim countdown bar with the full card's arc thickness and round caps, the remaining time and "Ends …" inside it, smooth movement. Option `show_timer_bar` (default on).
- **Tap anywhere on the compact card** (outside the buttons) opens the full card, like a Tile card.
- **Option `show_step_buttons`** (default on): hide the −1/+1 buttons on both dials and in the compact card.

**Update:** HACS → Metronome → Update, then reload the app or browser. The card resource gets its new version number at the next Home Assistant restart; if a device still shows the old card before that, clear its frontend cache (Companion app: Settings → Companion app → Reset frontend cache).

Full details in the [CHANGELOG](https://github.com/ak111pro/ha-metronome/blob/main/CHANGELOG.md).
