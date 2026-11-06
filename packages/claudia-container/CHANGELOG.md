# Changelog of claudia-container

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.3.0] - 2026-11-03

Blocks, head record, snapshot and the recovery key in use (E2.1, E2.5, E2.2; third slice).

### Added
- `read_state`, `begin`, `pack_journal`, `read_snapshot`, `State`, `TamperedDocument`: the history and the chat rest in
  the file as *blocks* (zlib-compressed, AES-256-GCM sealed, about 1 MiB each) that form a hash chain per domain; the
  *head record* (sealed with the history key) names the number and the last hash of each chain and the last journal
  generation that is folded in; a *snapshot* (a cache of the state, sealed with the content key) shortens opening.
  Packing replaces the file first and the journal second, so a crash between the two loses nothing. A block that is
  removed, changed, moved, swapped or taken from another document is refused (`TamperedDocument`). Not covered: putting
  back an older copy of the whole file.
- `has_recovery_key`, `set_recovery_key`, `recover_access`: a document can be given a new recovery key (the old one
  stops working) and a person can choose a new password with it, keeping their role; somebody who is not in the document
  becomes an owner. The key slot of the recovery key is hidden like all the others (D102).
- `JournalWriter.generation`, `JournalWriter.replace`, `journal_generation`; `blocks` module (`seal_block`,
  `open_block`, `seal_head`, `open_head`, `Head`, `Chain`, `Place`, `BlockError`).

### Changed
- Adding or removing a person, and changing a password, keep the packed blocks, the head, the snapshot and the
  recovery key.

### Fixed
- Argon2id with more than one lane fails or never returns when two threads use it at once (OpenSSL 4.0 through
  `cryptography` 50), which hung a server whose people logged in together. Such calls now take turns.

## [0.2.0] - 2026-11-02

Document file, journal and people (E2.1, E2.3, first slice).

### Added
- `create_document`, `read_manifest`, `unlock`, `unlock_with_recovery`, `read_people`, `add_user`, `remove_user`,
  `change_password`, `Manifest`, `Person`, `journal_path`, `FORMAT_TEXT`: the document file, a zip with a plain manifest,
  key slots and the sealed list of people; every change replaces the file atomically; a file from outside is checked
  (`ContainerError`, `NotAClaudiaDocument`, `UnsupportedFormat`, `ReaderLimitExceeded`).
- `JournalWriter`, `read_journal`, `JournalRecord`, `JournalError`: the encrypted journal of an open document; a change
  is on disk before it is acknowledged, a cut-off last record is dropped, tampering is refused.

## [0.1.0] - 2026-11-02

First version (E2.2, first slice). Design: D100-D112 in `claudiaoffice-log/notes/e2-container-and-encryption.md` of
the project.

### Added
- `KdfParams`, `LoginMaterial`, `derive_login_material`, `derive_recovery_material`: Argon2id and HKDF behind one small
  interface; a login yields a *locator* and a *key-encryption key* (names stay hidden, D102).
- `seal`, `open_sealed`, `random_key`, `DecryptionError`: AES-256-GCM with a random nonce and authenticated data.
- `password_problems`, `require_strong_password`, `WeakPassword`: the password rules of D109.
- `Role`, `Domain`, `KeySlot`, `Unlocked`, `new_domain_keys`, `make_slot`, `open_slot`: one key slot per user, holding the
  domain keys of the user's role (D101).
- `new_recovery_key`, `format_recovery_key`, `parse_recovery_key`, `InvalidRecoveryKey`: the recovery key (D105).
