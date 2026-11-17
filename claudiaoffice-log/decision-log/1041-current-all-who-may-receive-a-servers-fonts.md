---
id: D1041
title: "Who may receive a server's fonts: anywhere, this server's people, or nobody because they are not usable"
status: current
applies-to: all
date: 2026-11-16
round: "Font management (E3.13, branch font-server-ui)"
supersedes: []
superseded-by: []
---

# D1041 · Who may receive a server's fonts: anywhere, this server's people, or nobody because they are not usable

**Every font collection says who may receive its fonts, in three answers instead of D94's yes or no: *Anywhere*
(an open licence: the files go to every client, and may later be kept with documents and embedded in exports),
*This server* (a licence for one organisation: the files go only to the people using this server, and never into an
export or a document that leaves it), and *Not usable*, which no record gives: it is what the catalogue finds when
it cannot use a file (it forbids embedding, cannot be read, has no family name), shown with the reason in words.**
The owner chose the three answers on 2026-11-16, when asked for the first version of Server settings ▸ Fonts.

**On disk nothing changes:** `collection.json` keeps format 1; `redistributable: true` is *Anywhere*, `false` is
*This server* (`CollectionRecord.may_go`). What changes is what `false` means: before, such a font was used by the
server's own typesetting and never handed to a client, so a licensed house font could not be shown or printed in the
browser at all; now it is handed to the server's own people.

**The server's people** are those whose request carries the access secret, or an administrator's session; on a server
without an access secret, everyone who reaches it (the Add fonts… dialog says so when *This server* is chosen there).
`GET /api/fonts` lists such fonts only to them, the files are refused to others with 404, and both are marked
`Cache-Control: private` (`claudia_server.fonts`).

**Server settings ▸ Fonts** (E3.13 f, boards `notes/mockups/fonts-1-server-settings.svg` and `fonts-2-add-fonts.svg`)
is where an administrator sees and changes this: a fourth page beside Typesetting. Collections come from three places,
read in this order, a later font replacing an earlier one of the same family and style: the starter set (D500,
shown as one card, "Shipped with Claudia"), the operator's `--fonts` folders, and `STATE_DIR/fonts`, where the page
adds collections (now read with `--fonts` too). Only collections added on the page can be renamed or removed there.
Adding is check first, then add: nothing changes on the server before the second step, and the confirmation names the
server and who will receive the fonts.

**Not yet (backlog, E3.13):** the web client does not yet send the access secret when it loads fonts, so a document's
people who are not administrators get *This server* fonts only on a server without an access secret; and no export or
PDF checks *This server* yet (the print preview embeds what it lays out). Both are needed before a licensed font is
added to a server with an access secret. LaTeX formulas see added fonts after the server restarts.

**Notes.** Refines D94 (2): the licence record stays mandatory per collection; "served to browsers only if
redistributable" becomes the rule above. D500 (the shipped set always present) and D905 (layout fonts from the
server's catalogue) are unchanged.
