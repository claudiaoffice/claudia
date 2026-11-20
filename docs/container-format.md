# The document file and the export file

This page specifies the two files Claudia reads and writes as its own: the **document file** (`.claudia`), which is sealed,
and the **export file** (`.claudia-export.zip`), which is not. It is written for a person who wants to read a file without
Claudia, or write a program that does. The Python package `claudia_container` is the reference implementation
([API](api/claudia_container)); where this page and the code differ, the code is right and this page has a bug.

Decisions behind it: D100–D111 (the container, slots, domains), D1263 and D1274 (renewal, keys and letters), D1265 (the private
domain), D1269 (blocks), D1271 (the record of what leaves), D1270
and D1272 (the export and its import), D1268 (what is not detected).

## 1. The document file

One zip, written anew for every change and put in place atomically, so a crash leaves the old file or the new one.

| Entry | What it holds | Who can read it |
|---|---|---|
| `format` | The text `claudia-document 2`, stored without compression, **first** in the zip | anybody |
| `manifest.json` | name, uid, description, tags, app, times, the cost of the password hashing, the salt | anybody |
| `slots.json` | the key slots: a locator and the sealed domain keys, the person's X25519 private key and her private-domain key, no names | anybody sees the sizes |
| `people.bin` | names, roles, slot locators, public keys and private-domain ids of everybody, sealed with the content key | people with the content key |
| `inbox/<locator>.bin` | a letter to a person who was not there: a sealed box to her public key with her role and the keys she is missing (§1, *Keys and letters*) | the person it is for |
| `private/<id>/NNNNNN.blk`, `private/<id>/head.bin` | a person's private domain: its own chain and head, sealed with her private-domain key only (always one, possibly empty, block) | that person |
| `head.bin` | how many blocks each chain has and the hash of its last block, sealed with the history key | owners and editors |
| `content/snapshot.bin` | a cache of the current state (optional), sealed with the content key | everybody in the document |
| `content/original.bin` | the file the document was imported from, if it is kept (optional) | everybody in the document |
| `history/NNNNNN.blk` | the command history, in blocks | owners and editors |
| `chat/NNNNNN.blk` | the chat, in blocks | owners and editors |
| `audit/NNNNNN.blk` | the record of what left the document (§3), in blocks | owners and editors |

Next to the file, while somebody has the document open, there is a **journal** (`<name>.claudia.journal`) that takes each
change before the server answers; packing folds it into the blocks.

### Sealing

Passwords become keys with Argon2id (the cost is in the manifest); one secret becomes several keys with HKDF-SHA256; every
value is sealed with AES-256-GCM, a random 12-byte nonce in front and the 16-byte tag at the end. A person's **login** is
turned into a **locator** (which slot is theirs) and a **key-encryption key** (which opens it), both from name *and*
password, so a wrong name and a wrong password are the same refusal. A **role** decides which domain keys a slot holds: an
owner and an editor hold the content, history and chat keys, a viewer the content key only.

### Blocks and the head

A **block** holds a run of payloads, framed, compressed and sealed with the key of its chain. Its authenticated data names
the document, the chain, the number of the block and the hash of the block before it; the hash is SHA-256 of the stored
bytes. A block therefore opens in exactly one place. A block closes at about 1 MiB before compression
(`BLOCK_TARGET_BYTES`); the last block, while it is under the target, is replaced when more arrives; a reader accepts a
block of up to 64 MiB once opened. The **head** lists the number of blocks and the last hash of the history, the chat and
the record, and the last journal generation folded in. A file whose blocks do not fit its head is refused.

### What is detected, and what is not

Detected: a block that is removed, added, swapped, moved to another document, put after another predecessor or changed; a
journal record that is altered, moved or repeated; a document opened with the wrong key.

**Not detected: putting an older copy of the whole file back.** Its head fits its own blocks, so it is a valid file
(D1268). A server could count generations outside the file; that is not done.

