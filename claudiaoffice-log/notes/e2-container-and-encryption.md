# Epic 2 — document container and encryption

Written 2026-11-02, extended 2026-11-03; moved here 2026-11-05. The decisions in this document were originally
numbered D70–D82 and collided with the product decisions of the same numbers; they are now **D100–D112** and the
mapping is in `decision-log.md`. The code still cites the old numbers (DOC-01 in `bugtracker.md`).

## 1. Decisions

See `decision-log/`, D100–D112. In short: the threat model (D100); one key slot per user wrapping the domain keys
of their role (D101); names found by a locator derived from name *and* password so they never appear in the file
(D102); a small plain manifest anyone may read (D103); Argon2id, HKDF-SHA256 and AES-256-GCM from the `cryptography`
package with the algorithm ids recorded (D104); an optional recovery key shown once (D105); a journal next to the zip,
packed into blocks when idle, with every file a person takes away being one complete file (D106); a new package
`claudia-container` (D107); unencrypted export and import, logged (D108); password rules and a stored KDF cost (D109);
non-owners get a download with only their own slot (D110); viewers see all user names (D111); the extension
`.claudia` (D112).

## 2. Threat model v0 (the first page of E2.8)

**Protected:** content, history, chat, user names, and the roles of each.

**Deliberately readable:** the manifest fields of D103, and the number of key slots (hiding it needs padding; not in
version 1).

| Who | Can do | Cannot do / not claimed |
|---|---|---|
| Outsider with a copy (stolen laptop, cloud backup) | Read the manifest; try passwords offline, at the cost Argon2id sets and with the password's strength deciding; delete the file; replace it with an older valid copy | Read content, history, chat or names. Change a block, swap two blocks or cut off the end without it being noticed (hash chain and head record). **Not detected:** replacing the whole file by an earlier valid version |
| Co-editor or viewer | Read what their role's keys open; keep what they have seen or copied; export (D108) | Read domains they have no key for. Be unseen when exporting unencrypted. Be locked out of copies they already hold after removal (D20) |
| Server operator, or anybody who controls the running server | Everything, while a document is open: the server holds the keys and sees passwords at login | Out of scope. The mitigation is to run your own server. Closed documents are unreadable on the server (E2.7) |
| Network attacker | — | TLS; see SEC-01, SEC-06, SEC-07 |
| Somebody who sends a **malicious file** | Try to exploit the reader: zip bombs, path tricks, huge counts | Reader limits are part of E2.1 |

Out of scope: malware on the client, shoulder surfing, side channels, quantum attackers (the algorithm ids allow a
later change).

## 3. Format v0

### The file (one zip, extension `.claudia`)

```
format               stored, not compressed: "claudia-document 1"  (first entry, so tools can recognise the file)
manifest.json        plain: id, title, app, last change, size, unlisted, format version,
                     KDF parameters, cipher ids, document salt
slots.json           the key slots: locators and sealed keys, no names
head.bin             encrypted (history key): number and last hash of each chain, last journal generation folded in
people.bin           encrypted (content key): names, roles and slot locators of all users
content/snapshot.bin encrypted (content key): state cache, can be deleted and rebuilt
history/NNNNNN.blk   encrypted blocks of the command log (history key)
chat/NNNNNN.blk      encrypted blocks of chat records (chat key)
assets/              reserved for content-addressed blobs
```

Each block holds compressed JSON lines of commands, then encrypts them with AES-256-GCM. The additional authenticated
data names document id, domain, block number and the hash of the previous block, so a block cannot be moved, reordered
or taken from another document. The head record detects removal of the newest blocks for anyone holding the file but
no key.

### Key slots and hidden names

For a login the server computes `Argon2id(password, salt = H(document salt, normalised name))` and splits the result
with HKDF into a **locator** and a **key-encryption key**. A slot is stored as `locator` plus
`AES-GCM(key-encryption key, {name, role, domain keys of that role})`.

Consequences:

- Names never appear in the file outside encrypted parts.
- A wrong name and a wrong password look identical: no slot matches. This keeps D50, and the equal-time requirement of
  SEC-04 holds automatically, because every attempt costs one Argon2id run.
- An attacker must guess name *and* password together.
- Changing a password replaces that user's slot; removing a user deletes it; rotating keys re-encrypts blocks and
  rewraps all remaining slots.

**Recovery key:** 256 random bits, shown once. Locator and key come from it by HKDF, with no Argon2id needed. It opens
an owner slot.

**Roles and domains:** owner = content, history, chat; editor = content, history, chat; viewer = content only. Owner
and editor hold the same keys, so the difference between them is enforced by the server, not by cryptography.

### Journal (while a document is open)

