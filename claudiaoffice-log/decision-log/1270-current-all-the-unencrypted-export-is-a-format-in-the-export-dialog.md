---
id: D1270
title: "The unencrypted export is a format in the Export dialog; Download stays for the sealed file"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1270 · The unencrypted export is a format in the Export dialog; Download stays for the sealed file

**Decided by the owner 2026-11-19 (accepted the proposal). Not built.** It supersedes nothing but sharpens D108 and D145.
The menu workbook describes File ▸ Download as the sealed Claudia file that carries history, users and chat (D110), and
File ▸ Export… as the other formats. In the code today, though, File ▸ Download writes the *unencrypted* content-only JSON,
and the sealed download of D110 does not exist. Story E2.9 still says "File ▸ Save As", which the menu structure no longer
has. This decision puts each thing in one place:

- **The Export dialog gets one more format: "Claudia, unencrypted (JSON in a zip)".** One documented file (`format`,
  `export.json` with who, when and which parts, `content.json`, and for owners `history.jsonl` and `chat.jsonl`, hidden side
  lines included). No key slots, no password hashes, no people list.
- **Who may include what.** Every role may export the content. Only owners see the checkbox "Include history and chat", off
  by default. An editor or viewer is told in a line that history and chat can only be exported by owners.
- **A plain-language confirmation before saving:** the file is not protected by a password; anyone who gets it can read it;
  the export is recorded in the document (D1271); and the log cannot tell whether someone copies from the screen.
- **File ▸ Download keeps the meaning the workbook gives it** — the sealed `.claudia` file — and is built as D110 says
  (owners the whole file, editors and viewers a file with their own slot only) as the story E2.12. Until then Download
  keeps writing what it writes now, and says so.
- The old `claudia-export 1` single JSON file stays readable only as far as it is today; the project is pre-release, so it
  is not migrated.

**Notes.** The code's comment in `ExportDialog.vue` and the workbook disagree about Download; this is the owner's call to
confirm when E2.12 is picked up.
