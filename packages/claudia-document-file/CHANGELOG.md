# Changelog of claudia-document-file

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Changed
- **Breaking** — the package is `claudia-document-file`, imported as `claudia_document_file` (was `claudia-container`,
  `claudia_container`): it is the document file, not the glossary's container (D1430, E1.18). Its main module is
  `claudia_document_file.file` (was `.container`), and `DocumentFileError` (was `ContainerError`) is the base of
  `NotAClaudiaDocument`, `UnsupportedFormat`, `TamperedDocument` and `ReaderLimitExceeded`. Older entries below keep
  the old names.

## [0.12.0] - 2026-11-19

### Changed
- **Format 2** (`claudia-document 2`, D1279). A file of format 1 is refused with `OutdatedFormat` (a sentence for the
  person: it was written by an older version); format 3 and up is "newer". Slots hold an X25519 `private_key` and a
  `private` domain id; `people.bin` lists each person's `public_key` and `private` id; the head has a `recovery` locator
  and `recovery_public`.

### Added
- Keys and people (D1274): `new_key_pair`, `KeyPair`, `seal_to`, `open_inbox`. A letter to a person is a sealed box in
  `inbox/<locator>.bin` holding her role and the keys she was not there to receive. Login opens her slot, then her
  letter, checks it against the people list and the head, and writes the catch-up (`unlock`, `unlock_with_recovery`).
  A forged or swapped letter is ignored. `sealed_copy` for somebody else leaves the inbox and the private chains out.
- Renewal (D1263): `change_role(path, keys, writer, name, role, snapshot=)` and `remove_person(...)` return
  `Renewed(keys, writer, renewed)`. Removing a viewer renews the content key; removing an editor or owner renews all
  three; lowering an editor to viewer renews history and chat. One atomic replacement of the file re-seals the chains,
  the head, the people list and the original; pending journal records are folded in and a new journal starts under the
  new keys. `RenewalInterrupted(keys)` if only the journal step failed. The snapshot is dropped unless passed.
- The private domain (D1265): `private/<id>/NNNNNN.blk` with its own head, sealed with her private-domain key only;
  `read_private`, `write_private`, `new_private_domain`, `PrivateDomain`. A stand-in mechanism for E16.8. Recovery gives
  the person a new key pair and a new private domain and deletes the old chain.
- Discarding side history stays owner-only (D1264, unchanged).

## [0.11.0] - 2026-11-19

