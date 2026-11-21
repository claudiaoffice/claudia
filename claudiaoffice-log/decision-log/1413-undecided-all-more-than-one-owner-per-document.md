---
id: D1413
title: "More than one owner per document: deferred; new work never assumes there is only one"
status: undecided
applies-to: all
date: 2026-11-21
round: "Glossary session: domain notions (glossary.md)"
supersedes: []
superseded-by: []
---

# D1413 · More than one owner per document: open, and deferred

**Open.** Whether a document may have more than one owner, so that two people are responsible for it and one can be
away (holidays, illness, parental leave) without anybody else stepping in. Today a document has exactly one owner:
only the creator starts as one, people are added as editors or viewers, and a hand-over (D142) swaps owner and
editor in one step. The steward of the organisation model (`notes/organisations-entry-continuity-exit.pdf`, not
decided) is a last resort for an owner gone for good, not the answer to everyday absence.

**Deferred, by the owner, 2026-11-21.** Waiting costs little: the document file already allows several owners (it
refuses to remove or let leave the *last* owner, and `add_user` in `claudia-container` accepts the owner role); the
rule of one owner lives only in the server's methods for adding people and changing roles, in the hand-over, and in
about eight interface strings. No stored data assumes a single owner, and claudia is pre-release.

**The one rule that holds from now on:** new work does not assume a document has only one owner. Code, interface text,
specs and notes say "an owner" or "the owners", and a feature that needs one person's agreement or attention (the
hand-over wizard, the steward, agreeing to a restore, D1114's private items) says what happens when there are several.

**Sizing (for E2.13).** Small to medium, about one slice, no change of the file format: in the document file, *make
co-owner* (an editor accepts with her own password, as in D142, because her role is sealed in her key slot) and *step
down* (an owner becomes an editor with her own password if another owner remains); on the server, a co-owner variant
of the hand-over proposal and a step-down method (the owner-only checks already mean "is an owner", and D1284 already
keeps owners from being lowered or removed by others); in the clients, *Make co-owner* and *Step down* in the Role
dialog, several owners in the list of people, the strings that say "the owner", the German catalogs and the menu
workbook.

**To decide before it is built:** what a co-owner may do alone, and what needs every owner: deleting the document,
making a new recovery key, removing people, agreeing to a restore, D1114.

**Notes.** Raised by the owner in the glossary session, 2026-11-21, from how organisations handle absence and
key-person risk (two people responsible for one thing).
