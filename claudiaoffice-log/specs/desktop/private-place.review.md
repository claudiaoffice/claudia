# Review of `private-place.feature` (draft of 2026-11-25, E8.5)

How to answer: "ok" accepts my proposal; anything else replaces it. Suggested order: the `@core` scenarios first.

## A. What I found when I read the code (not run)

CODE-99 and CODE-100, logged on 2026-11-25 (`bugtracker.md`); each gets a failing scenario before its fix (the two
marked `# CODE-99`, and the one marked `# CODE-100`).

## B. The matrix, walked

| Axis | Covered by | Left out, and why |
|---|---|---|
| States: no server yet / my server runs / another person's runs / a shared server / one of another version / a stranger on my port | the first six scenarios | a huge number of documents: unchanged by this work |
| Actors: one person / two people / the ai | one and two people | the ai: it works inside a document, and nothing here changes where documents are |
| Operations: make, open, reload, lists (Mine, collections) | make, open, lists | export, import, undo: not touched by which server is used |
| Clients: macOS, Windows, Linux app; Firefox tab | all four (the place names in a tab: the last scenario) | |

## C. Questions (proposal first)

| Q   | Question                                                                                                                                                                                                                                                                          | Proposal                                                                                                                                                  | Answer |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 1   | A program that is not mine holds my private place's usual address. My apps start my server at another address; my documents are there, but Mine, collections and server bookmarks are kept per address, so they look empty while it lasts. Move for good, or for this start only? | **For this start only:** the next start tries the usual address again, and my lists come back once it is free. The log says why; the window says nothing. | Ok     |
| 2   | My own server is still running in an older version after an update (it stops ten minutes after its last window).                                                                                                                                                                  | As today: the window says it will stop by itself within ten minutes; it is now true, because only my own server is compared.                              | Ok     |
| 3   | Can I rename "Private on this computer" in my list?                                                                                                                                                                                                                               | No, as today for the local entry: it is named by the app, in my language. A shared or remote server can be renamed, as today.                             | Ok     |
| 4   | A browser tab on a claudia server of this computer (`./start.sh`): is it "Shared on this computer"?                                                                                                                                                                               | Yes (your answer to question 2 of the architecture, 2026-11-25).                                                                                          | yes    |
