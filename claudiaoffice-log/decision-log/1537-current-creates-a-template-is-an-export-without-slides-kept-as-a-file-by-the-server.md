---
id: D1537
title: "A template is a Claudia export of a presentation without slides, and a server keeps its templates as files"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1537 · A template is an export without slides, and the server's library is a folder of such files

A template needs no format of its own: it is the unencrypted Claudia export (D1270, D1272) of a presentation that has
no slides, plus a note of what it is (`TemplateInfo`: name, what it is for, language) in the state under `template`
(state schema 20).

* **The file.** `template_state` writes a presentation as a template: no slides, no notes, no planned times, and no
  picture, shape or container that only slides used; what the layouts show stays, with what it needs. The file has the
  parts `format`, `export.json` and `content.json` and nothing else: no history, no chat. `read_template_file` refuses
  a file that is no export, comes from another app or another state schema, has slides, has no layout, or has no note.
* **The library.** A server has the built-in **Basic** template (one layout without placeholders; its name and purpose
  are said in the language asked) and the templates its administrators added: one file each under
  `STATE_DIR/templates/<id>.claudia-export.zip`. What is stored is rebuilt from what was checked, so a file that came
  with a history or a chat keeps neither. A name is unique ignoring case, Basic included. Basic cannot be removed.
* **Server settings ▸ Templates** (`/api/admin/templates`): administrators only; check, add, remove, and the whole
  page as the answer. The file is the body of each request and is sent again for the add; a template is a few hundred
  kilobytes, so nothing is held between the two steps (the font pages hold files because a collection is many files).
* **Saving** (`save_as_template`) is an export: the record of what left the document shows it (D1271), the assistant
  may not do it, and the answer is the file for the client to save; the administrator adds it on the page.

Considered and rejected: a template as a document of the server (it would have an owner, a history and a password, and
a copy would have to be made from a document nobody opens); a format of its own (a second reader for the same state).
