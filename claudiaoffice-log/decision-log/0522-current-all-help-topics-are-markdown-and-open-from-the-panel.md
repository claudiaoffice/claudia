---
id: D522
title: "A help topic is shown as Markdown, and "About searching and patterns" opens its own topic"
status: current
applies-to: all
date: 2026-11-15
round: "The search panel and movable dialogs (branch `search-ui`)"
supersedes: []
superseded-by: []
---

# D522 · A help topic is shown as Markdown, and "About searching and patterns" opens its own topic

**Decision.** The body of a help topic is drawn with the same small, safe Markdown reader as the speaker notes (D347): headings, paragraphs, lists, bold, emphasis, code and links, **never HTML**, so a topic that someone wrote cannot put markup, a picture or a script on the screen. A line break inside a paragraph is a space, as Markdown says, because the topic files are written in lines of 120 characters and the panel is narrower. The help for a **function** stays preformatted plain text: it is a signature and an example, not prose. Each app's `SearchHost` names its topic (`helpTopic`: `composes.searching-and-replacing`, `creates.…`, `computes.…`), and **⋯ ▸ About searching and patterns** opens the dock if it is closed, switches to the Help tab, opens that topic and puts the focus on its heading. An id the server does not know falls back to the how-to list, never to an empty panel.

**Notes.** Refines D76 (the topic is the knowledge base's unit; its form is Markdown) and answers the first open point of the search round (the help link opened the how-to list, not the topic). Reported by the owner on 2026-11-15: the panel showed `**` and `##` as typed. `lib/help-markdown.ts` joins the soft line breaks and hands the text to `notes-markdown.ts`; `NotesText.vue` takes a `flow` property for it. The topics' three Look-in paragraphs, a section on moving the panel, and their German translations were rewritten with this decision (the translations' `source-hash` follows the English file, `help.py`).
