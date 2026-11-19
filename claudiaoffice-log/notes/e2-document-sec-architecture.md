# E2 round two — architecture proposal (viewers, back-off, hashing cost, key renewal, exports and their record)

**Status: proposal of 2026-11-19, with the owner's answers of the same day (§6) and the first built parts (§8).** Branch `e2-document-sec`, written against `main` at `518a7bf`.
Decisions: D1261–D1278 (D1274 and D1276 decided by the owner on 2026-11-19). Mock-ups in `notes/mockups/`:

| File | Shows |
|---|---|
| `e2-viewer-and-roles.svg` | A viewer's dock and the waiting state; Share… with a role change; the remove confirmation and its progress |
| `e2-export-import-and-record.svg` | Export with the unencrypted format (owner, editor/viewer), the confirmation, print preview and PDF, Import, the History & Chat rows |
| `e2-login-wait-and-hashing-cost.svg` | The login with a wait; Server settings ▸ Security |
| `e2-document-sec-architecture.svg` | The class diagram: what is new or changed in the container, the server and the clients |

## 1. What is there today (read in the code on `main`)

| Fact | Where |
|---|---|
| A viewer's file keys open the content only, a test shows it cannot read history or chat blocks | `claudia_container/slots.py` (`ROLE_DOMAINS`) |
| The live session ignores roles for reading: `_audience` filters by author, recipient and sender only; `log`, `chat_log` and `peek_revision` answer any account; `welcome` carries checkpoints, lines and restore proposals | `hub.py`, `protocol.py` |
| The web client only needs a `command` event for the revision and its history rows; the content comes in the apps' own state events | `web/app/lib/base-session.ts` (`onEvent`) |
| No back-off for failed logins; `_Waiting` caps sockets only; the administrator's sign-in has none either | `app.py`, `admin_api.py` |
| The address of a connection is `websocket.client.host`, so behind `--behind-proxy` it is the proxy's for everybody | `app.py` (`Gateway.serve`), `cli.py` |
| The hashing cost is `KdfParams.default()`: 3 passes, 64 MiB, 4 lanes; the manifest stores it; hashing runs in threads behind a cap, and multi-lane hashes take turns (the OpenSSL deadlock) | `crypto.py`, `app.py`, E2 notes slice 3 |
| A slot is `locator` + AES-GCM under a key derived from the person's name **and password**; the people list (names, roles, slot locators) is sealed with the content key | `slots.py`, `container.py` |
| Packing, redaction and journal rewrite seal the blocks anew in one atomic replacement of the file | `container.py` (`pack_journal`, `rewrite_journal`) |
| A block closes at 1 MiB before compression; the last block under the target is extended; pack every 500 changes and on release | `blocks.py` (`BLOCK_TARGET_BYTES`), `container.py` (`_chunks`, `_extend`), `sealed.py` |
| File ▸ Download writes the unencrypted content-only JSON; the Export dialog is for Office formats; D110 (the sealed download) has no code | `ExportDialog.vue`, `ExportFormatDialog.vue` |
| Import knows the Office formats and the sealed Claudia file; not the unencrypted export | `formats.py` |
| About 47 event `type` literals exist across the packages | `grep` over `packages/` |

## 2. Three slices, each one patch with its own scenarios

| Slice | Delivers | Closes | Needs a format change? |
|---|---|---|---|
| **A · Viewers, back-off, cost** | The audience table and `reads=` on every method (D1261, D1262); `LoginThrottle` for the document and the admin login (D1266); `KdfPolicy` and Server settings ▸ Security (D1267) | SEC-17, SEC-11, the live half of E2.4, E2.7, the open point of D109; finishes the "weaker than it reads" of E7.4 | No |
| **B · What leaves** | The audit chain (D1271), the export zip and its import (D1270, D1272), print and PDF reports, the format specification and the block-policy measurement (D1269, D1268) | E2.9, E2.5 (policy part), E2.1 (specification) | Yes: a chain of blocks beside history and chat |
| **C · Keys and people** | Per-person key pairs and the inbox (D1274), role changes and renewal on removal or downgrade (D1263), private domains (D1265), side-history rule (D1264) | E2.2 and E2.3 open points, the basis of E16.8 | Yes: slots, people list, inbox |

A first because it closes the open P2 security findings and changes no file. B and C change the format, so they are
written together with the specification and are the ones the external review will read (D1273). E2.11 (read-only
hosting) and E2.12 (the sealed download, D110) are outside this branch unless the owner pulls them in.

## 3. The design, point by point

### 3.1 Audience: one table, fail closed (D1261)

`claudia_server/audience.py` (new) holds `EVENT_DOMAINS`, which maps every event `type` to `content`, `history` or
`chat`, and `Audience.delivery(event, role)`, which answers `full`, `revision_only` or `drop`. A viewer gets `content`
events in full, a `command` event as its revision alone, and nothing else. An event type that is in no table goes to owners
and editors only.

