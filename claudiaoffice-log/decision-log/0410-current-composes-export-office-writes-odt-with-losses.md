---
id: D410
title: "`export_office` writes odt for the text app and answers with the list of losses; the import screen is not part of this work"
status: current
applies-to: composes
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D410 · `export_office` writes odt for the text app and answers with the list of losses; the import screen is not part of this work

**`export_office` accepts `"odt"` besides `"docx"` for the text app; its answer is `{format, content_type, data}` and, for odt, `losses` (a list of `{kind, detail, count}`, D405).** The File ▸ Export… dialog offers "OpenDocument text (.odt)". Like docx it leaves out the history and the chat (D212), and the open suggestions unless `tracked_changes` is asked for (D411). The error for an unknown format names both. **Not in this change:** an import screen (another agent is working on it with the owner), a screen for `losses`, and ods in the Export dialog (odp: D412).

**Notes.** `losses` is in the answer only for a format that can say (`office_export(fmt, data, losses=None)`), so docx's answer is unchanged. The web app does not read it yet; `ExportedFile` in `base-session.ts` types it for when it does.
