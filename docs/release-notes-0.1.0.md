# Metronome 0.1.0

First stable release. It is beta.9 plus one fix, after a full browser check of every card
feature at phone sizes (19 check scripts, see [TESTING.md](https://github.com/ak111pro/ha-metronome/blob/main/docs/TESTING.md)).

## Fixed
- **Expanded dialog on short phones:** with the timer open on a small screen (e.g. 360×640) the dialog no longer opens scrolled down a little with the title cut off at the top.

## Also new since beta.9
- README screenshots show the compact card with its timer bar.

**Update:** HACS → Metronome → Update, then reload the app or browser. The card resource gets its new version number at the next Home Assistant restart; until then, bump the resource's `?v=` yourself or clear the frontend cache (Companion app: Settings → Companion app → Reset frontend cache).

Full details in the [CHANGELOG](https://github.com/ak111pro/ha-metronome/blob/main/CHANGELOG.md).
