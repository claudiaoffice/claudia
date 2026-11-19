---
id: D1270
title: "The unencrypted export is a format in the Export dialog; File ▸ Download is the sealed file"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1270 · The unencrypted export is a format in the Export dialog; File ▸ Download is the sealed file

**Decided by the owner 2026-11-19 (accepted the proposal; and "File > Download should be the sealed file, please update all
decisions and the code accordingly"). The Download half is built (E2.12); the Export-dialog format is not (E2.9).** It supersedes nothing but sharpens D108 and D145.
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
- **File ▸ Download is the sealed `.claudia` file**, as the workbook says and D110 describes: owners get the whole file, editors
  and viewers a file with their own slot only (a viewer's with only the parts the content key opens). **Built 2026-11-19**
  (E2.12): `download_claudia` on the wire, `sealed_copy` in the container, `DownloadDialog.vue`. The person's password is
  asked again, because it is what finds her slot. Until E2.9 is built **there is no unencrypted export in the menus**: the
  owner accepted that, and `export_content` stays on the wire for tests and for E2.9 to build on.
- The old `claudia-export 1` single JSON file stays readable only as far as it is today; the project is pre-release, so it
  is not migrated.

**Notes.** The code and the workbook disagreed about Download; the owner settled it on 2026-11-19 in favour of the workbook.
