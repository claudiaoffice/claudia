---
id: D1318
title: "A description is stored like an object's, and a paragraph's is offered as a comment on export"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1318 · A description is stored like an object's, and a paragraph's is offered as a comment on export

**Decided 2026-11-19** by the owner, in `specs/objects/names.review.md` and in the message that followed it. It settles the two points D1317 left to the architecture round and the one it assumed.

**Storage.** For now, **every object has a name and a description**, and a description of a paragraph, heading, list, table, sheet, slide, chart tab or range is **stored in the same pattern as the description of any other object**: a plain string next to the thing's name, changed by a logged command, undone with Ctrl+Z, seen at once by the other people. No new kind of record. (The owner's words: "paragraph descriptions for now should be stored in the same pattern as the description for any object. Every object has a name and a description for now.")

**Export.** A description of a paragraph is **presented as an option to the person when exporting to Word or OpenDocument, as a comment** (owner: "present as option to user on export, yes"). It is never written without being asked, because it may be a private note (corkboard, E16.5).

**An unnamed range or table:** *Edit ▸ Name & describe…* **asks for a name** (the dialog of `notes/mockups/names-02-…`); the owner reviewed the mocks and agreed with all of them, which includes the chip over the view, *View ▸ Back where I was* (Ctrl+Shift+B / Cmd+Shift+B) and the font banner whose **Get** is for **administrators only**.

**Assumptions, for the owner to correct** (they are not in the answers; the architecture note `notes/e1-architecture.md` asks them again with defaults):

* The option is a tick in the export dialog, **off by default**, labelled "Write paragraph descriptions as comments"; it only appears for a document that has at least one.
* Only **paragraphs, headings, lists and tables** become comments (the things Word and OpenDocument can comment on); the description of a sheet, slide or range goes with those apps' own exporters and is out of this decision.
* **Import does not read comments back as descriptions** (a comment is a conversation, not a note on a thing).
* The author of such a comment is the person who exports, the date is the export's.

**Notes.** The corkboard (E16.5) revisits the data structure; the storage pattern chosen here is a string beside the name so that splitting it later (alternative text and note) needs no new mechanism. Neither the docx nor the odt writer writes comments today (they only recognise them on import, to say that a removed block had one), so the export option needs new writing code on both sides.
