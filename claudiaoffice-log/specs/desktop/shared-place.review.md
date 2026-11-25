# Review of `shared-place.feature` (draft of 2026-11-25, E8.5)

How to answer: "ok" accepts my proposal; anything else replaces it. Suggested order: the `@core` scenarios first.

## A. The matrix, walked

| Axis | Covered by | Left out, and why |
|---|---|---|
| States: service installed / not installed / removed / without administrator | the scenarios | a service listening to other computers: not in this work (D743, E8.5) |
| Actors: one person / two people / an administrator of the computer / the ai | all but the ai | the ai: unchanged, it is a user of a document wherever the document is |
| Operations: find the place, make, open, edit together, name the first administrator | the scenarios | export and import: unchanged by where the document is |
| Clients: macOS and Windows app | both | Linux: no service (E8.5, Q21); a browser tab: `private-place.feature` |

## B. Questions (proposal first)

| Q | Question | Proposal | Answer |
|---|---|---|---|
| 1 | Once the service has an administrator, say Anna: is the place still "Shared on this computer", or "Anna's server" as for other servers today? | **Still "Shared on this computer"**: it says what it is and where; each person can rename it in her own list, as any server. | |
| 2 | Can every person of the computer see the titles of all shared documents? | As on any server: yes, except documents marked unlisted; contents only with a role. | |
| 3 | The service is removed while someone has a shared document open. | As when any server goes away: the window says the connection is lost and keeps trying; the place leaves the list at the next start of an app. | |
| 4 | Where do I choose the shared place for a new document? | In the place list of the Open/New dialog, as for any server; nothing new. | |
| 5 | The wording for someone who is not an administrator of the computer. | "Only an administrator of this computer can name this server's first administrator. Ask one." German, in the "Sie" and the "Administrator" of the existing translations: "Nur ein Administrator dieses Computers kann den ersten Administrator dieses Servers bestimmen. Fragen Sie einen." | |