`MethodTable.method(...)` gets `reads=` (`content` by default). `dispatch` refuses a viewer for `history` and `chat` with
`forbidden`. `log`, `chat_log`, `peek_revision`, `changes_since`, `checkpoints`, the restore methods and `audit_log` are
`history`. `welcome` asks the same table for what it may carry. The assistant's document lens is built under the asker's
role, so a viewer's question sees content only (D261).

**Why a table and not an `if viewer` where the leak was found.** The leak was a forgotten case. Two guards make the next
one fail a test instead of a person: (1) a test finds every `"type"` literal in `packages/` and fails for one that is not
classified; (2) a test walks the registered methods and fails for one with no `reads`. The kernel stays free of roles
(`claudia_core` is not touched).

**To verify with the first scenario:** that a viewer's window renders live content from the state events alone. The
client code says so (§1); a scenario with two windows proves it.

### 3.2 Back-off (D1266, D1275)

`LoginThrottle` is a plain class with an injected clock and no I/O: `check(address, doc, name)` returns the seconds to wait
or 0, `failed(...)` and `succeeded(address)` update two counters (per address, per document-and-name), `forget` drops
anything quiet for fifteen minutes. It lives in memory; a restart forgets, which is fine for a delay (nothing is locked). The owner asked whether writing it to
disk would be safer: a little, in one narrow case (a restart or a crash resets the wait), at the cost of keeping hashed
addresses on disk. **Decided (D1276): it stays in memory**; the threat model states the gap.

`Gateway._hello` asks it **before** `_hello` reaches the hashing semaphore, so a refused guesser costs nothing. The document
`hello` (also with a recovery key) and `POST /api/admin/login` use the same instance. The counters count a name whether or
not the document exists, so the answer reveals nothing (SEC-04).

**Open technical points.** (a) How the refusal travels: a `hello` answer frame with `error.code = "retry_after"` and
`seconds`, if `hello` failures are frames today, otherwise a close code next to 4403 and 4423; I'll read that code before
the first line is written. (b) The address behind a proxy, D1275 (decided and built, §8): the right-most `X-Forwarded-For` entry with
`--behind-proxy`. The same fix repairs `max_waiting_per_address`.

### 3.3 Hashing cost (D1267)

`claudia_container/kdf.py` (new): `calibrate(target_seconds, max_memory_kib, floor)` returns `KdfParams`. It times one hash
at the floor, scales memory (then passes) to the target, and checks the result with a second measurement. `KdfPolicy` (new,
in the server) calls it in a background thread at start and when the setting changes, and gives `SealedDocuments` the
parameters for new documents and for the decoy.