A file next to the zip. Header: document id, format version, generation number. Each record: length, domain, sequence
number, nonce, ciphertext with tag, CRC. Additional authenticated data: document id, domain, sequence number.

- **Acknowledgement:** the server answers an edit only after its record is fsynced. *The design says a writer task does
  this off the event loop and writes several records per fsync, which would fix PERF-02. That part was never built.*
- **Torn tail after a crash:** a last record that fails its check was never acknowledged and is dropped.
- **Packing:** a new zip is written to a temporary file, fsynced, renamed over the old one, the directory fsynced, and
  then the journal moves to the next generation. A crash between rename and journal reset is safe because the new
  zip's head says which generation it already contains.
- **Redaction:** the same atomic rewrite, removing the redacted entries from blocks and journal. **Not built**
  (SEC-05).

### Reader limits (malicious files)

A maximum number of entries, size per entry, compression ratio and total uncompressed size; entry names only from a
whitelist pattern; no absolute paths, `..` or duplicates; never extract to disk, read by name.

### Server side

Keys live in memory only while a document is open and are dropped on last leave and on idle timeout. A consequence of
D101: a viewer holds only the content key, so a viewer who is first to log in after a restart cannot bring the
document up. **A snapshot does not remove this by itself** — a snapshot lets a holder of the content key read the
*state*, but the server brings a document up as a live, editable document from the history, which a viewer cannot
read. Letting a viewer go first needs read-only hosting of the snapshot (E2.4). Until then the answer is the error
code `sealed` (close 4423) and the web app retries.

## 4. First tests (written before any code)

1. Round trip: write, close, reopen, equal state.
2. Wrong password, wrong name and unknown document give the same answer in about the same time.
3. A byte scan of the whole folder finds none of the typed text, user names or passwords.
4. A block changed, two blocks swapped, the last block removed, and a block from another document are each detected.
5. Journal: a torn last record is dropped; a crash between rename and journal reset loses nothing acknowledged.
6. A viewer's key cannot decrypt history or chat blocks; an editor's can.
7. The recovery key opens the owner slot; password change and user removal behave as in D101.
8. Login flood: `ping` from an open session stays under 20 ms while eight clients hash.
9. A store whose append sleeps 50 ms does not delay other users.
10. Unencrypted export: a viewer gets content only, an owner everything, both logged, no slots or hashes inside, and
    import reproduces the state.
11. Malicious zips: a bomb, a `..` path, duplicate names and a huge entry count are refused.
12. Known-answer tests for the Argon2id, HKDF and AES-GCM wrappers.

Tests 9 and 10 are still unmet: the group commit and the unencrypted export were never built.

## 5. Progress

### Slice 1 — `claudia-container` 0.1.0, E2.2 partly

| Part | Where | Tests |
|---|---|---|
| Argon2id, HKDF and AES-256-GCM behind one interface, with KDF limits against hostile files | `crypto.py` | known-answer tests from RFC 5869, RFC 9106, the argon2 reference suite and GCM cases 13 and 14 |
| Password rules as translatable codes | `passwords.py` | rules, codes, Unicode length |
| Key slots with hidden names, roles and domains, recovery key | `slots.py` | plus swapping, moving and damaging slots |

80 new tests.

**Finding: the default KDF cost is below the target of D109.** With 3 passes, 64 MiB and 4 lanes (the second option
recommended by RFC 9106) one login takes about 0.09 s on the development machine, not 0.5 s, and the time depends
strongly on the number of cores. Options: keep the defaults, or add a `calibrate(target_seconds)` that picks the
memory cost for the server's hardware at creation and stores it in the manifest, with a floor. **Not decided.** The
cost also decides how many logins a server can hash at once.

### Slice 2 — `claudia-container` 0.2.0 and `claudia-server` 0.4.0

E2.1 partly, E2.3, E2.7 partly, SEC-03 and SEC-04. The web demo now stores encrypted documents.

| Part | Where | Tests |
|---|---|---|
| The document file: zip with manifest, key slots and sealed people; atomic replace; reader limits; add and remove users, change password, recovery-key login | `container.py` | zip bombs, `..` paths, duplicate names, too many entries, a lying size, unknown format version, atomicity |
| Journal: sealed records with CRC, bound to document, generation, domain and number; torn tail repaired; any other damage an error | `journal.py` | cut-off and garbled tails, gaps, repeats, swaps, foreign journals, wrong or missing keys |
| `SealedDocuments`: the server's provider and user directory in one; keys in memory only | `claudia_server/sealed.py` | restart, byte scan of the folder, 0600 files, equal answers, SEC-04 timing, viewer-first refusal, key expiry, release, rollback of a failed creation, damaged and tampered journals |
| Hashing in threads behind a cap of 2; a decoy hash for unknown documents | `app.py` | the event loop is not blocked, the cap is respected |
| `--dir` is sealed; `--plain-dir` keeps the old store | `cli.py` | banner, exclusive options, a real session |

