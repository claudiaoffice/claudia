---
id: D722
title: "Later steps that need the redacted content are blanked with it, named first"
status: superseded
applies-to: all
date: 2026-11-16
round: "The redaction contract (D229), 2026-11-16"
supersedes: [D229]
superseded-by: [D729]
---

# D722 · Later steps that need the redacted content are blanked with it, named first

**Later steps that need the redacted content are blanked with it, and named before anything happens.** The plan
replays every line that holds a blanked step; a later step that no longer applies is blanked too and listed as a
dependent, until every line replays. Refusing is the last resort: only when a later step does not apply even blanked.
A request that names bare steps (no plan) is refused if it would take others with it, so nobody's work is blanked
without being shown; over the wire the client confirms by repeating the dependents it showed.

**Notes.** The owner's choice of 2026-11-16 between refusing, offering the dependents, and squashing the history.

*Superseded on 2026-11-18 by D729: a dependent whose blank still fails becomes a tombstone instead of stopping the redaction.*