**Measured on this machine (2 cores, today's sandbox, not a server):**

| Passes | Memory | Lanes | One hash |
|---|---|---|---|
| 3 | 64 MiB | 4 | 0.16 s |
| 3 | 128 MiB | 4 | 0.33 s |
| 3 | 192 MiB | 4 | 0.44 s |
| 3 | 256 MiB | 4 | 0.58 s |

Time grows about linearly with memory times passes, so the 0.75 s target on a machine like this one lands at 256 MiB and 4
passes. With the cap of two concurrent hashes that is about 512 MiB of memory at the peak, which is the number to watch on
a NAS; it is why the memory ceiling is a setting. One lane or four made no difference on two cores. Two single-lane hashes
in two threads together took 0.21 s against 0.17 s for one, so single-lane hashing does run in parallel here; whether that
holds on the real server (and is safe, since the deadlock was found with several lanes) is a measurement to repeat there
before the cap changes.

`KdfParams.__doc__` says raising the cost later is "a matter of re-deriving each slot at the next login". That is wrong for
a document with several people; the sentence goes in this slice (D1267).

### 3.4 Renewing keys: the inbox (D1263, D1274)

**The problem found while planning.** A slot opens with a key derived from its person's password. The owner cannot rewrite
anyone else's slot, so "renew the keys and rewrite every remaining slot" cannot be done. The same holds for the recovery
key's slot, which nobody can open once the key has been shown.

**Proposal (D1274).** Every person and the recovery key get an X25519 key pair. The private key sits in the slot; the
public key sits in the people list (sealed with the content key, not secret). `claudia_container/inbox.py` (new) offers
`seal_to(public_key, keys)` and `open_inbox(private_key, blob)`; `container.renew_keys` writes one inbox entry per person
who stays and none for a person who goes. At the next login the server opens the slot with the password the person just
typed, opens the inbox, writes a slot that holds the new keys, and deletes the entry.

```
remove tobi / downgrade tobi
  owner (server holds all keys)
    1  new keys for the domains tobi held
    2  re-seal history, chat, people list, snapshot, head      (one atomic replacement, as packing)
    3  re-seal the journal under the new keys                  (as the redaction rewrite)
    4  for each person who stays and for the recovery key: inbox entry sealed to her public key
    5  tobi: slot deleted (removal) or rewritten without the keys he lost (downgrade: she is connected, so
       her password is in memory; else it happens at her next login)
  every other person, next login
    6  slot opened with her password -> private key -> inbox -> new keys -> new slot, inbox entry deleted
```

Crash safety is the one of packing: the new file is written to a temporary name, fsynced and renamed, and the journal
moves to the next generation afterwards; the head record says which generation a file already contains.

**Role change.** The people list changes at once and the server enforces the new role from it, so a person who gains a
role is served live immediately. What her slot in the file holds catches up at her next login through her inbox.

**What stays outside it.** A private domain's key is in its owner's slot only and is never renewed by someone else's
removal. The audit chain uses the history key, so it is renewed with history.

**Alternatives rejected** are in D1274. **Cost:** X25519 is one more primitive in a reviewed scheme; D104 lists the
algorithm ids, so adding it is a value in the manifest, not a new format family.

### 3.5 The audit chain and the reports (D1271)

`claudia_container/audit.py` (new): `AuditRecord(kind, who, when, format, parts, pages)`, sealed in blocks like history and
chat, under the history key, in `audit/NNNNNN.blk`, covered by the head record. Redaction and the journal rewrite must pass
the chain through untouched; a test fails if a redaction changes one byte of it.

`SealedDocuments.record(...)` writes it. Server-made exports call it themselves with the authenticated account. Print and
PDF call a new method, `report_output(kind, format, pages)`, **which takes `who` from the connection and never from the
payload** and is rate-limited per account so a script cannot fill the file. A new method `audit_log` (`reads=history`)
feeds the muted rows in the dock.

### 3.6 The export and its import (D1270, D1272)

`claudia_container/export_file.py` (new): `write_export` / `read_export`, the zip `claudia-export 2`. `export.json` names
the parts and a SHA-256 of each (integrity, not authenticity), the exporter, the time and the document's app and state
schema. The reader uses the container's limits against bombs and bad paths (E2.1). Import goes through `formats.import_state`
as a new kind next to the Office formats; replaying the imported log must give the identical state, which is a test.

### 3.7 Documentation and versions

The format specification `docs/container-format.md` is written with slices B and C. API documentation stays generated from
docstrings (Sphinx). Public changes in `claudia-container` and `claudia-server` raise their minor versions, with a CHANGELOG
entry and `scripts/api_surface.py --write` (`docs/versioning.md`). The wire changes (`reads=` metadata, `retry_after`,
`audit_log`, `report_output`, `set_role`, `export_claudia`) are additive. `PROTOCOL_VERSION` stays at 2 (owner, 2026-11-19) and the
change in what a viewer receives is described in `docs/server.md`.

## 4. Tests (written first)

Unit: `LoginThrottle` with a fake clock (free tries, doubling, caps, reset on success, forgetting, a name that does not
exist counted like one that does); `calibrate` with a fake timer; `Audience` for every type and role; the two registry
tests; inbox seal and open (wrong key, wrong document, swapped entries); renewal (the removed person's old keys open
nothing written after; every remaining person and the recovery key still get in; a crash at each step); the audit chain
survives redaction; the export zip round trip and its refusals; the byte scan finds no names, passwords or chat text after
renewal.

End to end, against the real stack (Firefox first), in `specs/container/*.feature` once the owner has agreed the scenarios:
a viewer window shows content and the sentence and never the history, with an editor typing in a second window; a wrong
password four times shows the wait and a correct one after it opens; owner and viewer export; an unencrypted export imports as a
new document with identical content; a print and a PDF appear as rows; a role change and a removal as seen from the
person concerned. Console errors fail every scenario, as agreed.

## 5. Menus, languages, accessibility

No new menu entries. The strings go into the `.po` files (`po/`) with the rest; every new dialog has translated labels and
the keys the shell uses for dialogs. BITV: the wait is announced politely once and when it ends, not every second; the
viewer sentence is text, not colour; the role control has a visible label and the progress bar a role and a text; focus
goes to the first control of every dialog and returns to the one that opened it. Where we diverge, the patch notes say so.

## 6. Questions for the owner — answered 2026-11-19

| # | Question | Answer |
|---|---|---|
| 1 | D1274, the inbox with a key pair per person | **Yes, as proposed** after the plain-words explanation at the top of D1274; built in slice C |
| 2 | D1275, the address behind a proxy | **Yes** (built, §8) |
| 3 | The record is not redactable (D1271) | **Yes, not by the owner either** |
| 4 | File ▸ Download and D110 (D1270, E2.12) | **Download is the sealed file**; decisions and code updated (built, §8) |
| 5 | Protocol version | **Stays 2** |
| 6 | Slice order | **A, B, C** |
| new | D1276: the back-off state on disk | **No: it stays in memory** (decided) |

## 7. Findings while reading (all four fixed 2026-11-19; the owner asked for it)

| What | Size | Now |
|---|---|---|
| `KdfParams`' docstring claims the cost can be raised "at the next login"; it cannot for a document with several people | 3 | fixed (CODE-72) |
| `docs/versioning.md` says the protocol version is "now 1"; the code says 2 | 3 | fixed, and a test compares them (DOC-04) |
| D110 (the sealed download) is current since 2026-11-02 and has no code; File ▸ Download in the code and in the menu workbook mean different things | 2 | fixed: Download is the sealed file (CODE-73) |
| Behind `--behind-proxy` every client has the proxy's address: `max_waiting_per_address` (SEC-02) is then one cap for everybody | 2 | fixed (SEC-20, D1275) |

Found while fixing them: **SEC-21** (password-confirming methods hash on the event loop; open, size 2) and **PROC-34** (the
`backlog` branch broke `tests/test_backlog.py` by a renamed story file; fixed).

## 8. What is built (2026-11-19, branch `e2-document-sec`)

| Part | Where | Tests |
|---|---|---|
| The sealed copy for one person: owner whole file, editor own slot, viewer own slot and the content parts only | `claudia_container.container.sealed_copy` | `claudia-container/tests/test_sealed_copy.py` (11) |
| `download_claudia` on the wire and `SealedCopyDirectory`; an open document is packed first | `protocol.py`, `auth.py`, `sealed.py` | `claudia-server/tests/test_server_download.py` (6) |
| File ▸ Download in the web app, and so in the GTK and Neutralino shells (they show it; their Save dialog takes the `.claudia` name) | `DownloadDialog.vue` (was `ExportDialog.vue`), `BaseSession.downloadClaudia` | `web/tests/session.test.ts`, `document-menus.test.ts`, and the scenarios of `specs/container/download.feature` (3 of 6 run in Chrome) |
| The address of a connection behind a proxy; `--proxy-hops` | `client_address.py`, `app.py`, `cli.py` | `test_server_client_address.py` (16), `test_server_cli.py`, `test_server_uid.py` |
| German and pseudo-locale strings, the menu workbook, `docs/server.md`, `docs/web.md`, changelogs and API snapshots (container 0.9.0, server 0.38.0) | | the gate (`scripts/check_debt.py`) |

| Viewer filter: events and methods by domain; the viewer's window and panel | `audience.py`, `protocol.py` (`reads=`), `hub.py`, `base-session.ts`, `SidePanel.vue` | `test_server_audience.py`, `tests/method_reads.json`, `web/tests/session.test.ts`, `specs/container/viewer.feature` (2 of 3 core scenarios run) |
| Sealed-first viewer waits (D1262) | `base-session.ts` (`waiting`), `DocumentFrame.vue` | `web/tests/session.test.ts` (the scenario in `viewer.feature` has no step code for the server restart) |
| Back-off (D1266, D1276) | `login_throttle.py`, `app.py`, `admin_api.py`, `login-wait.ts` | `test_server_login_throttle.py` (24), `test_server_login_waits.py`, `web/tests/login-wait.test.ts`, `specs/container/login-wait.feature` |
| SEC-21: hash ahead in a thread (D1277) | `crypto.py` (`warm_login_material`), `container.warm`, `Method.hashes`, `Gateway.prepare` | `test_warm_login.py`, `test_server_password_methods.py` |
| Hashing cost calibrated (D1267, D1278) | `kdf.py`, `kdf_policy.py`, `server_settings.py`, `AdminSecurity.vue` | `test_kdf_calibration.py`, `test_server_kdf_policy.py`, `web/tests/security-settings.test.ts` |

Slice A is built (container 0.10.0, server 0.39.0). Not built: authorship for viewers (SEC-22, waits for the owner), slices B and C.

## 9. Threat-model consequences of slice A

| Statement | Where it lives |
|---|---|
| A viewer receives content, names and presence and nothing from the history or chat, in the live session, in the welcome and in her sealed file; she is refused the methods that read them | D1261, `audience.py` |
| A viewer sees who wrote which stretch (not masked) | SEC-22 |
| A restart forgets the back-off counters; a guesser regains at most one wait (30 s at the top) | D1276 |
| Guessing is paced by the waits (per address, per document and name), by the hashing cap and by the cost of one hash; many addresses at once are not stopped by the waits | D1266 |
| The process holds derived login material (not the password) for up to 30 s, once, for requests that confirm a password | D1277 |
| New documents are hashed at a cost measured on the server; old documents keep theirs | D1267, D1278 | A viewer's downloaded copy cannot be opened until E2.11 (read-only hosting)
exists.
