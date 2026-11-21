# Review of `document-file/viewer.feature` and `document-file/login-wait.feature` (draft of 2026-11-19, slice A)

**Not reviewed by the owner yet.** How to answer: "ok" accepts my proposal, anything else replaces it.

| Q | Question | Proposal |
|---|---|---|
| 1 | After how many wrong passwords does the wait start? D1266 says three free tries, so the fourth wrong password is the first that makes the *next* try wait one second. The scenario says "four wrong passwords, then once more". | As D1266. |
| 2 | A viewer who opens a sealed document waits for an editor to open it (D1262). The window tries again every few seconds, without a limit. Is "never gives up" right, with a Close button, or should it stop after some minutes? | Never gives up; Close is always there. |
| 3 | The history and chat parts are not drawn for a viewer; one sentence says they are for editors. Should the tab itself ("History & Chat") stay visible so that it is clear that it exists? | Stay visible, with the sentence (as built). |
| 4 | Authorship ("who wrote which stretch") is part of the content, so a viewer sees it. D1261 says no data should be behind "show who wrote what" for a viewer. Mask it, or accept it as content? | **Needs your decision** (bug SEC-22, size 2). Not in these scenarios. |
