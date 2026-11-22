---
id: D1434
title: "The parts of a document in the code: Part, the key to private notes, and stream for a chain of blocks"
status: current
applies-to: all
date: 2026-11-22
round: "The remaining renames of E1.18 (branch e1-18-remaining-names)"
supersedes: []
superseded-by: []
---

# D1434 · The parts of a document in the code

The glossary calls the content, the history and the chat of a document its **parts** (_avoid_: domain), and a person's
own notes her **private notes** (_avoid_: private domain, private part). D1430 had no line for them, so D1433 left
`Domain` as it was. The owner agreed the names below on 2026-11-22, by the rule of D1433 (the full list first).

| Before | After |
|---|---|
| `Domain`, `ROLE_DOMAINS`, `new_domain_keys` | `Part`, `ROLE_PARTS`, `new_part_keys` |
| every `domain` that holds one of the three parts (`JournalRecord.domain`, the journal's `_DOMAIN_BYTE`, parameters, loops) | `part` (`JournalRecord.part`, `_PART_BYTE`, …) |
| `PrivateDomain`, `new_private_domain` | `PrivateNotesKey`, `new_private_notes_key` (the owner's choice: the class holds the id and the key of someone's private notes, not the notes) |
| `domain` naming a chain of blocks, which may be a part, `"audit"` or `"private/<id>"` (`blocks.Place.domain`, the `domain: str` of `_sealed_chain` and `_extend`, the loop over `_STREAMS`) | `stream` (the owner's choice; the code already said `_STREAMS` and `_STREAM_BYTE`): the record of what left and private notes are chains, not parts |
| server: `audience.Rule.domain`, `may_read(role, domain)` | `Rule.part`, `may_read(role, part)` |
| `audit.PARTS`, which spelt the three names out again | made from `Part` |
| test file `test_private_domain.py` | `test_private_notes.py` |
| prose: "domain", "domain key", "private domain" | "part", "part key", "private notes" (with the verb in the plural) |

Kept: "part" in its other senses (the files inside an export in `export_file.py`, the pieces a MAC is made of in
`crypto.py`, "part of"), the gettext domain (`i18n.DOMAIN`), a mathematical domain error in computes, PDF's `/Domain`,
an internet domain, and the history: changelog entries, decisions, notes and the backlog's stories (E2.4 "Key domains
and visibility", E16.8) keep the word they were written with.

`stream` and "part key" are words of the code and stay out of the glossary: the glossary holds only the main concepts
people meet when they use claudia (the owner, 2026-11-22).

Nothing in the file and nothing on the wire changes: the file names a part by its value (`content`, `history`, `chat`)
and never wrote the word.