Checked with the real server process: create, edit, chat, add a person, restart, log in as the editor first, read the
cells and chat back, and scan every byte of the folder for names, passwords and chat text — nothing found. Creating a
document took about 0.3 s with the default KDF.

**Decisions taken on the way.** A failed document creation takes the owner and the empty document back (removing the
only person of a document without changes deletes both files; a document with content is never deleted this way). A
name with a control character is refused, not tidied up. Passwords are explained in a sentence.

### Slice 3 — `claudia-container` 0.3.0 and `claudia-server` 0.8.0

E2.1 (blocks, head, snapshot), E2.2 and E2.5 (recovery key in the server and web UI).

| Part | Where | Tests |
|---|---|---|
| Blocks: records framed, zlib-compressed, AES-256-GCM sealed (about 1 MiB each), authenticated data naming document, domain, number and the previous block's hash | `blocks.py` | wrong key, wrong place, swapped, moved to another document or domain, changed, decompression bomb |
| Head record (history key): number and last hash of each chain and the last journal generation folded in | `blocks.py`, `container.py` | removed newest block, removed head, extra block, head from another document |
| Snapshot (content key) as a cache: a stale, foreign or unreadable one is ignored | `container.py`, `sealed.py` | opening uses it, work after it is replayed, rubbish is ignored |
| Packing: file first, journal second; a crash in between loses nothing | `container.py`, `journal.py` | every failure point, repeated crashes, people changes in between |
| Server: packs on release, on open with leftovers, every 500 changes, and when the server stops; failures are logged and lose nothing | `sealed.py`, `hub.py` | byte scan after packing, generation advances, a failing pack still forgets the keys, release in a thread under the open lock |
| Recovery key: `new_recovery_key` (owner only, shown once, never stored), `hello` with `recovery_key` and a new password, `created` in the answer | `container.py`, `sealed.py`, `app.py`, `protocol.py`, `auth.py` | the old key stops working, a wrong key looks like a missing document, a weak password is explained, only owners |
| Web: a recovery-key dialog after creating a document, "Make a new recovery key" in Share, "I forgot my password" on the start page | `RecoveryKeyDialog.vue`, `ShareDialog.vue`, `OpenDialog.vue` | vitest plus the browser run `web/e2e/recovery.cjs` |

**Found and fixed on the way, both older than this slice:**

- **A deadlock in the password hashing.** OpenSSL's Argon2id with more than one lane (the default has four) fails
  ("Not enough memory to derive key") or never returns when two threads use it at once. Two people logging in
  together, for instance after a restart, hung the server for ever. Multi-lane calls now take turns, with a test that
  hashes from six threads. **Consequence:** the `max_hashing` cap of 2 is effectively 1 at the default parameters, so
  a server handles 2.5–5 logins per second. This makes the KDF calibration question more pressing, not less.
- **A viewer who reconnected first gave up for good.** The refusal "this document is sealed" was `bad_request`, which
  the web client treats as final. It is now its own code, `sealed` (close 4423), and the client keeps trying.

**Decisions taken on the way.** The recovery key is a formatted string (13 groups of 4 base32 characters) shown once.
A document whose key could not be made simply opens. A person who recovers keeps their role; a viewer who recovers
does not leave the keys waiting. Undo steps made before the snapshot are not restored when a document is opened from
it, because the kernel rebuilds them only by replay — a visible change for people who used to undo across a reload.

## 6. Known limitations

Carried into `backlog.md` and `bugtracker.md`:

- Redaction does not rewrite packed blocks or the journal: a redacted text rests in older blocks, and in the snapshot
  until the next packing (SEC-05).
- An older copy of the whole file can be put back; the head of the old copy fits its old blocks.
- A viewer still cannot be the first to open a sealed document (E2.4).
- Packing writes the whole zip again, every 500 changes and at release. Fine up to some tens of megabytes; larger
  documents need appending or a split (PERF-06). Threshold packing runs on the event loop; release runs in a thread.
- Every edit still does its fsync on the event loop (PERF-02), and `add_user` and `new_recovery_key` run on the loop.
- Key rotation, unencrypted export and import (E2.9), role changes without removing the person, and KDF calibration
  are all open.
- The recovery key opens an owner slot with all keys: anyone who holds it can read the document. The dialog says so.
- Folders made by `--dir` before the container exist only under `--plain-dir`; there is no migration (D107).
