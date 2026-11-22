# Review notes for `export-and-record.feature` (slice B of E2 round two)

For the owner to read before the scenarios are agreed. Drafted 2026-11-19 with the code, not before it; change anything.

| Scenario | Runs in | What it protects |
|---|---|---|
| Ann exports without protection after being told | Chrome, real server | D1270: the question comes first, the file has no keys, slots or people; D1271: the row |
| Ann changes her mind | Chrome | nothing is saved or recorded without the second click |
| An owner adds history and chat | Chrome | D1270: "Include history and chat" is the owner's, off by default; the row says all parts |
| An editor | Chrome, two windows | an editor has no box and is told why |
| PDF from the print preview | Chrome | D1271: the client reports a PDF when it is saved, the server writes the row |
| Comes back in | Chrome | D1272: an export is a new document with the same content; the importer is its only owner |
| The three `@extended` ones | unit tests | the record is not redactable; who comes from the connection; the reader's limits |

Not run in a browser: printing to a printer (the browser's dialog cannot be answered in an automated run; the
`__claudiaPrintDialog` hook of the preview is used by the unit test of the report), a viewer's own window (she has no
menu entry for the record), the history and chat *import* (not built, see the bugtracker).
