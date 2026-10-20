# Changelog

## Unreleased (0.1.0-alpha.1)

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