Also visible to anybody who holds the file, without any key: the app, the times, the number of key slots and of blocks,
and the size of each. They are not hidden.

### A reader of a file from anybody

Before anything is opened the reader checks the entry names (a short, fixed alphabet; no folders other than the three
chains and `content/`), the number and size of entries, the ratio of compression (encrypted data does not compress, so a
high ratio is a bomb) and the cost of hashing the manifest asks for.

### Keys and letters

Every person has an X25519 key pair. Her private key sits in her own slot; her public key is in `people.bin`. The head
also names a **recovery** locator and a recovery public key, so that a recovery key can receive letters as a person can.
When somebody gets keys she is not present to receive (a role raised, or the keys renewed), the owner writes a **letter**:
`inbox/<locator hex>.bin`, a sealed box to her public key whose plaintext is JSON with her role and keys; its authenticated
data names the document and the locator. At her next login the program opens her slot, then her letter, and accepts the
letter only if the content key it holds opens `people.bin`, `people.bin` lists the same role for her and the history key
opens the head. Anything else (forged, swapped or from another document) is ignored. The accepted letter is written back
as a new slot, and the letter is removed.

### Renewal

Removing a person, or lowering an editor to viewer, replaces the keys she held: removing a viewer renews the content key;
removing an editor or owner renews all three; lowering an editor renews history and chat. One atomic replacement of the file
re-seals the blocks, the record, the head, the people list and the kept original under the new keys, folds in the pending
journal records and starts a new journal for the next generation. Everybody who stays gets a letter, and so does the
recovery key. The removed person's slot, letter and private chain are deleted. What she already saw, and any copy she
saved, stay readable: nothing can change that.

### Versions

The format text is `claudia-document 2`. A file of format 1 is refused with a sentence that says it was written by an
older version (slice C added the keys of people and the private domain, and there is no upgrade in place). A program that
does not know the record (`audit/`) refuses a file that has one as damaged, because it does not know the entry; a program
that knows a higher number of the format refuses the file with a sentence that names the version.

## 2. The export file

An unencrypted, readable zip (D1270). It holds **no key, no slot, no password hash, no list of people and no manifest**:
whoever has it can read what it holds and nothing else.

| Entry | What it holds |
|---|---|
| `format` | `claudia-export 2`, stored without compression, first |
| `export.json` | the app, the version of the state, who exported it (`exporter`), when (`exported_at`), and for every other part its SHA-256 and size |
| `content.json` | the state of the document as the app's own serialisation gives it |
| `history.jsonl` | the history, one change per line, hidden side lines included — only if an **owner** exported it |
| `chat.jsonl` | the chat, one message per line — only if an owner exported it |

The hashes protect against a damaged file, not against somebody who writes a file themselves: anybody can. The reader
refuses a name that is not on this list, a part of more than 256 MiB, a high ratio of compression, a hash that does not
fit, a newer version, and a state of another version than the server's app uses, each with a sentence.

An export **comes back in as a new document** (D1272): the importer is its only owner, nobody named in the file is given
access, and the document starts with one step in its history that says it was imported. *The history and chat parts of an
export are written but are not read back yet* (see the bug list of the log).

## 3. The record of what left

Each export in any format, each print and each PDF is one record in the `audit/` chain (D1271): the kind (`export`,
`print`, `pdf`), who (the account the server authenticated, never a name a client says), when (UTC), the format, which
parts (`content`, `history`, `chat`) and, for a print or PDF, the number of pages. The records are JSON in blocks of their
own, sealed with the history key and covered by the head. They are **not** part of the history: they add no revision and
no undo step, a redaction does not touch them, and no function in the package removes one. Owners and editors read them; a
viewer does not (D1261), though a viewer's export is recorded under her name.

A print or a PDF is reported by the window that made it, after the file is saved or the page sent; Claudia cannot know
whether someone copies from the screen or photographs it.
