---
id: D729
title: "Later steps that need the redacted content are blanked with it; one that still fails becomes a tombstone"
status: current
applies-to: all
date: 2026-11-18
round: "The redaction screens (E3.14), 2026-11-18"
supersedes: [D722]
superseded-by: []
---

# D729 · Later steps that need the redacted content are blanked with it; one that still fails becomes a tombstone

**Later steps that need the redacted content are blanked with it, and named before anything happens.** The plan
replays every line that holds a blanked step; a later step that no longer applies is blanked too and listed as a
dependent, until every line replays. **A dependent whose blank of the same shape (D720) still does not apply becomes a
no-op tombstone**, which always applies. A request that names bare steps (no plan) is refused if it would take others
with it, so nobody's work is blanked without being shown; over the wire the client confirms by repeating the dependents
it showed. The only refusal left is a history that does not replay before any blanked step: it was broken already, and
blanking more would hide that.

**Notes.** Found while building the screens (2026-11-18): an editor's paragraph split in composes, with an owner's typing
in the new paragraph after it, could not be redacted at all, because the typing's blank (filler of the same length)
still needed the paragraph the split made. D722 called refusing "the last resort"; in practice it came first. With the
tombstone the plan names the owner's typing as going too, and the editor is told to ask an owner (D727). The rest of
D722 (the owner's choice of 2026-11-16 between refusing, offering the dependents and squashing) stands.
