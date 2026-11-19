# Review of `container/download.feature` (draft of 2026-11-19)

How to answer: for each question, "ok" accepts my proposal; anything else replaces it. When all are answered I move the
answers into the feature file (and the decision log) and delete this file.

The code for the `@core` scenarios is built and they pass in Chrome (`./run-e2e.sh --feature download`). The `@extended` ones
need two people in two windows (not built in the harness yet) or a round trip.

| Q | Question | Proposal |
|---|---|---|
| 1 | The password is asked again in the Download dialog, for everybody. It is also what finds the person's slot in the file, so it cannot be left out; the question is only whether the dialog says why. | The label reads "Your password, to prepare your copy". |
| 2 | Until E2.9 is built there is no unencrypted export in the menus. Is a gap acceptable, or should the old JSON stay reachable for now (for example as "Claudia, unencrypted (JSON)" in the Export dialog, without the zip, the record or the owner-only parts)? | Accept the gap (what you said); E2.9 is next in slice B. |
| 3 | A viewer can only be connected while an editor has the document open, so a viewer's Download works only then. After E2.11 she can open a sealed document and read it. | As now; E2.11 follows. |
| 4 | Should the dialog show the size of the file before it is saved? | No; the browser or the Save dialog shows it. |
| 5 | A downloaded file keeps the document's name (`report.claudia`). When it is taken in again on the same server it is refused as a duplicate (same uid, D533). Is that what you want, or "keep both"? | Refuse, as Open ▸ Open file does today; the scenario "taken in again" first deletes the original. |
