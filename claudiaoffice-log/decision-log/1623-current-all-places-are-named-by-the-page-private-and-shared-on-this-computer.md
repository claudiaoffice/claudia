---
id: D1623
title: "The page names the places on this computer: \"Private on this computer\" and \"Shared on this computer\""
status: current
applies-to: all
date: 2026-11-25
round: "E8.5 macOS installer, part 1: Private on this computer (branch `mac-installer`)"
supersedes: []
superseded-by: []
---

# D1623 · The page names the places on this computer: "Private on this computer" and "Shared on this computer"

**Her own server is "Private on this computer" (German "Privat auf diesem Computer"); a claudia server on this computer
seen from a plain browser tab, which cannot tell whose it is, is "Shared on this computer" ("Geteilt auf diesem Computer").
The page gives these names (`named` and `defaultLabel` in `web/app/lib/server-bookmarks.ts`), in her language, whatever
label a desktop shell sent: the macOS and Windows shell's messages are English only (D660), and a label the page shows must
be translated.** The private place cannot be renamed (as the local entry before); a shared or remote place can. The shells'
own label for it is "Private on this computer" too, for a page from before this. "This computer" goes (the glossary's
*avoid*). The service, once it is listed (D1622), is "Shared on this computer" until each person renames it, also once it
has an administrator (review of `shared-place.feature`, question 1).

**Why.** "This computer" did not say whose server it was; with a service on the same computer there are two (the grilling
of 2026-11-25, Q16 and Q20; the owner chose (a) over "My local documents", which sat too close to Mine).

**Changes D243** in its wording only: the shell's list still starts with her own server, under the new name.

**Notes.** The name of a place is the glossary's ("Place"). The translator is a parameter of `named` and `defaultLabel`
(named `t`, so that `scripts/extract_i18n.py` finds the strings), for the tests to ask in German.
