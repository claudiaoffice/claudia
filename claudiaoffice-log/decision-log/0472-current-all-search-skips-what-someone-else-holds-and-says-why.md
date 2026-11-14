---
id: D472
title: "A replace skips what someone else is working in, what changed since it was shown, and what would not fit"
status: current
applies-to: all
date: 2026-11-14
round: "Search & replace in composes and creates (branch `search`)"
supersedes: []
superseded-by: []
---

# D472 · A replace skips what someone else is working in, what changed since it was shown, and what would not fit

**Locks (D11, D47).** A replace never writes where another person is. In **composes** a match is skipped when it lies in a zone another person holds (`presence.conflicts` over the text range of the edit), and the skip is **per paragraph**, not per match: if any match of a paragraph lies in someone else's zone, the paragraph is left as it is and named as `locked`. An object is skipped when another person has selected it. In **creates** an object is skipped when another person has selected it; speaker notes are not locked, because they are not selected and are edited as one field. **Changed since shown (D287 (8)):** the client sends the text a match had when it was shown (`said`); if it differs the text is skipped as `changed`, so numbers that moved while others typed never replace the wrong words. **Too long:** a result longer than a paragraph, an object's text (or notes, 20 000 characters) may be is skipped as `too_long`. Every skip is listed with its reason, as for cells.

**Who may replace.** A viewer is refused. In composes **the replace is for people only**: the text belongs to the persons who write it, and an assistant that rewrites a term everywhere does so by proposing (D262). In creates the assistant may replace like any other user. The assistant's `search_replace` model method is registered for computes only; adding it to composes and creates is open.

**Limits.** At most 10 000 texts per replace (`MAX_REPLACED_TEXTS`), 2 000 changes previewed, 10 000 `leave` entries, and the 2-second budget of D284 for the whole request.