### Added
- The record of what left the document (D1271, E2.9): `AuditRecord(kind, who, when, format, parts, pages)` with `check()`,
  `to_bytes()` and `from_bytes()`; `AUDIT_KINDS`, `AUDIT_PARTS`; `record_audit(path, keys, record)` and
  `read_audit(path, keys)`. The records are blocks of a third chain, `audit/NNNNNN.blk`, sealed with the history key and
  covered by the head (`Head.audit`, `blocks.AUDIT`, `Place.domain` is now the chain's name). A redaction, packing and the
  rewrite of the journal carry the chain over byte for byte; `sealed_copy` for a viewer leaves it out. Nothing removes a
  record. The format text stays `claudia-document 1`: a file only has the chain after its first export, and an older
  program refuses such a file as damaged (it does not know the folder).
- The unencrypted export (D1270, D1272): `write_export(app, state_schema, state, exporter=, exported_at=, history=, chat=)`,
  `read_export(data)` (an `ExportFile`), `is_export(data)`, `ExportRefused`, `FORMAT_TEXT` `claudia-export 2`. A zip of
  `format`, `export.json` (with the SHA-256 and size of each part), `content.json` and, for an owner, `history.jsonl` and
  `chat.jsonl`; no key, slot, password hash or list of people. The reader checks the listing and the compression ratio
  before it inflates, and refuses with a sentence.

### Changed
- `blocks.Place.domain` is a `str` (a domain's value or `"audit"`), not a `Domain`.

## [0.10.0] - 2026-11-19

### Added
- `warm_login_material(password, name, doc_salt, params)` and `warm(path, name, password)` (SEC-21): do the slow hashing
  of a login ahead of time, so that the next `derive_login_material` (and so `unlock`, `sealed_copy`, `change_password`,
  `add_user` and the like) for the very same inputs takes the result. One-shot, expires after 30 s, at most 64 kept, filed
  under a keyed hash of the inputs and never under the password or the name. A server calls it in a worker thread so that
  its event loop does not stand still for a hash.
- `calibrate(target_seconds, max_memory_kib, floor, measure)` (D1267): the Argon2id cost that takes about the target on
  this machine: all the memory allowed, then the passes that fill the time, never weaker than the floor.

## [0.9.0] - 2026-11-19

### Added
- `sealed_copy(path, name, password)` (D110, D1270, E2.12): the document as a file for one person to keep, still sealed.
  An owner gets the whole file; anybody else gets it with only their own key slot (so nobody can attack the other
  people's passwords offline with it), and a viewer's file has only what the content key opens: no history, chat or head,
  but the snapshot. `None` for a wrong name or password. The file at `path` is not changed.

### Changed
- `KdfParams`' docstring no longer says that the cost can be raised "at the next login": it cannot for a document with
  several people, since every slot is sealed with a key from its own person's password (D1267). Words only.
- The document file and the journal are written with `claudia_file_writer.atomic_file` (CODE-34, D701); the retry on
  Windows and the message naming a handle of our own that still holds the file moved there with it.

## [0.8.0] - 2026-11-16

### Added
- `rewrite_journal(path, keys, writer, *, history, chat, snapshot)` (D725, SEC-05): seal the blocks of the file anew
  from the given payloads alone and replace the journal by an empty one, so that nothing redacted is left in the
  document folder. Same order and crash safety as `pack_journal`.
- `forget_original(path, keys)` (D723): remove the kept original of an imported document.

## [0.7.0] - 2026-11-15

The random id of a document, and the document's name called by its name (D533, D534). Breaking: files of 0.6 are not read
(pre-release, no migration).

### Added
- `Manifest.uid`: a random version 4 UUID, made by `create_document`, kept for good, checked on reading (`is_uid`,
  `new_uid`). `Manifest.binding` is `name:uid`.

### Changed
- `Manifest.id` is `Manifest.name` (manifest key `name`) and `create_document(doc_id=...)` is `create_document(name=...)`.
- Slots, the list of people, blocks, head, snapshot, original and journal are bound to `Manifest.binding` instead of
  the id, so a manifest whose name or uid was changed opens nothing.

### Removed
- `Manifest.title` and the `title` argument of `create_document`: it was a copy of the name.

## [0.6.0] - 2026-11-15

### Added
- `Manifest.description` (Markdown, at most `MAX_DESCRIPTION` = 2000 characters) and `Manifest.tags` (at most `MAX_TAGS` =
  10, each at most `MAX_TAG` = 30 characters): what the owner says about a document, kept in the plain manifest so that it
  can be read without a password (D530). `create_document(..., description="", tags=())`; files without them read as empty.
- `set_details(path, keys, description, tags)` replaces them (needs all keys); `clean_details(description, tags)` tidies
  them (trims, lower-cases tags, drops repeats) and raises `ValueError` with a sentence for what does not fit.

## [0.5.0] - 2026-11-14

### Added
- `write_original(path, keys, data)` and `read_original(path, keys)`: the file an imported document was made from,
  sealed with the content key as the entry `content/original.bin` and bound to the document's id (D439). Every later
  write of the file carries it along; `read_original` raises `TamperedDocument` for an entry that does not belong.

## [0.4.0] - 2026-11-06

Leaving a document and handing over ownership (E2.3).

### Added
- `leave_document`: a person removes themself with their own password, needing none of the document's keys (so a
  viewer, who only ever holds the content key, can leave too). Refused if they are the document's only owner.
- `transfer_owner`: make an existing editor the new owner and the old owner an editor, each proving themselves with
  their own current password. A role lives inside its own password-sealed slot (D102), so changing one means
  resealing it, which takes the password that sealed it — this is why a transfer needs both passwords at once,
  rather than just the current owner's.

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
