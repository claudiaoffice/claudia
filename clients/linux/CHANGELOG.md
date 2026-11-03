# Changelog of the Linux client and the shell contract

Newest first. The shell contract has its own version (`clients/contract/`); this file lists both.

## [0.1.0] - unreleased

First slice of the native Linux client (epic 5), for composes only.

### Added
- `claudia-composes`: GTK 4 / libadwaita window with the native menus File, Edit, Tools and Help (D4), a History and
  Chat toggle in the header bar (D40) and an About dialog (D28); application id `de.claudiaoffice.composes`.
- A local server per window (loopback, plain, the bundled frontend served from the same origin) that is ended with the
  window and when the shell dies.
- Shell contract **version 1** (`clients/contract/shell-contract.v1.schema.json`): `hello`, `welcome`, `action`,
  `action_state`, `error`.
- A page adapter that lets the unchanged web app take part in the contract.
